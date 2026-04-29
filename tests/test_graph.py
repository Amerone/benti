from __future__ import annotations

import socket
import re

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD

from mvp.core import graph


class FakeFusekiClient:
    """用于锁定 graph.py 与 Fuseki named graph 同步契约的假客户端。"""

    def __init__(self) -> None:
        self.graphs: dict[str, str] = {}

    def upload_graph(self, graph_iri: str, turtle_text: str) -> None:
        self.graphs[graph_iri] = turtle_text

    def construct(self, sparql: str) -> str:
        match = re.search(r"GRAPH\s+<([^>]+)>", sparql)
        if not match:
            raise AssertionError(f"unexpected sparql: {sparql}")
        return self.graphs.get(match.group(1), "")


def test_graph_iri_returns_four_named_graphs() -> None:
    assert graph.graph_iri("manufacturing-trial") == "https://hifar.top/mto/graph/manufacturing-trial"
    assert graph.graph_iri("manufacturing-trial", "data").endswith("/manufacturing-trial/data")
    assert graph.graph_iri("manufacturing-trial", "result").endswith("/manufacturing-trial/result")
    assert graph.graph_iri("manufacturing-trial", "spec").endswith("/manufacturing-trial/spec")

    with pytest.raises(ValueError, match="kind"):
        graph.graph_iri("manufacturing-trial", "bad")


def test_specification_idempotency_and_supersedes_chain() -> None:
    repo = graph.BusinessGraphRepository()

    first = graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    same = graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    changed = graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=190,
        reason="上限收紧",
        effective_from="2026-04-23T01:00:00Z",
        repository=repo,
    )

    assert first["spec_version"] == "Spec_v1"
    assert same["created"] is False
    assert same["spec_version"] == "Spec_v1"
    assert changed["spec_version"] == "Spec_v2"
    assert changed["supersedes"] == "Spec_v1"
    assert graph.list_specifications("manufacturing-trial", "temperature", repository=repo)["items"][-1][
        "supersedes"
    ] == "Spec_v1"


def test_specification_supersedes_handles_parameter_codes_with_underscores() -> None:
    repo = graph.BusinessGraphRepository()

    graph.create_specification(
        "manufacturing-trial",
        "cq_temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_specification(
        "manufacturing-trial",
        "cq_temperature",
        lower=180,
        upper=200,
        reason="上限放宽",
        effective_from="2026-04-23T01:00:00Z",
        repository=repo,
    )

    specifications = graph.list_specifications("manufacturing-trial", "cq_temperature", repository=repo)["items"]

    assert specifications[-1]["spec_version"] == "Spec_v2"
    assert specifications[-1]["supersedes"] == "Spec_v1"


def test_create_and_infer_no_spec_records_measurement_without_result() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter("manufacturing-trial", "vibration_frequency", unit="Hz", repository=repo)

    result = graph.create_and_infer(
        "manufacturing-trial",
        "M201",
        batch_id="B01",
        parameter_code="vibration_frequency",
        value=12.5,
        repository=repo,
    )

    assert result["status"] == "not_inferred"
    assert result["reason"] == "parameter has no specification"
    assert graph.list_measurements("manufacturing-trial", repository=repo)["items"][0]["measurement_id"] == "M201"
    assert repo.count_graph("manufacturing-trial", "result") == 0


def test_trial_batch_measurement_lists_are_filterable() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", label="注塑工艺验证", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", label="低温", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B02", label="中温", repository=repo)
    graph.create_measurement(
        "manufacturing-trial",
        "M001",
        batch_id="B01",
        parameter_code="temperature",
        value=179.5,
        repository=repo,
    )

    assert graph.list_trials("manufacturing-trial", repository=repo)["items"][0]["trial_id"] == "T001"
    assert [item["batch_id"] for item in graph.list_batches("manufacturing-trial", "T001", repository=repo)["items"]] == [
        "B01",
        "B02",
    ]
    assert graph.list_measurements("manufacturing-trial", "temperature", repository=repo)["total"] == 1


def test_fuseki_integration_placeholder_skips_when_server_is_down() -> None:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        if sock.connect_ex(("127.0.0.1", 3030)) != 0:
            pytest.skip("Fuseki 未启动，跳过图谱集成测试")


