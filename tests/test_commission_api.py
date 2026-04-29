from __future__ import annotations

from fastapi.testclient import TestClient

from mvp.api.main import create_app
from mvp.core.graph import BusinessGraphRepository
from mvp.core.llm.base import LLMProvider


class UnavailableProvider(LLMProvider):
    name = "test-unavailable"
    default_model = "none"

    def available(self) -> bool:
        return False

    def chat(self, prompt: str, **kwargs):
        raise AssertionError("chat should not be called when provider is unavailable")


def _client() -> TestClient:
    return TestClient(
        create_app(
            repository=BusinessGraphRepository(),
            llm_provider=UnavailableProvider(),
        )
    )


def _client_for_repo(repository: BusinessGraphRepository) -> TestClient:
    return TestClient(create_app(repository=repository, llm_provider=UnavailableProvider()))


def _order_payload(order_no: str, project_id: str, task_id: str, *, project_name: str = "Project") -> dict:
    return {
        "order_no": order_no,
        "requester": "QA",
        "product": {"name": "Radar seeker", "model": order_no},
        "projects": [
            {
                "project_id": project_id,
                "name": project_name,
                "task_id": task_id,
                "items": [
                    {
                        "item_code": "RCS_MEAN",
                        "item_name": "RCS mean",
                        "unit": "m\u00b2",
                    }
                ],
            }
        ],
    }


def test_commission_demo_reset_and_upgrade_flow():
    with _client() as client:
        reset_response = client.post("/api/v1/commission/demo/reset")

        assert reset_response.status_code == 200
        assert reset_response.json()["data"] == {
            "ontology_id": "commission-testing",
            "order_no": "CO-2024-001",
            "task_count": 2,
            "record_count": 2,
            "result_count": 2,
        }

        order_response = client.get("/api/v1/commission/orders/CO-2024-001")

        assert order_response.status_code == 200
        order = order_response.json()["data"]
        assert order["order_no"] == "CO-2024-001"
        assert order["active_standard"]["standard_version"] == "V1"
        assert [project["task_id"] for project in order["projects"]] == ["T-001", "T-002"]

        decompose_response = client.post("/api/v1/commission/orders/CO-2024-001/decompose")

        assert decompose_response.status_code == 200
        assert decompose_response.json()["data"] == {
            "order_no": "CO-2024-001",
            "tasks": [
                {
                    "task_id": "T-001",
                    "project_id": "P-001",
                    "name": order["projects"][0]["name"],
                    "status": "Completed",
                },
                {
                    "task_id": "T-002",
                    "project_id": "P-002",
                    "name": order["projects"][1]["name"],
                    "status": "Completed",
                },
            ],
        }

        upgrade_response = client.post("/api/v1/commission/standards/GJB-7821-2024/upgrade")

        assert upgrade_response.status_code == 200
        upgrade_payload = upgrade_response.json()["data"]
        changed_by_task = {item["task_id"]: item for item in upgrade_payload["changed"]}
        assert upgrade_payload["upgraded_to"] == "V2"
        assert changed_by_task["T-001"]["flipped"] is True
        assert changed_by_task["T-001"]["new_status"] == "Fail"
        assert changed_by_task["T-001"]["task_status"] == "NeedsReview"
        assert changed_by_task["T-002"]["flipped"] is False

        latest_response = client.get("/api/v1/commission/impacts/latest")

        assert latest_response.status_code == 200
        latest = latest_response.json()["data"]
        latest_by_task = {item["task_id"]: item for item in latest["changed"]}
        assert latest_by_task["T-001"]["new_standard"] == "V2"
        assert latest_by_task["T-001"]["flipped"] is True
        assert latest_by_task["T-002"]["new_standard"] == "V2"


def test_latest_commission_impact_is_loaded_from_persisted_graph_after_app_restart():
    repository = BusinessGraphRepository()
    with _client_for_repo(repository) as client:
        assert client.post("/api/v1/commission/demo/reset").status_code == 200
        upgrade_response = client.post("/api/v1/commission/standards/GJB-7821-2024/upgrade")
        assert upgrade_response.status_code == 200
        upgrade_payload = upgrade_response.json()["data"]

    with _client_for_repo(repository) as restarted_client:
        latest_response = restarted_client.get("/api/v1/commission/impacts/latest")

    assert latest_response.status_code == 200
    assert latest_response.json()["data"] == upgrade_payload


