"""Fuseki 客户端的单元与集成测试。

本文件先用轻量 fake session 固定错误处理、认证和默认配置契约，再在本地
Fuseki 可用时执行 Graph Store Protocol 与 SPARQL 端到端读写验证。
"""

from __future__ import annotations

import os
import uuid

import pytest

from mvp.core.sparql_client import FusekiClient, FusekiError


class FakeResponse:
    """模拟 requests.Response 中客户端依赖的最小行为。"""

    def __init__(
        self,
        status_code: int,
        text: str = "",
        payload=None,
        content_type: str = "text/plain",
        *,
        content: bytes | None = None,
        encoding: str | None = None,
        apparent_encoding: str | None = None,
    ):
        self.status_code = status_code
        self._text = text
        self._payload = payload
        self.content = content if content is not None else text.encode("utf-8")
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding
        self.headers = {"content-type": content_type}

    @property
    def text(self) -> str:
        codec = self.encoding or "utf-8"
        if self._text:
            return self._text
        return self.content.decode(codec, errors="replace")

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class RecordingSession:
    """记录 HTTP 调用，便于验证 URL、认证和请求体。"""

    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class FailingSession:
    """模拟底层 HTTP 客户端异常，避免真实 traceback 泄露认证上下文。"""

    def request(self, method, url, **kwargs):
        raise RuntimeError("connection failed with super-secret-password")


def _integration_timeout() -> float:
    return float(os.getenv("FUSEKI_TEST_TIMEOUT", os.getenv("FUSEKI_TIMEOUT", "15")))


def test_default_configuration_builds_fuseki_endpoint_urls(monkeypatch, tmp_path):
    """未显式传参时应使用设计文档约定的 Fuseki 默认配置。"""

    monkeypatch.delenv("FUSEKI_BASE_URL", raising=False)
    monkeypatch.delenv("FUSEKI_DATASET", raising=False)
    monkeypatch.chdir(tmp_path)

    client = FusekiClient(session=RecordingSession(FakeResponse(200)))

    assert client.base_url == "http://localhost:3030"
    assert client.dataset == "manufacturing-trial"
    assert client.query_url == "http://localhost:3030/manufacturing-trial/query"
    assert client.update_url == "http://localhost:3030/manufacturing-trial/update"
    assert client.data_url == "http://localhost:3030/manufacturing-trial/data"


def test_configuration_loads_dotenv_credentials(monkeypatch, tmp_path):
    """后端应读取项目 .env 中的 Fuseki 写入认证配置。"""

    monkeypatch.delenv("FUSEKI_BASE_URL", raising=False)
    monkeypatch.delenv("FUSEKI_DATASET", raising=False)
    monkeypatch.delenv("FUSEKI_USER", raising=False)
    monkeypatch.delenv("FUSEKI_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath(".env").write_text(
        "\n".join(
            [
                "FUSEKI_BASE_URL=http://dotenv-fuseki:3030",
                "FUSEKI_DATASET=dotenv-dataset",
                "FUSEKI_USER=admin",
                "FUSEKI_PASSWORD=dotenv-secret",
            ]
        ),
        encoding="utf-8",
    )
    session = RecordingSession(FakeResponse(200, payload={"boolean": True}, content_type="application/sparql-results+json"))

    client = FusekiClient(session=session)
    assert client.base_url == "http://dotenv-fuseki:3030"
    assert client.dataset == "dotenv-dataset"

    assert client.ask("ASK { ?s ?p ?o }") is True
    assert session.calls[0][2]["auth"] == ("admin", "dotenv-secret")


