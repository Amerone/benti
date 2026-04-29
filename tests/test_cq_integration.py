from __future__ import annotations

import os

import pytest

from mvp.core import cq, graph
from mvp.core.llm.base import LLMProvider
from mvp.core.sparql_client import FusekiClient, FusekiError


class UnavailableProvider(LLMProvider):
    name = "test-unavailable"
    default_model = "none"

    def available(self) -> bool:
        return False

    def chat(self, prompt: str, **kwargs):
        raise AssertionError("chat should not be called when provider is unavailable")


def _integration_timeout() -> float:
    return float(os.getenv("FUSEKI_TEST_TIMEOUT", os.getenv("FUSEKI_TIMEOUT", "15")))


def _repo_or_skip() -> graph.BusinessGraphRepository:
    client = FusekiClient(timeout=_integration_timeout())
    if not client.ping():
        pytest.skip("Fuseki unavailable; run `docker compose up -d` before CQ integration tests")
    return graph.BusinessGraphRepository(client=client)


def test_cq_runner_executes_measurement_judgement_cqs_against_fuseki():
    repo = _repo_or_skip()
    runner = cq.CQRunner(repository=repo, provider=UnavailableProvider())
    questions = cq.parse_cq_markdown()

    try:
        runner.prepare_measurement_judgement_fixture()
    except FusekiError as exc:
        if exc.code == "FUSEKI_HTTP_401":
            pytest.skip("Fuseki requires write credentials; set FUSEKI_USER/FUSEKI_PASSWORD")
        if exc.code == "FUSEKI_UNAVAILABLE":
            pytest.skip("Fuseki write endpoint unavailable or timed out; increase FUSEKI_TEST_TIMEOUT if needed")
        raise

    results = [runner.run_question(question) for question in questions]

    assert [result.question.id for result in results] == ["CQ-MJ-001", "CQ-MJ-002", "CQ-MJ-003"]
    assert [result.row["status"] for result in results] == ["Fail_High", "Fail_Low", "Pass"]
    assert [float(result.row["deviation"]) for result in results] == [2.2, 0.9, 0.0]
    assert all(result.qa_evidence["measurement_id"] == result.row["measurement_id"] for result in results)
    assert all(result.qa_evidence["status"] == result.row["status"] for result in results)
    assert all(set(result.question.evidence_fields).issubset(result.qa_evidence.keys()) for result in results)
