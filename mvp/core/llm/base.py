"""LLM 供应商抽象。

本模块定义 QA 层依赖的最小协议，避免问答业务直接绑定某一家模型 SDK。
LLM 在本项目中只负责解释结构化 evidence，不参与 Pass/Fail 判定，也不生成自由 SPARQL。
"""

from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    """LLM 供应商协议。

    实现类需要暴露供应商名称、默认模型、可用性探测和一次性聊天接口。
    ``chat`` 失败时返回 ``None`` 或抛出异常均可，QA 层会按 Q9 直接降级到本地解释。
    """

    name: str
    default_model: str

    def available(self) -> bool:
        """返回当前供应商是否具备发起请求的最小条件。"""

    def chat(
        self,
        prompt: str,
        *,
        max_tokens: int = 400,
        temperature: float = 0.2,
    ) -> str | None:
        """基于已脱敏 prompt 生成解释文本，失败时返回 ``None``。"""
