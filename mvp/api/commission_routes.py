from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from mvp.api import envelope
from mvp.api.exceptions import DomainError

_LATEST_IMPACT_DEFAULT = {"changed": []}
_SUPPORTED_STANDARD_CODE = "GJB-7821-2024"


def create_router() -> APIRouter:
    router = APIRouter(prefix="/commission")

    @router.post("/demo/reset")
    async def reset_demo(request: Request):
        result = await run_in_threadpool(request.app.state.commission_graph.reset_demo)
        request.app.state.latest_commission_impact = dict(_LATEST_IMPACT_DEFAULT)
        return envelope.ok(result, trace=request.state.trace)

    @router.get("/orders/{order_no}")
    async def get_order(order_no: str, request: Request):
        try:
            result = await run_in_threadpool(request.app.state.commission_graph.get_order, order_no)
        except ValueError as exc:
            raise DomainError("COMMISSION_ORDER_NOT_FOUND", str(exc), status=404) from exc
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/orders/{order_no}/decompose")
    async def decompose_order(order_no: str, request: Request):
        try:
            result = await run_in_threadpool(request.app.state.commission_graph.decompose_order, order_no)
        except ValueError as exc:
            raise DomainError("COMMISSION_ORDER_NOT_FOUND", str(exc), status=404) from exc
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/standards/{standard_code}/upgrade")
    async def upgrade_standard(standard_code: str, request: Request):
        if standard_code != _SUPPORTED_STANDARD_CODE:
            raise DomainError(
                "COMMISSION_STANDARD_NOT_SUPPORTED",
                f"standard not supported: {standard_code}",
                status=400,
            )
        result = await run_in_threadpool(request.app.state.commission_graph.upgrade_standard_to_demo_v2)
        request.app.state.latest_commission_impact = result
        return envelope.ok(result, trace=request.state.trace)

    @router.get("/impacts/latest")
    async def latest_impact(request: Request):
        impact = await run_in_threadpool(request.app.state.commission_graph.latest_impact)
        return envelope.ok(impact, trace=request.state.trace)

    return router
