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
    assert "GRAPH <{{result_graph_iri}}>" in questions[0].sparql
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


def test_render_sparql_uses_supplied_ontology_named_graphs():
    question = cq.parse_cq_markdown(DOC_PATH)[0]

    rendered = cq.render_sparql(question, "custom-ontology")

    assert "https://hifar.top/mto/graph/custom-ontology/data" in rendered
    assert "https://hifar.top/mto/graph/custom-ontology/result" in rendered
    assert "https://hifar.top/mto/graph/manufacturing-trial/data" not in rendered
    assert "{{" not in rendered


def test_validate_evidence_accepts_equivalent_utc_datetime_forms():
    question = cq.CompetencyQuestion(
        id="CQ-MJ-001",
        title="datetime normalization",
        metadata={},
        sparql="SELECT * WHERE {}",
        expected={"row_count": "1"},
        evidence_fields=["inferred_at"],
    )

    cq.validate_evidence_fields(
        question,
        {"inferred_at": "2026-04-28T10:36:58.730208+00:00"},
        {"inferred_at": "2026-04-28T10:36:58.730208Z"},
    )


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
