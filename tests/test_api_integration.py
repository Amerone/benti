from __future__ import annotations

import asyncio
import time
from pathlib import Path
from urllib.parse import quote

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from rdflib import URIRef

from mvp.core import graph
from mvp.core import owlready_reasoner
from mvp.core.sparql_client import FusekiClient, FusekiError


class UnavailableProvider:
    name = "local_fallback"
    default_model = "none"

    def available(self) -> bool:
        return False

    def chat(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> str | None:
        return None


@pytest.fixture
def repository() -> graph.BusinessGraphRepository:
    repo = graph.BusinessGraphRepository()
    graph.load_ontologies(repository=repo, reload=True)
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    graph.register_parameter(
        "manufacturing-trial",
        "temperature",
        name="注塑温度",
        unit="C",
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
        value=192.1,
        repository=repo,
    )
    return repo


@pytest.fixture
def app(repository: graph.BusinessGraphRepository):
    from mvp.api.main import create_app

    return create_app(repository=repository, llm_provider=UnavailableProvider())


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_health_returns_envelope_and_trace(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["trace_id"]
    assert payload["started_at"]
    assert isinstance(payload["elapsed_ms"], int)
    assert len(payload["trace"]) >= 3
    assert payload["trace"][0]["step"] == "request.begin"
    assert {step["step"] for step in payload["trace"]} >= {
        "probe_fuseki",
        "probe_owlready",
        "probe_java_or_pellet",
        "probe_llm",
    }


@pytest.mark.asyncio
async def test_api_flow_covers_parameters_measurements_specs_impacts_and_qa(
    client: AsyncClient,
) -> None:
    parameters_response = await client.post(
        "/api/v1/parameters",
        json={
            "ontology_id": "manufacturing-trial",
            "code": "vibration_frequency",
            "name": "振动频率",
            "unit": "Hz",
            "value_type": "number",
            "participates_in_inference": True,
        },
    )
    assert parameters_response.status_code == 200
    assert parameters_response.json()["data"] == {"code": "vibration_frequency", "created": True}

    parameters_list = await client.get("/api/v1/parameters", params={"ontology_id": "manufacturing-trial"})
    assert parameters_list.status_code == 200
    assert {item["code"] for item in parameters_list.json()["data"]["items"]} >= {
        "temperature",
        "vibration_frequency",
    }

    subjects_response = await client.get("/api/v1/ontologies/manufacturing-trial/subjects")
    assert subjects_response.status_code == 200
    assert subjects_response.json()["data"]["ontology_id"] == "manufacturing-trial"
    assert isinstance(subjects_response.json()["data"]["classes"], list)

    activate_response = await client.post("/api/v1/ontologies/manufacturing-trial/activate")
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["active_ontology_id"] == "manufacturing-trial"

    create_spec = await client.post(
        "/api/v1/specifications",
        json={
            "ontology_id": "manufacturing-trial",
            "parameter": "vibration_frequency",
            "lower": 10,
            "upper": 50,
            "reason": "新增规格",
            "effective_from": "2026-04-23T01:00:00Z",
        },
    )
    assert create_spec.status_code == 200
    assert create_spec.json()["data"]["created"] is True
    assert create_spec.json()["data"]["spec_version"] == "Spec_v1"

    measurement_response = await client.post(
        "/api/v1/measurements",
        json={
            "ontology_id": "manufacturing-trial",
            "measurement_id": "M010",
            "batch": "B01",
            "parameter": "vibration_frequency",
            "value": 21.5,
        },
    )
    assert measurement_response.status_code == 200
    measurement_payload = measurement_response.json()["data"]
    assert measurement_payload["status"] == "Pass"
    assert measurement_payload["explanation"]["branch"] == "within_limits"
    assert measurement_payload["explanation"]["abox"] == {
        "measurement_id": "M010",
        "batch": "B01",
        "parameter": "vibration_frequency",
        "value": 21.5,
    }
    assert measurement_payload["explanation"]["matched_rule"] == "Rule_Pass"

    measurements_list = await client.get(
        "/api/v1/measurements",
        params={"ontology_id": "manufacturing-trial", "parameter": "vibration_frequency"},
    )
    assert measurements_list.status_code == 200
    assert measurements_list.json()["data"]["total"] == 1
    assert measurements_list.json()["data"]["items"][0]["measurement_id"] == "M010"

    change_response = await client.post(
        "/api/v1/specifications/change",
        json={
            "ontology_id": "manufacturing-trial",
            "parameter": "temperature",
            "lower": 180,
            "upper": 190,
            "reason": "规格收紧",
            "effective_from": "2026-04-23T02:00:00Z",
        },
    )
    assert change_response.status_code == 200
    changed = change_response.json()["data"]["changed"]
    assert changed
    assert changed[0]["measurement_id"] == "M001"

    impacts_response = await client.get(
        "/api/v1/impacts/latest",
        params={"ontology_id": "manufacturing-trial", "parameter": "temperature"},
    )
    assert impacts_response.status_code == 200
    assert impacts_response.json()["data"]["new_spec"] == "Spec_v2"
    assert impacts_response.json()["data"]["changed"][0]["measurement_id"] == "M001"

    specifications_response = await client.get(
        "/api/v1/specifications",
        params={"ontology_id": "manufacturing-trial", "parameter": "temperature"},
    )
    assert specifications_response.status_code == 200
    specifications = specifications_response.json()["data"]["items"]
    assert [
        {
            "spec_version": item["spec_version"],
            "lower": item["lower"],
            "upper": item["upper"],
            "reason": item["reason"],
            "supersedes": item["supersedes"],
        }
        for item in specifications
    ] == [
        {
            "spec_version": "Spec_v1",
            "lower": 180.0,
            "upper": 195.0,
            "reason": "初始规格",
            "supersedes": None,
        },
        {
            "spec_version": "Spec_v2",
            "lower": 180.0,
            "upper": 190.0,
            "reason": "规格收紧",
            "supersedes": "Spec_v1",
        },
    ]

    qa_response = await client.post(
        "/api/v1/qa",
        json={"ontology_id": "manufacturing-trial", "question": "M001 为什么 Fail？"},
    )
    assert qa_response.status_code == 200
    assert qa_response.json()["data"]["source"] == "local_fallback"
    assert qa_response.json()["data"]["intent"] == "why_fail"


@pytest.mark.asyncio
async def test_subjects_support_query_and_limit_contract(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/ontologies/manufacturing-trial/subjects",
        params={"q": "Batch", "limit": 1},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert len(payload["classes"]) <= 1
    assert all("batch" in str(item).lower() for item in payload["classes"])


@pytest.mark.asyncio
async def test_subjects_preserve_chinese_labels_when_remote_turtle_has_no_charset() -> None:
    """远端 Fuseki 回读 ontology Turtle 时，中文 label 不能因默认西文编码而乱码。"""

    ttl_bytes = Path("mvp/ontology/manufacturing-trial.ttl").read_bytes()

    class CharsetlessTurtleResponse:
        status_code = 200
        headers = {"content-type": "text/turtle"}
        content = ttl_bytes
        encoding = "ISO-8859-1"
        apparent_encoding = "utf-8"

        @property
        def text(self) -> str:
            return self.content.decode(self.encoding, errors="replace")

        def json(self):
            raise ValueError("no json")

    class OneShotSession:
        def request(self, method, url, **kwargs):
            return CharsetlessTurtleResponse()

    from mvp.api.main import create_app

    app = create_app(
        repository=graph.BusinessGraphRepository(client=FusekiClient(session=OneShotSession())),
        llm_provider=UnavailableProvider(),
    )

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as async_client:
        response = await async_client.get("/api/v1/ontologies/manufacturing-trial/subjects")

    assert response.status_code == 200
    class_labels = [item["label"] for item in response.json()["data"]["classes"] if "label" in item]
    assert "判定结果" in class_labels
    assert "参数" in class_labels


@pytest.mark.asyncio
async def test_measurements_compare_mode_writes_parallel_pellet_swrl_result(
    client: AsyncClient,
    repository: graph.BusinessGraphRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mvp.api.main.owlready_reasoner.load_and_reason",
        lambda *args, **kwargs: {
            "ontology_id": "manufacturing-trial",
            "loaded_by": "owlready2",
            "reasoner": "pellet",
            "classes": [],
            "individuals": [],
            "object_properties": [],
            "data_properties": [],
            "pellet_status": "success",
            "pellet_ms": 12,
            "pellet_error": None,
            "retry_after_ms": None,
            "cache_key": "test",
            "cache_hit": False,
            "swrl_enabled": True,
            "swrl_status": "success",
            "swrl_error": None,
        },
    )

    response = await client.post(
        "/api/v1/measurements",
        json={
            "ontology_id": "manufacturing-trial",
            "measurement_id": "M777",
            "batch": "B01",
            "parameter": "temperature",
            "value": 197.2,
            "enable_swrl": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["reasoner"] == "python-deterministic"
    assert payload["compare_result"]["reasoner"] == "pellet-swrl"
    assert payload["compare_result"]["swrl_status"] == "success"

    result_graph = repository.graph("manufacturing-trial", "result")
    measurement_node = URIRef(f"{graph.INDIVIDUAL_BASE}/manufacturing-trial/measurement/{quote('M777', safe='')}")
    result_nodes = list(result_graph.subjects(graph.MTO.forMeasurement, measurement_node))
    reasoners = sorted(str(obj) for node in result_nodes for obj in result_graph.objects(node, graph.MTO.reasoner))

    assert reasoners == ["pellet-swrl", "python-deterministic"]


@pytest.mark.asyncio
async def test_measurements_compare_mode_sends_multiple_inference_parameters_to_pellet(
    client: AsyncClient,
    repository: graph.BusinessGraphRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    graph.register_parameter(
        "manufacturing-trial",
        "vibration_frequency",
        unit="Hz",
        participates_in_inference=True,
        repository=repository,
    )
    graph.register_parameter(
        "manufacturing-trial",
        "ambient_humidity",
        unit="%",
        participates_in_inference=False,
        repository=repository,
    )
    graph.create_specification(
        "manufacturing-trial",
        "vibration_frequency",
        lower=10,
        upper=50,
        reason="新增规格",
        effective_from="2026-04-23T01:00:00Z",
        repository=repository,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M-vibration",
        batch_id="B01",
        parameter_code="vibration_frequency",
        value=21.5,
        repository=repository,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M-humidity",
        batch_id="B01",
        parameter_code="ambient_humidity",
        value=55,
        repository=repository,
    )

    def fake_load_and_reason(_ontology_id: str, turtle_text: str, **_kwargs):
        captured["turtle_text"] = turtle_text
        return {
            "ontology_id": "manufacturing-trial",
            "loaded_by": "owlready2",
            "reasoner": "pellet",
            "classes": [],
            "individuals": [],
            "object_properties": [],
            "data_properties": [],
            "pellet_status": "success",
            "pellet_ms": 12,
            "pellet_error": None,
            "retry_after_ms": None,
            "cache_key": "test",
            "cache_hit": False,
            "swrl_enabled": True,
            "swrl_status": "success",
            "swrl_error": None,
        }

    monkeypatch.setattr("mvp.api.main.owlready_reasoner.load_and_reason", fake_load_and_reason)

    response = await client.post(
        "/api/v1/measurements",
        json={
            "ontology_id": "manufacturing-trial",
            "measurement_id": "M-multi-pellet",
            "batch": "B01",
            "parameter": "temperature",
            "value": 188,
            "enable_swrl": True,
        },
    )

    assert response.status_code == 200
    assert "temperature" in captured["turtle_text"]
    assert "vibration_frequency" in captured["turtle_text"]
    assert "M-vibration" in captured["turtle_text"]
    assert "ambient_humidity" not in captured["turtle_text"]
    assert "M-humidity" not in captured["turtle_text"]


@pytest.mark.asyncio
async def test_errors_are_wrapped_by_unified_exception_handlers(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    not_found = await client.get("/api/v1/nonexistent")
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "HTTP_404"
    assert not_found.json()["trace"][0]["step"] == "request.begin"

    invalid = await client.post("/api/v1/measurements", json={"foo": "bar"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "REQUEST_VALIDATION"
    assert any(step["step"] == "request_validation" for step in invalid.json()["trace"])

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("mvp.api.main.graph.create_and_infer", boom)
    internal = await client.post(
        "/api/v1/measurements",
        json={
            "ontology_id": "manufacturing-trial",
            "measurement_id": "M999",
            "batch": "B01",
            "parameter": "temperature",
            "value": 188.0,
        },
    )
    assert internal.status_code == 500
    assert internal.json()["error"]["code"] == "INTERNAL_ERROR"
    assert any(step["step"] == "unhandled" for step in internal.json()["trace"])


@pytest.mark.asyncio
async def test_fuseki_errors_are_wrapped_with_actionable_api_message(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fuseki_unauthorized(*args, **kwargs):
        raise FusekiError(
            "FUSEKI_HTTP_401",
            "Fuseki HTTP 401",
            status_code=401,
            endpoint="http://localhost:3030/manufacturing-trial/data?graph=...",
            response_text="Unauthorized",
        )

    monkeypatch.setattr("mvp.api.main.graph.create_and_infer", fuseki_unauthorized)

    response = await client.post(
        "/api/v1/measurements",
        json={
            "ontology_id": "manufacturing-trial",
            "measurement_id": "M401",
            "batch": "B01",
            "parameter": "temperature",
            "value": 188.0,
            "enable_swrl": True,
        },
    )

    assert response.status_code == 502
    payload = response.json()
    assert payload["error"]["code"] == "FUSEKI_HTTP_401"
    assert "FUSEKI_USER" in payload["error"]["message"]
    assert payload["error"]["detail"]["status_code"] == 401
    assert "localhost:3030" in payload["error"]["detail"]["endpoint"]
    assert any(step["step"] == "fuseki_error" for step in payload["trace"])


@pytest.mark.asyncio
async def test_reason_endpoint_is_concurrency_safe_via_reasoner_cache(
    app,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owlready_reasoner.clear_reasoner_cache()
    ttl_text = Path("mvp/ontology/manufacturing-trial.ttl").read_text(encoding="utf-8")
    calls = {"count": 0}

    def fake_sync_reasoner_pellet(*args, **kwargs) -> None:
        calls["count"] += 1
        time.sleep(0.05)

    monkeypatch.setattr("mvp.api.main.graph.construct_ontology_turtle", lambda *args, **kwargs: ttl_text)
    monkeypatch.setattr("mvp.core.owlready_reasoner.sync_reasoner_pellet", fake_sync_reasoner_pellet)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as async_client:
        responses = await asyncio.gather(
            *[
                async_client.post("/api/v1/ontologies/manufacturing-trial/reason", json={"force": False})
                for _ in range(5)
            ]
        )

    assert all(response.status_code == 200 for response in responses)
    assert {response.json()["data"]["pellet_status"] for response in responses} == {"success"}
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_reload_only_overwrites_ontology_graph_without_breaking_other_graphs(
    client: AsyncClient,
    repository: graph.BusinessGraphRepository,
) -> None:
    data_before = repository.count_graph("manufacturing-trial", "data")
    result_before = repository.count_graph("manufacturing-trial", "result")
    spec_before = repository.count_graph("manufacturing-trial", "spec")

    response = await client.post("/api/v1/ontologies/load", json={"reload": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["data"]["reload"] is True
    assert payload["data"]["failed"] == []
    assert repository.count_graph("manufacturing-trial", "data") == data_before
    assert repository.count_graph("manufacturing-trial", "result") == result_before
    assert repository.count_graph("manufacturing-trial", "spec") == spec_before


@pytest.mark.asyncio
async def test_qa_requires_explicit_ontology_id(client: AsyncClient) -> None:
    response = await client.post("/api/v1/qa", json={"question": "M001 为什么 Fail？"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ONTOLOGY_ID_REQUIRED"


@pytest.mark.asyncio
async def test_api_qa_supports_why_pass_judgement(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/qa",
        json={"ontology_id": "manufacturing-trial", "question": "M001 为什么 Pass？"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "why_judgement"
    assert data["evidence"]["measurement_id"] == "M001"
    assert data["evidence"]["status"] == "Pass"
    assert "Pass" in data["answer"]
