"""请求级 Trace 中间件。
中间件负责在每个 HTTP 请求开始时创建 `ExecutionTrace`，并挂到 `request.state` 上供路由和异常处理器复用。
它只处理请求入口的统一埋点与响应头透传，不改写业务数据结构。
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from mvp.core.logging_setup import setup_logging
from mvp.core.trace import ExecutionTrace

LOGGER = setup_logging(logger_name="mvp.api.trace")


class TraceMiddleware(BaseHTTPMiddleware):
    """为每个请求创建 ExecutionTrace，并记录统一入口埋点。"""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace = ExecutionTrace()
        request.state.trace = trace
        trace.log(
            "request.begin",
            "started",
            reason="接收 HTTP 请求并创建统一链路上下文",
            method=request.method,
            path=request.url.path,
        )
        LOGGER.info(
            "request.begin",
            extra={
                "trace_id": trace.trace_id,
                "path": request.url.path,
                "method": request.method,
            },
        )
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace.trace_id
        return response

