"""Fuseki SPARQL 与 Graph Store Protocol 客户端。

本模块位于基础设施边界，只负责把上层领域代码的查询、更新和 named graph
上传请求转换为 Fuseki HTTP 调用。它不理解业务本体结构，也不记录敏感认证
信息，便于后续 API 层把 FusekiError 映射为统一错误信封。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode


DEFAULT_BASE_URL = "http://localhost:3030"
DEFAULT_DATASET = "manufacturing-trial"
DEFAULT_TIMEOUT = 10.0
_CHARSET_MARKER = "charset="
_LOADED_DOTENV_PATHS: set[str] = set()


def _load_dotenv_from_cwd() -> None:
    """加载当前工作目录可发现的 .env，保持显式环境变量优先。"""

    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return

    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path or dotenv_path in _LOADED_DOTENV_PATHS:
        return
    load_dotenv(dotenv_path=dotenv_path, override=False)
    _LOADED_DOTENV_PATHS.add(dotenv_path)


def _env(name: str, default: str = "") -> str:
    """读取环境变量并去除首尾空白，避免配置文件换行影响 URL 拼接。"""

    return os.getenv(name, default).strip()


def _mask_sensitive(text: str, *secrets: str | None) -> str:
    """屏蔽错误上下文中的敏感值，尤其是 FUSEKI_PASSWORD。

    Fuseki 认证失败或代理错误有可能回显请求上下文。这里在异常进入 API 层前
    先做一次最小净化，避免后续日志、trace 或错误信封泄露密码。
    """

    masked = text
    candidates = [*_secrets_from_env(), *secrets]
    for secret in candidates:
        if secret:
            masked = masked.replace(secret, "***")
    return masked


def _secrets_from_env() -> list[str]:
    """收集本客户端相关的环境密钥值。"""

    return [value for key, value in os.environ.items() if key == "FUSEKI_PASSWORD" and value]


def _decode_text_response(response: Any, *, fallback_encoding: str = "utf-8-sig") -> str:
    """在服务端未声明 charset 时，按 UTF-8 回退解码文本响应。

    Fuseki 的 `text/turtle` 常见返回头只有 `text/turtle`，`requests` 会按
    ISO-8859-1 处理 `response.text`。对 Turtle / RDF/XML 这类本项目使用的
    RDF 文本格式，缺省按 UTF-8 bytes 解码更符合实际返回内容。
    """

    text = str(getattr(response, "text", ""))
    headers = getattr(response, "headers", {}) or {}
    content_type = str(headers.get("content-type", ""))
    if _CHARSET_MARKER in content_type.lower():
        return text

    raw = getattr(response, "content", None)
    encoding = str(getattr(response, "encoding", "") or "").lower()
    if not isinstance(raw, (bytes, bytearray)):
        return text
    if encoding not in {"", "iso-8859-1"}:
        return text

    try:
        return bytes(raw).decode(fallback_encoding)
    except UnicodeDecodeError:
        return text


@dataclass(slots=True)
class FusekiError(Exception):
    """Fuseki 调用失败。

    属性包含可被 API 层稳定映射的 `code`、HTTP `status_code`、请求 `endpoint`
    与净化后的响应摘要。异常字符串同样保证不包含 FUSEKI_PASSWORD。
    """

    code: str
    message: str
    status_code: int | None = None
    endpoint: str | None = None
    response_text: str | None = None

    def __str__(self) -> str:
        """返回适合日志和 API 错误详情使用的净化文本。"""

        parts = [self.code, self.message]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.endpoint:
            parts.append(f"endpoint={self.endpoint}")
        if self.response_text:
            parts.append(f"response={self.response_text}")
        return " | ".join(parts)


class FusekiClient:
    """Apache Jena Fuseki HTTP 客户端。

    负责构造 query/update/data 三类端点，提供 SELECT、ASK、CONSTRUCT、UPDATE、
    named graph 上传和健康探测能力。默认读取 FUSEKI_* 环境变量；调用失败统一
    抛出 FusekiError，Fuseki 不可用的 ping 则返回 False 便于健康检查降级。
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        dataset: str | None = None,
        user: str | None = None,
        password: str | None = None,
        timeout: float | None = None,
        session: Any | None = None,
    ) -> None:
        """初始化客户端配置。

        参数优先级为显式传参高于环境变量，高于设计默认值。`session` 用于测试
        或复用 requests.Session；不传时延迟创建 requests 会话。
        """

        _load_dotenv_from_cwd()
        self.base_url = (base_url or _env("FUSEKI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.dataset = (dataset or _env("FUSEKI_DATASET", DEFAULT_DATASET)).strip("/")
        self.user = user if user is not None else _env("FUSEKI_USER")
        self.password = password if password is not None else _env("FUSEKI_PASSWORD")
        self.timeout = float(timeout if timeout is not None else _env("FUSEKI_TIMEOUT", str(DEFAULT_TIMEOUT)))
        self._session = session

    @property
    def query_url(self) -> str:
        """返回当前 dataset 的 SPARQL 查询端点。"""

        return f"{self.base_url}/{self.dataset}/query"

    @property
    def update_url(self) -> str:
        """返回当前 dataset 的 SPARQL Update 端点。"""

        return f"{self.base_url}/{self.dataset}/update"

    @property
    def data_url(self) -> str:
        """返回当前 dataset 的 Graph Store Protocol 端点。"""

        return f"{self.base_url}/{self.dataset}/data"

    def select(self, sparql: str) -> list[dict[str, Any]]:
        """执行 SELECT 查询并返回 SPARQL JSON bindings 列表。

        Fuseki 返回非 JSON 或缺少 `results.bindings` 时抛出 FusekiError，避免
        上层在不完整数据上继续推理。
        """

        payload = self._query_json(sparql)
        try:
            bindings = payload["results"]["bindings"]
        except (KeyError, TypeError) as exc:
            raise FusekiError("FUSEKI_BAD_RESPONSE", "SELECT 响应缺少 results.bindings") from exc
        if not isinstance(bindings, list):
            raise FusekiError("FUSEKI_BAD_RESPONSE", "SELECT 响应 bindings 不是列表")
        return bindings

    def ask(self, sparql: str) -> bool:
        """执行 ASK 查询并返回布尔结果。"""

        payload = self._query_json(sparql)
        if "boolean" not in payload:
            raise FusekiError("FUSEKI_BAD_RESPONSE", "ASK 响应缺少 boolean")
        return bool(payload["boolean"])

    def construct(self, sparql: str, *, accept: str = "text/turtle") -> str:
        """执行 CONSTRUCT/DESCRIBE 类查询并返回 RDF 文本。"""

        response = self._request(
            "POST",
            self.query_url,
            data={"query": sparql},
            headers={"Accept": accept},
        )
        return _decode_text_response(response)

    def update(self, sparql: str) -> None:
        """执行 SPARQL UPDATE。

        Update 只关心 Fuseki 是否接受请求；失败时抛出 FusekiError，成功返回 None。
        """

        self._request(
            "POST",
            self.update_url,
            data={"update": sparql},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def upload_graph(self, graph_iri: str, turtle_text: str, *, content_type: str = "text/turtle") -> None:
        """使用 Graph Store Protocol PUT 覆盖 named graph。

        PUT 语义用于保证重复加载本体图时幂等；调用方必须显式传入 graph IRI，
        本客户端不会推断业务图类型。
        """

        url = self._graph_store_url(graph_iri)
        self._request("PUT", url, data=turtle_text.encode("utf-8"), headers={"Content-Type": content_type})

    def ping(self) -> bool:
        """探测 Fuseki 与当前 dataset 是否可用。

        健康检查不应让普通单测或 API `/health` 因网络问题崩溃，因此所有
        FusekiError 都转换为 False。
        """

        try:
            self.ask("ASK { ?s ?p ?o }")
        except FusekiError:
            return False
        return True

    def _query_json(self, sparql: str) -> dict[str, Any]:
        """执行返回 SPARQL JSON 的查询并解析响应。"""

        response = self._request(
            "POST",
            self.query_url,
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise FusekiError(
                "FUSEKI_BAD_RESPONSE",
                "Fuseki 返回非 JSON 查询结果",
                status_code=response.status_code,
                endpoint=self.query_url,
                response_text=_mask_sensitive(_decode_text_response(response)[:500], self.password),
            ) from exc
        if not isinstance(payload, dict):
            raise FusekiError("FUSEKI_BAD_RESPONSE", "Fuseki JSON 响应不是对象", endpoint=self.query_url)
        return payload

    def _graph_store_url(self, graph_iri: str) -> str:
        """构造 named graph 的 GSP URL。"""

        return f"{self.data_url}?{urlencode({'graph': graph_iri})}"

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        """执行 HTTP 请求并统一处理网络、认证和 HTTP 错误。"""

        request_kwargs = dict(kwargs)
        request_kwargs.setdefault("timeout", self.timeout)
        if self.user:
            request_kwargs.setdefault("auth", (self.user, self.password))

        try:
            response = self._get_session().request(method, url, **request_kwargs)
        except Exception as exc:  # requests 不一定存在于测试环境，只在边界统一转义。
            message = _mask_sensitive(str(exc), self.password)
            raise FusekiError("FUSEKI_UNAVAILABLE", f"Fuseki 请求失败：{message}", endpoint=url) from None

        status_code = getattr(response, "status_code", None)
        if status_code is None:
            raise FusekiError("FUSEKI_BAD_RESPONSE", "HTTP 响应缺少 status_code", endpoint=url)
        if 200 <= status_code < 300:
            return response

        response_text = _mask_sensitive(_decode_text_response(response)[:500], self.password)
        code = self._error_code(status_code)
        raise FusekiError(
            code,
            f"Fuseki HTTP {status_code}",
            status_code=status_code,
            endpoint=url,
            response_text=response_text,
        )

    def _error_code(self, status_code: int) -> str:
        """把 Fuseki HTTP 状态映射为上层稳定识别的错误码。

        不同 Fuseki 镜像在 dataset 缺失时可能返回 404，也可能在 `/query`
        服务未挂载时返回 405。两者对 API 层都表示目标 dataset 不存在或不可用。
        """

        if status_code in {404, 405}:
            return "FUSEKI_DATASET_NOT_FOUND"
        return f"FUSEKI_HTTP_{status_code}"

    def _get_session(self) -> Any:
        """延迟创建 requests.Session，便于测试注入 fake session。"""

        if self._session is None:
            try:
                import requests
            except ImportError as exc:
                raise FusekiError("FUSEKI_CLIENT_UNAVAILABLE", "缺少 requests 依赖，无法访问 Fuseki") from exc
            self._session = requests.Session()
        return self._session