def test_business_graphs_are_persisted_to_and_rehydrated_from_fuseki_client() -> None:
    client = FakeFusekiClient()
    repo = graph.BusinessGraphRepository(client=client)

    graph.load_ontologies(repository=repo, reload=True)
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter(
        "manufacturing-trial",
        "temperature",
        name="注塑温度",
        unit="°C",
        repository=repo,
    )
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_and_infer(
        "manufacturing-trial",
        "M001",
        batch_id="B01",
        parameter_code="temperature",
        value=197.2,
        repository=repo,
    )

    assert graph.graph_iri("manufacturing-trial") in client.graphs
    assert graph.graph_iri("manufacturing-trial", "data") in client.graphs
    assert graph.graph_iri("manufacturing-trial", "spec") in client.graphs
    assert graph.graph_iri("manufacturing-trial", "result") in client.graphs

    rehydrated = graph.BusinessGraphRepository(client=client)
    measurements = graph.list_measurements("manufacturing-trial", repository=rehydrated)["items"]

    assert measurements[0]["measurement_id"] == "M001"
    assert measurements[0]["status"] == "Fail_High"
    assert measurements[0]["reasoner"] == "python-deterministic"


def test_construct_reasoning_turtle_includes_multiple_inference_parameters() -> None:
    repo = graph.BusinessGraphRepository()
    graph.load_ontologies(repository=repo, reload=True)
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter(
        "manufacturing-trial",
        "temperature",
        unit="C",
        participates_in_inference=True,
        repository=repo,
    )
    graph.register_parameter(
        "manufacturing-trial",
        "vibration_frequency",
        unit="Hz",
        participates_in_inference=True,
        repository=repo,
    )
    graph.register_parameter(
        "manufacturing-trial",
        "ambient_humidity",
        unit="%",
        participates_in_inference=False,
        repository=repo,
    )
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="温度规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_specification(
        "manufacturing-trial",
        "vibration_frequency",
        lower=10,
        upper=50,
        reason="振动规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M-temperature",
        batch_id="B01",
        parameter_code="temperature",
        value=188,
        repository=repo,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M-vibration",
        batch_id="B01",
        parameter_code="vibration_frequency",
        value=21.5,
        repository=repo,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M-humidity",
        batch_id="B01",
        parameter_code="ambient_humidity",
        value=55,
        repository=repo,
    )

    turtle_text = graph.construct_reasoning_turtle("manufacturing-trial", repository=repo)

    assert "temperature" in turtle_text
    assert "vibration_frequency" in turtle_text
    assert "M-temperature" in turtle_text
    assert "M-vibration" in turtle_text
    assert "temperature_Spec_v1" in turtle_text
    assert "vibration_frequency_Spec_v1" in turtle_text
    assert "ambient_humidity" not in turtle_text
    assert "M-humidity" not in turtle_text


def test_business_graph_literals_match_ontology_datatype_ranges() -> None:
    repo = graph.BusinessGraphRepository()
    graph.load_ontologies(repository=repo, reload=True)
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="C", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="temperature spec",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_and_infer(
        "manufacturing-trial",
        "M-temperature",
        batch_id="B01",
        parameter_code="temperature",
        value=188,
        repository=repo,
    )

    data_graph = repo.graph("manufacturing-trial", "data")
    spec_graph = repo.graph("manufacturing-trial", "spec")
    result_graph = repo.graph("manufacturing-trial", "result")
    parameter_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/parameter/temperature")
    measurement_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/measurement/M-temperature")
    spec_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/specification/temperature_Spec_v1")
    result_node = next(result_graph.subjects(graph.MTO.forMeasurement, measurement_node))

    assert next(data_graph.objects(parameter_node, graph.MTO.createdAt)).datatype == XSD.dateTime
    assert next(data_graph.objects(measurement_node, graph.MTO.measuredAt)).datatype == XSD.dateTime
    assert next(data_graph.objects(measurement_node, graph.MTO.measuredValue)).datatype == XSD.decimal
    assert next(spec_graph.objects(spec_node, graph.MTO.effectiveFrom)).datatype == XSD.dateTime
    assert next(spec_graph.objects(spec_node, graph.MTO.lowerLimit)).datatype == XSD.decimal
    assert next(spec_graph.objects(spec_node, graph.MTO.upperLimit)).datatype == XSD.decimal
    assert next(result_graph.objects(result_node, graph.MTO.inferredAt)).datatype == XSD.dateTime
    assert next(result_graph.objects(result_node, graph.MTO.deviation)).datatype == XSD.decimal
    assert next(result_graph.objects(result_node, graph.MTO.evidenceValue)).datatype == XSD.decimal


def test_constructed_reasoning_turtle_is_pellet_consistent() -> None:
    from mvp.core import owlready_reasoner

    runtime = owlready_reasoner.describe_java_runtime()
    if runtime.get("java_exe") is None:
        pytest.skip("Java runtime is required for Pellet consistency verification")

    repo = graph.BusinessGraphRepository()
    graph.load_ontologies(repository=repo, reload=True)
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="C", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="temperature spec",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_and_infer(
        "manufacturing-trial",
        "M-temperature",
        batch_id="B01",
        parameter_code="temperature",
        value=188,
        repository=repo,
    )

    turtle_text = graph.construct_reasoning_turtle("manufacturing-trial", repository=repo)
    owlready_reasoner.clear_reasoner_cache()
    result = owlready_reasoner.load_and_reason(
        "manufacturing-trial",
        turtle_text,
        run_pellet=True,
        force=True,
    )

    assert result["pellet_status"] == "success"
    assert result["pellet_error"] is None


