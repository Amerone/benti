# CQ Measurement Judgement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Markdown-maintained, machine-executable CQ validation path for the measurement judgement loop.

**Architecture:** CQ definitions live in `docs/cq/measurement-judgement-cqs.md`; `mvp/core/cq.py` parses them, initializes a fixed Fuseki-backed fixture, executes declared SPARQL, and validates QA evidence against the same fields. Parser tests run offline, while integration tests skip cleanly when Fuseki is unavailable.

**Tech Stack:** Python 3.11+, pytest, rdflib-backed `BusinessGraphRepository`, Apache Jena Fuseki via `FusekiClient`, existing `qa.answer()` fallback path.

---

## Execution Notes

Current planning workspace `E:\company\temp\benti` is not a git repository. If implementation runs in a real git worktree, create a Lore-format commit after each task. If it runs in this same non-git directory, replace commit steps with a checkpoint note listing changed files and verification output.

Spec source: `docs/superpowers/specs/2026-04-27-cq-measurement-judgement-design.md`.

## File Structure

- Create `docs/cq/measurement-judgement-cqs.md`: business-readable CQ source with three executable SPARQL blocks.
- Create `mvp/core/cq.py`: CQ dataclasses, Markdown parser, fixture initializer, SPARQL row normalization, expected assertion validation, and QA evidence validation.
- Modify `mvp/core/qa.py`: extend the existing measurement evidence template to support Pass explanation questions without enabling free-form QA.
- Modify `mvp/core/graph.py`: add scoped CQ fixture reset support to delete only fixed CQ data and sync touched named graphs.
- Create `tests/test_cq_parser.py`: offline parser contract tests.
- Create `tests/test_cq_integration.py`: real Fuseki/SPARQL CQ runner tests with skip when Fuseki is unavailable.
- Modify `tests/test_graph.py`: lock scoped fixture reset behavior.
- Modify `tests/test_qa.py`: lock Pass judgement intent extraction and local fallback behavior.
- Modify `README.md`: document how to maintain and run CQ validation.

---

### Task 1: CQ Markdown Source And Parser Test

**Files:**
- Create: `docs/cq/measurement-judgement-cqs.md`
- Create: `tests/test_cq_parser.py`
- Later implementation target: `mvp/core/cq.py`

- [ ] **Step 1: Create the CQ source document**

Create `docs/cq/measurement-judgement-cqs.md` with this complete content:

````markdown
# Measurement Judgement Competency Questions

These competency questions define the first executable requirements for the measurement judgement loop. Each CQ is business-readable and machine-executable: the SPARQL block is the validation query, `Expected` is the assertion set, and `Evidence fields` is the contract shared with QA evidence.

## CQ-MJ-001 Why is M007 Fail_High?

- Business question: M007 为什么 Fail？
- Intent: why_fail
- Covers: Measurement, Specification, Result
- Demo data: M007, temperature=197.2, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Fail_High, rule=Rule_Fail_High, spec_version=Spec_v1, deviation=2.2

```sparql
PREFIX mto: <https://hifar.top/mto#>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {
  GRAPH <https://hifar.top/mto/graph/manufacturing-trial/data> {
    ?m a mto:Measurement ;
       mto:localId "M007" ;
       mto:localId ?measurement_id ;
       mto:measuredValue ?value .
  }
  GRAPH <https://hifar.top/mto/graph/manufacturing-trial/result> {
    ?m mto:hasLatestResult ?r .
    ?r mto:resultStatus ?status ;
       mto:appliedRule ?rule ;
       mto:againstSpecVersion ?spec_version ;
       mto:evidenceLowerLimit ?lower_limit ;
       mto:evidenceUpperLimit ?upper_limit ;
       mto:deviation ?deviation ;
       mto:reasoner ?reasoner ;
       mto:inferredAt ?inferred_at .
  }
}
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M007 为什么 Fail？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.

## CQ-MJ-002 Why is M008 Fail_Low?

- Business question: M008 为什么 Fail？
- Intent: why_fail
- Covers: Measurement, Specification, Result
- Demo data: M008, temperature=179.1, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Fail_Low, rule=Rule_Fail_Low, spec_version=Spec_v1, deviation=0.9

```sparql
PREFIX mto: <https://hifar.top/mto#>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {
  GRAPH <https://hifar.top/mto/graph/manufacturing-trial/data> {
    ?m a mto:Measurement ;
       mto:localId "M008" ;
       mto:localId ?measurement_id ;
       mto:measuredValue ?value .
  }
  GRAPH <https://hifar.top/mto/graph/manufacturing-trial/result> {
    ?m mto:hasLatestResult ?r .
    ?r mto:resultStatus ?status ;
       mto:appliedRule ?rule ;
       mto:againstSpecVersion ?spec_version ;
       mto:evidenceLowerLimit ?lower_limit ;
       mto:evidenceUpperLimit ?upper_limit ;
       mto:deviation ?deviation ;
       mto:reasoner ?reasoner ;
       mto:inferredAt ?inferred_at .
  }
}
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M008 为什么 Fail？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.

