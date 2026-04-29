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
    payload["generation_mode"] = generation_mode
    payload["source_trace"] = list(payload["source_trace"]) + [
        {"mode": generation_mode, "provider": provider_name, "status": "success", "source": "llm"}
    ]
    return payload


def _parse_provider_json(response: str | None) -> dict[str, Any]:
    if not response or not str(response).strip():
        raise DraftGenerationError("provider must return valid JSON")
    text = _unwrap_json_block(str(response).strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DraftGenerationError("provider must return valid JSON") from exc
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
    normalized_text = " ".join((business_text or "").split())
    source_trace = list(trace or [])
    source_trace.append(
        {
            "mode": generation_mode,
            "fallback": "template_only",
            "business_text_excerpt": normalized_text[:120],
        }
    )
    return {
        "generation_mode": generation_mode,
        "candidate_cqs": [
            {
                "id": "CQ-CT-004",
                "title": "Which historical results flipped after V2?",
                "intent": "standard_upgrade_flips",
            }
        ],
        "candidate_classes": ["CommissionOrder", "TestTask"],
        "candidate_relations": ["decomposesToTask", "supersedesStandard"],
        "candidate_properties": ["draftStatus", "draftPayload"],
        "candidate_rules": ["project_decomposes_to_task", "standard_upgrade_requires_review"],
        "draft_turtle": (
            "# commission-testing draft sketch only\n"
            "# This is a draft sketch for human review, not formal OWL/Turtle.\n"
            "CommissionOrder -> decomposesToTask -> TestTask\n"
            "StandardVersion -> supersedesStandard -> StandardVersion\n"
            "Focus CQ: CQ-CT-004 historical flip analysis.\n"
        ),
        "draft_sparql_tests": ["CQ-CT-004: flipped historical results after V2"],
        "source_trace": source_trace,
    }
