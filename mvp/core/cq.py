"""Competency question parsing and validation support.

CQ definitions are maintained as Markdown so business and ontology reviewers can
read them directly. This module gives tests and future tooling a narrow parser
that accepts only the structure documented in the CQ design spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from mvp.core import graph, inference, qa
from mvp.core.llm.base import LLMProvider


DEFAULT_CQ_PATH = Path("docs/cq/measurement-judgement-cqs.md")
REQUIRED_FIELDS = (
    "Business question",
    "Intent",
    "Covers",
    "Demo data",
    "Expected",
    "Evidence fields",
    "Linked QA example",
    "Acceptance",
)
SUPPORTED_EXPECTED_KEYS = {"row_count", "status", "rule", "spec_version", "deviation"}
SECTION_RE = re.compile(r"^##\s+(CQ-MJ-\d{3})\s+(.+?)\s*$", re.MULTILINE)
SPARQL_RE = re.compile(r"```sparql\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
METADATA_RE = re.compile(r"^-\s+([^:]+):\s*(.*)\s*$")
DEFAULT_ONTOLOGY_ID = "manufacturing-trial"
CQ_TRIAL_ID = "T001"
CQ_BATCH_ID = "B03"
CQ_PARAMETER = {
    "code": "cq_temperature",
    "name": "CQ 注塑温度",
    "unit": "°C",
    "value_type": "number",
    "participates_in_inference": True,
}
CQ_SPEC = {
    "lower": 180.0,
    "upper": 195.0,
    "reason": "CQ fixture",
    "effective_from": "2026-04-27T00:00:00Z",
}
CQ_MEASUREMENTS = (
    {"measurement_id": "M007", "value": 197.2},
    {"measurement_id": "M008", "value": 179.1},
    {"measurement_id": "M009", "value": 188.0},
)


class CQParseError(ValueError):
    """Raised when a CQ Markdown document violates the executable contract."""


@dataclass(frozen=True)
class CompetencyQuestion:
    """Parsed executable competency question."""

    id: str
    title: str
    metadata: dict[str, str]
    sparql: str
    expected: dict[str, str]
    evidence_fields: list[str]

    @property
    def linked_qa_example(self) -> str:
        """Return the natural-language QA example linked to this CQ."""

        return self.metadata["Linked QA example"]


@dataclass(frozen=True)
class CQRunResult:
    """Result of executing one CQ against Fuseki and QA evidence."""

    question: CompetencyQuestion
    row: dict[str, Any]
    qa_evidence: dict[str, Any]


class CQEvidenceAdapter:
    """Minimal graph adapter for qa.answer during CQ validation."""

    def __init__(self, repository: graph.BusinessGraphRepository) -> None:
        self.repository = repository

    def graph_iri(self, ontology_id: str, kind: str = "ontology") -> str:
        return graph.graph_iri(ontology_id, kind)

    def get_qa_evidence(self, ontology_id: str, intent_name: str, params: dict[str, str]) -> list[dict[str, Any]]:
        if intent_name not in {"why_fail", "why_judgement"}:
            return []
        measurement_id = params["measurement_id"]
        measurement = self.repository.get_measurement(ontology_id, measurement_id)
        if measurement is None:
            return []
        latest = self.repository.latest_result_for_measurement(ontology_id, measurement_id)
        if latest is None:
            return [{"measurement_id": measurement_id, "missing": True}]
        specification = _find_specification(
            self.repository,
            ontology_id,
            measurement["parameter"],
            latest.spec_version,
        )
        return [
            {
                "measurement_id": measurement_id,
                "value": measurement["value"],
                "status": latest.status,
                "rule": latest.rule,
                "spec_version": latest.spec_version,
                "lower_limit": None if specification is None else specification["lower"],
                "upper_limit": None if specification is None else specification["upper"],
                "deviation": latest.deviation,
                "reasoner": latest.reasoner,
                "inferred_at": latest.inferred_at,
            }
        ]


class CQRunner:
    """Executes measurement judgement CQs against a repository and QA evidence."""

    def __init__(
        self,
        *,
        repository: graph.BusinessGraphRepository,
        provider: LLMProvider | None = None,
        ontology_id: str = DEFAULT_ONTOLOGY_ID,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.ontology_id = ontology_id

    def prepare_measurement_judgement_fixture(self) -> dict[str, Any]:
        """Recreate the fixed CQ measurement judgement fixture."""

        self.repository.load_ontologies(reload=True)
        self.repository.reset_cq_fixture(
            self.ontology_id,
            measurement_ids=[item["measurement_id"] for item in CQ_MEASUREMENTS],
            parameter_code=CQ_PARAMETER["code"],
            spec_versions=["Spec_v1"],
        )
        graph.create_trial(self.ontology_id, CQ_TRIAL_ID, repository=self.repository)
        graph.create_batch(self.ontology_id, CQ_TRIAL_ID, CQ_BATCH_ID, repository=self.repository)
        graph.register_parameter(self.ontology_id, repository=self.repository, **CQ_PARAMETER)
        graph.create_specification(
            self.ontology_id,
            CQ_PARAMETER["code"],
            lower=CQ_SPEC["lower"],
            upper=CQ_SPEC["upper"],
            reason=CQ_SPEC["reason"],
            effective_from=CQ_SPEC["effective_from"],
            repository=self.repository,
        )
        measurements: list[str] = []
        for measurement in CQ_MEASUREMENTS:
            graph.create_measurement(
                self.ontology_id,
                measurement["measurement_id"],
                batch_id=CQ_BATCH_ID,
                parameter_code=CQ_PARAMETER["code"],
                value=measurement["value"],
                repository=self.repository,
            )
            judgement = inference.evaluate_single(
                measurement["value"],
                CQ_SPEC["lower"],
                CQ_SPEC["upper"],
                "Spec_v1",
            )
            graph.save_inference_result(
                self.ontology_id,
                measurement["measurement_id"],
                status=judgement.status,
                rule=judgement.rule,
                spec_version=judgement.spec_version,
                deviation=judgement.deviation,
                reasoner=judgement.reasoner,
                evidence_value=measurement["value"],
                evidence_lower_limit=CQ_SPEC["lower"],
                evidence_upper_limit=CQ_SPEC["upper"],
                repository=self.repository,
            )
            measurements.append(measurement["measurement_id"])
        return {"ontology_id": self.ontology_id, "measurement_ids": measurements}

    def run_question(self, question: CompetencyQuestion) -> CQRunResult:
        """Execute one CQ and validate its SPARQL row plus QA evidence."""

        rows = self._select_rows(render_sparql(question, self.ontology_id))
        validate_expected(question, rows)
        row = rows[0]
        qa_result = qa.answer(
            CQEvidenceAdapter(self.repository),
            self.ontology_id,
            question.linked_qa_example,
            provider=self.provider,
        )
        qa_evidence = dict(qa_result["evidence"])
        validate_evidence_fields(question, row, qa_evidence)
        return CQRunResult(question=question, row=row, qa_evidence=qa_evidence)

    def _select_rows(self, sparql: str) -> list[dict[str, Any]]:
        if self.repository.client is None:
            raise RuntimeError("CQRunner requires a repository with a Fuseki client")
        return [
            {str(key): normalize_sparql_value(value) for key, value in row.items()}
            for row in self.repository.client.select(sparql)
        ]


def parse_cq_markdown(path: str | Path = DEFAULT_CQ_PATH) -> list[CompetencyQuestion]:
    """Parse a CQ Markdown document into executable CQ records."""

    cq_path = Path(path)
    text = cq_path.read_text(encoding="utf-8")
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        raise CQParseError(f"{cq_path} contains no CQ-MJ sections")

    questions: list[CompetencyQuestion] = []
    seen: set[str] = set()
    for index, match in enumerate(matches):
        cq_id = match.group(1)
        title = match.group(2).strip()
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[body_start:body_end]

        if cq_id in seen:
            raise CQParseError(f"duplicate CQ id: {cq_id}")
        seen.add(cq_id)

        metadata = _parse_metadata(cq_id, body)
        sparql = _parse_sparql(cq_id, body)
        expected = _parse_expected(cq_id, metadata["Expected"])
        evidence_fields = _parse_csv_field(metadata["Evidence fields"])
        if not evidence_fields:
            raise CQParseError(f"{cq_id} Evidence fields must not be empty")

        questions.append(
            CompetencyQuestion(
                id=cq_id,
                title=title,
                metadata=metadata,
                sparql=sparql,
                expected=expected,
                evidence_fields=evidence_fields,
            )
        )
    return questions


def _parse_metadata(cq_id: str, body: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for raw_line in body.splitlines():
        match = METADATA_RE.match(raw_line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            metadata[key] = value

    for field in REQUIRED_FIELDS:
        if field not in metadata or not metadata[field]:
            raise CQParseError(f"{cq_id} missing required field: {field}")
    return metadata


def _parse_sparql(cq_id: str, body: str) -> str:
    blocks = [block.strip() for block in SPARQL_RE.findall(body)]
    if len(blocks) != 1:
        raise CQParseError(f"{cq_id} must contain exactly one sparql code block")
    return blocks[0]


def _parse_expected(cq_id: str, raw: str) -> dict[str, str]:
    expected: dict[str, str] = {}
    for item in _parse_csv_field(raw):
        if "=" not in item:
            raise CQParseError(f"{cq_id} invalid Expected assertion: {item}")
        key, value = [part.strip() for part in item.split("=", 1)]
        if key not in SUPPORTED_EXPECTED_KEYS:
            raise CQParseError(f"{cq_id} unsupported Expected key: {key}")
        if not value:
            raise CQParseError(f"{cq_id} Expected value for {key} must not be empty")
        expected[key] = value
    if "row_count" not in expected:
        raise CQParseError(f"{cq_id} missing Expected assertion: row_count")
    return expected


def _parse_csv_field(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_sparql_value(value: Any) -> Any:
    """Normalize SPARQL JSON binding values to simple Python scalars."""

    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def render_sparql(question: CompetencyQuestion | str, ontology_id: str) -> str:
    """Render CQ SPARQL graph placeholders for the target ontology."""

    sparql = question.sparql if isinstance(question, CompetencyQuestion) else str(question)
    replacements = {
        "{{ontology_graph_iri}}": graph.graph_iri(ontology_id),
        "{{data_graph_iri}}": graph.graph_iri(ontology_id, "data"),
        "{{result_graph_iri}}": graph.graph_iri(ontology_id, "result"),
        "{{spec_graph_iri}}": graph.graph_iri(ontology_id, "spec"),
    }
    rendered = sparql
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)

    # Backward-compatible rendering for older CQ documents that embedded the
    # original demo ontology graph IRIs directly.
    for kind in ("ontology", "data", "result", "spec"):
        rendered = rendered.replace(graph.graph_iri(DEFAULT_ONTOLOGY_ID, kind), graph.graph_iri(ontology_id, kind))
    return rendered


def validate_expected(question: CompetencyQuestion, rows: list[dict[str, Any]]) -> None:
    """Validate row count and scalar expected assertions."""

    expected_count = int(question.expected["row_count"])
    if len(rows) != expected_count:
        raise AssertionError(f"{question.id} expected {expected_count} rows, got {len(rows)}")
    if not rows:
        return
    row = rows[0]
    for key, expected in question.expected.items():
        if key == "row_count":
            continue
        actual = row.get(key)
        if key == "deviation":
            if round(float(actual), 10) != round(float(expected), 10):
                raise AssertionError(f"{question.id} expected {key}={expected}, got {actual}")
        elif str(actual) != expected:
            raise AssertionError(f"{question.id} expected {key}={expected}, got {actual}")


def validate_evidence_fields(
    question: CompetencyQuestion,
    sparql_row: dict[str, Any],
    qa_evidence: dict[str, Any],
) -> None:
    """Validate that QA evidence covers and matches CQ evidence fields."""

    missing = [field for field in question.evidence_fields if field not in qa_evidence]
    if missing:
        raise AssertionError(f"{question.id} QA evidence missing fields: {', '.join(missing)}")
    for field in question.evidence_fields:
        left = sparql_row.get(field)
        right = qa_evidence.get(field)
        if field in {"value", "lower_limit", "upper_limit", "deviation"}:
            if left is None or right is None:
                raise AssertionError(f"{question.id} field {field} missing numeric value: {left} != {right}")
            if round(float(left), 10) != round(float(right), 10):
                raise AssertionError(f"{question.id} field {field} mismatch: {left} != {right}")
        elif field in {"inferred_at"}:
            if _normalize_utc_datetime_text(left) != _normalize_utc_datetime_text(right):
                raise AssertionError(f"{question.id} field {field} mismatch: {left} != {right}")
        elif str(left) != str(right):
            raise AssertionError(f"{question.id} field {field} mismatch: {left} != {right}")


def _normalize_utc_datetime_text(value: Any) -> str:
    text = str(value)
    return f"{text[:-6]}Z" if text.endswith("+00:00") else text


def _find_specification(
    repository: graph.BusinessGraphRepository,
    ontology_id: str,
    parameter_code: str,
    spec_version: str,
) -> dict[str, Any] | None:
    for item in repository.list_specifications(ontology_id, parameter_code)["items"]:
        if item["spec_version"] == spec_version:
            return item
    return None
