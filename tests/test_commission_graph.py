import json
from copy import deepcopy

from mvp.core import commission_graph as cg
from mvp.core.graph import BusinessGraphRepository


def _load_demo(path=None):
    return json.loads((path or cg.DEMO_PATH).read_text(encoding="utf-8"))


def test_seed_demo_writes_order_project_task_record_and_result_chain():
    repo = BusinessGraphRepository()
    service = cg.CommissionGraphService(repository=repo)
    demo = _load_demo()
    first_project = demo["order"]["projects"][0]
    second_project = demo["order"]["projects"][1]

    summary = service.reset_demo()

    assert summary == {
        "ontology_id": "commission-testing",
        "order_no": "CO-2024-001",
        "task_count": 2,
        "record_count": 2,
        "result_count": 2,
    }

    order = service.get_order("CO-2024-001")

    assert order["ontology_id"] == "commission-testing"
    assert order["order_no"] == "CO-2024-001"
    assert order["requester"] == demo["order"]["requester"]
    assert order["product"]["name"] == demo["order"]["product"]["name"]
    assert order["product"]["model"] == "X-01"
    assert order["active_standard"]["standard_version"] == "V1"
    assert [project["task_id"] for project in order["projects"]] == ["T-001", "T-002"]
    assert order["projects"][0]["items"] == [
        {
            "item_code": "RCS_MEAN",
            "item_name": first_project["items"][0]["item_name"],
            "unit": first_project["items"][0]["unit"],
            "value": 0.042,
            "data_record_id": "DR-T-001-RCS_MEAN",
            "current_result": {
                "result_id": "DR-T-001-RCS_MEAN_Result_1",
                "status": "Pass",
                "reason": "0.042 <= 0.05",
                "standard_code": "GJB-7821-2024",
                "standard_version": "V1",
            },
        }
    ]
    assert order["projects"][1]["items"] == [
        {
            "item_code": "BER",
            "item_name": second_project["items"][0]["item_name"],
            "unit": second_project["items"][0]["unit"],
            "value": 0.00021,
            "data_record_id": "DR-T-002-BER",
            "current_result": {
                "result_id": "DR-T-002-BER_Result_1",
                "status": "Pass",
                "reason": "0.00021 <= 0.001",
                "standard_code": "GJB-7821-2024",
                "standard_version": "V1",
            },
        }
    ]


def test_standard_upgrade_preserves_old_results_and_records_flip():
    repo = BusinessGraphRepository()
    service = cg.CommissionGraphService(repository=repo)
    service.reset_demo()

    impact = service.upgrade_standard_to_demo_v2()

    assert impact == {
        "ontology_id": "commission-testing",
        "standard_code": "GJB-7821-2024",
        "upgraded_to": "V2",
        "changed": [
            {
                "task_id": "T-001",
                "data_record_id": "DR-T-001-RCS_MEAN",
                "item_code": "RCS_MEAN",
                "old_status": "Pass",
                "new_status": "Fail",
                "flipped": True,
                "task_status": "NeedsReview",
                "old_standard": "V1",
                "new_standard": "V2",
            },
            {
                "task_id": "T-002",
                "data_record_id": "DR-T-002-BER",
                "item_code": "BER",
                "old_status": "Pass",
                "new_status": "Pass",
                "flipped": False,
                "task_status": "Completed",
                "old_standard": "V1",
                "new_standard": "V2",
            },
        ],
    }

    task_001 = service.get_task("T-001")
    assert task_001["task_status"] == "NeedsReview"
    assert task_001["items"][0]["results"] == [
        {
            "result_id": "DR-T-001-RCS_MEAN_Result_1",
            "status": "Pass",
            "reason": "0.042 <= 0.05",
            "standard_code": "GJB-7821-2024",
            "standard_version": "V1",
        },
        {
            "result_id": "DR-T-001-RCS_MEAN_Result_2",
            "status": "Fail",
            "reason": "0.042 > 0.035",
            "standard_code": "GJB-7821-2024",
            "standard_version": "V2",
        },
    ]
    assert task_001["impacts"] == [
        {
            "impact_id": "DR-T-001-RCS_MEAN_Impact_V1_to_V2",
            "data_record_id": "DR-T-001-RCS_MEAN",
            "item_code": "RCS_MEAN",
            "old_status": "Pass",
            "new_status": "Fail",
            "flipped": True,
            "task_status": "NeedsReview",
            "old_standard": "V1",
            "new_standard": "V2",
        }
    ]

    task_002 = service.get_task("T-002")
    assert task_002["task_status"] == "Completed"
    assert [result["status"] for result in task_002["items"][0]["results"]] == ["Pass", "Pass"]
    assert task_002["items"][0]["current_result"]["standard_version"] == "V2"
    assert service.decompose_order("CO-2024-001") == {
        "order_no": "CO-2024-001",
        "tasks": [
            {"task_id": "T-001", "project_id": "P-001", "name": task_001["project_name"], "status": "NeedsReview"},
            {"task_id": "T-002", "project_id": "P-002", "name": task_002["project_name"], "status": "Completed"},
        ],
    }