def test_cq_engine_template_only_generation_and_draft_review():
    with _client() as client:
        generate_response = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        )

        assert generate_response.status_code == 200
        generated = generate_response.json()["data"]
        assert generated["generation_mode"] == "template_only"
        assert generated["candidate_cqs"][0]["id"] == "CQ-CT-001"
        assert generated["source_trace"][0]["generator"] == "template"

        create_response = client.post("/api/v1/cq-engine/drafts", json={"payload": generated})

        assert create_response.status_code == 200
        created = create_response.json()["data"]
        assert created["draft_id"] == "CQD-001"
        assert created["draft_status"] == "draft"
        assert created["payload"]["generation_mode"] == "template_only"

        list_response = client.get("/api/v1/cq-engine/drafts")

        assert list_response.status_code == 200
        assert list_response.json()["data"] == {
            "items": [
                {
                    "draft_id": "CQD-001",
                    "draft_status": "draft",
                    "payload": generated,
                }
            ],
            "total": 1,
        }

        update_response = client.patch("/api/v1/cq-engine/drafts/CQD-001", json={"draft_status": "reviewed"})

        assert update_response.status_code == 200
        updated = update_response.json()["data"]
        assert updated["draft_id"] == "CQD-001"
        assert updated["draft_status"] == "reviewed"
        assert updated["payload"]["generation_mode"] == "template_only"
        assert updated["payload"] == generated


def test_cq_engine_generate_defaults_to_fallback_mode():
    with _client() as client:
        generate_response = client.post(
            "/api/v1/cq-engine/generate",
            json={"business_text": "Commission orders decompose into tasks and track standard upgrades."},
        )

        assert generate_response.status_code == 200
        generated = generate_response.json()["data"]
        assert generated["generation_mode"] == "llm_with_template_fallback"
        assert generated["source_trace"][0]["generator"] == "template"
        assert generated["source_trace"][-1]["status"] == "fallback"


def test_cq_engine_rejects_invalid_generation_mode_and_draft_status():
    with _client() as client:
        invalid_generation = client.post(
            "/api/v1/cq-engine/generate",
            json={"business_text": "Commission test", "generation_mode": "invalid"},
        )

        assert invalid_generation.status_code == 400
        assert invalid_generation.json()["ok"] is False
        assert invalid_generation.json()["error"]["code"] == "CQ_ENGINE_ERROR"

        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={"business_text": "Commission test", "generation_mode": "template_only"},
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]

        invalid_status = client.patch(
            f"/api/v1/cq-engine/drafts/{created['draft_id']}",
            json={"draft_status": "archived"},
        )

        assert invalid_status.status_code == 400
        assert invalid_status.json()["ok"] is False
        assert invalid_status.json()["error"]["code"] == "CQ_ENGINE_ERROR"


