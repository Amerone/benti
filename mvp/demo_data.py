"""MVP 演示数据装载器。

本模块只复用 `graph`、`parameters`、`inference` 暴露出来的公开接口，
用于按验收约束写入一套稳定、可重复导入的演示数据。导入逻辑需要满足：

1. 固定生成 Trial `T001`、Batch `B01-B03`、Parameter `temperature`、`Spec_v1`、`M001-M007`。
2. 重复执行后对象数量稳定，不额外膨胀 Result 图。
3. `M007` 的结果可直接复用于 why_fail fallback 解释。
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from mvp.core import graph
from mvp.core.inference import evaluate_single
from mvp.core.parameters import list_parameters, register_parameter

DEFAULT_ONTOLOGY_ID = "manufacturing-trial"
DEFAULT_EFFECTIVE_FROM = "2026-04-23T00:00:00Z"

TRIAL = {"trial_id": "T001", "label": "注塑工艺验证"}
BATCHES = (
    {"batch_id": "B01", "label": "低温 183°C"},
    {"batch_id": "B02", "label": "中温 188°C"},
    {"batch_id": "B03", "label": "高温 193°C"},
)
PARAMETER = {
    "code": "temperature",
    "name": "注塑温度",
    "unit": "°C",
    "value_type": "number",
    "participates_in_inference": True,
}
SPECIFICATION = {
    "parameter_code": "temperature",
    "lower": 180.0,
    "upper": 195.0,
    "reason": "初始规格",
    "effective_from": DEFAULT_EFFECTIVE_FROM,
}
MEASUREMENTS = (
    {"measurement_id": "M001", "batch_id": "B01", "parameter_code": "temperature", "value": 179.5},
    {"measurement_id": "M002", "batch_id": "B01", "parameter_code": "temperature", "value": 180.0},
    {"measurement_id": "M003", "batch_id": "B02", "parameter_code": "temperature", "value": 188.0},
    {"measurement_id": "M004", "batch_id": "B02", "parameter_code": "temperature", "value": 190.0},
    {"measurement_id": "M005", "batch_id": "B03", "parameter_code": "temperature", "value": 192.1},
    {"measurement_id": "M006", "batch_id": "B03", "parameter_code": "temperature", "value": 195.0},
    {"measurement_id": "M007", "batch_id": "B03", "parameter_code": "temperature", "value": 197.2},
)


def load_demo_data(
    *,
    ontology_id: str = DEFAULT_ONTOLOGY_ID,
    repository: Any | None = None,
) -> dict[str, Any]:
    """导入固定演示数据并返回摘要。

    该函数会先确保 Trial、Batch、Parameter、Specification 存在，再按固定顺序补齐
    `M001-M007`。若某条 Measurement 已存在且最新结果与 `Spec_v1` 下的期望一致，
    则跳过重推理，避免 Result 图膨胀；若数据缺失或结果不一致，则只修复必要项。
    """

    repo = repository or graph.get_default_repository()
    created = {
        "trials": 0,
        "batches": 0,
        "parameters": 0,
        "specifications": 0,
        "measurements": 0,
        "results": 0,
    }

    trial_result = graph.create_trial(
        ontology_id,
        TRIAL["trial_id"],
        label=TRIAL["label"],
        repository=repo,
    )
    created["trials"] += int(bool(trial_result["created"]))

    for batch in BATCHES:
        batch_result = graph.create_batch(
            ontology_id,
            TRIAL["trial_id"],
            batch["batch_id"],
            label=batch["label"],
            repository=repo,
        )
        created["batches"] += int(bool(batch_result["created"]))

    parameter_result = register_parameter(
        ontology_id,
        code=PARAMETER["code"],
        name=PARAMETER["name"],
        unit=PARAMETER["unit"],
        value_type=PARAMETER["value_type"],
        participates_in_inference=PARAMETER["participates_in_inference"],
        repository=repo,
    )
    created["parameters"] += int(bool(parameter_result["created"]))

    specification_result = graph.create_specification(
        ontology_id,
        SPECIFICATION["parameter_code"],
        lower=SPECIFICATION["lower"],
        upper=SPECIFICATION["upper"],
        reason=SPECIFICATION["reason"],
        effective_from=SPECIFICATION["effective_from"],
        repository=repo,
    )
    created["specifications"] += int(bool(specification_result["created"]))

    existing_measurements = {
        item["measurement_id"]: item
        for item in graph.list_measurements(ontology_id, repository=repo)["items"]
    }

    for measurement in MEASUREMENTS:
        expected = _expected_measurement_state(measurement["value"])
        current = existing_measurements.get(measurement["measurement_id"])
        if _matches_expected_state(current, measurement, expected):
            continue

        result = graph.create_and_infer(
            ontology_id,
            measurement["measurement_id"],
            batch_id=measurement["batch_id"],
            parameter_code=measurement["parameter_code"],
            value=measurement["value"],
            repository=repo,
        )
        created["measurements"] += int(current is None)
        created["results"] += int(result.get("status") != "not_inferred")

    measurements = graph.list_measurements(ontology_id, repository=repo)["items"]
    return {
        "ontology_id": ontology_id,
        "trial_id": TRIAL["trial_id"],
        "batch_ids": [item["batch_id"] for item in BATCHES],
        "parameter_code": PARAMETER["code"],
        "spec_version": "Spec_v1",
        "measurement_ids": [item["measurement_id"] for item in MEASUREMENTS],
        "created": created,
        "counts": {
            "trials": len(graph.list_trials(ontology_id, repository=repo)["items"]),
            "batches": len(graph.list_batches(ontology_id, TRIAL["trial_id"], repository=repo)["items"]),
            "parameters": len(list_parameters(ontology_id, repository=repo)["items"]),
            "specifications": len(graph.list_specifications(ontology_id, PARAMETER["code"], repository=repo)["items"]),
            "measurements": len(measurements),
            "latest_results": sum(1 for item in measurements if item.get("status")),
        },
        "graph_triples": {
            "data": repo.count_graph(ontology_id, "data"),
            "result": repo.count_graph(ontology_id, "result"),
            "spec": repo.count_graph(ontology_id, "spec"),
        },
    }


def build_why_fail_evidence(
    ontology_id: str,
    measurement_id: str,
    *,
    repository: Any | None = None,
) -> dict[str, Any]:
    """构造 why_fail fallback 需要的 evidence 字典。

    该函数优先从公开列表接口拼装证据，避免调用底层图存储细节。若目标测量不存在，
    返回带 `missing=true` 的最小结果，供 fallback 给出可解释提示。
    """

    repo = repository or graph.get_default_repository()
    measurement = next(
        (
            item
            for item in graph.list_measurements(ontology_id, repository=repo)["items"]
            if item["measurement_id"] == measurement_id
        ),
        None,
    )
    if measurement is None:
        return {"measurement_id": measurement_id, "missing": True}

    spec_version = str(measurement.get("spec_version") or "")
    specification = next(
        (
            item
            for item in graph.list_specifications(ontology_id, measurement["parameter"], repository=repo)["items"]
            if item["spec_version"] == spec_version
        ),
        None,
    )
    if specification is None:
        specifications = graph.list_specifications(ontology_id, measurement["parameter"], repository=repo)["items"]
        specification = specifications[-1] if specifications else None

    return {
        "measurement_id": measurement["measurement_id"],
        "value": measurement["value"],
        "status": measurement.get("status"),
        "rule": measurement.get("rule"),
        "spec_version": spec_version,
        "lower_limit": specification["lower"] if specification is not None else None,
        "upper_limit": specification["upper"] if specification is not None else None,
        "deviation": measurement.get("deviation"),
        "reasoner": measurement.get("reasoner"),
        "inferred_at": measurement.get("inferred_at"),
    }


def main(argv: list[str] | None = None) -> int:
    """命令行导入演示数据并输出 JSON 摘要。"""

    parser = argparse.ArgumentParser(description="导入制造试验本体 MVP 演示数据")
    parser.add_argument("--ontology-id", default=DEFAULT_ONTOLOGY_ID, help="目标 ontology_id")
    args = parser.parse_args(argv)

    report = load_demo_data(ontology_id=args.ontology_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _expected_measurement_state(value: float | int) -> dict[str, Any]:
    judgement = evaluate_single(value, SPECIFICATION["lower"], SPECIFICATION["upper"], "Spec_v1")
    return {
        "status": judgement.status,
        "rule": judgement.rule,
        "spec_version": judgement.spec_version,
        "deviation": judgement.deviation,
    }


def _matches_expected_state(
    current: dict[str, Any] | None,
    measurement: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    if current is None:
        return False
    return (
        current.get("batch") == measurement["batch_id"]
        and current.get("parameter") == measurement["parameter_code"]
        and float(current.get("value", 0.0)) == float(measurement["value"])
        and current.get("status") == expected["status"]
        and current.get("rule") == expected["rule"]
        and current.get("spec_version") == expected["spec_version"]
        and float(current.get("deviation", 0.0)) == float(expected["deviation"])
    )


if __name__ == "__main__":  # pragma: no cover - 命令行入口
    raise SystemExit(main())
