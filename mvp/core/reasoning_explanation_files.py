"""LLM-backed explanation file generation for reasoning results.

LLM output is limited to explaining existing structured evidence. It must not
participate in the deterministic Pellet/Python judgement path.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from mvp.core.llm.base import LLMProvider


def build_explanation_files(
    ontology_id: str,
    reasoner_result: dict[str, Any],
    *,
    provider: LLMProvider,
    trace: Any = None,
) -> dict[str, Any]:
    """Build downloadable reasoning explanation files from structured evidence."""

    provider_name = getattr(provider, "name", "unknown")
    evidence = _reasoning_evidence(ontology_id, reasoner_result)
    explanation = None
    source = "local_fallback"

    if provider.available():
        prompt = _build_prompt(evidence)
        try:
            explanation = provider.chat(prompt, max_tokens=700, temperature=0.1)
        except Exception as exc:
            _trace_log(
                trace,
                "llm_reasoning_explanation",
                "fallback",
                "LLM 推理解释调用失败，降级到本地解释文件。",
                provider=provider_name,
                error=type(exc).__name__,
            )
        else:
            if explanation:
                source = provider_name
                _trace_log(
                    trace,
                    "llm_reasoning_explanation",
                    "success",
                    "LLM 已基于结构化 evidence 生成推理解释文件。",
                    provider=provider_name,
                )
    else:
        _trace_log(
            trace,
            "llm_reasoning_explanation",
            "fallback",
            "当前 provider 不可用，生成本地解释文件。",
            provider=provider_name,
        )

    markdown = _markdown_file(
        ontology_id,
        evidence,
        explanation or _local_explanation(evidence),
        source=source,
        provider=provider_name,
    )
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)

    return {
        "ontology_id": ontology_id,
        "source": source,
        "provider": provider_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {
                "filename": "reasoning-explanation.md",
                "content_type": "text/markdown; charset=utf-8",
                "description": "面向业务/技术读者的推理解释文件",
                "content": markdown,
            },
            {
                "filename": "reasoning-evidence.json",
                "content_type": "application/json; charset=utf-8",
                "description": "LLM 解释所依据的结构化 evidence",
                "content": evidence_json,
            },
        ],
    }


def _reasoning_evidence(ontology_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ontology_id": ontology_id,
        "reasoner": result.get("reasoner"),
        "pellet_status": result.get("pellet_status"),
        "pellet_ms": result.get("pellet_ms"),
        "pellet_error": result.get("pellet_error"),
        "retry_after_ms": result.get("retry_after_ms"),
        "cache_hit": result.get("cache_hit"),
        "inferred_triple_count": int(result.get("inferred_triple_count") or 0),
        "class_count": len(list(result.get("classes") or [])),
        "individual_count": len(list(result.get("individuals") or [])),
        "object_property_count": len(list(result.get("object_properties") or [])),
        "data_property_count": len(list(result.get("data_properties") or [])),
        "swrl_enabled": result.get("swrl_enabled"),
        "swrl_status": result.get("swrl_status"),
        "java_source": result.get("java_source"),
    }


def _build_prompt(evidence: dict[str, Any]) -> str:
    evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    return (
        "你是制造业本体推理解释助手。"
        "只能解释 Evidence JSON 中已经存在的事实；不得新增判定、不得改变 Pellet 状态、不得编写自由 SPARQL。"
        "请输出 Markdown，包含：推理流程、推理方向、结果说明、风险或降级原因。"
        f"\nEvidence JSON: {evidence_json}"
    )


def _markdown_file(
    ontology_id: str,
    evidence: dict[str, Any],
    explanation: str,
    *,
    source: str,
    provider: str,
) -> str:
    return (
        f"# 推理解释文件\n\n"
        f"- 本体：`{ontology_id}`\n"
        f"- 解释来源：`{source}`\n"
        f"- Provider：`{provider}`\n"
        f"- Pellet 状态：`{evidence.get('pellet_status') or 'unknown'}`\n"
        f"- 推理耗时：`{evidence.get('pellet_ms') or '-'}` ms\n"
        f"- 新增推断：`{evidence.get('inferred_triple_count')}`\n\n"
        "## 解释正文\n\n"
        f"{explanation.strip()}\n\n"
        "## Evidence 摘要\n\n"
        f"- 类数量：{evidence.get('class_count')}\n"
        f"- 个体数量：{evidence.get('individual_count')}\n"
        f"- 对象属性数量：{evidence.get('object_property_count')}\n"
        f"- 数据属性数量：{evidence.get('data_property_count')}\n"
    )


def _local_explanation(evidence: dict[str, Any]) -> str:
    status = evidence.get("pellet_status") or "unknown"
    if status == "success":
        return (
            "本地解释：Pellet 推理成功。页面展示的状态、耗时、主体数量和新增推断"
            "来自后端结构化 evidence，LLM 未参与判定。"
        )
    if status == "busy":
        return "本地解释：当前同一 Turtle 指纹的推理任务仍在运行，建议稍后重试。"
    if status in {"failed", "missing_java"}:
        return f"本地解释：Pellet 未完成，降级原因为 {evidence.get('pellet_error') or status}。"
    return f"本地解释：当前推理状态为 {status}，请结合 evidence JSON 查看链路。"


def _trace_log(trace: Any, step: str, status: str, reason: str, **detail: Any) -> None:
    if trace is not None and hasattr(trace, "log"):
        trace.log(step, status, reason=reason, **detail)