## CQ-MJ-003 Why is M009 Pass?

- Business question: M009 为什么 Pass？
- Intent: why_judgement
- Covers: Measurement, Specification, Result
- Demo data: M009, temperature=188.0, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Pass, rule=Rule_Pass, spec_version=Spec_v1, deviation=0.0

```sparql
PREFIX mto: <https://hifar.top/mto#>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {
  GRAPH <https://hifar.top/mto/graph/manufacturing-trial/data> {
    ?m a mto:Measurement ;
       mto:localId "M009" ;
       mto:localId ?measurement_id ;
       mto:measuredValue ?value .
  }
  GRAPH <https://hifar.top/mto/graph/manufacturing-trial/result> {
    ?m mto:hasLatestResult ?r .
    ?r mto:resultStatus ?status ;
       mto:appliedRule ?rule ;
       mto:againstSpecVersion ?spec_version ;
       mto:evidenceLowerLimit ?lower_limit ;
       mto:evidenceUpperLimit ?upper_limit ;
       mto:deviation ?deviation ;
       mto:reasoner ?reasoner ;
       mto:inferredAt ?inferred_at .
  }
}
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M009 为什么 Pass？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.
````

- [ ] **Step 2: Write the failing parser tests**

Create `tests/test_cq_parser.py` with this complete content:

```python
from pathlib import Path

import pytest

from mvp.core import cq


DOC_PATH = Path("docs/cq/measurement-judgement-cqs.md")


def test_parse_measurement_judgement_cqs():
    questions = cq.parse_cq_markdown(DOC_PATH)

    assert [item.id for item in questions] == ["CQ-MJ-001", "CQ-MJ-002", "CQ-MJ-003"]
    assert questions[0].title == "Why is M007 Fail_High?"
    assert questions[0].metadata["Business question"] == "M007 为什么 Fail？"
    assert questions[0].metadata["Intent"] == "why_fail"
    assert questions[0].expected == {
        "row_count": "1",
        "status": "Fail_High",
        "rule": "Rule_Fail_High",
        "spec_version": "Spec_v1",
        "deviation": "2.2",
    }
    assert "GRAPH <https://hifar.top/mto/graph/manufacturing-trial/result>" in questions[0].sparql
    assert questions[0].evidence_fields == [
        "measurement_id",
        "value",
        "status",
        "rule",
        "spec_version",
        "lower_limit",
        "upper_limit",
        "deviation",
        "reasoner",
        "inferred_at",
    ]


def test_parse_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "duplicate.md"
    path.write_text(
        """# Bad

## CQ-MJ-001 First

- Business question: q1
- Intent: why_fail
- Covers: Measurement
- Demo data: M001
- Expected: row_count=1

```sparql
SELECT * WHERE { ?s ?p ?o }
```

- Evidence fields: measurement_id
- Linked QA example: M001 为什么 Fail？
- Acceptance: one row

## CQ-MJ-001 Second

- Business question: q2
- Intent: why_fail
- Covers: Measurement
- Demo data: M002
- Expected: row_count=1

```sparql
SELECT * WHERE { ?s ?p ?o }
```

- Evidence fields: measurement_id
- Linked QA example: M002 为什么 Fail？
- Acceptance: one row
""",
        encoding="utf-8",
    )

    with pytest.raises(cq.CQParseError, match="duplicate CQ id: CQ-MJ-001"):
        cq.parse_cq_markdown(path)