def test_multi_item_task_persists_all_items_and_keeps_flipped_task_needs_review(tmp_path, monkeypatch):
    demo = deepcopy(_load_demo())
    multi_item_project = deepcopy(demo["order"]["projects"][0])
    multi_item_project["items"].append(deepcopy(demo["order"]["projects"][1]["items"][0]))
    demo["order"]["projects"] = [multi_item_project]

    demo_path = tmp_path / "commission-testing-demo.json"
    demo_path.write_text(json.dumps(demo, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cg, "DEMO_PATH", demo_path)

    repo = BusinessGraphRepository()
    service = cg.CommissionGraphService(repository=repo)

    summary = service.reset_demo()
    assert summary == {
        "ontology_id": "commission-testing",
        "order_no": "CO-2024-001",
        "task_count": 1,
        "record_count": 2,
        "result_count": 2,
    }

    order = service.get_order("CO-2024-001")
    assert [project["task_id"] for project in order["projects"]] == ["T-001"]
    assert [item["item_code"] for item in order["projects"][0]["items"]] == ["BER", "RCS_MEAN"]

    impact = service.upgrade_standard_to_demo_v2()
    assert impact == {
        "ontology_id": "commission-testing",
        "standard_code": "GJB-7821-2024",
        "upgraded_to": "V2",
        "changed": [
            {
                "task_id": "T-001",
                "data_record_id": "DR-T-001-BER",
                "item_code": "BER",
                "old_status": "Pass",
                "new_status": "Pass",
                "flipped": False,
                "task_status": "NeedsReview",
                "old_standard": "V1",
                "new_standard": "V2",
            },
            {
                "task_id": "T-001",
                "data_record_id": "DR-T-001-RCS_MEAN",
                "item_code": "RCS_MEAN",
                "old_status": "Pass",
                "new_status": "Fail",
                "flipped": True,
                "task_status": "NeedsReview",
                "old_standard": "V1",
                "new_standard": "V2",
            },
        ],
    }

    task = service.get_task("T-001")
    assert task["task_status"] == "NeedsReview"
    assert [item["item_code"] for item in task["items"]] == ["BER", "RCS_MEAN"]
    assert [impact["item_code"] for impact in task["impacts"]] == ["BER", "RCS_MEAN"]
    assert all(impact_entry["task_status"] == "NeedsReview" for impact_entry in task["impacts"])

    item_by_code = {item["item_code"]: item for item in task["items"]}
    assert [result["status"] for result in item_by_code["BER"]["results"]] == ["Pass", "Pass"]
    assert [result["standard_version"] for result in item_by_code["BER"]["results"]] == ["V1", "V2"]
    assert [result["status"] for result in item_by_code["RCS_MEAN"]["results"]] == ["Pass", "Fail"]
    assert [result["standard_version"] for result in item_by_code["RCS_MEAN"]["results"]] == ["V1", "V2"]

    assert service.decompose_order("CO-2024-001") == {
        "order_no": "CO-2024-001",
        "tasks": [
            {"task_id": "T-001", "project_id": "P-001", "name": task["project_name"], "status": "NeedsReview"},
        ],
    }
