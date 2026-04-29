"""推理链问答核心。

QA 层只把白名单自然语言问题映射到固定 SPARQL 模板，查询图谱中的结构化
evidence，再交给 LLM 或本地 fallback 解释。LLM 不参与业务判定，也不得生成
白名单外的自由 SPARQL。
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from mvp.core.llm.base import LLMProvider
from mvp.core.llm.factory import get_provider

try:
    from mvp.core.ontology_registry import graph_iri_for
except ModuleNotFoundError:
    graph_iri_for = None

try:
    from mvp.core.sanitize import sanitize as _external_sanitize
except ModuleNotFoundError:
    _external_sanitize = None


ONTO_NS = "https://hifar.top/mto#"
MAX_EVIDENCE_BYTES = 4096
UNSUPPORTED_ANSWER = "暂不支持该类问题，请按『M007 为什么 Fail？』、『M009 为什么 Pass？』、规格变更影响或参数/批次汇总模板提问。"

TEMPLATES: dict[str, str] = {
    "why_fail": """
PREFIX mto: <{onto_ns}>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {{
  GRAPH <{data_graph_iri}> {{
    ?m a mto:Measurement ;
       mto:localId "{measurement_id}" .
    OPTIONAL {{ ?m mto:measuredValue ?value . }}
  }}
  GRAPH <{result_graph_iri}> {{
    ?m mto:hasLatestResult ?r .
    OPTIONAL {{ ?r mto:resultStatus ?status . }}
    OPTIONAL {{ ?r mto:appliedRule ?rule . }}
    OPTIONAL {{ ?r mto:againstSpecVersion ?spec_version . }}
    OPTIONAL {{ ?r mto:evidenceLowerLimit ?lower_limit . }}
    OPTIONAL {{ ?r mto:evidenceUpperLimit ?upper_limit . }}
    OPTIONAL {{ ?r mto:deviation ?deviation . }}
    OPTIONAL {{ ?r mto:reasoner ?reasoner . }}
    OPTIONAL {{ ?r mto:inferredAt ?inferred_at . }}
  }}
}}
""",
    "spec_change_impact": """
PREFIX mto: <{onto_ns}>
SELECT ?measurement_id ?old_status ?new_status ?old_spec ?new_spec ?deviation WHERE {{
  GRAPH <{result_graph_iri}> {{
    ?impact mto:forMeasurement ?m ;
            mto:oldStatus ?old_status ;
            mto:newStatus ?new_status ;
            mto:oldSpecVersion ?old_spec ;
            mto:newSpecVersion ?new_spec ;
            mto:deviation ?deviation .
    ?m mto:localId ?measurement_id .
  }}
  FILTER (?old_spec = "{old_spec}" && ?new_spec = "{new_spec}")
}}
""",
    "parameter_or_batch_summary": """
