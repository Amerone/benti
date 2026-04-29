from __future__ import annotations

from unittest.mock import ANY

import pytest

from mvp.core import graph, qa
from mvp.core.parameters import list_parameters
from mvp import demo_data


def test_load_demo_data_populates_acceptance_seed() -> None:
    repo = graph.BusinessGraphRepository()

    report = demo_data.load_demo_data(repository=repo)

    assert report["ontology_id"] == "manufacturing-trial"
    assert graph.list_trials("manufacturing-trial", repository=repo)["items"] == [
        {"trial_id": "T001", "label": "注塑工艺验证"}
    ]
    assert [item["batch_id"] for item in graph.list_batches("manufacturing-trial", "T001", repository=repo)["items"]] == [
        "B01",
        "B02",
        "B03",
    ]
    assert list_parameters("manufacturing-trial", repository=repo)["items"] == [
        {
            "code": "temperature",
            "name": "注塑温度",
            "unit": "°C",
            "value_type": "number",
            "participates_in_inference": True,
            "created_at": ANY,
        }
    ]
    assert graph.list_specifications("manufacturing-trial", "temperature", repository=repo)["items"] == [
        {
            "spec_id": "temperature_Spec_v1",
            "parameter": "temperature",
            "lower": 180.0,
            "upper": 195.0,
            "reason": "初始规格",
            "effective_from": "2026-04-23T00:00:00Z",
            "spec_version": "Spec_v1",
            "supersedes": None,
        }
    ]

    measurements = graph.list_measurements("manufacturing-trial", repository=repo)
    assert [item["measurement_id"] for item in measurements["items"]] == [
        "M001",
        "M002",
        "M003",
        "M004",
        "M005",
        "M006",
        "M007",
    ]
    assert {
        item["measurement_id"]: (item["batch"], item["value"], item["status"], item["spec_version"])
        for item in measurements["items"]
    } == {
        "M001": ("B01", 179.5, "Fail_Low", "Spec_v1"),
        "M002": ("B01", 180.0, "Pass", "Spec_v1"),
        "M003": ("B02", 188.0, "Pass", "Spec_v1"),
        "M004": ("B02", 190.0, "Pass", "Spec_v1"),
        "M005": ("B03", 192.1, "Pass", "Spec_v1"),
        "M006": ("B03", 195.0, "Pass", "Spec_v1"),
        "M007": ("B03", 197.2, "Fail_High", "Spec_v1"),
    }


def test_load_demo_data_is_idempotent_without_graph_bloat() -> None:
    repo = graph.BusinessGraphRepository()

    first = demo_data.load_demo_data(repository=repo)
    first_counts = {
        kind: repo.count_graph("manufacturing-trial", kind)
        for kind in ("data", "result", "spec")
    }

    second = demo_data.load_demo_data(repository=repo)
    second_counts = {
        kind: repo.count_graph("manufacturing-trial", kind)
        for kind in ("data", "result", "spec")
    }

    assert first["created"] == {
        "trials": 1,
        "batches": 3,
        "parameters": 1,
        "specifications": 1,
        "measurements": 7,
        "results": 7,
    }
    assert second["created"] == {
        "trials": 0,
        "batches": 0,
        "parameters": 0,
        "specifications": 0,
        "measurements": 0,
        "results": 0,
    }
    assert first_counts == second_counts


def test_build_why_fail_evidence_supports_m007_fallback() -> None:
    repo = graph.BusinessGraphRepository()
    demo_data.load_demo_data(repository=repo)

    evidence = demo_data.build_why_fail_evidence(
        "manufacturing-trial",
        "M007",
        repository=repo,
    )
    answer = qa.local_fallback("why_fail", evidence)

    assert evidence == {
        "measurement_id": "M007",
        "value": 197.2,
        "status": "Fail_High",
        "rule": "Rule_Fail_High",
        "spec_version": "Spec_v1",
        "lower_limit": 180.0,
        "upper_limit": 195.0,
        "deviation": pytest.approx(2.2),
        "reasoner": "python-deterministic",
        "inferred_at": ANY,
    }
    assert "M007" in answer
    assert "Fail_High" in answer
    assert "197.2" in answer
    assert "Spec_v1" in answer
    assert "Rule_Fail_High" in answer
