import json

import pytest

from mvp.core import qa


class Trace:
    def __init__(self):
        self.steps = []

    def log(self, step, status, reason="", **detail):
        self.steps.append(
            {"step": step, "status": status, "reason": reason, "detail": detail}
        )


class FakeSparql:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def select(self, query):
        self.queries.append(query)
        return self.rows


class FakeGraph:
    def __init__(self, rows):
        self.sparql = FakeSparql(rows)

    def graph_iri(self, ontology_id, kind="ontology"):
        suffix = "" if kind == "ontology" else f"/{kind}"
        return f"https://hifar.top/mto/graph/{ontology_id}{suffix}"


class Provider:
    def __init__(self, name="deepseek", available=True, text="LLM 解释"):
        self.name = name
        self.default_model = "test-model"
        self._available = available
        self.text = text
        self.prompts = []

    def available(self):
        return self._available

    def chat(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return self.text


def evidence_row(**overrides):
    row = {
        "measurement_id": "M007",
        "value": "197.2",
        "status": "Fail_High",
        "rule": "Rule_Fail_High",
        "spec_version": "Spec_v1",
        "lower_limit": "180",
        "upper_limit": "195",
        "deviation": "2.2",
        "reasoner": "python-deterministic",
        "inferred_at": "2026-04-23T00:00:00Z",
    }
    row.update(overrides)
    return row


def test_local_fallback_explains_m007_why_fail():
    evidence = evidence_row()

    text = qa.local_fallback("why_fail", evidence)

    assert "M007" in text
    assert "Fail_High" in text
    assert "197.2" in text
    assert "Spec_v1" in text
    assert "Rule_Fail_High" in text
    assert "2.2" in text


def test_answer_rejects_missing_ontology_id():
    with pytest.raises(qa.OntologyIdRequired) as exc:
        qa.answer(FakeGraph([evidence_row()]), "", "M007 为什么 Fail？")

    assert exc.value.code == "ONTOLOGY_ID_REQUIRED"


def test_answer_rejects_question_outside_template_whitelist():
    trace = Trace()

    result = qa.answer(
        FakeGraph([evidence_row()]),
        "manufacturing-trial",
        "M007 是什么型号？",
        provider=Provider(),
        trace=trace,
    )

    assert result["source"] == "local_fallback"
    assert result["sparql"] is None
    assert "不支持" in result["answer"]
    assert [item["step"] for item in trace.steps] == [
        "extract_intent",
        "compose_answer",
    ]
    assert trace.steps[0]["status"] == "skipped"


def test_answer_uses_current_provider_when_available():
    provider = Provider(name="qwen", text="来自 qwen 的解释")
    trace = Trace()

    result = qa.answer(
        FakeGraph([evidence_row()]),
        "manufacturing-trial",
        "M007 为什么 Fail？",
        provider=provider,
        trace=trace,
    )

    assert result["source"] == "qwen"
    assert result["answer"] == "来自 qwen 的解释"
    assert result["evidence"]["measurement_id"] == "M007"
    assert result["sparql"] and "M007" in result["sparql"]
    assert provider.prompts
    assert [item["step"] for item in trace.steps] == [
        "extract_intent",
        "build_sparql",
        "fuseki_select",
        "llm_call",
        "compose_answer",
    ]


def test_provider_failure_does_not_switch_and_falls_back(monkeypatch):
    class TimeoutProvider(Provider):
        def chat(self, prompt, **kwargs):
            raise TimeoutError("too slow")

    monkeypatch.setattr(
        qa,
        "get_provider",
        lambda: TimeoutProvider(name="deepseek", available=True),
    )

    result = qa.answer(
        FakeGraph([evidence_row()]),
        "manufacturing-trial",
        "M007 为什么 Fail？",
    )

    assert result["source"] == "local_fallback"
    assert result["provider"] == "deepseek"
    assert "Fail_High" in result["answer"]


def test_prompt_evidence_is_limited_and_sensitive_fields_are_filtered():
    provider = Provider(name="openai", text="ok")
    row = evidence_row(
        Authorization="Bearer should-not-leak",
        OPENAI_API_KEY="sk-test-leak",
        x_api_key="secret-header",
        notes="x" * 9000,
    )

    result = qa.answer(
        FakeGraph([row]),
        "manufacturing-trial",
        "M007 为什么 Fail？",
        provider=provider,
    )

    prompt = provider.prompts[0]
    evidence_json = prompt.split("Evidence JSON:", 1)[1]
    assert len(evidence_json.encode("utf-8")) <= 4096 + len("\n<truncated>")
    assert "sk-test-leak" not in prompt
    assert "should-not-leak" not in prompt
    assert "secret-header" not in prompt
    assert result["evidence"]["notes"] == "x" * 9000
    assert json.dumps(result["evidence"], ensure_ascii=False)


def test_answer_supports_why_pass_question_with_same_measurement_evidence():
    provider = Provider(name="none", available=False)

    result = qa.answer(
        FakeGraph([evidence_row(measurement_id="M009", value="188.0", status="Pass", rule="Rule_Pass", deviation="0.0")]),
        "manufacturing-trial",
        "M009 为什么 Pass？",
        provider=provider,
    )

    assert result["source"] == "local_fallback"
    assert result["intent"] == "why_judgement"
    assert result["evidence"]["measurement_id"] == "M009"
    assert result["evidence"]["status"] == "Pass"
    assert "Pass" in result["answer"]


def test_answer_backfills_measurement_id_for_why_judgement_rows_without_alias():
    provider = Provider(name="none", available=False)
    row = evidence_row(value="188.0", status="Pass", rule="Rule_Pass", deviation="0.0")
    row.pop("measurement_id")

    result = qa.answer(
        FakeGraph([row]),
        "manufacturing-trial",
        "M009 为什么 Pass？",
        provider=provider,
    )

    assert result["intent"] == "why_judgement"
    assert result["evidence"]["measurement_id"] == "M009"
    assert "M009" in result["answer"]
