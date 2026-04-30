from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from rdflib import Literal
from rdflib.namespace import RDF

from mvp.api.main import create_app
from mvp.core import commission_graph
from mvp.core.cq_engine import CQDraftService, CQEngineError
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


def _reviewable_draft_turtle(order_no: str = "CO-EDIT-001", project_id: str = "P-EDIT-001", task_id: str = "T-EDIT-001") -> str:
    return f"""# ontology-id: commission-testing
@prefix cto: <https://hifar.top/cto#> .

<https://hifar.top/cto/individual/order/{order_no}> a cto:CommissionOrder ;
    cto:orderNo "{order_no}" ;
    cto:hasTestProject <https://hifar.top/cto/individual/project/{project_id}> .

<https://hifar.top/cto/individual/project/{project_id}> a cto:TestProject ;
    cto:localId "{project_id}" ;
    cto:decomposesToTask <https://hifar.top/cto/individual/task/{task_id}> .

<https://hifar.top/cto/individual/task/{task_id}> a cto:TestTask ;
    cto:localId "{task_id}" ;
    cto:taskStatus "Draft" .
"""


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


def test_cq_engine_draft_payload_can_be_edited_before_review_and_publish():
    with _client() as client:
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]
        edited_payload = {
            **generated,
            "candidate_cqs": [{"id": "CQ-EDIT-001", "question": "Edited CQ remains traceable"}],
            "draft_turtle": _reviewable_draft_turtle(),
            "draft_sparql_tests": ["CQ-EDIT-001"],
        }

        edit_response = client.patch(
            f"/api/v1/cq-engine/drafts/{created['draft_id']}",
            json={"payload": edited_payload},
        )

        assert edit_response.status_code == 200
        edited = edit_response.json()["data"]
        assert edited["draft_id"] == created["draft_id"]
        assert edited["draft_status"] == "draft"
        assert edited["payload"]["draft_turtle"].startswith("# ontology-id: commission-testing")
        assert edited["payload"]["draft_sparql_tests"] == ["CQ-EDIT-001"]

        listed = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"][0]
        assert listed["payload"] == edited_payload

        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})
        published = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish").json()["data"]
        assert published["exports"]["draft_turtle"].startswith("# ontology-id: commission-testing")
        assert published["exports"]["draft_sparql_tests"] == ["CQ-EDIT-001"]


def test_cq_engine_rejects_invalid_draft_payload_and_keeps_published_drafts_immutable():
    with _client() as client:
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]

        invalid_create = client.post("/api/v1/cq-engine/drafts", json={"payload": {"foo": "bar"}})

        assert invalid_create.status_code == 400
        assert invalid_create.json()["error"]["code"] == "CQ_ENGINE_ERROR"

        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]
        invalid_edit = client.patch(
            f"/api/v1/cq-engine/drafts/{created['draft_id']}",
            json={"payload": {"foo": "bar"}},
        )

        assert invalid_edit.status_code == 400
        assert invalid_edit.json()["error"]["code"] == "CQ_ENGINE_ERROR"

        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})
        published = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish").json()["data"]
        original_turtle = published["exports"]["draft_turtle"]

        mutate_published = client.patch(
            f"/api/v1/cq-engine/drafts/{created['draft_id']}",
            json={
                "payload": {
                    **generated,
                    "draft_turtle": "MUTATED",
                }
            },
        )

        assert mutate_published.status_code == 400
        assert mutate_published.json()["error"]["code"] == "CQ_ENGINE_ERROR"
        listing = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"]
        listed = next(item for item in listing if item["draft_id"] == created["draft_id"])
        assert listed["draft_status"] == "published"
        assert listed["exports"]["draft_turtle"] == original_turtle


def test_cq_engine_rejects_publishing_stored_invalid_draft_payload_without_mutating_status():
    repository = BusinessGraphRepository()
    draft_node = commission_graph._node("draft", "CQD-BAD")
    data_graph = repository.graph("commission-testing", "data")
    data_graph.add((draft_node, RDF.type, commission_graph.CTO.CQDraft))
    data_graph.set((draft_node, commission_graph.CTO.localId, Literal("CQD-BAD")))
    data_graph.set((draft_node, commission_graph.CTO.draftStatus, Literal("reviewed")))
    data_graph.set((draft_node, commission_graph.CTO.draftPayload, Literal('{"foo":"bar"}')))

    with _client_for_repo(repository) as client:
        publish_response = client.post("/api/v1/cq-engine/drafts/CQD-BAD/publish")

        assert publish_response.status_code == 400
        assert publish_response.json()["error"]["code"] == "CQ_ENGINE_ERROR"
        listing = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"]
        listed = next(item for item in listing if item["draft_id"] == "CQD-BAD")
        assert listed["draft_status"] == "reviewed"
        assert "exports" not in listed


