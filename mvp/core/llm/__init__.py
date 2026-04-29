"""LLM 适配层。

该包为 QA 核心提供统一 provider 协议、HTTP 实现和环境变量工厂。
"""

from mvp.core.llm.base import LLMProvider
from mvp.core.llm.factory import get_provider
from mvp.core.llm.providers import (
    ClaudeProvider,
    DEEPSEEK,
    OPENAI,
    QWEN,
    OpenAICompatibleProvider,
)

__all__ = [
    "ClaudeProvider",
    "DEEPSEEK",
    "LLMProvider",
    "OPENAI",
    "OpenAICompatibleProvider",
    "QWEN",
    "get_provider",
]