def test_parse_rejects_missing_required_field(tmp_path):
    path = tmp_path / "missing.md"
    path.write_text(
        """# Bad

## CQ-MJ-001 Missing Expected

- Business question: q1
- Intent: why_fail
- Covers: Measurement
- Demo data: M001

```sparql
SELECT * WHERE { ?s ?p ?o }
```

- Evidence fields: measurement_id
- Linked QA example: M001 为什么 Fail？
- Acceptance: one row
""",
        encoding="utf-8",
    )

    with pytest.raises(cq.CQParseError, match="CQ-MJ-001 missing required field: Expected"):
        cq.parse_cq_markdown(path)


def test_parse_rejects_multiple_sparql_blocks(tmp_path):
    path = tmp_path / "multi.md"
    path.write_text(
        """# Bad

## CQ-MJ-001 Too Many Queries

- Business question: q1
- Intent: why_fail
- Covers: Measurement
- Demo data: M001
- Expected: row_count=1

```sparql
SELECT * WHERE { ?s ?p ?o }
```

```sparql
SELECT * WHERE { ?s ?p ?o }
```

- Evidence fields: measurement_id
- Linked QA example: M001 为什么 Fail？
- Acceptance: one row
""",
        encoding="utf-8",
    )

    with pytest.raises(cq.CQParseError, match="CQ-MJ-001 must contain exactly one sparql code block"):
        cq.parse_cq_markdown(path)
```

- [ ] **Step 3: Run parser test to verify it fails before implementation**

Run:

```powershell
python -m pytest tests/test_cq_parser.py -q
```

Expected: FAIL during import with `ImportError` or `ModuleNotFoundError` for `mvp.core.cq`.

- [ ] **Step 4: Checkpoint**

Current workspace has no `.git`; record changed files and failing test:

```powershell
Get-ChildItem docs\cq,tests -File | Select-Object FullName
python -m pytest tests/test_cq_parser.py -q
```

Expected: file list includes `docs/cq/measurement-judgement-cqs.md` and `tests/test_cq_parser.py`; pytest still fails because `mvp.core.cq` is not implemented.

---

### Task 2: CQ Parser Implementation

**Files:**
- Create: `mvp/core/cq.py`
- Test: `tests/test_cq_parser.py`

- [ ] **Step 1: Add the parser implementation**

Create `mvp/core/cq.py` with this initial complete content:

```python
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
```

- [ ] **Step 2: Run parser tests**

Run:

```powershell
python -m pytest tests/test_cq_parser.py -q
```

Expected: PASS with `4 passed`.

- [ ] **Step 3: Run import compile check**

Run:

```powershell
python -m compileall mvp\core\cq.py tests\test_cq_parser.py
```

Expected: both files compile successfully.

- [ ] **Step 4: Checkpoint**

If execution is in a git repository, use this Lore commit:

```bash
git add docs/cq/measurement-judgement-cqs.md tests/test_cq_parser.py mvp/core/cq.py
git commit -m "Make measurement CQs executable requirements

Introduce a Markdown CQ contract and parser so measurement judgement requirements can be reviewed by business stakeholders and executed by tests.

Constraint: CQ source must remain Markdown for business and ontology review
Rejected: Store first-pass CQ records as RDF | adds ontology governance before validation is stable
Confidence: high
Scope-risk: narrow
Tested: python -m pytest tests/test_cq_parser.py -q
Tested: python -m compileall mvp\core\cq.py tests\test_cq_parser.py"
```

If execution is in this non-git workspace, record `tests/test_cq_parser.py -q` output and changed files.

---

### Task 3: Scoped CQ Fixture Reset In Graph Repository

**Files:**
- Modify: `tests/test_graph.py`
- Modify: `mvp/core/graph.py`

- [ ] **Step 1: Add the failing graph reset test**

Append this test to `tests/test_graph.py`:

```python
def test_reset_cq_fixture_removes_only_fixed_measurement_scope() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B03", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="°C", repository=repo)
    graph.register_parameter("manufacturing-trial", "pressure", unit="MPa", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="CQ fixture",
        effective_from="2026-04-27T00:00:00Z",
        repository=repo,
    )
    graph.create_specification(
        "manufacturing-trial",
        "pressure",
        lower=1,
        upper=2,
        reason="Unrelated",
        effective_from="2026-04-27T00:00:00Z",
        repository=repo,
    )
    graph.create_and_infer(
        "manufacturing-trial",
        "M007",
        batch_id="B03",
        parameter_code="temperature",
        value=197.2,
        repository=repo,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M999",
        batch_id="B03",
        parameter_code="pressure",
        value=1.5,
        repository=repo,
    )

    removed = repo.reset_cq_fixture(
        "manufacturing-trial",
        measurement_ids=["M007"],
        parameter_code="temperature",
        spec_versions=["Spec_v1"],
    )

    assert removed["measurements"] == 1
    assert removed["parameters"] == 1
    assert removed["specifications"] == 1
    assert removed["results"] == 1
    assert graph.list_measurements("manufacturing-trial", repository=repo)["items"] == [
        {"measurement_id": "M999", "batch": "B03", "parameter": "pressure", "value": 1.5}
    ]
    assert graph.list_parameters("manufacturing-trial", repository=repo)["items"][0]["code"] == "pressure"
    assert graph.list_specifications("manufacturing-trial", "pressure", repository=repo)["items"][0]["spec_version"] == "Spec_v1"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
