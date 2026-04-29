from __future__ import annotations

import pytest

from mvp.core import graph
from mvp.core.inference import (
    PYTHON_DETERMINISTIC_REASONER,
    evaluate_single,
    rerun_after_spec_change,
    run_inference,
)


def test_evaluate_single_uses_deterministic_boundaries() -> None:
    assert evaluate_single(179.99, 180, 195, "Spec_v1").status == "Fail_Low"
    assert evaluate_single(180, 180, 195, "Spec_v1").status == "Pass"
    assert evaluate_single(195, 180, 195, "Spec_v1").status == "Pass"

    high = evaluate_single(197.2, 180, 195, "Spec_v1")

    assert high.status == "Fail_High"
    assert high.rule == "Rule_Fail_High"
    assert high.deviation == pytest.approx(2.2)
    assert high.reasoner == PYTHON_DETERMINISTIC_REASONER


def test_evaluate_single_exposes_customer_readable_decision_path() -> None:
    high = evaluate_single(197.2, 180, 195, "Spec_v1")
    low = evaluate_single(179.5, 180, 195, "Spec_v1")
    passed = evaluate_single(188, 180, 195, "Spec_v1")

    assert high.explanation["abox"]["value"] == 197.2
    assert high.explanation["spec"] == {
        "lower_limit": 180.0,
        "upper_limit": 195.0,
        "spec_version": "Spec_v1",
    }
    assert high.explanation["branch"] == "above_upper"
    assert high.explanation["branch_label"] == "高于上限"
    assert high.explanation["matched_rule"] == "Rule_Fail_High"
    assert high.explanation["condition"] == "value > upper_limit"
    assert high.explanation["result"] == {
        "status": "Fail_High",
        "deviation": pytest.approx(2.2),
    }
    assert [step["name"] for step in high.explanation["path"]] == [
        "读取 ABOX 测量事实",
        "匹配规格版本",
        "按规则判断分支",
        "输出判定结果",
    ]
    assert low.explanation["branch"] == "below_lower"
    assert low.explanation["matched_rule"] == "Rule_Fail_Low"
    assert passed.explanation["branch"] == "within_limits"
    assert passed.explanation["matched_rule"] == "Rule_Pass"


def test_run_inference_persists_latest_result_chain() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B03", repository=repo)
    graph.register_parameter(
        "manufacturing-trial",
        "temperature",
        name="注塑温度",
        unit="C",
        repository=repo,
    )
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_measurement(
        "manufacturing-trial",
        "M007",
        batch_id="B03",
        parameter_code="temperature",
        value=197.2,
        repository=repo,
    )

    first = run_inference("manufacturing-trial", "M007", repository=repo)
    second = run_inference("manufacturing-trial", "M007", repository=repo)

    assert first["status"] == "Fail_High"
    assert second["status"] == "Fail_High"
    assert graph.has_latest_result("manufacturing-trial", "M007", second["result_id"], repository=repo)
    assert graph.result_superseded_by("manufacturing-trial", first["result_id"], repository=repo) == second["result_id"]


def test_rerun_after_spec_change_reports_status_diffs() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B03", repository=repo)
    graph.register_parameter("manufacturing-trial", "temperature", unit="C", repository=repo)
    graph.create_specification(
        "manufacturing-trial",
        "temperature",
        lower=180,
        upper=195,
        reason="初始规格",
        effective_from="2026-04-23T00:00:00Z",
        repository=repo,
    )
    graph.create_and_infer(
        "manufacturing-trial",
        "M005",
        batch_id="B03",
        parameter_code="temperature",
        value=192.1,
        repository=repo,
    )

    report = rerun_after_spec_change(
        "manufacturing-trial",
        "temperature",
        new_lower=180,
        new_upper=190,
        reason="上限收紧",
        effective_from="2026-04-23T01:00:00Z",
        repository=repo,
    )

    assert report["spec_version"] == "Spec_v2"
    assert report["created"] is True
    assert report["changed"] == [
        {
            "measurement_id": "M005",
            "old_status": "Pass",
            "new_status": "Fail_High",
            "old_spec": "Spec_v1",
            "new_spec": "Spec_v2",
            "deviation": pytest.approx(2.1),
        }
    ]
