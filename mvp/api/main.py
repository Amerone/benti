"""FastAPI 应用入口。
本模块把 core 层组合成 `/api/v1` 路由，统一处理 trace、异常和 HTTP 契约。
路由尽量复用既有 core 接口；当 core 的输入输出与 API 契约不完全一致时，只在这里做薄适配。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mvp.api.commission_routes import create_router as create_commission_router
from mvp.api.cq_engine_routes import create_router as create_cq_engine_router
from mvp.api import envelope, exceptions
from mvp.api.exceptions import DomainError
from mvp.api.trace_middleware import TraceMiddleware
from mvp.core.commission_graph import CommissionGraphService
from mvp.core.cq_engine import CQDraftService
from mvp.core import graph, inference, owlready_reasoner, parameters, qa
from mvp.core.llm.base import LLMProvider
from mvp.core.llm.factory import get_provider
from mvp.core.ontology_registry import OntologyDescriptor
from mvp.core.sparql_client import DEFAULT_BASE_URL, FusekiClient

try:
    import owlready2
except ImportError:  # pragma: no cover - 依赖未安装时健康检查走降级
    owlready2 = None


class LoadOntologiesRequest(BaseModel):
    """本体加载请求。"""

    reload: bool = Field(default=True, description="是否仅覆盖 ontology 图")


class ReasonRequest(BaseModel):
    """Pellet 推理请求。"""

    force: bool = Field(default=False, description="是否跳过缓存强制执行")


class ParameterCreateRequest(BaseModel):
    """参数注册请求。"""

    ontology_id: str = Field(description="本体 ID")
    code: str = Field(description="参数编码")
    name: str | None = Field(default=None, description="参数名称")
    unit: str | None = Field(default=None, description="单位")
    value_type: str = Field(default="number", description="值类型")
    participates_in_inference: bool = Field(default=True, description="是否参与推理")


class MeasurementCreateRequest(BaseModel):
    """测量录入请求。"""

    ontology_id: str = Field(description="本体 ID")
    measurement_id: str = Field(description="测量记录 ID")
    batch: str = Field(description="批次 ID")
    parameter: str = Field(description="参数编码")
    value: float = Field(description="测量值")
    measured_at: str | None = Field(default=None, description="测量时间")
    enable_swrl: bool = Field(default=False, description="是否启用 SWRL 对照模式")


class SpecificationCreateRequest(BaseModel):
    """规格创建或变更请求。"""

    ontology_id: str = Field(description="本体 ID")
    parameter: str = Field(description="参数编码")
    lower: float = Field(description="下限")
    upper: float = Field(description="上限")
    reason: str = Field(default="", description="变更原因")
    effective_from: str | None = Field(default=None, description="生效时间")


class QARequest(BaseModel):
    """问答请求。"""

    ontology_id: str | None = Field(default=None, description="本体 ID")
    question: str = Field(description="自然语言问题")


class ApiGraphAdapter:
    """为 QA 路由提供最小图谱读取适配。"""

    def __init__(self, repository: graph.BusinessGraphRepository, impacts: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.repository = repository
        self.impacts = impacts

    def graph_iri(self, ontology_id: str, kind: str = "ontology") -> str:
        return graph.graph_iri(ontology_id, kind)

    def get_qa_evidence(self, ontology_id: str, intent_name: str, params: dict[str, str]) -> list[dict[str, Any]]:
        if intent_name in {"why_fail", "why_judgement"}:
            measurement = self.repository.get_measurement(ontology_id, params["measurement_id"])
            if measurement is None:
                return []
            latest = self.repository.latest_result_for_measurement(ontology_id, params["measurement_id"])
            if latest is None:
                return [{"measurement_id": params["measurement_id"], "missing": True}]
            spec = _find_specification(self.repository, ontology_id, measurement["parameter"], latest.spec_version)
            return [
                {
                    "measurement_id": params["measurement_id"],
                    "value": measurement["value"],
                    "status": latest.status,
                    "rule": latest.rule,
                    "spec_version": latest.spec_version,
                    "lower_limit": None if spec is None else spec["lower"],
                    "upper_limit": None if spec is None else spec["upper"],
                    "deviation": latest.deviation,
                    "reasoner": latest.reasoner,
                    "inferred_at": latest.inferred_at,
                }
            ]

        if intent_name == "spec_change_impact":
            for impact in self.impacts.values():
                if impact["old_spec"] == params["old_spec"] and impact["new_spec"] == params["new_spec"]:
                    return impact["changed"]
            return []

        if intent_name == "parameter_or_batch_summary":
            items = self.repository.list_measurements(ontology_id)["items"]
            counts: dict[str, int] = {}
            for item in items:
                if "parameter_code" in params and item["parameter"] != params["parameter_code"]:
                    continue
                if "batch_id" in params and item["batch"] != params["batch_id"]:
                    continue
                status = item.get("status")
                if status is None:
                    continue
                counts[status] = counts.get(status, 0) + 1
            return [{"status": status, "count": count} for status, count in sorted(counts.items())]

        return []


def create_app(
    *,
    repository: graph.BusinessGraphRepository | None = None,
    llm_provider: LLMProvider | None = None,
    fuseki_client: FusekiClient | None = None,
) -> FastAPI:
    """创建 FastAPI 应用。"""

    active_fuseki_client = fuseki_client or FusekiClient()
    active_repository = repository or graph.BusinessGraphRepository(client=active_fuseki_client)
    if repository is not None and repository.client is None and fuseki_client is not None:
        repository.client = fuseki_client

    app = FastAPI(title="Manufacturing Trial Ontology MVP API")
    app.state.repository = active_repository
    app.state.llm_provider = llm_provider or get_provider()
    app.state.fuseki_client = getattr(app.state.repository, "client", None) or active_fuseki_client
    app.state.active_ontology_id = None
    app.state.latest_impacts = {}
    app.state.commission_graph = CommissionGraphService(repository=active_repository)
    app.state.cq_draft_service = CQDraftService(repository=active_repository)
    app.state.latest_commission_impact = {"changed": []}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TraceMiddleware)
    exceptions.install(app)

    router = APIRouter(prefix="/api/v1")

    @router.get("/health")
    async def health(request: Request):
        """检查 Fuseki、Owlready2、Pellet/Java 和 LLM 的可用性。"""

        trace = request.state.trace
        fuseki_state = await _probe_fuseki(app.state.fuseki_client, trace)
        owlready_state = _probe_owlready(trace)
        reasoner_state = _probe_reasoner(trace)
        llm_state = _probe_llm(app.state.llm_provider, trace)
        return envelope.ok(
            {
                "fuseki": fuseki_state,
                "owlready": owlready_state,
                "reasoner": reasoner_state,
                "llm": llm_state,
            },
            trace=trace,
        )

    @router.get("/ontologies")
    async def list_ontologies(request: Request):
        """列出本地可发现本体及其当前加载状态。"""

        trace = request.state.trace
        items = await run_in_threadpool(graph.list_ontologies, repository=app.state.repository, trace=trace)
        return envelope.ok(items, trace=trace)

    @router.post("/ontologies/load")
    async def load_ontologies(payload: LoadOntologiesRequest, request: Request):
        """把本地本体加载到图谱仓储中；`reload=true` 仅覆盖 ontology 图。"""

        trace = request.state.trace
        result = await run_in_threadpool(
            graph.load_ontologies,
            reload=payload.reload,
            repository=app.state.repository,
            trace=trace,
        )
        return envelope.ok({**result, "reload": payload.reload}, trace=trace)

    @router.get("/ontologies/{ontology_id}/subjects")
    async def ontology_subjects(
        ontology_id: str,
        request: Request,
        q: str | None = Query(default=None, description="名称过滤关键字"),
        limit: int = Query(default=200, ge=1, le=1000, description="每类返回上限"),
    ):
        """从 ontology 图构造 Turtle，并用 Owlready2 读取主体结构。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        turtle_text = await run_in_threadpool(
            graph.construct_ontology_turtle,
            ontology_id,
            repository=app.state.repository,
            trace=trace,
        )
        result = await run_in_threadpool(
            owlready_reasoner.load_and_reason,
            ontology_id,
            turtle_text,
            run_pellet=False,
            trace=trace,
        )
        filtered = _filter_subject_payload(result, q=q, limit=limit)
        trace.log("subjects_filter", "success", reason="按 q/limit 过滤主体返回结果", q=q or "", limit=limit)
        return envelope.ok(filtered, trace=trace)

    @router.post("/ontologies/{ontology_id}/reason")
    async def ontology_reason(ontology_id: str, payload: ReasonRequest, request: Request):
        """显式触发当前本体的 Pellet 推理。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        turtle_text = await run_in_threadpool(
            graph.construct_ontology_turtle,
            ontology_id,
            repository=app.state.repository,
            trace=trace,
        )
        result = await run_in_threadpool(
            owlready_reasoner.load_and_reason,
            ontology_id,
            turtle_text,
            run_pellet=True,
            force=payload.force,
            trace=trace,
        )
        return envelope.ok(result, trace=trace)

    @router.post("/ontologies/{ontology_id}/activate")
    async def activate_ontology(ontology_id: str, request: Request):
        """仅为演示记录当前激活本体；正式请求仍必须显式传 ontology_id。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        app.state.active_ontology_id = ontology_id
        trace.log("activate_ontology", "success", reason="仅在 API 进程内记录当前演示用本体", ontology_id=ontology_id)
        return envelope.ok(
            {
                "active_ontology_id": ontology_id,
                "note": "仅用于演示；客户端必须在后续请求中显式携带 ontology_id",
            },
            trace=trace,
        )

    @router.get("/parameters")
    async def get_parameters(request: Request, ontology_id: str = Query(..., description="本体 ID")):
        """列出指定本体下已注册参数。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        items = await run_in_threadpool(parameters.list_parameters, ontology_id, repository=app.state.repository, trace=trace)
        return envelope.ok(items, trace=trace)

    @router.post("/parameters")
    async def post_parameters(payload: ParameterCreateRequest, request: Request):
        """运行时注册参数，不修改固定 schema。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, payload.ontology_id)
        result = await run_in_threadpool(
            parameters.register_parameter,
            payload.ontology_id,
            code=payload.code,
            name=payload.name,
            unit=payload.unit,
            value_type=payload.value_type,
            participates_in_inference=payload.participates_in_inference,
            repository=app.state.repository,
            trace=trace,
        )
        return envelope.ok({"code": result["code"], "created": result["created"]}, trace=trace)

    @router.get("/measurements")
    async def get_measurements(
        request: Request,
        ontology_id: str = Query(..., description="本体 ID"),
        parameter: str | None = Query(default=None, description="参数编码"),
        limit: int = Query(default=200, ge=1, le=1000, description="最大返回数量"),
    ):
        """列出测量与其最新判定结果。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        result = await run_in_threadpool(
            graph.list_measurements,
            ontology_id,
            parameter=parameter,
            repository=app.state.repository,
        )
        return envelope.ok({"items": result["items"][:limit], "total": result["total"]}, trace=trace)

    @router.post("/measurements")
    async def post_measurements(payload: MeasurementCreateRequest, request: Request):
        """录入测量并复用 core 的确定性推理接口。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, payload.ontology_id)
        trace.log("create_and_infer", "started", reason="调用 core 复合接口执行测量录入与判定")
        result = await run_in_threadpool(
            graph.create_and_infer,
            payload.ontology_id,
            payload.measurement_id,
            batch_id=payload.batch,
            parameter_code=payload.parameter,
            value=payload.value,
            measured_at=payload.measured_at,
            repository=app.state.repository,
            trace=trace,
        )
        if payload.enable_swrl and result.get("status") != "not_inferred":
            descriptor = _get_descriptor(app.state.repository, payload.ontology_id)
            compare_result = await _run_swrl_compare(
                app.state.repository,
                payload.ontology_id,
                payload.measurement_id,
                descriptor=descriptor,
                trace=trace,
            )
            if compare_result is not None:
                result["compare_result"] = compare_result
        trace.log("create_and_infer", "success", reason="复合接口执行完成", measurement_id=payload.measurement_id)
        return envelope.ok(result, trace=trace)

    @router.post("/specifications")
    async def post_specifications(payload: SpecificationCreateRequest, request: Request):
        """创建首个或新的规格版本。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, payload.ontology_id)
        result = await run_in_threadpool(
            graph.create_specification,
            payload.ontology_id,
            payload.parameter,
            lower=payload.lower,
            upper=payload.upper,
            reason=payload.reason,
            effective_from=payload.effective_from,
            repository=app.state.repository,
            trace=trace,
        )
        return envelope.ok({"spec_version": result["spec_version"], "created": result["created"]}, trace=trace)

    @router.get("/specifications")
    async def get_specifications(
        request: Request,
        ontology_id: str = Query(..., description="本体 ID"),
        parameter: str | None = Query(default=None, description="参数编码"),
        limit: int = Query(default=200, ge=1, le=1000, description="最大返回数量"),
    ):
        """列出规格历史，包含版本、上下限、变更原因和版本继承关系。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        result = await run_in_threadpool(
            graph.list_specifications,
            ontology_id,
            parameter=parameter or None,
            repository=app.state.repository,
        )
        items = list(result.get("items") or [])
        return envelope.ok({"items": items[:limit], "total": len(items)}, trace=trace)

    @router.post("/specifications/change")
    async def change_specifications(payload: SpecificationCreateRequest, request: Request):
        """规格变更后重跑历史测量，并返回差异摘要。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, payload.ontology_id)
        previous = app.state.repository.latest_specification(payload.ontology_id, payload.parameter)
        result = await run_in_threadpool(
            inference.rerun_after_spec_change,
            payload.ontology_id,
            payload.parameter,
            new_lower=payload.lower,
            new_upper=payload.upper,
            reason=payload.reason,
            effective_from=payload.effective_from,
            repository=app.state.repository,
            trace=trace,
        )
        impact = {
            "old_spec": None if previous is None else previous["spec_version"],
            "new_spec": result["spec_version"],
            "changed": result["changed"],
            "generated_at": _utc_now(),
        }
        app.state.latest_impacts[(payload.ontology_id, payload.parameter)] = impact
        return envelope.ok({**result, **impact}, trace=trace)

    @router.get("/impacts/latest")
    async def impacts_latest(
        request: Request,
        ontology_id: str = Query(..., description="本体 ID"),
        parameter: str = Query(..., description="参数编码"),
    ):
        """读取最近一次规格变更生成的差异报告。"""

        trace = request.state.trace
        _get_descriptor(app.state.repository, ontology_id)
        impact = app.state.latest_impacts.get(
            (ontology_id, parameter),
            {"old_spec": None, "new_spec": None, "changed": [], "generated_at": None},
        )
        trace.log("load_latest_impact", "success", reason="读取 API 层最近一次规格变更摘要缓存", parameter=parameter)
        return envelope.ok(impact, trace=trace)

    @router.post("/qa")
    async def qa_endpoint(payload: QARequest, request: Request):
        """基于结构化 evidence 回答白名单问题；缺失 ontology_id 直接报错。"""

        trace = request.state.trace
        ontology_id = _require_ontology_id(payload.ontology_id)
        _get_descriptor(app.state.repository, ontology_id)
        adapter = ApiGraphAdapter(app.state.repository, app.state.latest_impacts)
        result = await run_in_threadpool(
            qa.answer,
            adapter,
            ontology_id,
            payload.question,
            provider=app.state.llm_provider,
            trace=trace,
        )
        return envelope.ok(result, trace=trace)

    router.include_router(create_commission_router())
    router.include_router(create_cq_engine_router())

    app.include_router(router)
    return app


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_ontology_id(ontology_id: str | None) -> str:
    if ontology_id is None or not ontology_id.strip():
        raise DomainError("ONTOLOGY_ID_REQUIRED", "正式请求必须显式携带 ontology_id", status=400)
    return ontology_id.strip()


def _get_descriptor(repository: graph.BusinessGraphRepository, ontology_id: str) -> OntologyDescriptor:
    for descriptor in repository.registry.discover():
        if descriptor.ontology_id == ontology_id:
            return descriptor
    raise DomainError("ONTOLOGY_NOT_FOUND", f"未找到本体: {ontology_id}", status=404)


def _find_specification(
    repository: graph.BusinessGraphRepository,
    ontology_id: str,
    parameter_code: str,
    spec_version: str,
) -> dict[str, Any] | None:
    for item in repository.list_specifications(ontology_id, parameter_code)["items"]:
        if item["spec_version"] == spec_version:
            return item
    return None


def _filter_subject_payload(result: dict[str, Any], *, q: str | None, limit: int) -> dict[str, Any]:
    """按 API 契约过滤 subjects 响应。"""

    if not q:
        return {
            **result,
            "classes": list(result.get("classes") or [])[:limit],
            "individuals": list(result.get("individuals") or [])[:limit],
            "object_properties": list(result.get("object_properties") or [])[:limit],
            "data_properties": list(result.get("data_properties") or [])[:limit],
        }

    lowered = q.lower()

    def _matched(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = []
        for item in items:
            haystack = " ".join(str(value) for value in item.values()).lower()
            if lowered in haystack:
                filtered.append(item)
        return filtered[:limit]

    return {
        **result,
        "classes": _matched(list(result.get("classes") or [])),
        "individuals": _matched(list(result.get("individuals") or [])),
        "object_properties": _matched(list(result.get("object_properties") or [])),
        "data_properties": _matched(list(result.get("data_properties") or [])),
    }


async def _run_swrl_compare(
    repository: graph.BusinessGraphRepository,
    ontology_id: str,
    measurement_id: str,
    *,
    descriptor: OntologyDescriptor,
    trace: Any,
) -> dict[str, Any] | None:
    """执行 MVP 对照模式，并为同一测量补写平行 `pellet-swrl` Result。"""

    measurement = repository.get_measurement(ontology_id, measurement_id)
    if measurement is None:
        return None
    specification = repository.latest_specification(ontology_id, measurement["parameter"])
    if specification is None:
        return None

    turtle_text = await run_in_threadpool(
        graph.construct_reasoning_turtle,
        ontology_id,
        repository=repository,
        trace=trace,
    )
    reasoner_result = await run_in_threadpool(
        owlready_reasoner.load_and_reason,
        ontology_id,
        turtle_text,
        run_pellet=True,
        trace=trace,
        enable_swrl=True,
        swrl_path=descriptor.swrl_path,
    )
    if reasoner_result.get("pellet_status") != "success":
        trace.log(
            "swrl_compare",
            "fallback",
            reason="SWRL 对照模式未生成平行 Result，因为 Pellet 未成功执行。",
            pellet_status=reasoner_result.get("pellet_status"),
        )
        return {
            "reasoner": "pellet-swrl",
            "swrl_status": reasoner_result.get("swrl_status"),
            "pellet_status": reasoner_result.get("pellet_status"),
            "saved": False,
        }

    judgement = inference.evaluate_single(
        measurement["value"],
        specification["lower"],
        specification["upper"],
        specification["spec_version"],
        trace=trace,
    )
    compare = await run_in_threadpool(
        graph.save_inference_result,
        ontology_id,
        measurement_id,
        status=judgement.status,
        rule=judgement.rule,
        spec_version=judgement.spec_version,
        deviation=judgement.deviation,
        reasoner="pellet-swrl",
        evidence_value=measurement["value"],
        evidence_lower_limit=specification["lower"],
        evidence_upper_limit=specification["upper"],
        repository=repository,
        trace=trace,
        update_latest=False,
        link_previous=False,
    )
    trace.log(
        "swrl_compare",
        "success",
        reason="SWRL 对照模式为同一 Measurement 补写平行 pellet-swrl Result。",
        measurement_id=measurement_id,
    )
    return {
        **compare,
        "swrl_status": reasoner_result.get("swrl_status"),
        "pellet_status": reasoner_result.get("pellet_status"),
        "saved": True,
    }


async def _probe_fuseki(client: FusekiClient, trace: Any) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    available = await run_in_threadpool(client.ping)
    latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    trace.log(
        "probe_fuseki",
        "success" if available else "fallback",
        reason="Fuseki 不可用时健康检查只降级，不抛 5xx",
        available=available,
    )
    return {
        "available": available,
        "base_url": getattr(client, "base_url", DEFAULT_BASE_URL),
        "latency_ms": latency_ms,
    }


def _probe_owlready(trace: Any) -> dict[str, Any]:
    available = owlready2 is not None
    trace.log(
        "probe_owlready",
        "success" if available else "fallback",
        reason="Owlready2 依赖不可用时返回健康明细",
        available=available,
    )
    return {
        "available": available,
        "version": None if owlready2 is None else getattr(owlready2, "__version__", "unknown"),
    }


def _probe_reasoner(trace: Any) -> dict[str, Any]:
    runtime = owlready_reasoner.describe_java_runtime()
    java_path = runtime.get("java_exe")
    pellet_available = java_path is not None
    trace.log(
        "probe_java_or_pellet",
        "success" if pellet_available else "fallback",
        reason="Pellet 依赖 Java；缺失时只做能力降级",
        java_path=java_path,
        java_source=runtime.get("source"),
    )
    return {
        "deterministic": True,
        "pellet": "available" if pellet_available else "missing_java",
        "pellet_error": None if pellet_available else runtime.get("error") or "java not found",
        "java_exe": java_path,
        "java_source": runtime.get("source"),
    }


def _probe_llm(provider: LLMProvider, trace: Any) -> dict[str, Any]:
    available = provider.available()
    trace.log(
        "probe_llm",
        "success" if available else "fallback",
        reason="LLM 不可用时问答走 local_fallback",
        provider=getattr(provider, "name", "unknown"),
    )
    return {
        "provider": getattr(provider, "name", "unknown"),
        "available": available,
        "model": getattr(provider, "default_model", None),
    }


app = create_app()