PREFIX mto: <{onto_ns}>
SELECT (COUNT(?r) AS ?count) ?status WHERE {{
  GRAPH <{data_graph_iri}> {{
    ?m a mto:Measurement .
    OPTIONAL {{ ?m mto:forParameter ?p . ?p mto:parameterCode ?parameter_code . }}
    OPTIONAL {{ ?m mto:forBatch ?b . ?b mto:localId ?batch_id . }}
    {filter_clause}
  }}
  GRAPH <{result_graph_iri}> {{
    ?r mto:forMeasurement ?m ;
       mto:resultStatus ?status .
  }}
}} GROUP BY ?status
""",
}
TEMPLATES["why_judgement"] = TEMPLATES["why_fail"]


class OntologyIdRequired(ValueError):
    """QA 核心拒绝缺失 ontology_id 的正式请求。"""

    code = "ONTOLOGY_ID_REQUIRED"

    def __init__(self) -> None:
        super().__init__("正式 QA 请求必须显式携带 ontology_id")


@dataclass(frozen=True)
class QAIntent:
    """白名单问答意图。

    ``name`` 必须来自 ``TEMPLATES`` 或 ``unknown``；``params`` 保存模板渲染需要的
    measurement_id、spec 版本、参数编码或批次号。
    """

    name: str
    params: dict[str, str]
    reason: str


def extract_intent(question: str) -> QAIntent:
    """从用户问题中提取白名单意图。

    第一阶段仅支持 why_fail、why_judgement、spec_change_impact、parameter_or_batch_summary。
    即使提取到 measurement_id，只要语义不属于白名单判定问题，也返回 unknown，避免
    后续生成白名单外 SPARQL。
    """

    text = (question or "").strip()
    lowered = text.lower()
    mid = _first_match(r"\b(M\d{3,})\b", text, flags=re.IGNORECASE)
    if mid and _looks_like_why_fail(text, lowered):
        return QAIntent("why_fail", {"measurement_id": mid.upper()}, "命中 measurement why_fail 模板")
    if mid and _looks_like_why_judgement(text, lowered):
        return QAIntent("why_judgement", {"measurement_id": mid.upper()}, "命中 measurement judgement 模板")

    specs = re.findall(r"\bSpec_v\d+\b", text, flags=re.IGNORECASE)
    if len(specs) >= 2 and re.search(r"影响|变更|重推|差异|impact|change", text, re.IGNORECASE):
        return QAIntent(
            "spec_change_impact",
            {"old_spec": specs[0], "new_spec": specs[1]},
            "命中规格变更影响模板",
        )

    batch = _first_match(r"\b(B\d{2,})\b", text, flags=re.IGNORECASE)
    code = _first_match(r"\b([a-z][a-z0-9_]{2,})\b", lowered)
    if re.search(r"汇总|统计|分布|summary|count|多少", text, re.IGNORECASE):
        params: dict[str, str] = {}
        if batch:
            params["batch_id"] = batch.upper()
        elif code:
            params["parameter_code"] = code
        if params:
            return QAIntent("parameter_or_batch_summary", params, "命中参数或批次汇总模板")

    return QAIntent("unknown", {}, "未匹配任何白名单模板")


def local_fallback(intent_name: str, evidence: dict[str, Any] | None) -> str:
    """基于结构化 evidence 生成本地中文解释。

    fallback 覆盖 measurement judgement 场景，确保无 LLM Key 或 provider 超时时仍能演示
    推理链闭环；它只复述 evidence，不新增图谱中不存在的事实。
    """

    evidence = evidence or {}
    if intent_name in {"why_fail", "why_judgement"}:
        mid = evidence.get("measurement_id") or evidence.get("mid") or "该测量"
        if not evidence or evidence.get("missing"):
            return f"{mid} 暂未查询到可解释的推理链 evidence。"
        return (
            f"{mid} 判定为 {evidence.get('status', '未知状态')}：测量值 "
            f"{evidence.get('value', '未知')}，规格 {evidence.get('spec_version', '未知版本')} "
            f"范围为 {evidence.get('lower_limit', '未知')} 到 {evidence.get('upper_limit', '未知')}，"
            f"触发规则 {evidence.get('rule', '未知规则')}，偏差 {evidence.get('deviation', '未知')}。"
        )
    if intent_name == "spec_change_impact":
        return f"规格变更影响基于查询到的 evidence 汇总：{_compact_json(evidence)}"
    if intent_name == "parameter_or_batch_summary":
        return f"参数或批次汇总基于查询到的 evidence 汇总：{_compact_json(evidence)}"
    return UNSUPPORTED_ANSWER


def answer(
    graph: Any,
    ontology_id: str | None,
    question: str,
    *,
    provider: LLMProvider | None = None,
    trace: Any = None,
) -> dict[str, Any]:
    """回答推理链问题。

    ``graph`` 采用鸭子类型以兼容并行开发中的 graph 层：优先使用
    ``graph.get_qa_evidence``，否则尝试 ``graph.sparql.select`` 或 ``graph.select``。
    当前 provider 不可用、超时或返回空文本时直接进入 local_fallback，不自动切换到
    其它 provider。
    """

    if not ontology_id:
        _trace_log(trace, "extract_intent", "failed", "正式 QA 请求缺少 ontology_id")
        raise OntologyIdRequired()

    intent = extract_intent(question)
    if intent.name not in TEMPLATES:
        _trace_log(trace, "extract_intent", "skipped", intent.reason)
        _trace_log(trace, "compose_answer", "fallback", "白名单外问题由本地固定答复处理")
        return {
            "answer": local_fallback(intent.name, None),
            "source": "local_fallback",
            "provider": None,
            "sparql": None,
            "evidence": {},
            "intent": intent.name,
        }

    _trace_log(trace, "extract_intent", "success", intent.reason, intent=intent.name)
    sparql = _build_sparql(graph, ontology_id, intent)
    _trace_log(trace, "build_sparql", "success", "使用白名单模板生成 SPARQL", intent=intent.name)

    rows = _select_evidence(graph, ontology_id, intent, sparql)
    evidence = _normalize_evidence(rows[0] if rows else {}, intent)
    _trace_log(trace, "fuseki_select", "success", "读取推理链 evidence", rows=len(rows))

    active_provider = provider or get_provider()
    provider_name = getattr(active_provider, "name", "unknown")
    text: str | None = None
    if active_provider.available():
        prompt = build_prompt(ontology_id, question, intent, evidence)
        try:
            text = active_provider.chat(prompt)
        except Exception as exc:
            _trace_log(
                trace,
                "llm_call",
                "fallback",
                "当前 provider 调用异常，按 Q9 直接本地降级",
                provider=provider_name,
                error=type(exc).__name__,
            )
    else:
        _trace_log(
            trace,
            "llm_call",
            "fallback",
            "当前 provider 不可用，按 Q9 直接本地降级",
            provider=provider_name,
        )

    if text:
        _trace_log(trace, "llm_call", "success", "当前 provider 返回解释", provider=provider_name)
        _trace_log(trace, "compose_answer", "success", "返回 LLM 解释并附带 evidence")
        return {
            "answer": text,
            "source": provider_name,
            "provider": provider_name,
            "sparql": sparql,
            "evidence": evidence,
            "intent": intent.name,
        }

    fallback = local_fallback(intent.name, evidence)
    _trace_log(trace, "compose_answer", "fallback", "使用本地 fallback 复述结构化 evidence")
    return {
        "answer": fallback,
        "source": "local_fallback",
        "provider": provider_name,
        "sparql": sparql,
        "evidence": evidence,
        "intent": intent.name,
    }


def build_prompt(
    ontology_id: str,
    question: str,
    intent: QAIntent,
    evidence: dict[str, Any],
) -> str:
    """构造只包含脱敏 evidence 的 LLM prompt。"""

    evidence_json = _limited_evidence_json(sanitize(evidence))
    prompt = (
        "你是制造业试验数据本体 MVP 的解释助手。"
        "只能解释 Evidence JSON 中已经存在的事实；不得新增判定、不得编写自由 SPARQL。"
        f"\nOntology: {sanitize(ontology_id)}"
        f"\nIntent: {intent.name}"
        f"\nQuestion: {sanitize(question)}"
        f"\nEvidence JSON:{evidence_json}"
    )
    return sanitize(prompt)


def sanitize(value: Any) -> Any:
    """递归脱敏 prompt、trace 和日志可见内容。"""

    if _external_sanitize is not None:
        try:
            return _external_sanitize(value)
        except Exception:
            pass

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                cleaned[key] = "***"
            else:
                cleaned[key] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize(item) for item in value)
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _build_sparql(graph: Any, ontology_id: str, intent: QAIntent) -> str:
    data_graph_iri = _graph_iri(graph, ontology_id, "data")
    result_graph_iri = _graph_iri(graph, ontology_id, "result")
    spec_graph_iri = _graph_iri(graph, ontology_id, "spec")
    params = {
        "onto_ns": ONTO_NS,
        "ontology_id": ontology_id,
        "data_graph_iri": data_graph_iri,
        "result_graph_iri": result_graph_iri,
        "spec_graph_iri": spec_graph_iri,
        "filter_clause": _summary_filter_clause(intent.params),
        **intent.params,
    }
    return TEMPLATES[intent.name].format(**params).strip()


def _select_evidence(graph: Any, ontology_id: str, intent: QAIntent, sparql: str) -> list[dict[str, Any]]:
    if hasattr(graph, "get_qa_evidence"):
        result = graph.get_qa_evidence(ontology_id, intent.name, intent.params)
        return _rows(result)

    sparql_client = getattr(graph, "sparql", None) or getattr(graph, "sparql_client", None)
    if sparql_client is not None and hasattr(sparql_client, "select"):
        return _rows(sparql_client.select(sparql))
    if hasattr(graph, "select"):
        return _rows(graph.select(sparql))
    return []


def _rows(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []
    if isinstance(result, dict):
        return [result]
    return list(result)


def _normalize_evidence(row: dict[str, Any], intent: QAIntent) -> dict[str, Any]:
    normalized = {str(key): _unwrap_value(value) for key, value in row.items()}
    aliases = {
        "mid": "measurement_id",
        "measurement": "measurement_id",
        "specV": "spec_version",
        "specVersion": "spec_version",
        "lo": "lower_limit",
        "lower": "lower_limit",
        "up": "upper_limit",
        "upper": "upper_limit",
        "dev": "deviation",
        "n": "count",
    }
    for old, new in aliases.items():
        if old in normalized and new not in normalized:
            normalized[new] = normalized.pop(old)

    if intent.name in {"why_fail", "why_judgement"} and "measurement_id" not in normalized:
        normalized["measurement_id"] = intent.params.get("measurement_id")
    if not normalized:
        normalized = {"missing": True, **intent.params}
    return normalized


def _unwrap_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _graph_iri(graph: Any, ontology_id: str, kind: str) -> str:
    if hasattr(graph, "graph_iri"):
        return graph.graph_iri(ontology_id, kind)
    if graph_iri_for is not None:
        return graph_iri_for(ontology_id, kind)
    suffix = "" if kind == "ontology" else f"/{kind}"
    return f"https://hifar.top/mto/graph/{ontology_id}{suffix}"


def _summary_filter_clause(params: dict[str, str]) -> str:
    if "batch_id" in params:
        return f'FILTER (?batch_id = "{params["batch_id"]}")'
    if "parameter_code" in params:
        return f'FILTER (?parameter_code = "{params["parameter_code"]}")'
    return ""


def _limited_evidence_json(evidence: Any) -> str:
    text = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    encoded = text.encode("utf-8")
    if len(encoded) <= MAX_EVIDENCE_BYTES:
        return text
    truncated = encoded[:MAX_EVIDENCE_BYTES].decode("utf-8", errors="ignore")
    return f"{truncated}\n<truncated>"


def _trace_log(trace: Any, step: str, status: str, reason: str, **detail: Any) -> None:
    if trace is None or not hasattr(trace, "log"):
        return
    trace.log(step, status, reason=reason, **sanitize(detail))


def _looks_like_why_fail(text: str, lowered: str) -> bool:
    return bool(re.search(r"fail|失败|不合格|为什么|why|原因", lowered, re.IGNORECASE)) and bool(
        re.search(r"fail|失败|不合格", text, re.IGNORECASE)
    )


def _looks_like_why_judgement(text: str, lowered: str) -> bool:
    return bool(re.search(r"为什么|why|原因", lowered, re.IGNORECASE)) and bool(
        re.search(r"pass|fail|合格|不合格|通过|失败", text, re.IGNORECASE)
    )


def _first_match(pattern: str, text: str, flags: int = 0) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1) if match else None


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return lowered in {"authorization", "x_api_key", "cookie"} or lowered.endswith("api_key")


def _sanitize_text(text: str) -> str:
    cleaned = re.sub(
        r"(?i)(authorization|x-api-key|cookie)\s*[:=]\s*[^,\s}]+",
        r"\1=***",
        text,
    )
    cleaned = re.sub(r"(?i)([a-z0-9_]*api_key)\s*[:=]\s*[^,\s}]+", r"\1=***", cleaned)
    cleaned = re.sub(r"(?i)([?&](?:token|key|api_key|secret)=)[^&\s]+", r"\1***", cleaned)
    return cleaned


def _compact_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