def test_construct_reasoning_turtle_repairs_legacy_literal_datatypes() -> None:
    repo = graph.BusinessGraphRepository()
    graph.load_ontologies(repository=repo, reload=True)
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="C", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="temperature spec",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M-legacy",
        batch_id="B01",
        parameter_code="temperature",
        value=188,
        measured_at="2026-04-23T01:00:00Z",
        repository=repo,
    )

    data_graph = repo.graph("manufacturing-trial", "data")
    spec_graph = repo.graph("manufacturing-trial", "spec")
    parameter_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/parameter/temperature")
    measurement_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/measurement/M-legacy")
    spec_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/specification/temperature_Spec_v1")
    data_graph.set((parameter_node, graph.MTO.createdAt, Literal("2026-04-23T00:00:00Z")))
    data_graph.set((measurement_node, graph.MTO.measuredAt, Literal("2026-04-23T01:00:00Z")))
    data_graph.set((measurement_node, graph.MTO.measuredValue, Literal(188.0, datatype=XSD.double)))
    spec_graph.set((spec_node, graph.MTO.effectiveFrom, Literal("2026-04-23T00:00:00Z")))
    spec_graph.set((spec_node, graph.MTO.lowerLimit, Literal(180.0, datatype=XSD.double)))
    spec_graph.set((spec_node, graph.MTO.upperLimit, Literal(195.0, datatype=XSD.double)))

    turtle_text = graph.construct_reasoning_turtle("manufacturing-trial", repository=repo)
    reasoning_graph = Graph()
    reasoning_graph.parse(data=turtle_text, format="turtle")

    assert next(reasoning_graph.objects(parameter_node, graph.MTO.createdAt)).datatype == XSD.dateTime
    assert next(reasoning_graph.objects(measurement_node, graph.MTO.measuredAt)).datatype == XSD.dateTime
    assert next(reasoning_graph.objects(measurement_node, graph.MTO.measuredValue)).datatype == XSD.decimal
    assert next(reasoning_graph.objects(spec_node, graph.MTO.effectiveFrom)).datatype == XSD.dateTime
    assert next(reasoning_graph.objects(spec_node, graph.MTO.lowerLimit)).datatype == XSD.decimal
    assert next(reasoning_graph.objects(spec_node, graph.MTO.upperLimit)).datatype == XSD.decimal


def test_compare_result_can_be_written_without_replacing_latest_python_result() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="°C", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_and_infer(
        "manufacturing-trial",
        "M009",
        batch_id="B01",
        parameter_code="temperature",
        value=197.2,
        repository=repo,
    )

    compare = graph.save_inference_result(
        "manufacturing-trial",
        "M009",
        status="Fail_High",
        rule="Rule_Fail_High",
        spec_version="Spec_v1",
        deviation=2.2,
        reasoner="pellet-swrl",
        evidence_value=197.2,
        evidence_lower_limit=180.0,
        evidence_upper_limit=195.0,
        repository=repo,
        update_latest=False,
        link_previous=False,
    )

    latest = repo.latest_result_for_measurement("manufacturing-trial", "M009")
    result_graph = repo.graph("manufacturing-trial", "result")
    measurement_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/measurement/M009")
    result_count = len(list(result_graph.subjects(graph.MTO.forMeasurement, measurement_node)))

    assert compare["reasoner"] == "pellet-swrl"
    assert latest is not None
    assert latest.reasoner == "python-deterministic"
    assert result_count == 2


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
    assert graph.list_specifications("manufacturing-trial", "pressure", repository=repo)["items"][0][
        "spec_version"
    ] == "Spec_v1"


def test_reset_cq_fixture_preserves_shared_parameter_scope_when_other_measurements_use_it() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B03", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="C", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="Business spec",
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
    graph.create_and_infer(
        "manufacturing-trial",
        "M123",
        batch_id="B03",
        parameter_code="temperature",
        value=188.0,
        repository=repo,
    )

    removed = repo.reset_cq_fixture(
        "manufacturing-trial",
        measurement_ids=["M007"],
        parameter_code="temperature",
        spec_versions=["Spec_v1"],
    )

    assert removed["measurements"] == 1
    assert removed["results"] == 1
    assert removed["parameters"] == 0
    assert removed["specifications"] == 0
    assert graph.list_parameters("manufacturing-trial", repository=repo)["items"][0]["code"] == "temperature"
    assert graph.list_specifications("manufacturing-trial", "temperature", repository=repo)["items"][0][
        "spec_version"
    ] == "Spec_v1"
    assert graph.list_measurements("manufacturing-trial", repository=repo)["items"][0]["measurement_id"] == "M123"
