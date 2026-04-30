"""Draft-only commission ontology generation helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from mvp.core.llm.base import LLMProvider


class DraftGenerationError(RuntimeError):
    """Raised when commission draft generation cannot produce a valid draft payload."""


VALID_GENERATION_MODES = {"llm_only", "llm_with_template_fallback", "template_only"}
_REQUIRED_KEYS = (
    "candidate_cqs",
    "candidate_classes",
    "candidate_relations",
    "candidate_properties",
    "candidate_rules",
    "draft_turtle",
    "draft_sparql_tests",
    "source_trace",
)
_TEMPLATE_CANDIDATE_CQS = (
    {"id": "CQ-CT-001", "question": "Which test projects belong to CO-2024-001?"},
    {"id": "CQ-CT-002", "question": "Is every test project decomposed into one task?"},
    {"id": "CQ-CT-003", "question": "Why did T-001 RCS pass under V1?"},
    {"id": "CQ-CT-004", "question": "Which historical results flipped after V2?"},
    {"id": "CQ-CT-005", "question": "Why does T-001 need review?"},
)
_TEMPLATE_CANDIDATE_CLASSES = (
    {"name": "CommissionOrder", "label": "Commission order"},
    {"name": "Product", "label": "Product"},
    {"name": "TestProject", "label": "Test project"},
    {"name": "TestTask", "label": "Test task"},
    {"name": "TestItem", "label": "Test item"},
    {"name": "TestDataRecord", "label": "Test data record"},
    {"name": "PassCriterion", "label": "Pass criterion"},
    {"name": "StandardVersion", "label": "Standard version"},
    {"name": "JudgementResult", "label": "Judgement result"},
    {"name": "ReevaluationImpact", "label": "Reevaluation impact"},
)
_TEMPLATE_CANDIDATE_RELATIONS = (
    {"name": "hasProduct", "domain": "CommissionOrder", "range": "Product"},
    {"name": "hasTestProject", "domain": "CommissionOrder", "range": "TestProject"},
    {"name": "decomposesToTask", "domain": "TestProject", "range": "TestTask"},
    {"name": "supersedesStandard", "domain": "StandardVersion", "range": "StandardVersion"},
)
_TEMPLATE_CANDIDATE_PROPERTIES = (
    {"name": "taskStatus", "domain": "TestTask", "range": "xsd:string"},
    {"name": "measuredValue", "domain": "TestDataRecord", "range": "xsd:decimal"},
    {"name": "threshold", "domain": "PassCriterion", "range": "xsd:decimal"},
)
_TEMPLATE_CANDIDATE_RULES = (
    {"id": "decompose_project_to_task", "then": "create_test_task"},
    {"id": "judge_less_equal_threshold", "then": "Pass"},
    {"id": "mark_task_needs_review_on_flip", "then": "taskStatus = NeedsReview"},
)


def generate_commission_draft(
    *,
    business_text: str,
    generation_mode: str,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Generate a reviewable commission-testing draft payload."""

    if generation_mode not in VALID_GENERATION_MODES:
        raise DraftGenerationError(f"generation_mode must be one of {sorted(VALID_GENERATION_MODES)}")

    if generation_mode == "template_only":
        return _template_payload(business_text=business_text, generation_mode=generation_mode)

    if generation_mode == "llm_only":
        active_provider = _require_provider(provider)
        response = active_provider.chat(_build_prompt(business_text))
        return _normalize_provider_payload(response, generation_mode=generation_mode, provider_name=active_provider.name)

    if provider is None or not provider.available():
        return _template_payload(
            business_text=business_text,
            generation_mode=generation_mode,
            trace=[
                {"mode": generation_mode, "provider": None, "status": "fallback", "reason": "provider unavailable"},
            ],
        )

    try:
        response = provider.chat(_build_prompt(business_text))
        return _normalize_provider_payload(response, generation_mode=generation_mode, provider_name=provider.name)
    except DraftGenerationError as exc:
        return _template_payload(
            business_text=business_text,
            generation_mode=generation_mode,
            trace=[
                {
                    "mode": generation_mode,
                    "provider": provider.name,
                    "status": "fallback",
                    "reason": str(exc),
                }
            ],
        )


def _require_provider(provider: LLMProvider | None) -> LLMProvider:
    if provider is None:
        raise DraftGenerationError("llm_only provider is required")
    if not provider.available():
        raise DraftGenerationError("llm_only provider is unavailable")
    return provider


def _normalize_provider_payload(response: str | None, *, generation_mode: str, provider_name: str) -> dict[str, Any]:
    payload = _parse_provider_json(response)
    missing = [key for key in _REQUIRED_KEYS if key not in payload]
    if missing:
        raise DraftGenerationError(f"provider response missing required keys: {', '.join(missing)}")
    normalized_payload = {
        "generation_mode": generation_mode,
        "candidate_cqs": _normalize_candidate_cqs(payload["candidate_cqs"]),
        "candidate_classes": _normalize_structured_objects(
            payload["candidate_classes"],
            field_name="candidate_classes",
            required_fields=("name",),
        ),
        "candidate_relations": _normalize_structured_objects(
            payload["candidate_relations"],
            field_name="candidate_relations",
            required_fields=("name", "domain", "range"),
        ),
        "candidate_properties": _normalize_structured_objects(
            payload["candidate_properties"],
            field_name="candidate_properties",
            required_fields=("name", "domain", "range"),
        ),
        "candidate_rules": _normalize_structured_objects(
            payload["candidate_rules"],
            field_name="candidate_rules",
            required_fields=("id", "then"),
        ),
        "draft_turtle": _require_string(payload["draft_turtle"], field_name="draft_turtle"),
        "draft_sparql_tests": _normalize_string_list(payload["draft_sparql_tests"], field_name="draft_sparql_tests"),
        "source_trace": _normalize_source_trace(payload["source_trace"]),
    }
    normalized_payload["source_trace"].append(
        {"mode": generation_mode, "provider": provider_name, "status": "success", "source": "llm"}
    )
    return normalized_payload


