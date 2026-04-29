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
