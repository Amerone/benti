"""CQ workflow quality gates for SPARQL/SHACL/pytest validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import warnings

from rdflib import Graph


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMMISSION_SHACL_PATH = PROJECT_ROOT / "mvp" / "shapes" / "commission-testing-shacl.ttl"


class CQWorkflowError(ValueError):
    """Raised when a CQ workflow gate blocks publication."""


@dataclass(frozen=True)
class CQQualityGateCheck:
    """One executable CQ workflow gate check."""

    category: str
    passed: bool
    message: str
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "passed": self.passed,
            "message": self.message,
            "detail": self.detail,
        }


def validate_shacl_graph(data_graph: Graph, shapes_path: str | Path = DEFAULT_COMMISSION_SHACL_PATH) -> CQQualityGateCheck:
    """Validate an RDF graph against a SHACL shapes graph."""

    try:
        from pyshacl import validate
    except ImportError as exc:  # pragma: no cover - exercised only in incomplete environments
        raise CQWorkflowError("pyshacl is required for SHACL validation") from exc

    resolved_shapes = Path(shapes_path)
    if not resolved_shapes.exists():
        raise CQWorkflowError(f"SHACL shapes file not found: {resolved_shapes}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        conforms, _report_graph, report_text = validate(
            data_graph=data_graph,
            shacl_graph=str(resolved_shapes),
            inference="rdfs",
            abort_on_first=False,
            allow_infos=True,
            allow_warnings=True,
        )
    message = "SHACL validation conforms" if conforms else "SHACL validation failed"
    return CQQualityGateCheck(
        category="shacl",
        passed=bool(conforms),
        message=message,
        detail={"conforms": bool(conforms), "report_text": str(report_text)},
    )


def validate_draft_quality_gate(
    payload: dict[str, Any],
    *,
    shapes_path: str | Path = DEFAULT_COMMISSION_SHACL_PATH,
) -> dict[str, Any]:
    """Validate a generated CQ draft before release publication."""

    checks = [_validate_draft_metadata(payload), _validate_draft_turtle(payload)]
    data_graph = Graph()
    try:
        data_graph.parse(data=str(payload["draft_turtle"]), format="turtle")
    except Exception as exc:
        raise CQWorkflowError(f"draft Turtle is invalid: {exc}") from exc

    shacl_check = validate_shacl_graph(data_graph, shapes_path)
    checks.append(shacl_check)
    if not shacl_check.passed:
        raise CQWorkflowError(shacl_check.message)

    return {
        "passed": all(check.passed for check in checks),
        "checks": [check.to_dict() for check in checks],
    }


def _validate_draft_metadata(payload: dict[str, Any]) -> CQQualityGateCheck:
    candidate_cqs = payload.get("candidate_cqs")
    sparql_tests = payload.get("draft_sparql_tests")
    if not isinstance(candidate_cqs, list) or not candidate_cqs:
        raise CQWorkflowError("draft quality gate requires at least one candidate CQ")
    if not isinstance(sparql_tests, list) or not sparql_tests:
        raise CQWorkflowError("draft quality gate requires at least one SPARQL test")
    candidate_ids = _candidate_cq_ids(candidate_cqs)
    seen_sparql_tests: set[str] = set()
    for sparql_test in sparql_tests:
        if not isinstance(sparql_test, str) or not sparql_test.strip():
            raise CQWorkflowError("draft SPARQL test id must be a non-empty string")
        if sparql_test in seen_sparql_tests:
            raise CQWorkflowError(f"duplicate draft SPARQL test id: {sparql_test}")
        seen_sparql_tests.add(sparql_test)
        if sparql_test not in candidate_ids:
            raise CQWorkflowError(f"draft SPARQL test references unknown candidate CQ: {sparql_test}")
    return CQQualityGateCheck(
        category="metadata",
        passed=True,
        message="CQ draft metadata is reviewable",
        detail={"candidate_cq_count": len(candidate_cqs), "sparql_test_count": len(sparql_tests)},
    )


def _candidate_cq_ids(candidate_cqs: list[Any]) -> set[str]:
    ids: set[str] = set()
    for index, item in enumerate(candidate_cqs):
        if not isinstance(item, dict):
            raise CQWorkflowError(f"candidate_cqs[{index}] must be an object")
        cq_id = item.get("id")
        if not isinstance(cq_id, str) or not cq_id.strip():
            raise CQWorkflowError(f"candidate_cqs[{index}].id must be a non-empty string")
        if cq_id in ids:
            raise CQWorkflowError(f"duplicate candidate CQ id: {cq_id}")
        review_text = item.get("question", item.get("title"))
        if not isinstance(review_text, str) or not review_text.strip():
            raise CQWorkflowError(f"candidate_cqs[{index}] must include question or title")
        ids.add(cq_id)
    return ids


def _validate_draft_turtle(payload: dict[str, Any]) -> CQQualityGateCheck:
    raw_turtle = payload.get("draft_turtle")
    if not isinstance(raw_turtle, str) or not raw_turtle.strip():
        raise CQWorkflowError("draft quality gate requires non-empty draft Turtle")

    data_graph = Graph()
    try:
        data_graph.parse(data=raw_turtle, format="turtle")
    except Exception as exc:
        raise CQWorkflowError(f"draft Turtle is invalid: {exc}") from exc

    return CQQualityGateCheck(
        category="turtle",
        passed=True,
        message="Draft Turtle parses",
        detail={"triple_count": len(data_graph)},
    )