def _parse_provider_json(response: str | None) -> dict[str, Any]:
    if not response or not str(response).strip():
        raise DraftGenerationError("provider must return valid JSON")
    text = _unwrap_json_block(str(response).strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DraftGenerationError(f"provider must return valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DraftGenerationError("provider must return a JSON object")
    return payload


def _unwrap_json_block(text: str) -> str:
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text


def _build_prompt(business_text: str) -> str:
    return (
        "Return JSON only for a reviewable commission-testing ontology draft. "
        "Do not write formal OWL/Turtle. Include candidate CQs, classes, relations, properties, rules, "
        "draft_turtle text, draft_sparql_tests, and source_trace.\n"
        f"Business text:\n{business_text.strip()}"
    )


def _template_payload(
    *,
    business_text: str,
    generation_mode: str,
    trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_trace = [
        {
            "generator": "template",
            "business_text": business_text.strip(),
        }
    ]
    source_trace.extend(_normalize_source_trace(trace or []))
    return {
        "generation_mode": generation_mode,
        "candidate_cqs": [dict(item) for item in _TEMPLATE_CANDIDATE_CQS],
        "candidate_classes": [dict(item) for item in _TEMPLATE_CANDIDATE_CLASSES],
        "candidate_relations": [dict(item) for item in _TEMPLATE_CANDIDATE_RELATIONS],
        "candidate_properties": [dict(item) for item in _TEMPLATE_CANDIDATE_PROPERTIES],
        "candidate_rules": [dict(item) for item in _TEMPLATE_CANDIDATE_RULES],
        "draft_turtle": (
            "# ontology-id: commission-testing\n"
            "@prefix cto: <https://hifar.top/cto#> .\n"
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n"
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n"
            "cto:CommissionOrder a owl:Class ; rdfs:label \"Commission order\" .\n"
            "cto:Product a owl:Class ; rdfs:label \"Product\" .\n"
            "cto:TestProject a owl:Class ; rdfs:label \"Test project\" .\n"
            "cto:TestTask a owl:Class ; rdfs:label \"Test task\" .\n"
            "cto:StandardVersion a owl:Class ; rdfs:label \"Standard version\" .\n\n"
            "cto:hasProduct a owl:ObjectProperty ; rdfs:domain cto:CommissionOrder ; rdfs:range cto:Product .\n"
            "cto:hasTestProject a owl:ObjectProperty ; rdfs:domain cto:CommissionOrder ; rdfs:range cto:TestProject .\n"
            "cto:decomposesToTask a owl:ObjectProperty ; rdfs:domain cto:TestProject ; rdfs:range cto:TestTask .\n"
            "cto:supersedesStandard a owl:ObjectProperty ; rdfs:domain cto:StandardVersion ; rdfs:range cto:StandardVersion .\n\n"
            "<https://hifar.top/cto/individual/order/CO-DRAFT-001> a cto:CommissionOrder ;\n"
            "    cto:orderNo \"CO-DRAFT-001\" ;\n"
            "    cto:hasTestProject <https://hifar.top/cto/individual/project/P-DRAFT-001> .\n\n"
            "<https://hifar.top/cto/individual/project/P-DRAFT-001> a cto:TestProject ;\n"
            "    cto:localId \"P-DRAFT-001\" ;\n"
            "    cto:decomposesToTask <https://hifar.top/cto/individual/task/T-DRAFT-001> .\n\n"
            "<https://hifar.top/cto/individual/task/T-DRAFT-001> a cto:TestTask ;\n"
            "    cto:localId \"T-DRAFT-001\" ;\n"
            "    cto:taskStatus \"Draft\" .\n"
        ),
        "draft_sparql_tests": ["CQ-CT-001", "CQ-CT-004"],
        "source_trace": source_trace,
    }


def _normalize_candidate_cqs(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise DraftGenerationError("candidate_cqs must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DraftGenerationError(f"candidate_cqs[{index}] must be an object")
        cq_id = _require_string(item.get("id"), field_name=f"candidate_cqs[{index}].id")
        question = item.get("question", item.get("title"))
        question_text = _require_string(question, field_name=f"candidate_cqs[{index}].question")
        normalized.append({"id": cq_id, "question": question_text})
    return normalized


def _normalize_structured_objects(
    value: Any,
    *,
    field_name: str,
    required_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise DraftGenerationError(f"{field_name} must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DraftGenerationError(f"{field_name}[{index}] must be an object")
        normalized_item = dict(item)
        for required_field in required_fields:
            normalized_item[required_field] = _require_string(
                normalized_item.get(required_field),
                field_name=f"{field_name}[{index}].{required_field}",
            )
        normalized.append(normalized_item)
    return normalized


def _normalize_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise DraftGenerationError(f"{field_name} must be a list")
    return [_require_string(item, field_name=f"{field_name}[{index}]") for index, item in enumerate(value)]


def _normalize_source_trace(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise DraftGenerationError("source_trace must be a list")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise DraftGenerationError(f"source_trace[{index}] must be an object")
        normalized.append(dict(item))
    return normalized


def _require_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DraftGenerationError(f"{field_name} must be a non-empty string")
    return value
