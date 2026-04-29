from __future__ import annotations

import pytest

from mvp.core import graph
from mvp.core.parameters import list_parameters, register_parameter


def test_register_parameter_is_idempotent_and_listable() -> None:
    repo = graph.BusinessGraphRepository()

    created = register_parameter(
        "manufacturing-trial",
        code="temperature",
        name="注塑温度",
        unit="C",
        value_type="number",
        participates_in_inference=True,
        repository=repo,
    )
    duplicate = register_parameter(
        "manufacturing-trial",
        code="temperature",
        name="注塑温度",
        unit="C",
        value_type="number",
        participates_in_inference=True,
        repository=repo,
    )

    assert created["created"] is True
    assert duplicate["created"] is False
    assert list_parameters("manufacturing-trial", repository=repo)["items"] == [
        {
            "code": "temperature",
            "name": "注塑温度",
            "unit": "C",
            "value_type": "number",
            "participates_in_inference": True,
            "created_at": created["created_at"],
        }
    ]


def test_register_parameter_rejects_missing_required_fields() -> None:
    repo = graph.BusinessGraphRepository()

    with pytest.raises(ValueError, match="code"):
        register_parameter("manufacturing-trial", code="", repository=repo)


def test_non_inference_parameter_short_circuits_result_creation() -> None:
    repo = graph.BusinessGraphRepository()
    graph.create_trial("manufacturing-trial", "T001", repository=repo)
    graph.create_batch("manufacturing-trial", "T001", "B01", repository=repo)
    register_parameter(
        "manufacturing-trial",
        code="ambient_humidity",
        unit="%",
        participates_in_inference=False,
        repository=repo,
    )

    result = graph.create_and_infer(
        "manufacturing-trial",
        "M101",
        batch_id="B01",
        parameter_code="ambient_humidity",
        value=55.2,
        repository=repo,
    )

    assert result["status"] == "not_inferred"
    assert result["reason"] == "parameter does not participate in inference"
    assert repo.count_graph("manufacturing-trial", "result") == 0