def test_commission_order_upsert_and_data_record_entry_are_generic():
    with _client() as client:
        create_response = client.post(
            "/api/v1/commission/orders",
            json={
                "order_no": "CO-TDD-001",
                "requester": "王工",
                "product": {"name": "相控阵雷达导引头", "model": "X-02"},
                "projects": [
                    {
                        "project_id": "P-TDD-001",
                        "name": "高低温振动试验",
                        "task_id": "T-TDD-001",
                        "items": [
                            {
                                "item_code": "RCS_MEAN",
                                "item_name": "RCS均值",
                                "unit": "m²",
                            }
                        ],
                    }
                ],
            },
        )

        assert create_response.status_code == 200
        assert create_response.json()["data"] == {
            "ontology_id": "commission-testing",
            "order_no": "CO-TDD-001",
            "task_count": 1,
            "item_count": 1,
            "record_count": 0,
            "result_count": 0,
        }

        order_response = client.get("/api/v1/commission/orders/CO-TDD-001")

        assert order_response.status_code == 200
        order = order_response.json()["data"]
        assert order["requester"] == "王工"
        assert order["product"] == {"name": "相控阵雷达导引头", "model": "X-02"}
        assert order["active_standard"]["standard_version"] == "V1"
        assert order["projects"][0]["task_id"] == "T-TDD-001"
        assert order["projects"][0]["task_status"] == "Pending"
        assert order["projects"][0]["items"][0]["current_result"] is None

        record_response = client.post(
            "/api/v1/commission/data-records",
            json={
                "task_id": "T-TDD-001",
                "item_code": "RCS_MEAN",
                "data_record_id": "DR-TDD-001-RCS",
                "value": 0.034,
                "unit": "m²",
            },
        )

        assert record_response.status_code == 200
        assert record_response.json()["data"] == {
            "task_id": "T-TDD-001",
            "item_code": "RCS_MEAN",
            "data_record_id": "DR-TDD-001-RCS",
            "value": 0.034,
            "unit": "m²",
            "result": {
                "result_id": "DR-TDD-001-RCS_Result_1",
                "status": "Pass",
                "reason": "0.034 <= 0.05",
                "standard_code": "GJB-7821-2024",
                "standard_version": "V1",
            },
            "task_status": "Completed",
        }

        updated_order = client.get("/api/v1/commission/orders/CO-TDD-001").json()["data"]
        item = updated_order["projects"][0]["items"][0]
        assert updated_order["projects"][0]["task_status"] == "Completed"
        assert item["value"] == 0.034
        assert item["data_record_id"] == "DR-TDD-001-RCS"
        assert item["current_result"]["status"] == "Pass"


def test_commission_data_record_failure_does_not_replace_existing_record():
    with _client() as client:
        assert client.post(
            "/api/v1/commission/orders",
            json=_order_payload("CO-ATOMIC-001", "P-ATOMIC-001", "T-ATOMIC-001"),
        ).status_code == 200
        assert client.post(
            "/api/v1/commission/data-records",
            json={
                "task_id": "T-ATOMIC-001",
                "item_code": "RCS_MEAN",
                "data_record_id": "DR-ATOMIC-GOOD",
                "value": 0.034,
                "unit": "m\u00b2",
            },
        ).status_code == 200

        invalid_response = client.post(
            "/api/v1/commission/data-records",
            json={
                "task_id": "T-ATOMIC-001",
                "item_code": "RCS_MEAN",
                "data_record_id": "DR-ATOMIC-BAD",
                "value": 0.033,
                "unit": "wrong-unit",
            },
        )

        assert invalid_response.status_code == 400
        item = client.get("/api/v1/commission/orders/CO-ATOMIC-001").json()["data"]["projects"][0]["items"][0]
        assert item["data_record_id"] == "DR-ATOMIC-GOOD"
        assert item["value"] == 0.034
        assert item["current_result"]["status"] == "Pass"


def test_commission_order_rejects_ids_that_belong_to_another_order_without_mutating_original():
    with _client() as client:
        first = _order_payload("CO-ID-001", "P-SHARED", "T-SHARED", project_name="Original project")
        second = _order_payload("CO-ID-002", "P-SHARED", "T-SHARED", project_name="Conflicting project")

        assert client.post("/api/v1/commission/orders", json=first).status_code == 200
        conflict_response = client.post("/api/v1/commission/orders", json=second)

        assert conflict_response.status_code == 400
        assert conflict_response.json()["error"]["code"] == "COMMISSION_ORDER_INVALID"
        assert client.get("/api/v1/commission/orders/CO-ID-002").status_code == 404
        original = client.get("/api/v1/commission/orders/CO-ID-001").json()["data"]
        assert original["projects"][0]["name"] == "Original project"
        assert [item["item_code"] for item in original["projects"][0]["items"]] == ["RCS_MEAN"]