def test_cq_engine_rejects_direct_patch_to_published_status():
    with _client() as client:
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]

        direct_publish = client.patch(
            f"/api/v1/cq-engine/drafts/{created['draft_id']}",
            json={"draft_status": "published"},
        )

        assert direct_publish.status_code == 400
        assert direct_publish.json()["error"]["code"] == "CQ_ENGINE_ERROR"
        listed = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"][0]
        assert listed["draft_status"] == "draft"
        assert "exports" not in listed


def test_cq_engine_rejects_mixed_invalid_payload_update_without_partial_status_mutation():
    with _client() as client:
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]

        mixed_update = client.patch(
            f"/api/v1/cq-engine/drafts/{created['draft_id']}",
            json={"draft_status": "reviewed", "payload": {"foo": "bar"}},
        )

        assert mixed_update.status_code == 400
        assert mixed_update.json()["error"]["code"] == "CQ_ENGINE_ERROR"
        listed = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"][0]
        assert listed["draft_status"] == "draft"
        assert listed["payload"] == generated


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
        assert published["release"]["quality_gate"]["passed"] is True
        assert [check["category"] for check in published["release"]["quality_gate"]["checks"]] == [
            "metadata",
            "turtle",
            "shacl",
        ]
        assert [rule["id"] for rule in published["exports"]["candidate_rules"]] == [
            "decompose_project_to_task",
            "judge_less_equal_threshold",
            "mark_task_needs_review_on_flip",
        ]

        listing = client.get("/api/v1/cq-engine/drafts").json()["data"]["items"]
        assert listing[0]["draft_status"] == "published"
        assert listing[0]["exports"]["draft_turtle"].startswith("# ontology-id: commission-testing")
        assert listing[0]["exports"]["draft_sparql_tests"] == ["CQ-CT-001", "CQ-CT-004"]


def test_cq_engine_default_release_root_is_repo_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    service = CQDraftService(repository=BusinessGraphRepository())

    repo_root = Path(__file__).resolve().parents[1]
    assert service.release_root.resolve() == repo_root / "runtime" / "cq-releases"


def test_cq_engine_relative_release_root_override_is_resolved_on_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    service = CQDraftService(repository=BusinessGraphRepository(), release_root="custom-releases")
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

    assert service.release_root == tmp_path / "custom-releases"


def test_cq_engine_publish_writes_release_files_and_lists_history(tmp_path):
    with _client() as client:
        client.app.state.cq_draft_service.release_root = tmp_path / "cq-releases"
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]
        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})

        publish_response = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish")

        assert publish_response.status_code == 200
        published = publish_response.json()["data"]
        release = published["release"]
        assert release["release_id"] == "CQR-001"
        assert release["version"] == "v1"
        assert release["draft_id"] == created["draft_id"]
        assert release["ontology_id"] == "commission-testing"
        assert release["quality_gate"]["passed"] is True
        assert set(release["files"]) == {
            "manifest",
            "draft_turtle",
            "candidate_rules",
            "draft_sparql_tests",
        }

        manifest_path = Path(release["files"]["manifest"])
        turtle_path = Path(release["files"]["draft_turtle"])
        rules_path = Path(release["files"]["candidate_rules"])
        sparql_path = Path(release["files"]["draft_sparql_tests"])
        assert manifest_path.exists()
        assert turtle_path.read_text(encoding="utf-8") == generated["draft_turtle"]
        assert json.loads(rules_path.read_text(encoding="utf-8")) == generated["candidate_rules"]
        assert json.loads(sparql_path.read_text(encoding="utf-8")) == generated["draft_sparql_tests"]

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest == release

        releases_response = client.get("/api/v1/cq-engine/releases")

        assert releases_response.status_code == 200
        releases = releases_response.json()["data"]
        assert releases == {"items": [release], "total": 1}


