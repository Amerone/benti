from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestProjectInput:
    project_id: str
    name: str
    task_id: str


@dataclass(frozen=True)
class TestTask:
    task_id: str
    project_id: str
    name: str
    status: str = "Pending"


@dataclass(frozen=True)
class PassCriterionInput:
    item_code: str
    operator: str
    threshold: float
    unit: str
    standard_code: str
    standard_version: str


@dataclass(frozen=True)
class JudgementResult:
    result_id: str
    data_record_id: str
    task_id: str
    item_code: str
    status: str
    reason: str
    standard_code: str
    standard_version: str


@dataclass(frozen=True)
class ReevaluationImpact:
    impact_id: str
    data_record_id: str
    task_id: str
    old_result_id: str
    new_result_id: str
    old_status: str
    new_status: str
    flipped: bool
    task_status: str


def decompose_projects(projects: list[TestProjectInput]) -> list[TestTask]:
    return [
        TestTask(task_id=project.task_id, project_id=project.project_id, name=project.name)
        for project in projects
    ]


def evaluate_record(
    data_record_id: str,
    task_id: str,
    item_code: str,
    measured_value: float,
    criterion: PassCriterionInput,
    *,
    result_no: int = 1,
) -> JudgementResult:
    if criterion.operator != "<=":
        raise ValueError(f"unsupported operator: {criterion.operator}")

    if measured_value <= criterion.threshold:
        status = "Pass"
        reason = f"{measured_value:g} <= {criterion.threshold:g}"
    else:
        status = "Fail"
        reason = f"{measured_value:g} > {criterion.threshold:g}"

    return JudgementResult(
        result_id=f"{data_record_id}_Result_{result_no}",
        data_record_id=data_record_id,
        task_id=task_id,
        item_code=item_code,
        status=status,
        reason=reason,
        standard_code=criterion.standard_code,
        standard_version=criterion.standard_version,
    )


def compare_results(old: JudgementResult, new: JudgementResult) -> ReevaluationImpact:
    if old.data_record_id != new.data_record_id:
        raise ValueError("old and new results must refer to the same data record")

    flipped = old.status != new.status
    return ReevaluationImpact(
        impact_id=f"{old.data_record_id}_Impact_{old.standard_version}_to_{new.standard_version}",
        data_record_id=old.data_record_id,
        task_id=new.task_id,
        old_result_id=old.result_id,
        new_result_id=new.result_id,
        old_status=old.status,
        new_status=new.status,
        flipped=flipped,
        task_status="NeedsReview" if flipped else "Completed",
    )
