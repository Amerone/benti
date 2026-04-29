"""全局异常处理。
404、422、领域错误和未捕获异常都在这里转换成统一信封，确保失败链路也带 `trace_id` 与 `trace`，
避免 FastAPI 默认 `detail` 响应破坏前端与验收约束。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from mvp.api import envelope
from mvp.core.logging_setup import setup_logging
from mvp.core.sparql_client import FusekiError

LOGGER = setup_logging(logger_name="mvp.api.errors")


@dataclass(slots=True)
class DomainError(Exception):
    """领域层到 API 层的稳定错误。"""

    code: str
    message: str
    status: int = 400
    detail: Any | None = None


def _fuseki_status(exc: FusekiError) -> int:
    if exc.code == "FUSEKI_UNAVAILABLE":
        return 503
    if exc.code == "FUSEKI_CLIENT_UNAVAILABLE":
        return 500
    return 502


def _fuseki_message(exc: FusekiError) -> str:
    if exc.code == "FUSEKI_HTTP_401":
        return "Fuseki 写入需要认证，请设置 FUSEKI_USER/FUSEKI_PASSWORD 后重启后端。"
    if exc.code == "FUSEKI_DATASET_NOT_FOUND":
        return "Fuseki dataset 不存在或未挂载，请检查 FUSEKI_BASE_URL/FUSEKI_DATASET。"
    if exc.code == "FUSEKI_UNAVAILABLE":
        return "Fuseki 不可用，请检查服务地址、dataset 和网络连接。"
    return exc.message


def _fuseki_detail(exc: FusekiError) -> dict[str, Any]:
    detail = {
        "status_code": exc.status_code,
        "endpoint": exc.endpoint,
        "response": exc.response_text,
    }
    return {key: value for key, value in detail.items() if value is not None}


def install(app: FastAPI) -> None:
    """安装全局异常处理器。"""

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError):
        trace = getattr(request.state, "trace", None)
        if trace is not None:
            trace.log("domain_error", "failed", reason=exc.message, code=exc.code)
        LOGGER.warning("domain_error", extra={"trace_id": getattr(trace, "trace_id", None), "code": exc.code})
        return envelope.fail(exc.code, exc.message, trace=trace, status=exc.status, detail=exc.detail)

    @app.exception_handler(FusekiError)
    async def _fuseki_error(request: Request, exc: FusekiError):
        trace = getattr(request.state, "trace", None)
        if trace is not None:
            trace.log(
                "fuseki_error",
                "failed",
                reason=_fuseki_message(exc),
                code=exc.code,
                status_code=exc.status_code,
            )
        LOGGER.warning(
            "fuseki_error",
            extra={
                "trace_id": getattr(trace, "trace_id", None),
                "code": exc.code,
                "status_code": exc.status_code,
            },
        )
        return envelope.fail(
            exc.code,
            _fuseki_message(exc),
            trace=trace,
            status=_fuseki_status(exc),
            detail=_fuseki_detail(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        trace = getattr(request.state, "trace", None)
        step_name = f"http_{exc.status_code}"
        if trace is not None:
            trace.log(step_name, "failed", reason=str(exc.detail), status_code=exc.status_code)
        return envelope.fail(
            f"HTTP_{exc.status_code}",
            str(exc.detail),
            trace=trace,
            status=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        trace = getattr(request.state, "trace", None)
        detail = {"errors": exc.errors()[:10]}
        if trace is not None:
            trace.log("request_validation", "failed", reason="请求参数校验失败", **detail)
        return envelope.fail(
            "REQUEST_VALIDATION",
            "请求参数不合法",
            trace=trace,
            status=422,
            detail=detail,
        )

    @app.exception_handler(Exception)
    async def _unhandled_error(request: Request, exc: Exception):
        trace = getattr(request.state, "trace", None)
        if trace is not None:
            trace.log("unhandled", "failed", reason=str(exc)[:200], error_type=type(exc).__name__)
        LOGGER.exception("unhandled", extra={"trace_id": getattr(trace, "trace_id", None)})
        return envelope.fail(
            "INTERNAL_ERROR",
            "服务内部错误",
            trace=trace,
            status=500,
        )