def test_cq_engine_publish_sync_failure_rolls_back_state_and_release_files(tmp_path):
    repository = BusinessGraphRepository()
    service = create_app(
        repository=repository,
        llm_provider=UnavailableProvider(),
    ).state.cq_draft_service
    service.release_root = tmp_path / "cq-releases"
    generated = {
        "draft_turtle": _reviewable_draft_turtle("CO-SYNC-001", "P-SYNC-001", "T-SYNC-001"),
        "candidate_cqs": [{"id": "CQ-CT-900", "question": "Reviewable sync failure draft"}],
        "candidate_rules": [],
        "draft_sparql_tests": ["CQ-CT-900"],
    }
    created = service.save_draft(generated)
    service.update_draft(created["draft_id"], draft_status="reviewed")

    def fail_sync() -> None:
        raise RuntimeError("remote sync failed")

    service._sync = fail_sync

    try:
        service.publish_draft(created["draft_id"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("publish should surface sync failure")

    listed = service.list_drafts()["items"][0]
    assert listed["draft_status"] == "reviewed"
    assert service.list_releases() == {"items": [], "total": 0}
    assert not list((tmp_path / "cq-releases").glob("commission-testing/CQR-*/manifest.json"))


def test_cq_engine_publish_release_write_failure_does_not_mutate_status(tmp_path):
    repository = BusinessGraphRepository()
    service = create_app(
        repository=repository,
        llm_provider=UnavailableProvider(),
    ).state.cq_draft_service
    service.release_root = tmp_path / "cq-releases"
    generated = {
        "draft_turtle": _reviewable_draft_turtle("CO-WRITE-001", "P-WRITE-001", "T-WRITE-001"),
        "candidate_cqs": [{"id": "CQ-CT-901", "question": "Reviewable write failure draft"}],
        "candidate_rules": [],
        "draft_sparql_tests": ["CQ-CT-901"],
    }
    created = service.save_draft(generated)
    service.update_draft(created["draft_id"], draft_status="reviewed")

    def fail_write(release: dict, exports: dict) -> None:
        raise CQEngineError("disk full")

    service._write_release = fail_write

    try:
        service.publish_draft(created["draft_id"])
    except CQEngineError:
        pass
    else:
        raise AssertionError("publish should surface release write failure")

    listed = service.list_drafts()["items"][0]
    assert listed["draft_status"] == "reviewed"
    assert service.list_releases() == {"items": [], "total": 0}


def test_cq_engine_publish_blocks_untraceable_sparql_tests_without_release(tmp_path):
    repository = BusinessGraphRepository()
    service = create_app(
        repository=repository,
        llm_provider=UnavailableProvider(),
    ).state.cq_draft_service
    service.release_root = tmp_path / "cq-releases"
    generated = {
        "draft_turtle": _reviewable_draft_turtle("CO-TRACE-001", "P-TRACE-001", "T-TRACE-001"),
        "candidate_cqs": [{"id": "CQ-CT-902", "question": "Traceable CQ"}],
        "candidate_rules": [],
        "draft_sparql_tests": ["CQ-CT-MISSING"],
    }
    created = service.save_draft(generated)
    service.update_draft(created["draft_id"], draft_status="reviewed")

    try:
        service.publish_draft(created["draft_id"])
    except CQEngineError as exc:
        assert "draft SPARQL test references unknown candidate CQ: CQ-CT-MISSING" in str(exc)
    else:
        raise AssertionError("publish should block untraceable SPARQL tests")

    listed = service.list_drafts()["items"][0]
    assert listed["draft_status"] == "reviewed"
    assert service.list_releases() == {"items": [], "total": 0}


def test_cq_engine_publish_skips_incomplete_release_directories(tmp_path):
    (tmp_path / "cq-releases" / "commission-testing" / "CQR-001").mkdir(parents=True)
    with _client() as client:
        client.app.state.cq_draft_service.release_root = tmp_path / "cq-releases"
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]
        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})

        publish_response = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish")

        assert publish_response.status_code == 200
        release = publish_response.json()["data"]["release"]
        assert release["release_id"] == "CQR-002"
        assert Path(release["files"]["manifest"]).exists()


