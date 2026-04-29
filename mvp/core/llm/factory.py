"""LLM 供应商工厂。

工厂按 ``LLM_PROVIDER`` 环境变量选择当前供应商。未知值不自动尝试其它供应商，
而是回到默认 Claude 实例；真正调用失败时由 QA 层降级到本地解释。
"""

from __future__ import annotations

import os

from mvp.core.llm.base import LLMProvider
from mvp.core.llm.providers import ClaudeProvider, DEEPSEEK, OPENAI, QWEN


def get_provider() -> LLMProvider:
    """返回当前环境配置的 LLM 供应商，缺省为 Claude。"""

    name = (os.getenv("LLM_PROVIDER") or "claude").strip().lower()
    providers: dict[str, LLMProvider] = {
        "claude": ClaudeProvider(),
        "openai": OPENAI,
        "deepseek": DEEPSEEK,
        "qwen": QWEN,
    }
    return providers.get(name, providers["claude"])