python -m pytest tests/test_graph.py::test_reset_cq_fixture_removes_only_fixed_measurement_scope -q
```

Expected: FAIL with `AttributeError: 'BusinessGraphRepository' object has no attribute 'reset_cq_fixture'`.

- [ ] **Step 3: Add graph reset helpers**

In `mvp/core/graph.py`, add this helper after `_replace_object`:

```python
def _remove_node_mentions(graph: Graph, node: URIRef) -> int:
    """Remove triples where node appears as subject or object and return removed count."""

    before = len(graph)
    graph.remove((node, None, None))
    graph.remove((None, None, node))
    return before - len(graph)
```

- [ ] **Step 4: Add the repository reset method**

Add this method inside `BusinessGraphRepository`, after `serialize_graph`:

```python
    def reset_cq_fixture(
        self,
        ontology_id: str,
        *,
        measurement_ids: list[str],
        parameter_code: str,
        spec_versions: list[str],
    ) -> dict[str, int]:
        """Delete only the fixed CQ fixture scope from data/spec/result graphs."""

        data_graph = self.graph(ontology_id, "data")
        spec_graph = self.graph(ontology_id, "spec")
        result_graph = self.graph(ontology_id, "result")

        measurement_nodes = [_node(ontology_id, "measurement", measurement_id) for measurement_id in measurement_ids]
        result_nodes: set[URIRef] = set()
        for measurement_node in measurement_nodes:
            result_nodes.update(node for node in result_graph.objects(measurement_node, MTO.hasLatestResult) if isinstance(node, URIRef))
            result_nodes.update(node for node in result_graph.subjects(MTO.forMeasurement, measurement_node) if isinstance(node, URIRef))

        removed = {"measurements": 0, "parameters": 0, "specifications": 0, "results": 0}
        for measurement_node in measurement_nodes:
            removed["measurements"] += int(_remove_node_mentions(data_graph, measurement_node) > 0)
            _remove_node_mentions(result_graph, measurement_node)

        for result_node in sorted(result_nodes, key=str):
            removed["results"] += int(_remove_node_mentions(result_graph, result_node) > 0)

        parameter_node = _node(ontology_id, "parameter", parameter_code)
        removed["parameters"] += int(_remove_node_mentions(data_graph, parameter_node) > 0)

        spec_nodes = {
            _node(ontology_id, "specification", f"{parameter_code}_{spec_version}")
            for spec_version in spec_versions
        }
        spec_nodes.update(
            node
            for node in spec_graph.subjects(MTO.parameterCode, Literal(parameter_code))
            if isinstance(node, URIRef)
        )
        for spec_node in sorted(spec_nodes, key=str):
            removed["specifications"] += int(_remove_node_mentions(spec_graph, spec_node) > 0)

        self._sync_graph_to_remote(ontology_id, "data")
        self._sync_graph_to_remote(ontology_id, "spec")
        self._sync_graph_to_remote(ontology_id, "result")
        return removed