def test_cq_engine_publish_continues_after_corrupt_historical_manifest(tmp_path):
    release_root = tmp_path / "cq-releases"
    release_dir = release_root / "commission-testing" / "CQR-001"
    release_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text("{bad-json", encoding="utf-8")

    with _client() as client:
        client.app.state.cq_draft_service.release_root = release_root
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]
        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})

        publish_response = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish")

        assert publish_response.status_code == 200
        release = publish_response.json()["data"]["release"]
        assert release["release_id"] == "CQR-002"
        assert Path(release["files"]["manifest"]).exists()


def test_cq_engine_release_history_sorts_by_numeric_release_id(tmp_path):
    release_root = tmp_path / "cq-releases"
    ontology_root = release_root / "commission-testing"
    for release_id in ["CQR-099", "CQR-1000", "CQR-101"]:
        release_dir = ontology_root / release_id
        release_dir.mkdir(parents=True)
        (release_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "release_id": release_id,
                    "version": f"v{release_id.rsplit('-', 1)[1]}",
                        "draft_id": "CQD-001",
                        "ontology_id": "commission-testing",
                        "published_at": "2026-04-30T00:00:00Z",
                        "files": {
                            "manifest": f"cq-releases/commission-testing/{release_id}/manifest.json",
                            "draft_turtle": f"cq-releases/commission-testing/{release_id}/draft.ttl",
                            "candidate_rules": f"cq-releases/commission-testing/{release_id}/candidate-rules.json",
                            "draft_sparql_tests": f"cq-releases/commission-testing/{release_id}/sparql-tests.json",
                        },
                    }
                ),
                encoding="utf-8",
        )

    service = CQDraftService(repository=BusinessGraphRepository(), release_root=release_root)

    releases = service.list_releases()["items"]
    assert [item["release_id"] for item in releases] == ["CQR-099", "CQR-101", "CQR-1000"]


def test_cq_engine_releases_endpoint_maps_bad_manifest_to_domain_error(tmp_path):
    release_dir = tmp_path / "cq-releases" / "commission-testing" / "CQR-001"
    release_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text("{bad-json", encoding="utf-8")

    with _client() as client:
        client.app.state.cq_draft_service.release_root = tmp_path / "cq-releases"

        response = client.get("/api/v1/cq-engine/releases")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CQ_ENGINE_ERROR"


def test_cq_engine_releases_endpoint_rejects_incomplete_manifest_object(tmp_path):
    release_dir = tmp_path / "cq-releases" / "commission-testing" / "CQR-001"
    release_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text(
        json.dumps({"draft_id": "CQD-001"}),
        encoding="utf-8",
    )

    with _client() as client:
        client.app.state.cq_draft_service.release_root = tmp_path / "cq-releases"

        response = client.get("/api/v1/cq-engine/releases")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CQ_ENGINE_ERROR"


def test_cq_engine_releases_endpoint_rejects_non_object_manifest(tmp_path):
    release_dir = tmp_path / "cq-releases" / "commission-testing" / "CQR-001"
    release_dir.mkdir(parents=True)
    (release_dir / "manifest.json").write_text(json.dumps([]), encoding="utf-8")

    with _client() as client:
        client.app.state.cq_draft_service.release_root = tmp_path / "cq-releases"

        response = client.get("/api/v1/cq-engine/releases")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "CQ_ENGINE_ERROR"


def test_cq_engine_draft_listing_survives_bad_release_manifest(tmp_path):
    with _client() as client:
        client.app.state.cq_draft_service.release_root = tmp_path / "cq-releases"
        generated = client.post(
            "/api/v1/cq-engine/generate",
            json={
                "business_text": "Commission orders decompose into tasks and track standard upgrades.",
                "generation_mode": "template_only",
            },
        ).json()["data"]
        created = client.post("/api/v1/cq-engine/drafts", json={"payload": generated}).json()["data"]
        client.patch(f"/api/v1/cq-engine/drafts/{created['draft_id']}", json={"draft_status": "reviewed"})
        published = client.post(f"/api/v1/cq-engine/drafts/{created['draft_id']}/publish").json()["data"]
        manifest_path = Path(published["release"]["files"]["manifest"])
        manifest_path.write_text("{bad-json", encoding="utf-8")

        response = client.get("/api/v1/cq-engine/drafts")

        assert response.status_code == 200
        listed = response.json()["data"]["items"][0]
        assert listed["draft_status"] == "published"
        assert listed["exports"]["draft_turtle"] == generated["draft_turtle"]
        assert "release" not in listed
