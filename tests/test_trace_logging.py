import io
import json
import logging

import pytest

from mvp.core.logging_setup import JsonFormatter, sanitize
from mvp.core.trace import ExecutionTrace, TraceStep


def test_execution_trace_log_returns_trace_step_and_records_statuses():
    trace = ExecutionTrace(trace_id="trace-test")

    statuses = ["started", "success", "failed", "skipped", "fallback"]
    for status in statuses:
        step = trace.log(f"step.{status}", status, reason=f"原因-{status}")
        assert isinstance(step, TraceStep)
        assert step.step == f"step.{status}"
        assert step.status == status
        assert step.reason == f"原因-{status}"

    assert [step.status for step in trace.steps] == statuses
    assert trace.steps[0].started_at.endswith("+00:00")


def test_execution_trace_rejects_unknown_status():
    trace = ExecutionTrace(trace_id="trace-test")

    with pytest.raises(ValueError):
        trace.log("bad.step", "unknown", reason="非法状态")


def test_sanitize_masks_api_keys_headers_cookie_and_url_token():
    raw = {
        "OPENAI_API_KEY": "sk-test-leak",
        "headers": {
            "Authorization": "Bearer auth-secret",
            "x-api-key": "x-secret",
            "Cookie": "sid=cookie-secret",
        },
        "base_url": "https://llm.example.test/v1/chat?token=url-secret&keep=1",
        "items": ["https://api.example.test/path?access_token=access-secret"],
    }

    clean = sanitize(raw)
    encoded = json.dumps(clean, ensure_ascii=False)

    assert clean["OPENAI_API_KEY"] == "***"
    assert clean["headers"]["Authorization"] == "***"
    assert clean["headers"]["x-api-key"] == "***"
    assert clean["headers"]["Cookie"] == "***"
    assert "token=***" in clean["base_url"]
    assert "access_token=***" in clean["items"][0]
    for secret in ["sk-test-leak", "auth-secret", "x-secret", "cookie-secret", "url-secret", "access-secret"]:
        assert secret not in encoded


def test_trace_detail_is_sanitized_before_returning_to_api():
    trace = ExecutionTrace(trace_id="trace-secret")

    step = trace.log(
        "llm_call",
        "fallback",
        reason="provider 不可用",
        OPENAI_API_KEY="sk-test-leak",
        base_url="https://llm.example.test/v1?token=url-secret",
    )

    encoded = json.dumps(step.detail, ensure_ascii=False)
    assert step.detail["OPENAI_API_KEY"] == "***"
    assert "token=***" in step.detail["base_url"]
    assert "sk-test-leak" not in encoded
    assert "url-secret" not in encoded


def test_json_formatter_outputs_parseable_sanitized_json_line():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("mvp.test.sanitize")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info(
        "qa.request",
        extra={
            "trace_id": "trace-json",
            "OPENAI_API_KEY": "sk-test-leak",
            "headers": {"Authorization": "Bearer auth-secret", "Cookie": "sid=cookie-secret"},
            "base_url": "https://llm.example.test/v1?token=url-secret",
        },
    )

    payload = json.loads(stream.getvalue())
    encoded = json.dumps(payload, ensure_ascii=False)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "mvp.test.sanitize"
    assert payload["message"] == "qa.request"
    assert payload["trace_id"] == "trace-json"
    assert payload["OPENAI_API_KEY"] == "***"
    assert payload["headers"]["Authorization"] == "***"
    assert payload["headers"]["Cookie"] == "***"
    assert "token=***" in payload["base_url"]
    for secret in ["sk-test-leak", "auth-secret", "cookie-secret", "url-secret"]:
        assert secret not in encoded