```

- [ ] **Step 5: Add a module-level wrapper**

In `mvp/core/graph.py`, add this function near the other module-level wrappers:

```python
def reset_cq_fixture(
    ontology_id: str,
    *,
    measurement_ids: list[str],
    parameter_code: str,
    spec_versions: list[str],
    repository: BusinessGraphRepository | None = None,
) -> dict[str, int]:
    """Delete only the fixed CQ fixture scope from data/spec/result graphs."""

    return (repository or _DEFAULT_REPOSITORY).reset_cq_fixture(
        ontology_id,
        measurement_ids=measurement_ids,
        parameter_code=parameter_code,
        spec_versions=spec_versions,
    )
```

- [ ] **Step 6: Run graph tests**

Run:

```powershell
python -m pytest tests/test_graph.py -q
```

Expected: PASS or existing Fuseki placeholder skip; the new reset test passes.

- [ ] **Step 7: Run compile check**

Run:

```powershell
python -m compileall mvp\core\graph.py tests\test_graph.py
```

Expected: both files compile successfully.

- [ ] **Step 8: Checkpoint**

If execution is in a git repository, use this Lore commit:

```bash
git add mvp/core/graph.py tests/test_graph.py
git commit -m "Constrain CQ fixture cleanup to owned graph data

Add a scoped reset hook so CQ validation can recreate its demo baseline without clearing unrelated Fuseki data.

Constraint: CQ runner must not wipe entire named graphs
Rejected: Clear data/result/spec graphs before CQ tests | would destroy manual demonstration data
Confidence: medium
Scope-risk: moderate
Tested: python -m pytest tests/test_graph.py -q
Tested: python -m compileall mvp\core\graph.py tests\test_graph.py"
```

If execution is in this non-git workspace, record changed files and test output.

---

### Task 4: CQ Runner And Fuseki Integration Test

**Files:**
- Modify: `mvp/core/cq.py`
- Modify: `mvp/core/qa.py`
- Modify: `tests/test_qa.py`
- Create: `tests/test_cq_integration.py`

- [ ] **Step 1: Write the failing QA Pass judgement test**

Append this test to `tests/test_qa.py`:

```python
def test_answer_supports_why_pass_question_with_same_measurement_evidence():
    provider = Provider(name="none", available=False)

    result = qa.answer(
        FakeGraph([evidence_row(measurement_id="M009", value="188.0", status="Pass", rule="Rule_Pass", deviation="0.0")]),
        "manufacturing-trial",
        "M009 为什么 Pass？",
        provider=provider,
    )

    assert result["source"] == "local_fallback"
    assert result["intent"] == "why_judgement"
    assert result["evidence"]["measurement_id"] == "M009"
    assert result["evidence"]["status"] == "Pass"
    assert "Pass" in result["answer"]
```

- [ ] **Step 2: Run the focused QA test and verify it fails**

Run:

```powershell
python -m pytest tests/test_qa.py::test_answer_supports_why_pass_question_with_same_measurement_evidence -q
```

Expected: FAIL because `qa.extract_intent()` currently treats `M009 为什么 Pass？` as an unsupported question.

- [ ] **Step 3: Extend QA to support Pass judgement questions**

In `mvp/core/qa.py`, after the `TEMPLATES` dictionary definition, add this alias:

```python
TEMPLATES["why_judgement"] = TEMPLATES["why_fail"]
```

In `extract_intent()`, keep the existing fail branch and add this Pass/judgement branch immediately after it:

```python
    if mid and _looks_like_why_judgement(text, lowered):
        return QAIntent("why_judgement", {"measurement_id": mid.upper()}, "命中 measurement judgement 模板")
```

In `local_fallback()`, change:

```python
    if intent_name == "why_fail":
```

to:

```python
    if intent_name in {"why_fail", "why_judgement"}:
```

At the bottom of `mvp/core/qa.py`, add this helper near `_looks_like_why_fail()`:

```python
def _looks_like_why_judgement(text: str, lowered: str) -> bool:
    return bool(re.search(r"为什么|why|原因", lowered, re.IGNORECASE)) and bool(
        re.search(r"pass|fail|合格|不合格|通过|失败", text, re.IGNORECASE)
    )
```

- [ ] **Step 4: Run QA tests**

Run:

```powershell
python -m pytest tests/test_qa.py -q
```

Expected: existing QA tests still pass, and the new Pass judgement test passes.

- [ ] **Step 5: Write the failing integration test**

Create `tests/test_cq_integration.py` with this complete content:

```python
from __future__ import annotations

import pytest

