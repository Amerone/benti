from __future__ import annotations

from rdflib import URIRef
from rdflib.namespace import RDF

from mvp.core import commission_graph
from mvp.core.cq_workflow import (
    DEFAULT_COMMISSION_SHACL_PATH,
    CQWorkflowError,
    validate_draft_quality_gate,
    validate_shacl_graph,
)
from mvp.core.graph import BusinessGraphRepository


def _reviewable_payload(*, candidate_cqs: list[dict], draft_sparql_tests: list[str]) -> dict:
    return {
        "draft_turtle": """
@prefix cto: <https://hifar.top/cto#> .

<https://hifar.top/cto/individual/order/CO-900> a cto:CommissionOrder ;
    cto:orderNo "CO-900" ;
    cto:hasTestProject <https://hifar.top/cto/individual/project/P-900> .

<https://hifar.top/cto/individual/project/P-900> a cto:TestProject ;
    cto:localId "P-900" ;
    cto:decomposesToTask <https://hifar.top/cto/individual/task/T-900> .

<https://hifar.top/cto/individual/task/T-900> a cto:TestTask ;
    cto:localId "T-900" ;
    cto:taskStatus "Draft" .
""",
        "candidate_cqs": candidate_cqs,
        "candidate_rules": [],
        "draft_sparql_tests": draft_sparql_tests,
    }


def test_commission_demo_conforms_to_shacl_shapes():
    repo = BusinessGraphRepository()
    service = commission_graph.CommissionGraphService(repository=repo)
    service.reset_demo()
    service.upgrade_standard_to_demo_v2()

    report = validate_shacl_graph(
        repo.graph(commission_graph.ONTOLOGY_ID, "data"),
        DEFAULT_COMMISSION_SHACL_PATH,
    )

    assert report.category == "shacl"
    assert report.passed is True
    assert report.message == "SHACL validation conforms"
    assert report.detail["conforms"] is True


def test_commission_shacl_shapes_reject_project_without_task():
    repo = BusinessGraphRepository()
    service = commission_graph.CommissionGraphService(repository=repo)
    service.reset_demo()
    data_graph = repo.graph(commission_graph.ONTOLOGY_ID, "data")
    broken_project = URIRef("https://hifar.top/cto/individual/project/BROKEN")
    data_graph.add((broken_project, RDF.type, commission_graph.CTO.TestProject))

    report = validate_shacl_graph(data_graph, DEFAULT_COMMISSION_SHACL_PATH)

    assert report.passed is False
    assert report.category == "shacl"
    assert "Less than 1 values" in str(report.detail["report_text"])


def test_draft_quality_gate_accepts_reviewable_payload():
    payload = _reviewable_payload(
        candidate_cqs=[{"id": "CQ-CT-900", "title": "Draft CQ"}],
        draft_sparql_tests=["CQ-CT-900"],
    )

    report = validate_draft_quality_gate(payload)

    assert report["passed"] is True
    assert [item["category"] for item in report["checks"]] == ["metadata", "turtle", "shacl"]


def test_draft_quality_gate_blocks_invalid_turtle():
    payload = {
        "draft_turtle": "not turtle",
        "candidate_cqs": [{"id": "CQ-CT-900", "title": "Draft CQ"}],
        "candidate_rules": [],
        "draft_sparql_tests": ["CQ-CT-900"],
    }

    try:
        validate_draft_quality_gate(payload)
    except CQWorkflowError as exc:
        assert "draft Turtle is invalid" in str(exc)
    else:
        raise AssertionError("invalid draft Turtle should block the gate")


def test_draft_quality_gate_requires_sparql_tests_to_reference_candidate_cqs():
    payload = _reviewable_payload(
        candidate_cqs=[{"id": "CQ-CT-901", "title": "Draft CQ"}],
        draft_sparql_tests=["CQ-CT-MISSING"],
    )

    try:
        validate_draft_quality_gate(payload)
    except CQWorkflowError as exc:
        assert "draft SPARQL test references unknown candidate CQ: CQ-CT-MISSING" in str(exc)
    else:
        raise AssertionError("untraceable SPARQL test should block the gate")


def test_draft_quality_gate_rejects_duplicate_candidate_cq_ids():
    payload = _reviewable_payload(
        candidate_cqs=[
            {"id": "CQ-CT-902", "title": "First"},
            {"id": "CQ-CT-902", "title": "Duplicate"},
        ],
        draft_sparql_tests=["CQ-CT-902"],
    )

    try:
        validate_draft_quality_gate(payload)
    except CQWorkflowError as exc:
        assert "duplicate candidate CQ id: CQ-CT-902" in str(exc)
    else:
        raise AssertionError("duplicate candidate CQ ids should block the gate")


def test_draft_quality_gate_rejects_duplicate_sparql_test_ids():
    payload = _reviewable_payload(
        candidate_cqs=[{"id": "CQ-CT-903", "title": "Draft CQ"}],
        draft_sparql_tests=["CQ-CT-903", "CQ-CT-903"],
    )

    try:
        validate_draft_quality_gate(payload)
    except CQWorkflowError as exc:
        assert "duplicate draft SPARQL test id: CQ-CT-903" in str(exc)
    else:
        raise AssertionError("duplicate SPARQL test ids should block the gate")


def test_draft_quality_gate_requires_candidate_cq_review_text():
    payload = _reviewable_payload(
        candidate_cqs=[{"id": "CQ-CT-904"}],
        draft_sparql_tests=["CQ-CT-904"],
    )

    try:
        validate_draft_quality_gate(payload)
    except CQWorkflowError as exc:
        assert "candidate_cqs[0] must include question or title" in str(exc)
    else:
        raise AssertionError("candidate CQ without review text should block the gate")
