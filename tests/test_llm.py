import os

from mvp.core.llm.factory import get_provider
from mvp.core.llm.providers import (
    ClaudeProvider,
    DEEPSEEK,
    OPENAI,
    QWEN,
    OpenAICompatibleProvider,
)


def test_factory_defaults_to_claude(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    provider = get_provider()

    assert isinstance(provider, ClaudeProvider)
    assert provider.name == "claude"


def test_factory_switches_configured_provider(monkeypatch):
    expected = {
        "openai": OPENAI,
        "deepseek": DEEPSEEK,
        "qwen": QWEN,
    }

    for name, instance in expected.items():
        monkeypatch.setenv("LLM_PROVIDER", name)
        assert get_provider() is instance


def test_openai_compatible_provider_posts_chat_completions(monkeypatch):
    calls = []

    class Response:
        ok = True

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "解释文本"}}]}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setenv("TEST_API_KEY", "secret")
    monkeypatch.setenv("TEST_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "model-from-env")
    monkeypatch.setattr("mvp.core.llm.providers.requests.post", fake_post)
    provider = OpenAICompatibleProvider(
        name="test",
        api_key_env="TEST_API_KEY",
        base_url_env="TEST_BASE_URL",
        default_base_url="https://default.invalid/v1",
        default_model="default-model",
        timeout=1,
    )

    assert provider.chat("hello", max_tokens=12, temperature=0.1) == "解释文本"
    assert calls[0][0] == "https://example.test/v1/chat/completions"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer secret"
    assert calls[0][1]["json"]["model"] == "model-from-env"
    assert calls[0][1]["json"]["messages"] == [{"role": "user", "content": "hello"}]


def test_claude_provider_posts_messages(monkeypatch):
    calls = []

    class Response:
        ok = True

        @staticmethod
        def json():
            return {"content": [{"text": "Claude 解释"}]}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setenv("CLAUDE_API_KEY", "claude-secret")
    monkeypatch.setenv("LLM_MODEL", "claude-env-model")
    monkeypatch.setattr("mvp.core.llm.providers.requests.post", fake_post)

    assert ClaudeProvider(timeout=1).chat("prompt") == "Claude 解释"
    assert calls[0][0] == "https://api.anthropic.com/v1/messages"
    assert calls[0][1]["headers"]["x-api-key"] == "claude-secret"
    assert calls[0][1]["headers"]["anthropic-version"] == "2023-06-01"
    assert calls[0][1]["json"]["model"] == "claude-env-model"