from mvp.core import cq, graph
from mvp.core.llm.base import LLMProvider
from mvp.core.sparql_client import FusekiClient, FusekiError


class UnavailableProvider(LLMProvider):
    name = "test-unavailable"
    default_model = "none"

    def available(self) -> bool:
        return False

    def chat(self, prompt: str, **kwargs):
        raise AssertionError("chat should not be called when provider is unavailable")


def _repo_or_skip() -> graph.BusinessGraphRepository:
    client = FusekiClient(timeout=2.0)
    if not client.ping():
        pytest.skip("Fuseki unavailable; run `docker compose up -d` before CQ integration tests")
    return graph.BusinessGraphRepository(client=client)


def test_cq_runner_executes_measurement_judgement_cqs_against_fuseki():
    repo = _repo_or_skip()
    runner = cq.CQRunner(repository=repo, provider=UnavailableProvider())
    questions = cq.parse_cq_markdown()

    try:
        runner.prepare_measurement_judgement_fixture()
    except FusekiError as exc:
        if exc.code == "FUSEKI_HTTP_401":
            pytest.skip("Fuseki requires write credentials; set FUSEKI_USER/FUSEKI_PASSWORD")
        raise

    results = [runner.run_question(question) for question in questions]

    assert [result.question.id for result in results] == ["CQ-MJ-001", "CQ-MJ-002", "CQ-MJ-003"]
    assert [result.row["status"] for result in results] == ["Fail_High", "Fail_Low", "Pass"]
    assert [float(result.row["deviation"]) for result in results] == [2.2, 0.9, 0.0]
    assert all(result.qa_evidence["measurement_id"] == result.row["measurement_id"] for result in results)
    assert all(result.qa_evidence["status"] == result.row["status"] for result in results)
    assert all(set(result.question.evidence_fields).issubset(result.qa_evidence.keys()) for result in results)
```

- [ ] **Step 6: Run the integration test and verify it fails**

Run with Fuseki started:

```powershell
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

Expected: FAIL with `AttributeError` for `CQRunner` if Fuseki is available. If Fuseki is unavailable, the test skips with the explicit message.

- [ ] **Step 7: Extend `mvp/core/cq.py` imports and constants**

In `mvp/core/cq.py`, extend imports:

```python
from mvp.core import graph, qa
from mvp.core.llm.base import LLMProvider
```

Then add these constants after `METADATA_RE`:

```python
DEFAULT_ONTOLOGY_ID = "manufacturing-trial"
CQ_TRIAL_ID = "T001"
CQ_BATCH_ID = "B03"
CQ_PARAMETER = {
    "code": "temperature",
    "name": "注塑温度",
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
```

- [ ] **Step 8: Add run result dataclass and evidence adapter**

Append this code to `mvp/core/cq.py`:

```python
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
```

- [ ] **Step 9: Add runner class and validation helpers**

Append this code to `mvp/core/cq.py`:

```python
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
            graph.create_and_infer(
                self.ontology_id,
                measurement["measurement_id"],
                batch_id=CQ_BATCH_ID,
                parameter_code=CQ_PARAMETER["code"],
                value=measurement["value"],
                repository=self.repository,
            )
            measurements.append(measurement["measurement_id"])
        return {"ontology_id": self.ontology_id, "measurement_ids": measurements}

    def run_question(self, question: CompetencyQuestion) -> CQRunResult:
        """Execute one CQ and validate its SPARQL row plus QA evidence."""

        rows = self._select_rows(question.sparql)
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
            if round(float(left), 10) != round(float(right), 10):
                raise AssertionError(f"{question.id} field {field} mismatch: {left} != {right}")
        elif str(left) != str(right):
            raise AssertionError(f"{question.id} field {field} mismatch: {left} != {right}")


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
```

- [ ] **Step 10: Run parser and integration tests**

Run:

```powershell
python -m pytest tests/test_cq_parser.py -q
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

Expected: parser tests PASS. Integration tests PASS when Fuseki accepts anonymous writes, skip with credential message if Graph Store requires auth, or skip with availability message if Fuseki is not running.

- [ ] **Step 11: Run compile check**

Run:

```powershell
python -m compileall mvp\core\cq.py tests\test_cq_integration.py
```

Expected: both files compile successfully.

- [ ] **Step 12: Checkpoint**

If execution is in a git repository, use this Lore commit:

```bash
git add mvp/core/cq.py mvp/core/qa.py tests/test_qa.py tests/test_cq_integration.py
git commit -m "Validate measurement CQs against Fuseki evidence

