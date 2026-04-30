from __future__ import annotations

import json

from mvp.core import reasoning_explanation_files


class Provider:
    name = "test-llm"
    default_model = "test-model"

    def __init__(self, *, available: bool = True, text: str | None = "LLM 解释正文") -> None:
        self._available = available
        self.text = text
        self.prompts: list[str] = []

    def available(self) -> bool:
        return self._available

    def chat(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> str | None:
        self.prompts.append(prompt)
        return self.text


def _reasoner_result() -> dict:
    return {
        "ontology_id": "manufacturing-trial",
        "reasoner": "pellet",
        "pellet_status": "success",
        "pellet_ms": 123,
        "inferred_triple_count": 4,
        "classes": [{"name": "Measurement"}],
        "individuals": [{"name": "M001"}],
        "object_properties": [{"name": "hasResult"}],
        "data_properties": [{"name": "value"}],
        "cache_hit": False,
    }


def test_reasoning_explanation_files_use_llm_for_markdown_explanation() -> None:
    provider = Provider(text="LLM：Pellet 成功完成推理，新增推断可追溯到输入 Turtle。")

    result = reasoning_explanation_files.build_explanation_files(
        "manufacturing-trial",
        _reasoner_result(),
        provider=provider,
    )

    assert result["source"] == "test-llm"
    assert result["provider"] == "test-llm"
    assert result["files"][0]["filename"] == "reasoning-explanation.md"
    assert "LLM：Pellet 成功完成推理" in result["files"][0]["content"]
    assert result["files"][1]["filename"] == "reasoning-evidence.json"
    evidence = json.loads(result["files"][1]["content"])
    assert evidence["pellet_status"] == "success"
    assert evidence["class_count"] == 1
    assert provider.prompts
    assert "不得新增判定" in provider.prompts[0]


def test_reasoning_explanation_files_fall_back_when_provider_unavailable() -> None:
    provider = Provider(available=False)

    result = reasoning_explanation_files.build_explanation_files(
        "manufacturing-trial",
        _reasoner_result(),
        provider=provider,
    )

    assert result["source"] == "local_fallback"
    assert result["provider"] == "test-llm"
    assert "本地解释" in result["files"][0]["content"]
    assert provider.prompts == []
