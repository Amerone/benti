"""JSON 日志与敏感信息脱敏基础设施。

本模块位于 core 层，只负责把结构化日志整理为可解析的 JSON 行，并在写入前统一过滤
API Key、认证头、Cookie 和 URL 查询 token。后续 API、LLM、Fuseki 客户端都应复用这里的
`sanitize()`，避免各模块自行处理导致遗漏。
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MASK = "***"
_URL_RE = re.compile(r"https?://[^\s'\"<>]+")
_AUTH_INLINE_RE = re.compile(
    r"(?i)\b(authorization|x-api-key|cookie)\s*[:=]\s*([^\s,;]+)"
)
_TOKEN_QUERY_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "apikey",
    "key",
}

_STANDARD_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


def _is_sensitive_key(key: Any) -> bool:
    """判断字段名是否属于必须屏蔽的敏感字段。"""

    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in {"authorization", "x_api_key", "cookie", "api_key"} or normalized.endswith(
        "_api_key"
    )


def _mask_url_token(value: str) -> str:
    """屏蔽 URL 查询串中的 token 类参数，保留其他查询参数便于排查。"""

    def _replace(match: re.Match[str]) -> str:
        url = match.group(0)
        parts = urlsplit(url)
        if not parts.query:
            return url

        query = [
            (name, MASK if name.lower() in _TOKEN_QUERY_KEYS else raw_value)
            for name, raw_value in parse_qsl(parts.query, keep_blank_values=True)
        ]
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, safe="*"), parts.fragment))

    return _URL_RE.sub(_replace, value)


def _mask_inline_headers(value: str) -> str:
    """屏蔽字符串中直接拼接的认证头，覆盖误把 headers 格式化成字符串的场景。"""

    return _AUTH_INLINE_RE.sub(lambda match: f"{match.group(1)}={MASK}", value)


def sanitize(value: Any) -> Any:
    """递归清理日志和 trace 明细中的敏感信息。

    输入可以是 dict、列表、元组、字符串或基础类型。函数会保留原始结构，便于日志仍可检索；
    只有明确的密钥字段、认证头字段和 URL token 值会被替换为 `***`。
    """

    if isinstance(value, Mapping):
        return {
            key: MASK if _is_sensitive_key(key) else sanitize(item)
            for key, item in value.items()
        }

    if isinstance(value, tuple):
        return tuple(sanitize(item) for item in value)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [sanitize(item) for item in value]

    if isinstance(value, str):
        return _mask_inline_headers(_mask_url_token(value))

    return value


class JsonFormatter(logging.Formatter):
    """输出单行 JSON 的日志格式化器。

    该格式化器会提取 `logging` 的标准字段和 `extra` 传入的业务字段，并在序列化前统一
    调用 `sanitize()`。日志消费者可以逐行 `json.loads()`，也能按 `trace_id` 检索链路。
    """

    def format(self, record: logging.LogRecord) -> str:
        """将 LogRecord 转为经过脱敏的 JSON 字符串。"""

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_KEYS and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(sanitize(payload), ensure_ascii=False, default=str)


def setup_logging(
    *,
    level: int | str = logging.INFO,
    log_file: str | Path | None = None,
    logger_name: str | None = None,
) -> logging.Logger:
    """安装 stdout JSON 日志处理器。

    参数允许后续 API 入口按需指定 logger 名称或文件路径。默认只写 stdout，避免本轮基础设施
    在未配置运行环境时创建额外副作用；传入 `log_file` 时会同时写入文件并自动创建父目录。
    """

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    logger.addHandler(stdout_handler)

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


__all__ = ["JsonFormatter", "MASK", "sanitize", "setup_logging"]
