"""核心层基础包。

该包放置与框架无关的核心能力，例如执行链路、日志、安全脱敏和后续图谱业务逻辑。
并行开发阶段允许部分模块尚未落地，因此这里对可选导入做兼容，避免包导入被
未完成的共享文件阻断。
"""

try:
    from mvp.core.trace import ExecutionTrace, TraceStep
except ModuleNotFoundError:  # pragma: no cover - 兼容并行任务尚未写入 trace.py
    __all__: list[str] = []
else:
    __all__ = ["ExecutionTrace", "TraceStep"]
