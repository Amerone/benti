import pytest

from mvp.core import commission_reasoning as cr


def test_decompose_projects_creates_one_task_per_project():
    projects = [
        cr.TestProjectInput(project_id="P-001", name="High/low temperature vibration test", task_id="T-001"),
        cr.TestProjectInput(project_id="P-002", name="Electromagnetic compatibility test", task_id="T-002"),
    ]

    tasks = cr.decompose_projects(projects)

    assert [task.task_id for task in tasks] == ["T-001", "T-002"]
    assert [task.project_id for task in tasks] == ["P-001", "P-002"]
    assert all(task.status == "Pending" for task in tasks)


def test_less_equal_criterion_passes_at_or_under_threshold():
    criterion = cr.PassCriterionInput(
        item_code="RCS_MEAN",
        operator="<=",
        threshold=0.05,
        unit="m2",
        standard_code="GJB-7821-2024",
        standard_version="V1",
    )

    result = cr.evaluate_record("DR-001", "T-001", "RCS_MEAN", 0.042, criterion)

    assert result.status == "Pass"
    assert result.reason == "0.042 <= 0.05"
    assert result.standard_version == "V1"


def test_less_equal_criterion_fails_above_threshold():
    criterion = cr.PassCriterionInput(
        item_code="RCS_MEAN",
        operator="<=",
        threshold=0.035,
        unit="m2",
        standard_code="GJB-7821-2024",
        standard_version="V2",
    )

    result = cr.evaluate_record("DR-001", "T-001", "RCS_MEAN", 0.042, criterion)

    assert result.status == "Fail"
    assert result.reason == "0.042 > 0.035"
    assert result.standard_version == "V2"


def test_evaluate_record_rejects_mismatched_item_code():
    criterion = cr.PassCriterionInput(
        item_code="RCS_PEAK",
        operator="<=",
        threshold=0.05,
        unit="m2",
        standard_code="GJB-7821-2024",
        standard_version="V1",
    )

    with pytest.raises(ValueError, match="item code"):
        cr.evaluate_record("DR-001", "T-001", "RCS_MEAN", 0.042, criterion)


def test_evaluate_record_rejects_mismatched_measured_unit():
    criterion = cr.PassCriterionInput(
        item_code="RCS_MEAN",
        operator="<=",
        threshold=0.05,
        unit="m2",
        standard_code="GJB-7821-2024",
        standard_version="V1",
    )

    with pytest.raises(ValueError, match="unit"):
        cr.evaluate_record("DR-001", "T-001", "RCS_MEAN", 0.042, criterion, measured_unit="dBsm")


def test_standard_upgrade_marks_flipped_task_needs_review():
    old = cr.JudgementResult(
        result_id="DR-001_Result_1",
        data_record_id="DR-001",
        task_id="T-001",
        item_code="RCS_MEAN",
        status="Pass",
        reason="0.042 <= 0.05",
        standard_code="GJB-7821-2024",
        standard_version="V1",
    )
    new = cr.JudgementResult(
        result_id="DR-001_Result_2",
        data_record_id="DR-001",
        task_id="T-001",
        item_code="RCS_MEAN",
        status="Fail",
        reason="0.042 > 0.035",
        standard_code="GJB-7821-2024",
        standard_version="V2",
    )

    impact = cr.compare_results(old, new)

    assert impact.flipped is True
    assert impact.task_id == "T-001"
    assert impact.old_status == "Pass"
    assert impact.new_status == "Fail"
    assert impact.task_status == "NeedsReview"


def test_standard_upgrade_keeps_unflipped_task_completed():
    old = cr.JudgementResult(
        result_id="DR-002_Result_1",
        data_record_id="DR-002",
        task_id="T-002",
        item_code="BER",
        status="Pass",
        reason="0.00021 <= 0.001",
        standard_code="GJB-7821-2024",
        standard_version="V1",
    )
    new = cr.JudgementResult(
        result_id="DR-002_Result_2",
        data_record_id="DR-002",
        task_id="T-002",
        item_code="BER",
        status="Pass",
        reason="0.00021 <= 0.001",
        standard_code="GJB-7821-2024",
        standard_version="V2",
    )

    impact = cr.compare_results(old, new)

    assert impact.flipped is False
    assert impact.task_status == "Completed"


@pytest.mark.parametrize(
    ("field_name", "old_overrides", "new_overrides"),
    [
        ("data_record_id", {"data_record_id": "DR-001"}, {"data_record_id": "DR-002"}),
        ("task_id", {"task_id": "T-001"}, {"task_id": "T-002"}),
        ("item_code", {"item_code": "RCS_MEAN"}, {"item_code": "RCS_PEAK"}),
        (
            "standard_code",
            {"standard_code": "GJB-7821-2024"},
            {"standard_code": "GJB-9001-2025"},
        ),
    ],
)
def test_compare_results_rejects_mismatched_identity_fields(field_name, old_overrides, new_overrides):
    baseline = dict(
        result_id="DR-001_Result_1",
        data_record_id="DR-001",
        task_id="T-001",
        item_code="RCS_MEAN",
        status="Pass",
        reason="0.042 <= 0.05",
        standard_code="GJB-7821-2024",
        standard_version="V1",
    )
    old = cr.JudgementResult(**{**baseline, **old_overrides})
    new = cr.JudgementResult(
        **{
            **baseline,
            "result_id": "DR-001_Result_2",
            "standard_version": "V2",
            **new_overrides,
        }
    )

    with pytest.raises(ValueError, match=field_name):
        cr.compare_results(old, new)


def test_unicode_project_name_and_square_meter_unit_round_trip():
    projects = [cr.TestProjectInput(project_id="P-003", name="雷达散射截面积测试", task_id="T-003")]
    criterion = cr.PassCriterionInput(
        item_code="RCS_MEAN",
        operator="<=",
        threshold=0.05,
        unit="m²",
        standard_code="GJB-7821-2024",
        standard_version="V3",
    )

    tasks = cr.decompose_projects(projects)
    result = cr.evaluate_record("DR-003", "T-003", "RCS_MEAN", 0.041, criterion, measured_unit="m²")

    assert tasks[0].name == "雷达散射截面积测试"
    assert criterion.unit == "m²"
    assert result.status == "Pass"
