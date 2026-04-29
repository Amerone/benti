from __future__ import annotations

import os

import pytest

from mvp.core.commission_graph import CommissionGraphService
from mvp.core.cq_engine import CommissionCQRunner, parse_commission_cq_markdown
from mvp.core.graph import BusinessGraphRepository
from mvp.core.sparql_client import FusekiClient, FusekiError


def test_commission_cq_runner_executes_all_plan_cqs_against_fuseki():
    client = FusekiClient(timeout=float(os.getenv("FUSEKI_TEST_TIMEOUT", "15")))
    if not client.ping():
        pytest.skip("Fuseki unavailable; run `docker compose up -d` before commission CQ integration tests")

    repo = BusinessGraphRepository(client=client)
    service = CommissionGraphService(repository=repo)
    runner = CommissionCQRunner(repository=repo)

    try:
        service.reset_demo()
        service.upgrade_standard_to_demo_v2()
    except FusekiError as exc:
        if exc.code == "FUSEKI_HTTP_401":
            pytest.skip("Fuseki requires write credentials; set FUSEKI_USER/FUSEKI_PASSWORD")
        raise

    questions = parse_commission_cq_markdown()
    results = [runner.run_question(question) for question in questions]

    assert [result.question.id for result in results] == [
        "CQ-CT-001",
        "CQ-CT-002",
        "CQ-CT-003",
        "CQ-CT-004",
        "CQ-CT-005",
    ]
    assert len(results[0].rows) == 2
    assert results[0].rows[0]["order_no"] == "CO-2024-001"
    assert results[2].rows[0]["status"] == "Pass"
    assert results[2].rows[0]["standard_version"] == "V1"
    assert results[3].rows[0]["task_status"] == "NeedsReview"
    assert results[4].rows[0]["task_status"] == "NeedsReview"
