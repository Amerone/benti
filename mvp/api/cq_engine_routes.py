from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from mvp.api import envelope
from mvp.api.exceptions import DomainError
from mvp.core import ontology_draft
from mvp.core.cq_engine import CQEngineError
from mvp.core.ontology_draft import DraftGenerationError


class GenerateDraftRequest(BaseModel):
    business_text: str = Field(description="Business text for commission ontology draft generation")
    generation_mode: str = Field(default="llm_with_template_fallback")


class SaveDraftRequest(BaseModel):
    payload: dict[str, Any] = Field(description="Draft payload to persist")


class UpdateDraftStatusRequest(BaseModel):
    draft_status: str = Field(description="New draft review status")


def create_router() -> APIRouter:
    router = APIRouter(prefix="/cq-engine")

    @router.post("/generate")
    async def generate(payload: GenerateDraftRequest, request: Request):
        try:
            result = await run_in_threadpool(
                ontology_draft.generate_commission_draft,
                business_text=payload.business_text,
                generation_mode=payload.generation_mode,
                provider=request.app.state.llm_provider,
            )
        except DraftGenerationError as exc:
            raise DomainError("CQ_ENGINE_ERROR", str(exc), status=400) from exc
        return envelope.ok(result, trace=request.state.trace)

    @router.get("/drafts")
    async def list_drafts(request: Request):
        result = await run_in_threadpool(request.app.state.cq_draft_service.list_drafts)
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/drafts")
    async def save_draft(payload: SaveDraftRequest, request: Request):
        try:
            result = await run_in_threadpool(request.app.state.cq_draft_service.save_draft, payload.payload)
        except CQEngineError as exc:
            raise _cq_engine_domain_error(exc) from exc
        return envelope.ok(result, trace=request.state.trace)

    @router.patch("/drafts/{draft_id}")
    async def update_draft_status(draft_id: str, payload: UpdateDraftStatusRequest, request: Request):
        try:
            result = await run_in_threadpool(
                request.app.state.cq_draft_service.update_status,
                draft_id,
                payload.draft_status,
            )
        except CQEngineError as exc:
            raise _cq_engine_domain_error(exc) from exc
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/drafts/{draft_id}/publish")
    async def publish_draft(draft_id: str, request: Request):
        try:
            result = await run_in_threadpool(request.app.state.cq_draft_service.publish_draft, draft_id)
        except CQEngineError as exc:
            raise _cq_engine_domain_error(exc) from exc
        return envelope.ok(result, trace=request.state.trace)

    return router


def _cq_engine_domain_error(exc: CQEngineError) -> DomainError:
    message = str(exc)
    if message.startswith("draft not found:"):
        return DomainError("CQ_DRAFT_NOT_FOUND", message, status=404)
    return DomainError("CQ_ENGINE_ERROR", message, status=400)
