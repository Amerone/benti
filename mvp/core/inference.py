"""确定性业务推理模块。

MVP 阶段业务判定必须稳定、可解释、可重放，因此 Result 由 Python 确定性规则产生：
`value < lower -> Fail_Low`，`value > upper -> Fail_High`，否则 `Pass`。Pellet
在这一阶段不是最终业务判定来源。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PYTHON_DETERMINISTIC_REASONER = "python-deterministic"


def _log_step(trace: Any, step: str, status: str = "success", reason: str = "", **detail: Any) -> None:
    if trace is not None and hasattr(trace, "log"):
        trace.log(step, status, reason=reason, **detail)


@dataclass(frozen=True)
class Judgement:
    """单条测量的确定性判定。"""

    status: str
    rule: str
    deviation: float
    spec_version: str
    explanation: dict[str, Any]
    reasoner: str = PYTHON_DETERMINISTIC_REASONER

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rule": self.rule,
            "deviation": self.deviation,
            "spec_version": self.spec_version,
            "reasoner": self.reasoner,
            "explanation": self.explanation,
        }


def evaluate_single(
    value: float | int,
    lower_limit: float | int,
    upper_limit: float | int,
    spec_version: str,
    *,
    trace: Any | None = None,
) -> Judgement:
    """执行单条测量的确定性上下限判定。"""

    value_f = float(value)
    lower_f = float(lower_limit)
    upper_f = float(upper_limit)
    if value_f < lower_f:
        judgement = Judgement(
            "Fail_Low",
            "Rule_Fail_Low",
            round(lower_f - value_f, 10),
            spec_version,
            _build_explanation(
                value_f,
                lower_f,
                upper_f,
                spec_version,
                status="Fail_Low",
                rule="Rule_Fail_Low",
                deviation=round(lower_f - value_f, 10),
                branch="below_lower",
                branch_label="低于下限",
                condition="value < lower_limit",
            ),
        )
    elif value_f > upper_f:
        judgement = Judgement(
            "Fail_High",
            "Rule_Fail_High",
            round(value_f - upper_f, 10),
            spec_version,
            _build_explanation(
                value_f,
                lower_f,
                upper_f,
                spec_version,
                status="Fail_High",
                rule="Rule_Fail_High",
                deviation=round(value_f - upper_f, 10),
                branch="above_upper",
                branch_label="高于上限",
                condition="value > upper_limit",
            ),
        )
    else:
        judgement = Judgement(
            "Pass",
            "Rule_Pass",
            0.0,
            spec_version,
            _build_explanation(
                value_f,
                lower_f,
                upper_f,
                spec_version,
                status="Pass",
                rule="Rule_Pass",
                deviation=0.0,
                branch="within_limits",
                branch_label="规格范围内",
                condition="lower_limit <= value <= upper_limit",
            ),
        )
    _log_step(trace, "evaluate", reason=f"{value_f} 相对 [{lower_f}, {upper_f}] 判定为 {judgement.status}")
    return judgement


def run_inference(
    ontology_id: str,
    measurement_id: str,
    *,
    repository: Any | None = None,
    trace: Any | None = None,
) -> dict[str, Any]:
    """读取 Measurement 和最新规格，保存单条 Result。"""

    from mvp.core import graph

    repo = repository or graph.get_default_repository()
    measurement = repo.get_measurement(ontology_id, measurement_id)
    if measurement is None:
        raise ValueError(f"measurement not found: {measurement_id}")

    parameter = repo.get_parameter(ontology_id, measurement["parameter"])
    if parameter is not None and not parameter["participates_in_inference"]:
        return {**measurement, "status": "not_inferred", "reason": "parameter does not participate in inference"}

    spec = repo.latest_specification(ontology_id, measurement["parameter"])
    if spec is None:
        return {**measurement, "status": "not_inferred", "reason": "parameter has no specification"}

    judgement = evaluate_single(
        measurement["value"],
        spec["lower"],
        spec["upper"],
        spec["spec_version"],
        trace=trace,
    )
    result = repo.save_inference_result(
        ontology_id,
        measurement_id,
        status=judgement.status,
        rule=judgement.rule,
        spec_version=judgement.spec_version,
        deviation=judgement.deviation,
        reasoner=judgement.reasoner,
        evidence_value=measurement["value"],
        evidence_lower_limit=spec["lower"],
        evidence_upper_limit=spec["upper"],
        trace=trace,
    )
    explanation = _with_abox_context(judgement.explanation, measurement)
    return {**measurement, **result, "explanation": explanation}


def rerun_after_spec_change(
    ontology_id: str,
    parameter_code: str,
    *,
    new_lower: float | int,
    new_upper: float | int,
    reason: str = "",
    effective_from: str | None = None,
    repository: Any | None = None,
    trace: Any | None = None,
) -> dict[str, Any]:
    """规格变更后重推指定参数的历史测量，并返回状态差异。"""

    from mvp.core import graph

    repo = repository or graph.get_default_repository()
    spec = repo.create_specification(
        ontology_id,
        parameter_code,
        lower=new_lower,
        upper=new_upper,
        reason=reason,
        effective_from=effective_from,
        trace=trace,
    )
    if not spec["created"]:
        return {
            "spec_version": spec["spec_version"],
            "created": False,
            "changed": [],
            "reason": "identical to existing spec",
        }

    measurements = repo.list_measurements(ontology_id, parameter_code)["items"]
    _log_step(trace, "iterate_history", reason="遍历历史 Measurement 做重推", count=len(measurements))
    changed = []
    for measurement in measurements:
        old = repo.latest_result_for_measurement(ontology_id, measurement["measurement_id"])
        judgement = evaluate_single(
            measurement["value"],
            spec["lower"],
            spec["upper"],
            spec["spec_version"],
            trace=trace,
        )
        repo.save_inference_result(
            ontology_id,
            measurement["measurement_id"],
            status=judgement.status,
            rule=judgement.rule,
            spec_version=judgement.spec_version,
            deviation=judgement.deviation,
            reasoner=judgement.reasoner,
            evidence_value=measurement["value"],
            evidence_lower_limit=spec["lower"],
            evidence_upper_limit=spec["upper"],
            trace=trace,
        )
        if old is not None and old.status != judgement.status:
            changed.append(
                {
                    "measurement_id": measurement["measurement_id"],
                    "old_status": old.status,
                    "new_status": judgement.status,
                    "old_spec": old.spec_version,
                    "new_spec": judgement.spec_version,
                    "deviation": judgement.deviation,
                }
            )
    _log_step(trace, "diff", reason="输出重推后的状态差异", count=len(changed))
    return {"spec_version": spec["spec_version"], "created": True, "changed": changed}


def _build_explanation(
    value: float,
    lower: float,
    upper: float,
    spec_version: str,
    *,
    status: str,
    rule: str,
    deviation: float,
    branch: str,
    branch_label: str,
    condition: str,
) -> dict[str, Any]:
    """生成面向 ABOX 讲解的规则分支解释。"""

    return {
        "abox": {"value": value},
        "spec": {
            "lower_limit": lower,
            "upper_limit": upper,
            "spec_version": spec_version,
        },
        "rule_set": "deterministic_boundary",
        "branch": branch,
        "branch_label": branch_label,
        "matched_rule": rule,
        "condition": condition,
        "result": {
            "status": status,
            "deviation": deviation,
        },
        "path": [
            {
                "name": "读取 ABOX 测量事实",
                "detail": f"测量值 value={value}",
            },
            {
                "name": "匹配规格版本",
                "detail": f"{spec_version}: lower_limit={lower}, upper_limit={upper}",
            },
            {
                "name": "按规则判断分支",
                "detail": f"命中 {condition}，进入“{branch_label}”分支",
            },
            {
                "name": "输出判定结果",
                "detail": f"{rule} => {status}，deviation={deviation}",
            },
        ],
    }


def _with_abox_context(explanation: dict[str, Any], measurement: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(explanation)
    enriched["abox"] = {
        "measurement_id": measurement["measurement_id"],
        "batch": measurement["batch"],
        "parameter": measurement["parameter"],
        "value": measurement["value"],
    }
    return enriched
