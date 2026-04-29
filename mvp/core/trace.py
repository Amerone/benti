"""执行链路 Trace 数据结构。

本模块只负责在内存中记录一次请求或任务的关键步骤，并把 detail 明细交给日志层脱敏。
它不依赖 FastAPI、Streamlit 或 Fuseki，因此后续 API 中间件、业务模块和测试都可以复用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Literal
from uuid import uuid4

from mvp.core.logging_setup import sanitize

TraceStatus = Literal["started", "success", "failed", "skipped", "fallback"]
TRACE_STATUSES = {"started", "success", "failed", "skipped", "fallback"}


def _utc_now() -> str:
    """返回统一的 UTC ISO 8601 时间字符串。"""

    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class TraceStep:
    """单个执行步骤。

    `step` 表示稳定的步骤名，`status` 只允许框架约定的五种状态，`reason` 用中文说明为什么
    记录该步骤或为什么降级/失败，`detail` 存放已脱敏的结构化上下文。
    """

    step: str
    status: TraceStatus
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=_utc_now)
    ended_at: str | None = None
    elapsed_ms: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """返回适合 API 信封和 JSON 日志序列化的字典。"""

        return {
            "step": self.step,
            "status": self.status,
            "reason": self.reason,
            "detail": self.detail,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(slots=True)
class ExecutionTrace:
    """一次请求或任务的执行链路。

    调用方通过 `log()` 追加步骤，返回值就是写入的 `TraceStep`，便于 API 层把同一对象继续写入
    响应信封或日志。该类不会主动记录完整 prompt 或密钥；所有 detail 都会先经过 `sanitize()`。
    """

    trace_id: str = field(default_factory=lambda: uuid4().hex)
    started_at: str = field(default_factory=_utc_now)
    steps: list[TraceStep] = field(default_factory=list)
    _started_perf: float = field(default_factory=perf_counter, init=False, repr=False)

    def log(self, step: str, status: str, reason: str = "", **detail: Any) -> TraceStep:
        """记录一个执行步骤并返回 `TraceStep`。

        `status` 只支持 started/success/failed/skipped/fallback。非法状态通常意味着埋点写错，
        直接抛出 `ValueError`，让测试和开发阶段尽早暴露问题。
        """

        if status not in TRACE_STATUSES:
            raise ValueError(f"unsupported trace status: {status}")

        now = _utc_now()
        trace_step = TraceStep(
            step=step,
            status=status,  # type: ignore[arg-type]
            reason=reason,
            detail=sanitize(detail),
            started_at=now,
            ended_at=now,
            elapsed_ms=0,
        )
        self.steps.append(trace_step)
        return trace_step

    def elapsed_ms(self) -> int:
        """返回从 trace 创建到当前的毫秒耗时。"""

        return int((perf_counter() - self._started_perf) * 1000)

    def as_dict(self) -> dict[str, Any]:
        """返回完整链路字典，供统一响应信封或调试日志使用。"""

        return {
            "trace_id": self.trace_id,
            "started_at": self.started_at,
            "elapsed_ms": self.elapsed_ms(),
            "trace": [step.as_dict() for step in self.steps],
        }


__all__ = ["ExecutionTrace", "TRACE_STATUSES", "TraceStatus", "TraceStep"]
