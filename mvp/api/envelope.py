"""统一响应信封。
API 层所有成功与失败响应都通过这里构造，保证 `ok/data/error/trace_id/trace/started_at/elapsed_ms`
字段稳定，便于前端、测试和日志排障共用同一份结构。
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from mvp.core.logging_setup import sanitize


def _trace_payload(trace: Any | None) -> dict[str, Any]:
    """把 ExecutionTrace 或兼容对象转换为响应信封中的链路字段。"""

    if trace is None:
        return {"trace_id": None, "trace": [], "started_at": None, "elapsed_ms": None}

    trace_id = getattr(trace, "trace_id", None)
    started_at = getattr(trace, "started_at", None)
    elapsed_ms = trace.elapsed_ms() if hasattr(trace, "elapsed_ms") else None
    steps = []
    for step in getattr(trace, "steps", []):
        if hasattr(step, "as_dict"):
            steps.append(step.as_dict())
        elif isinstance(step, dict):
            steps.append(step)
        else:
            steps.append(getattr(step, "__dict__", {}))
    return {
        "trace_id": trace_id,
        "trace": sanitize(steps),
        "started_at": started_at,
        "elapsed_ms": elapsed_ms,
    }


def ok(data: Any, *, trace: Any | None = None, status: int = 200) -> JSONResponse:
    """返回成功信封。"""

    return JSONResponse(
        status_code=status,
        content={
            "ok": True,
            "data": sanitize(data),
            "error": None,
            **_trace_payload(trace),
        },
    )


def fail(
    code: str,
    message: str,
    *,
    trace: Any | None = None,
    status: int = 400,
    detail: Any | None = None,
) -> JSONResponse:
    """返回失败信封。"""

    error = {"code": code, "message": message}
    if detail is not None:
        error["detail"] = sanitize(detail)
    return JSONResponse(
        status_code=status,
        content={
            "ok": False,
            "data": None,
            "error": error,
            **_trace_payload(trace),
        },
    )