def test_http_error_masks_password_and_exposes_dataset_not_found_code(monkeypatch):
    """404 数据集错误应成为明确 FusekiError，且不能泄露密码。"""

    monkeypatch.setenv("FUSEKI_USER", "admin")
    monkeypatch.setenv("FUSEKI_PASSWORD", "super-secret-password")
    session = RecordingSession(FakeResponse(404, "Dataset not found: super-secret-password"))
    client = FusekiClient(dataset="missing-dataset", session=session)

    with pytest.raises(FusekiError) as raised:
        client.select("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

    error = raised.value
    assert error.code == "FUSEKI_DATASET_NOT_FOUND"
    assert error.status_code == 404
    assert error.endpoint.endswith("/missing-dataset/query")
    assert "super-secret-password" not in str(error)
    assert session.calls[0][2]["auth"] == ("admin", "super-secret-password")


def test_transport_exception_masks_password_and_suppresses_context(monkeypatch):
    """网络异常字符串与 traceback 都不能把密码带到调用方。"""

    monkeypatch.setenv("FUSEKI_PASSWORD", "super-secret-password")
    client = FusekiClient(user="admin", password="super-secret-password", session=FailingSession())

    with pytest.raises(FusekiError) as raised:
        client.select("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

    error = raised.value
    assert error.code == "FUSEKI_UNAVAILABLE"
    assert "super-secret-password" not in str(error)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_select_and_ask_parse_sparql_json_results():
    """SELECT 返回 bindings，ASK 返回布尔值，调用方无需理解 SPARQL JSON 外壳。"""

    select_session = RecordingSession(
        FakeResponse(
            200,
            payload={"head": {"vars": ["s"]}, "results": {"bindings": [{"s": {"value": "urn:s"}}]}},
            content_type="application/sparql-results+json",
        )
    )
    select_client = FusekiClient(session=select_session)
    assert select_client.select("SELECT ?s WHERE { ?s ?p ?o }") == [{"s": {"value": "urn:s"}}]

    ask_session = RecordingSession(
        FakeResponse(200, payload={"boolean": True}, content_type="application/sparql-results+json")
    )
    ask_client = FusekiClient(session=ask_session)
    assert ask_client.ask("ASK { ?s ?p ?o }") is True


def test_construct_decodes_utf8_turtle_when_fuseki_omits_charset() -> None:
    """CONSTRUCT 的 Turtle 响应缺少 charset 时也必须按 UTF-8 解码中文标签。"""

    turtle_bytes = b'@prefix mto: <https://hifar.top/mto#> .\nmto:Result <http://www.w3.org/2000/01/rdf-schema#label> "\xe5\x88\xa4\xe5\xae\x9a\xe7\xbb\x93\xe6\x9e\x9c"@zh .\n'
    session = RecordingSession(
        FakeResponse(
            200,
            content=turtle_bytes,
            content_type="text/turtle",
            encoding="ISO-8859-1",
            apparent_encoding="utf-8",
        )
    )
    client = FusekiClient(session=session)

    constructed = client.construct("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }")

    assert '"判定结果"@zh' in constructed


def _integration_client_or_skip() -> FusekiClient:
    """Fuseki 未启动或默认数据集不存在时跳过集成测试。"""

    client = FusekiClient(timeout=_integration_timeout())
    if not client.ping():
        pytest.skip(
            "本地 Fuseki 默认数据集不可用；设置 FUSEKI_BASE_URL/FUSEKI_DATASET 并启动服务后运行集成测试"
        )
    return client


def test_fuseki_gsp_and_sparql_roundtrip():
    """在真实 Fuseki 上验证 GSP PUT 与 SELECT/ASK/CONSTRUCT/UPDATE 全链路。"""

    client = _integration_client_or_skip()
    graph_iri = f"https://example.test/graph/{uuid.uuid4()}"
    subject = f"https://example.test/s/{uuid.uuid4().hex}"
    ttl = f"""
@prefix ex: <https://example.test/> .
<{subject}> ex:p "v" .
"""

    try:
        client.upload_graph(graph_iri, ttl)
    except FusekiError as exc:
        if exc.code == "FUSEKI_HTTP_401":
            pytest.skip("本地 Fuseki 写入端点需要认证；设置 FUSEKI_USER/FUSEKI_PASSWORD 后运行")
        if exc.code == "FUSEKI_UNAVAILABLE":
            pytest.skip("本地 Fuseki 写入端点不可用或超时；可调大 FUSEKI_TEST_TIMEOUT 后重试")
        raise

    assert client.ask(f"ASK WHERE {{ GRAPH <{graph_iri}> {{ <{subject}> <https://example.test/p> \"v\" }} }}")

    rows = client.select(
        f"SELECT ?o WHERE {{ GRAPH <{graph_iri}> {{ <{subject}> <https://example.test/p> ?o }} }}"
    )
    assert rows[0]["o"]["value"] == "v"

    constructed = client.construct(f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph_iri}> {{ ?s ?p ?o }} }}")
    assert subject in constructed

    client.update(
        f"""
        INSERT DATA {{
          GRAPH <{graph_iri}> {{
            <{subject}> <https://example.test/p2> "v2" .
          }}
        }}
        """
    )
    assert client.ask(f"ASK WHERE {{ GRAPH <{graph_iri}> {{ <{subject}> <https://example.test/p2> \"v2\" }} }}")


def test_fuseki_missing_dataset_raises_clear_error():
    """真实 Fuseki 可访问时，错误 dataset 必须抛出可映射的 FusekiError。"""

    base_url = os.getenv("FUSEKI_BASE_URL", "http://localhost:3030")
    probe = FusekiClient(
        base_url=base_url,
        dataset=os.getenv("FUSEKI_DATASET", "manufacturing-trial"),
        timeout=_integration_timeout(),
    )
    if not probe.ping():
        pytest.skip("本地 Fuseki 不可用，跳过错误 dataset 集成验证")

    client = FusekiClient(base_url=base_url, dataset=f"missing-{uuid.uuid4().hex}", timeout=_integration_timeout())

    with pytest.raises(FusekiError) as raised:
        client.select("SELECT * WHERE { ?s ?p ?o } LIMIT 1")

    assert raised.value.code in {"FUSEKI_DATASET_NOT_FOUND", "FUSEKI_HTTP_404"}
    assert raised.value.status_code in {404, 405}
