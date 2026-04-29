"""LLM 供应商实现。

本模块只封装 Claude 与 OpenAI-compatible HTTP 协议差异。调用方负责构造安全 prompt；
这里不记录 headers、API Key 或完整 prompt，避免在日志与异常信息中泄露敏感内容。
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import requests


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class OpenAICompatibleProvider:
    """OpenAI 兼容 `/chat/completions` 供应商。

    适配 OpenAI、DeepSeek、Qwen 兼容模式。模型名优先读取 ``LLM_MODEL``，
    base URL 与 API Key 分别来自供应商自己的环境变量。
    """

    name: str
    api_key_env: str
    base_url_env: str
    default_base_url: str
    default_model: str
    timeout: float = 30.0

    @property
    def _key(self) -> str | None:
        return os.getenv(self.api_key_env)

    @property
    def _base_url(self) -> str:
        return os.getenv(self.base_url_env, self.default_base_url).rstrip("/")

    def available(self) -> bool:
        """仅以 API Key 是否存在判断当前供应商是否可尝试。"""

        return bool(self._key)

    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> str | None:
        """调用 OpenAI-compatible chat completions 接口。

        非 2xx、网络异常或响应结构不符合预期时返回 ``None``，由 QA 层按
        当前 provider 失败直接 fallback 的规则处理。
        """

        key = self._key
        if not key:
            return None

        model = os.getenv("LLM_MODEL") or self.default_model
        timeout = _env_float("LLM_TIMEOUT", self.timeout)
        try:
            response = requests.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=timeout,
            )
            if not response.ok:
                return None
            payload: dict[str, Any] = response.json()
            return payload["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            return None


@dataclass
class ClaudeProvider:
    """Anthropic Claude `/v1/messages` 供应商。

    请求必须携带 ``x-api-key`` 与 ``anthropic-version``。模型名同样允许通过
    ``LLM_MODEL`` 覆盖，便于测试和部署切换。
    """

    name: str = "claude"
    default_model: str = "claude-sonnet-4-5"
    timeout: float = 30.0

    def available(self) -> bool:
        """仅以 ``CLAUDE_API_KEY`` 是否存在判断 Claude 是否可尝试。"""

        return bool(os.getenv("CLAUDE_API_KEY"))

    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> str | None:
        """调用 Anthropic messages 接口生成解释文本。"""

        key = os.getenv("CLAUDE_API_KEY")
        if not key:
            return None

        model = os.getenv("LLM_MODEL") or self.default_model
        timeout = _env_float("LLM_TIMEOUT", self.timeout)
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=timeout,
            )
            if not response.ok:
                return None
            payload: dict[str, Any] = response.json()
            return payload["content"][0]["text"]
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            return None


OPENAI = OpenAICompatibleProvider(
    "openai",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "https://api.openai.com/v1",
    "gpt-4o-mini",
)
DEEPSEEK = OpenAICompatibleProvider(
    "deepseek",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "https://api.deepseek.com/v1",
    "deepseek-chat",
)
QWEN = OpenAICompatibleProvider(
    "qwen",
    "QWEN_API_KEY",
    "QWEN_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "qwen-plus",
)