def test_commission_task_remains_pending_until_all_items_have_records():
    with _client() as client:
        order = _order_payload("CO-MULTI-001", "P-MULTI-001", "T-MULTI-001")
        order["projects"][0]["items"].append(
            {
                "item_code": "BER",
                "item_name": "Bit error rate",
                "unit": "",
            }
        )
        assert client.post("/api/v1/commission/orders", json=order).status_code == 200

        first_record = client.post(
            "/api/v1/commission/data-records",
            json={
                "task_id": "T-MULTI-001",
                "item_code": "RCS_MEAN",
                "data_record_id": "DR-MULTI-RCS",
                "value": 0.034,
                "unit": "m\u00b2",
            },
        )

        assert first_record.status_code == 200
        assert first_record.json()["data"]["task_status"] == "Pending"
        project_after_first_item = client.get("/api/v1/commission/orders/CO-MULTI-001").json()["data"]["projects"][0]
        assert project_after_first_item["task_status"] == "Pending"
        assert [item["current_result"] is not None for item in project_after_first_item["items"]] == [False, True]

        second_record = client.post(
            "/api/v1/commission/data-records",
            json={
                "task_id": "T-MULTI-001",
                "item_code": "BER",
                "data_record_id": "DR-MULTI-BER",
                "value": 0.0002,
                "unit": "",
            },
        )

        assert second_record.status_code == 200
        assert second_record.json()["data"]["task_status"] == "Completed"
        project_after_second_item = client.get("/api/v1/commission/orders/CO-MULTI-001").json()["data"]["projects"][0]
        assert project_after_second_item["task_status"] == "Completed"


def test_commission_standard_upgrade_keeps_partially_recorded_task_pending():
    with _client() as client:
        order = _order_payload("CO-UPGRADE-PENDING-001", "P-UPGRADE-PENDING-001", "T-UPGRADE-PENDING-001")
        order["projects"][0]["items"].append(
            {
                "item_code": "BER",
                "item_name": "Bit error rate",
                "unit": "",
            }
        )
        assert client.post("/api/v1/commission/orders", json=order).status_code == 200
        assert client.post(
            "/api/v1/commission/data-records",
            json={
                "task_id": "T-UPGRADE-PENDING-001",
                "item_code": "RCS_MEAN",
                "data_record_id": "DR-UPGRADE-PENDING-RCS",
                "value": 0.034,
                "unit": "m\u00b2",
            },
        ).status_code == 200

        upgrade_response = client.post("/api/v1/commission/standards/GJB-7821-2024/upgrade")

        assert upgrade_response.status_code == 200
        changed = upgrade_response.json()["data"]["changed"]
        assert changed == [
            {
                "task_id": "T-UPGRADE-PENDING-001",
                "data_record_id": "DR-UPGRADE-PENDING-RCS",
                "item_code": "RCS_MEAN",
                "old_status": "Pass",
                "new_status": "Pass",
                "flipped": False,
                "task_status": "Pending",
                "old_standard": "V1",
                "new_standard": "V2",
            }
        ]
        project_after_upgrade = client.get("/api/v1/commission/orders/CO-UPGRADE-PENDING-001").json()["data"]["projects"][0]
        assert project_after_upgrade["task_status"] == "Pending"


def test_cq_engine_publish_requires_reviewed_and_returns_export_artifacts():
    with _client() as client:
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]

        draft_publish = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish")

        assert draft_publish.status_code == 400
        assert draft_publish.json()["ok"] is False
        assert draft_publish.json()["error"]["code"] == "CQ_ENGINE_ERROR"

        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})
        publish_response = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish")

        assert publish_response.status_code == 200
        published = publish_response.json()["data"]
        assert published["draft_id"] == created["draft_id"]
        assert published["draft_status"] == "published"
        assert published["exports"]["ontology_id"] == "commission-testing"
        assert published["exports"]["draft_turtle"].startswith("# ontology-id: commission-testing")
        assert published["exports"]["draft_sparql_tests"] == ["CQ-CT-001", "CQ-CT-004"]
        assert [rule["id"] for rule in published["exports"]["candidate_rules"]] == [
            "decompose_project_to_task",
            "judge_less_equal_threshold",
            "mark_task_needs_review_on_flip",
        ]

        listing = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"]
        assert listing[0]["draft_status"] == "published"