Add a CQ runner that recreates the measurement judgement fixture, executes declared SPARQL, and checks QA evidence against the same field contract. Extend the existing measurement evidence template to cover Pass questions without allowing free-form QA.

Constraint: First executable CQ path must use real Fuseki/SPARQL
Rejected: Validate only against in-memory repository | would miss named graph query drift
Confidence: medium
Scope-risk: moderate
Tested: python -m pytest tests/test_cq_parser.py -q
Tested: python -m pytest tests/test_qa.py -q
Tested: python -m pytest tests/test_cq_integration.py -q
Not-tested: Fuseki deployments that require write credentials unless configured locally"
```

If execution is in this non-git workspace, record changed files and verification output.

---

### Task 5: CQ Operating Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README CQ section**

Append this section to `README.md`:

````markdown
## CQ 验收

CQ（competency questions，胜任力问题）用于把本体需求、SPARQL 查询、推理 evidence 和 QA 解释绑定成可执行验收资产。

第一批 CQ 位于：

```text
docs/cq/measurement-judgement-cqs.md
```

新增 CQ 时必须包含：

- `Business question`
- `Intent`
- `Covers`
- `Demo data`
- `Expected`
- 一个 `sparql` 代码块
- `Evidence fields`
- `Linked QA example`
- `Acceptance`

离线解析测试：

```powershell
python -m pytest tests/test_cq_parser.py -q
```

真实 Fuseki/SPARQL 集成测试：

```powershell
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

如果 Fuseki 未启动，集成测试会跳过并提示先运行 `docker compose up -d`。如果 Fuseki 写入需要认证，请在 `.env` 或环境变量中设置 `FUSEKI_USER` 和 `FUSEKI_PASSWORD`。
````

- [ ] **Step 2: Run documentation-oriented checks**

Run:

```powershell
Select-String -Path README.md -Pattern "CQ 验收","docs/cq/measurement-judgement-cqs.md","tests/test_cq_integration.py"
```

Expected: all three patterns are found.

- [ ] **Step 3: Run full CQ verification**

Run:

```powershell
python -m pytest tests/test_cq_parser.py -q
python -m compileall mvp tests
```

Expected: parser tests pass; compileall succeeds.

Then, when Fuseki is available:

```powershell
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

Expected: integration tests pass or skip only for explicit Fuseki availability/auth reasons.

- [ ] **Step 4: Checkpoint**

If execution is in a git repository, use this Lore commit:

```bash
git add README.md
git commit -m "Document executable CQ validation workflow

Explain where measurement CQ definitions live and how to run parser plus Fuseki-backed CQ validation.

Constraint: Business reviewers need a Markdown entry point
Confidence: high
Scope-risk: narrow
Tested: Select-String README.md CQ patterns
Tested: python -m pytest tests/test_cq_parser.py -q
Tested: python -m compileall mvp tests
Not-tested: Full Fuseki CQ integration unless service is available"
```

If execution is in this non-git workspace, record README changes and verification output.

---

## Final Verification

Run these commands after all tasks:

```powershell
python -m pytest tests/test_cq_parser.py tests/test_graph.py tests/test_qa.py -q
python -m compileall mvp tests
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

Expected:

- Parser tests pass.
- Graph tests pass with any pre-existing Fuseki placeholder skip unchanged.
- QA tests pass, including Pass judgement evidence fallback.
- Compileall succeeds.
- CQ integration passes when Fuseki is running and write access is configured.
- CQ integration skips only when Fuseki is unavailable or requires missing credentials.

## Self-Review Notes

- Spec coverage: CQ Markdown, parser, runner, fixture initialization, Fuseki execution, QA evidence matching, Pass judgement support, README instructions, and skip behavior are mapped to Tasks 1-5.
- No unsupported CQ scope is included: specification-change CQ and RDF CQ synchronization remain future work.
- Type consistency: `CompetencyQuestion.expected` stores strings; numeric comparison is handled in `validate_expected()` and `validate_evidence_fields()`.
- Current workspace is not git-backed, so commit steps include non-git checkpoint guidance.
