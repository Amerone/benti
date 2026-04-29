"""业务图谱访问层。

本模块负责按本体的 ontology/data/result/spec 四类 named graph 读写业务数据。
实现优先复用已有 `ontology_registry` 与 `sparql_client`；同时保留内存 RDF 后端，
保证 Fuseki 未启动时普通 pytest 仍可覆盖确定性推理和参数校验。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from mvp.core.ontology_registry import OntologyDescriptor, OntologyRegistry, graph_iri_for

MTO = Namespace("https://hifar.top/mto#")
INDIVIDUAL_BASE = "https://hifar.top/mto/individual"
VALID_GRAPH_KINDS = {"ontology", "data", "result", "spec"}
DECIMAL_RANGE_PREDICATES = {
    MTO.deviation,
    MTO.evidenceLowerLimit,
    MTO.evidenceUpperLimit,
    MTO.evidenceValue,
    MTO.lowerLimit,
    MTO.measuredValue,
    MTO.measurementValue,
    MTO.upperLimit,
}
DATETIME_RANGE_PREDICATES = {
    MTO.createdAt,
    MTO.effectiveFrom,
    MTO.inferredAt,
    MTO.judgedAt,
    MTO.measuredAt,
    MTO.measurementTime,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log_step(trace: Any, step: str, status: str = "success", reason: str = "", **detail: Any) -> None:
    if trace is not None and hasattr(trace, "log"):
        trace.log(step, status, reason=reason, **detail)


def _node(ontology_id: str, category: str, local_id: str) -> URIRef:
    return URIRef(f"{INDIVIDUAL_BASE}/{ontology_id}/{category}/{quote(str(local_id), safe='')}")


def _coerce_number(value: float | int, field: str) -> float:
    if value is None:
        raise ValueError(f"{field} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _decimal_literal(value: float | int) -> Literal:
    return Literal(Decimal(str(_coerce_number(value, "value"))), datatype=XSD.decimal)


def _datetime_literal(value: Any) -> Literal:
    if isinstance(value, datetime):
        value = value.isoformat().replace("+00:00", "Z")
    return Literal(str(value), datatype=XSD.dateTime)


def _replace_literal(graph: Graph, subject: URIRef, predicate: URIRef, value: Any) -> None:
    graph.remove((subject, predicate, None))
    graph.add((subject, predicate, Literal(value)))


def _replace_object(graph: Graph, subject: URIRef, predicate: URIRef, value: URIRef | Literal) -> None:
    graph.remove((subject, predicate, None))
    graph.add((subject, predicate, value))


def _remove_node_mentions(graph: Graph, node: URIRef) -> int:
    """Remove triples where node appears as subject or object and return removed count."""

    before = len(graph)
    graph.remove((node, None, None))
    graph.remove((None, None, node))
    return before - len(graph)


def _first_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> Any:
    obj = next(graph.objects(subject, predicate), None)
    return obj.toPython() if isinstance(obj, Literal) else obj


def _first_literal_text(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    obj = next(graph.objects(subject, predicate), None)
    if not isinstance(obj, Literal):
        return None
    text = str(obj)
    if obj.datatype == XSD.dateTime and text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def _first_object(graph: Graph, subject: URIRef, predicate: URIRef) -> URIRef | None:
    obj = next(graph.objects(subject, predicate), None)
    return obj if isinstance(obj, URIRef) else None


def _bool_value(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"true", "1", "yes"}


def _normalize_pellet_literal_datatypes(target_graph: Graph) -> None:
    for predicate in DECIMAL_RANGE_PREDICATES:
        for subject, _, obj in list(target_graph.triples((None, predicate, None))):
            if isinstance(obj, Literal):
                target_graph.remove((subject, predicate, obj))
                target_graph.add((subject, predicate, _decimal_literal(obj.toPython())))

    for predicate in DATETIME_RANGE_PREDICATES:
        for subject, _, obj in list(target_graph.triples((None, predicate, None))):
            if isinstance(obj, Literal):
                target_graph.remove((subject, predicate, obj))
                target_graph.add((subject, predicate, _datetime_literal(obj.toPython())))


def _local_id_from_node(node: URIRef | str | None) -> str:
    if not node:
        return ""
    return str(node).rstrip("/").split("/")[-1]


def _version_number(version: str) -> int:
    try:
        return int(version.replace("Spec_v", ""))
    except ValueError:
        return 0


def _spec_version_from_id(spec_id: str, parameter_code: str) -> str:
    prefix = f"{parameter_code}_"
    if spec_id.startswith(prefix):
        return spec_id[len(prefix):]
    marker = "_Spec_v"
    if marker in spec_id:
        return f"Spec_v{spec_id.rsplit(marker, 1)[1]}"
    return spec_id


def _copy_triples(source: Graph, target: Graph) -> None:
    for triple in source:
        target.add(triple)


def _typed_subjects(graph: Graph, rdf_type: URIRef) -> set[URIRef]:
    return {subject for subject in graph.subjects(RDF.type, rdf_type) if isinstance(subject, URIRef)}


def graph_iri(ontology_id: str, kind: str = "ontology") -> str:
    """返回单 dataset 下某本体的 named graph IRI。"""

    if kind not in VALID_GRAPH_KINDS:
        raise ValueError(f"kind must be one of {sorted(VALID_GRAPH_KINDS)}")
    return graph_iri_for(ontology_id, kind)


@dataclass(frozen=True)
class ResultRecord:
    """最新 Result 摘要。"""

    result_id: str
    status: str
    rule: str
    spec_version: str
    deviation: float
    reasoner: str
    inferred_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "status": self.status,
            "rule": self.rule,
            "spec_version": self.spec_version,
            "deviation": self.deviation,
            "reasoner": self.reasoner,
            "inferred_at": self.inferred_at,
        }


class BusinessGraphRepository:
    """业务图谱仓储。

    仓储默认维护内存 named graph；当注入 Fuseki client 时，会在关键写路径同步执行
    远端 PUT/CONSTRUCT，从而兼顾普通单元测试与后续集成环境。
    """

    def __init__(
        self,
        *,
        registry: OntologyRegistry | None = None,
        client: Any | None = None,
        ontology_dir: str | Path | None = None,
    ) -> None:
        self.registry = registry or OntologyRegistry(ontology_dir or OntologyRegistry().ontology_dir)
        self.client = client
        self._graphs: dict[tuple[str, str], Graph] = {}
        self._ontologies: dict[str, OntologyDescriptor] = {}

    def graph(self, ontology_id: str, kind: str = "ontology") -> Graph:
        """获取某个 named graph 的内存表示。"""

        graph_iri(ontology_id, kind)
        key = (ontology_id, kind)
        if key not in self._graphs:
            local_graph = Graph()
            local_graph.bind("mto", MTO)
            local_graph.bind("rdfs", RDFS)
            self._graphs[key] = local_graph
            self._hydrate_graph_from_remote(ontology_id, kind, local_graph)
        return self._graphs[key]

    def _hydrate_graph_from_remote(self, ontology_id: str, kind: str, target: Graph) -> None:
        """在有 Fuseki client 时，按 named graph 回填远端已有数据。"""

        if self.client is None:
            return
        sparql = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph_iri(ontology_id, kind)}> {{ ?s ?p ?o }} }}"
        try:
            turtle_text = self.client.construct(sparql)
        except Exception:
            return
        if turtle_text and str(turtle_text).strip():
            target.parse(data=turtle_text, format="turtle")

    def _sync_graph_to_remote(self, ontology_id: str, kind: str) -> None:
        """把某个 named graph 的当前内容整体同步到 Fuseki。"""

        if self.client is None:
            return
        self.client.upload_graph(graph_iri(ontology_id, kind), self.serialize_graph(ontology_id, kind))

    def count_graph(self, ontology_id: str, kind: str = "ontology") -> int:
        """返回指定图的三元组数量。"""

        return len(self.graph(ontology_id, kind))

    def serialize_graph(self, ontology_id: str, kind: str = "ontology") -> str:
        """序列化某个图为 Turtle 文本。"""

        return self.graph(ontology_id, kind).serialize(format="turtle")

    def reset_cq_fixture(
        self,
        ontology_id: str,
        *,
        measurement_ids: list[str],
        parameter_code: str,
        spec_versions: list[str],
    ) -> dict[str, int]:
        """Delete only the fixed CQ fixture scope from data/spec/result graphs."""

        data_graph = self.graph(ontology_id, "data")
        spec_graph = self.graph(ontology_id, "spec")
        result_graph = self.graph(ontology_id, "result")

        measurement_nodes = [_node(ontology_id, "measurement", measurement_id) for measurement_id in measurement_ids]
        result_nodes: set[URIRef] = set()
        for measurement_node in measurement_nodes:
            result_nodes.update(node for node in result_graph.objects(measurement_node, MTO.hasLatestResult) if isinstance(node, URIRef))
            result_nodes.update(node for node in result_graph.subjects(MTO.forMeasurement, measurement_node) if isinstance(node, URIRef))

        removed = {"measurements": 0, "parameters": 0, "specifications": 0, "results": 0}
        for measurement_node in measurement_nodes:
            removed["measurements"] += int(_remove_node_mentions(data_graph, measurement_node) > 0)
            _remove_node_mentions(result_graph, measurement_node)

        for result_node in sorted(result_nodes, key=str):
            removed["results"] += int(_remove_node_mentions(result_graph, result_node) > 0)

        parameter_node = _node(ontology_id, "parameter", parameter_code)
        parameter_still_used = any(data_graph.subjects(MTO.forParameter, parameter_node))
        if not parameter_still_used:
            removed["parameters"] += int(_remove_node_mentions(data_graph, parameter_node) > 0)
            spec_nodes = {
                _node(ontology_id, "specification", f"{parameter_code}_{spec_version}")
                for spec_version in spec_versions
            }
            for spec_node in sorted(spec_nodes, key=str):
                removed["specifications"] += int(_remove_node_mentions(spec_graph, spec_node) > 0)

        self._sync_graph_to_remote(ontology_id, "data")
        self._sync_graph_to_remote(ontology_id, "spec")
        self._sync_graph_to_remote(ontology_id, "result")
        return removed

    def load_ontologies(self, *, reload: bool = True, trace: Any | None = None) -> dict[str, Any]:
        """加载本地发现的 TTL 到 ontology graph。

        `reload=True` 只覆盖 ontology 图，不触碰 data/result/spec 图，满足验收中的
        reload 语义。
        """

        descriptors = self.registry.discover()
        loaded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        _log_step(trace, "scan_dir", reason="扫描本地 TTL 本体文件", count=len(descriptors))
        for descriptor in descriptors:
            self._ontologies[descriptor.ontology_id] = descriptor
            try:
                ttl_text = Path(descriptor.ttl_path).read_text(encoding="utf-8")
                target = self.graph(descriptor.ontology_id, "ontology")
                if reload:
                    target.remove((None, None, None))
                target.parse(data=ttl_text, format="turtle")
                if self.client is not None:
                    self.client.upload_graph(descriptor.graph_iri, ttl_text)
                loaded.append(
                    {
                        "ontology_id": descriptor.ontology_id,
                        "graph_iri": descriptor.graph_iri,
                        "triples": len(target),
                        "ontology_graph_written": len(target),
                        "data_graph_preserved": True,
                    }
                )
                _log_step(trace, "upload_graph", reason="使用 GSP PUT 覆盖 ontology 图", ontology_id=descriptor.ontology_id)
            except Exception as exc:  # pragma: no cover - 远端 Fuseki/TTL 解析异常
                failed.append({"ontology_id": descriptor.ontology_id, "error": str(exc)})
        return {"loaded": loaded, "failed": failed}

    def list_ontologies(self, *, trace: Any | None = None) -> list[dict[str, Any]]:
        """列出本体描述与当前加载状态。"""

        for descriptor in self.registry.discover():
            self._ontologies.setdefault(descriptor.ontology_id, descriptor)
        _log_step(trace, "list_ontologies", reason="返回本体注册信息", count=len(self._ontologies))
        items = []
        for descriptor in sorted(self._ontologies.values(), key=lambda item: item.ontology_id):
            items.append(
                {
                    **descriptor.to_dict(),
                    "loaded": self.count_graph(descriptor.ontology_id, "ontology") > 0,
                    "triples": self.count_graph(descriptor.ontology_id, "ontology"),
                }
            )
        return items

    def construct_ontology_turtle(self, ontology_id: str, *, trace: Any | None = None) -> str:
        """仅构造 ontology 图的 Turtle，避免把运行时业务图送进语义加载器。"""

        if self.client is not None:
            sparql = f"CONSTRUCT {{ ?s ?p ?o }} WHERE {{ GRAPH <{graph_iri(ontology_id)}> {{ ?s ?p ?o }} }}"
            _log_step(trace, "construct_ontology_turtle", reason="从 Fuseki ontology graph 生成 Turtle")
            return self.client.construct(sparql)
        _log_step(trace, "construct_ontology_turtle", reason="从内存 ontology graph 生成 Turtle")
        return self.serialize_graph(ontology_id, "ontology")

    def construct_reasoning_turtle(self, ontology_id: str, *, trace: Any | None = None) -> str:
        """构造 Pellet 业务推理输入：ontology + 参与推理参数的数据/规格事实。"""

        reasoning_graph = Graph()
        reasoning_graph.bind("mto", MTO)
        reasoning_graph.bind("rdfs", RDFS)
        reasoning_graph.bind("rdf", RDF)
        reasoning_graph.bind("xsd", XSD)

        _copy_triples(self.graph(ontology_id, "ontology"), reasoning_graph)

        data_graph = self.graph(ontology_id, "data")
        spec_graph = self.graph(ontology_id, "spec")
        parameter_nodes = _typed_subjects(data_graph, MTO.Parameter)
        measurement_nodes = _typed_subjects(data_graph, MTO.Measurement)
        spec_nodes = _typed_subjects(spec_graph, MTO.Specification)

        inference_parameters = {
            node
            for node in parameter_nodes
            if _bool_value(_first_literal(data_graph, node, MTO.participatesInInference), default=True)
        }
        inference_measurements = {
            node
            for node in measurement_nodes
            if _first_object(data_graph, node, MTO.forParameter) in inference_parameters
        }
        inference_specs = {
            node
            for node in spec_nodes
            if _first_object(spec_graph, node, MTO.forParameter) in inference_parameters
        }

        for subject, predicate, obj in data_graph:
            if subject in parameter_nodes and subject not in inference_parameters:
                continue
            if obj in parameter_nodes and obj not in inference_parameters:
                continue
            if subject in measurement_nodes and subject not in inference_measurements:
                continue
            if obj in measurement_nodes and obj not in inference_measurements:
                continue
            reasoning_graph.add((subject, predicate, obj))

        for subject, predicate, obj in spec_graph:
            if subject in spec_nodes and subject not in inference_specs:
                continue
            if obj in spec_nodes and obj not in inference_specs:
                continue
            if obj in parameter_nodes and obj not in inference_parameters:
                continue
            reasoning_graph.add((subject, predicate, obj))

        _normalize_pellet_literal_datatypes(reasoning_graph)

        _log_step(
            trace,
            "construct_reasoning_turtle",
            reason="构造 Pellet 多参数推理输入，包含 ontology/data/spec 中参与推理的参数事实",
            parameter_count=len(inference_parameters),
            measurement_count=len(inference_measurements),
            specification_count=len(inference_specs),
        )
        return reasoning_graph.serialize(format="turtle")

    def upsert_parameter(
        self,
        ontology_id: str,
        code: str,
        *,
        name: str | None = None,
        unit: str | None = None,
        value_type: str = "number",
        participates_in_inference: bool = True,
        trace: Any | None = None,
    ) -> dict[str, Any]:
        """注册或复用参数。"""

        if not code:
            raise ValueError("code is required")
        graph_data = self.graph(ontology_id, "data")
        parameter_node = _node(ontology_id, "parameter", code)
        created = (parameter_node, RDF.type, MTO.Parameter) not in graph_data
        created_at = _first_literal_text(graph_data, parameter_node, MTO.createdAt) or _now_utc()
        graph_data.add((parameter_node, RDF.type, MTO.Parameter))
        _replace_literal(graph_data, parameter_node, MTO.parameterCode, code)
        _replace_literal(graph_data, parameter_node, MTO.parameterName, name or code)
        _replace_literal(graph_data, parameter_node, RDFS.label, name or code)
        _replace_literal(graph_data, parameter_node, MTO.unit, unit or "")
        _replace_literal(graph_data, parameter_node, MTO.valueType, value_type)
        _replace_object(graph_data, parameter_node, MTO.participatesInInference, Literal(participates_in_inference, datatype=XSD.boolean))
        _replace_object(graph_data, parameter_node, MTO.createdAt, _datetime_literal(created_at))
        self._sync_graph_to_remote(ontology_id, "data")
        _log_step(trace, "insert_parameter", reason="参数写入 data 图，不修改 schema", code=code, created=created)
        return {
            "code": code,
            "created": created,
            "name": name or code,
            "unit": unit or "",
            "value_type": value_type,
            "participates_in_inference": participates_in_inference,
            "created_at": str(created_at),
        }

    def list_parameters(self, ontology_id: str) -> dict[str, Any]:
        """列出 data 图中的参数。"""

        graph_data = self.graph(ontology_id, "data")
        items = []
        for subject in graph_data.subjects(RDF.type, MTO.Parameter):
            items.append(
                {
                    "code": str(_first_literal(graph_data, subject, MTO.parameterCode) or ""),
                    "name": str(_first_literal(graph_data, subject, MTO.parameterName) or ""),
                    "unit": str(_first_literal(graph_data, subject, MTO.unit) or ""),
                    "value_type": str(_first_literal(graph_data, subject, MTO.valueType) or "number"),
                    "participates_in_inference": _bool_value(_first_literal(graph_data, subject, MTO.participatesInInference)),
                    "created_at": _first_literal_text(graph_data, subject, MTO.createdAt) or "",
                }
            )
        return {"items": sorted(items, key=lambda item: item["code"])}

    def get_parameter(self, ontology_id: str, code: str) -> dict[str, Any] | None:
        for item in self.list_parameters(ontology_id)["items"]:
            if item["code"] == code:
                return item
        return None

    def create_trial(self, ontology_id: str, trial_id: str, *, label: str | None = None) -> dict[str, Any]:
        """创建 Trial。"""

        graph_data = self.graph(ontology_id, "data")
        trial_node = _node(ontology_id, "trial", trial_id)
        created = (trial_node, RDF.type, MTO.Trial) not in graph_data
        graph_data.add((trial_node, RDF.type, MTO.Trial))
        _replace_literal(graph_data, trial_node, MTO.localId, trial_id)
        _replace_literal(graph_data, trial_node, RDFS.label, label or trial_id)
        self._sync_graph_to_remote(ontology_id, "data")
        return {"trial_id": trial_id, "label": label or trial_id, "created": created}

    def create_batch(self, ontology_id: str, trial_id: str, batch_id: str, *, label: str | None = None) -> dict[str, Any]:
        """创建 Batch 并关联所属 Trial。"""

        graph_data = self.graph(ontology_id, "data")
        batch_node = _node(ontology_id, "batch", batch_id)
        created = (batch_node, RDF.type, MTO.Batch) not in graph_data
        graph_data.add((batch_node, RDF.type, MTO.Batch))
        _replace_literal(graph_data, batch_node, MTO.localId, batch_id)
        _replace_literal(graph_data, batch_node, RDFS.label, label or batch_id)
        _replace_object(graph_data, batch_node, MTO.belongsToTrial, _node(ontology_id, "trial", trial_id))
        self._sync_graph_to_remote(ontology_id, "data")
        return {"batch_id": batch_id, "trial_id": trial_id, "label": label or batch_id, "created": created}

    def list_trials(self, ontology_id: str) -> dict[str, Any]:
        """列出 Trial。"""

        graph_data = self.graph(ontology_id, "data")
        items = []
        for trial in graph_data.subjects(RDF.type, MTO.Trial):
            items.append(
                {
                    "trial_id": str(_first_literal(graph_data, trial, MTO.localId) or ""),
                    "label": str(_first_literal(graph_data, trial, RDFS.label) or ""),
                }
            )
        return {"items": sorted(items, key=lambda item: item["trial_id"])}

    def list_batches(self, ontology_id: str, trial_id: str | None = None) -> dict[str, Any]:
        """列出 Batch，可按 Trial 过滤。"""

        graph_data = self.graph(ontology_id, "data")
        items = []
        for batch in graph_data.subjects(RDF.type, MTO.Batch):
            parent = _first_object(graph_data, batch, MTO.belongsToTrial)
            current_trial_id = _local_id_from_node(parent)
            if trial_id is not None and current_trial_id != trial_id:
                continue
            items.append(
                {
                    "batch_id": str(_first_literal(graph_data, batch, MTO.localId) or ""),
                    "trial_id": current_trial_id,
                    "label": str(_first_literal(graph_data, batch, RDFS.label) or ""),
                }
            )
        return {"items": sorted(items, key=lambda item: item["batch_id"])}

    def create_measurement(
        self,
        ontology_id: str,
        measurement_id: str,
        *,
        batch_id: str,
        parameter_code: str,
        value: float | int,
        measured_at: str | None = None,
    ) -> dict[str, Any]:
        """创建 Measurement。"""

        numeric = _coerce_number(value, "value")
        graph_data = self.graph(ontology_id, "data")
        measurement_node = _node(ontology_id, "measurement", measurement_id)
        created = (measurement_node, RDF.type, MTO.Measurement) not in graph_data
        graph_data.add((measurement_node, RDF.type, MTO.Measurement))
        _replace_literal(graph_data, measurement_node, MTO.localId, measurement_id)
        _replace_object(graph_data, measurement_node, MTO.forBatch, _node(ontology_id, "batch", batch_id))
        _replace_object(graph_data, measurement_node, MTO.forParameter, _node(ontology_id, "parameter", parameter_code))
        _replace_literal(graph_data, measurement_node, MTO.parameterCode, parameter_code)
        _replace_object(graph_data, measurement_node, MTO.measuredValue, _decimal_literal(numeric))
        _replace_object(graph_data, measurement_node, MTO.measuredAt, _datetime_literal(measured_at or _now_utc()))
        self._sync_graph_to_remote(ontology_id, "data")
        return {
            "measurement_id": measurement_id,
            "batch": batch_id,
            "parameter": parameter_code,
            "value": numeric,
            "created": created,
        }

    def list_measurements(self, ontology_id: str, parameter: str | None = None) -> dict[str, Any]:
        """列出 Measurement，并附带最新 Result 摘要。"""

        graph_data = self.graph(ontology_id, "data")
        items: list[dict[str, Any]] = []
        for measurement in graph_data.subjects(RDF.type, MTO.Measurement):
            parameter_code = str(_first_literal(graph_data, measurement, MTO.parameterCode) or "")
            if parameter is not None and parameter_code != parameter:
                continue
            item = {
                "measurement_id": str(_first_literal(graph_data, measurement, MTO.localId) or ""),
                "batch": _local_id_from_node(_first_object(graph_data, measurement, MTO.forBatch)),
                "parameter": parameter_code,
                "value": float(_first_literal(graph_data, measurement, MTO.measuredValue) or 0),
            }
            latest = self.latest_result_for_measurement(ontology_id, item["measurement_id"])
            if latest is not None:
                item.update(
                    {
                        "status": latest.status,
                        "rule": latest.rule,
                        "deviation": latest.deviation,
                        "spec_version": latest.spec_version,
                        "reasoner": latest.reasoner,
                        "inferred_at": latest.inferred_at,
                    }
                )
                item["reasoners"] = self.result_reasoners_for_measurement(ontology_id, item["measurement_id"])
            items.append(item)
        items.sort(key=lambda item: item["measurement_id"])
        return {"items": items, "total": len(items)}

    def get_measurement(self, ontology_id: str, measurement_id: str) -> dict[str, Any] | None:
        for item in self.list_measurements(ontology_id)["items"]:
            if item["measurement_id"] == measurement_id:
                return item
        return None

    def create_specification(
        self,
        ontology_id: str,
        parameter_code: str,
        *,
        lower: float | int,
        upper: float | int,
        reason: str = "",
        effective_from: str | None = None,
        trace: Any | None = None,
    ) -> dict[str, Any]:
        """创建或复用规格版本。

        Q3 规则：lower/upper/reason/effective_from 全相同则幂等复用，否则升版，并写
        `mto:supersedesSpec`。
        """

        lower_value = _coerce_number(lower, "lower")
        upper_value = _coerce_number(upper, "upper")
        if lower_value > upper_value:
            raise ValueError("lower must be <= upper")

        effective = effective_from or _now_utc()
        existing = self.list_specifications(ontology_id, parameter_code)["items"]
        for item in existing:
            if (
                item["lower"] == lower_value
                and item["upper"] == upper_value
                and item["reason"] == reason
                and item["effective_from"] == effective
            ):
                _log_step(trace, "create_specification", reason="规格完全相同，复用旧版本", created=False)
                return {**item, "created": False}

        version = f"Spec_v{len(existing) + 1}"
        spec_id = f"{parameter_code}_{version}"
        spec_node = _node(ontology_id, "specification", spec_id)
        previous = existing[-1]["spec_version"] if existing else None
        graph_spec = self.graph(ontology_id, "spec")
        graph_spec.add((spec_node, RDF.type, MTO.Specification))
        _replace_literal(graph_spec, spec_node, MTO.localId, spec_id)
        _replace_object(graph_spec, spec_node, MTO.forParameter, _node(ontology_id, "parameter", parameter_code))
        _replace_literal(graph_spec, spec_node, MTO.parameterCode, parameter_code)
        _replace_object(graph_spec, spec_node, MTO.lowerLimit, _decimal_literal(lower_value))
        _replace_object(graph_spec, spec_node, MTO.upperLimit, _decimal_literal(upper_value))
        _replace_literal(graph_spec, spec_node, MTO.specVersion, version)
        _replace_literal(graph_spec, spec_node, MTO.reason, reason)
        _replace_object(graph_spec, spec_node, MTO.effectiveFrom, _datetime_literal(effective))
        if previous is not None:
            _replace_object(graph_spec, spec_node, MTO.supersedesSpec, _node(ontology_id, "specification", f"{parameter_code}_{previous}"))
        self._sync_graph_to_remote(ontology_id, "spec")
        _log_step(trace, "create_specification", reason="规格变化，创建新版本", spec_version=version)
        return {
            "spec_id": spec_id,
            "parameter": parameter_code,
            "lower": lower_value,
            "upper": upper_value,
            "reason": reason,
            "effective_from": effective,
            "spec_version": version,
            "supersedes": previous,
            "created": True,
        }

    def list_specifications(self, ontology_id: str, parameter: str | None = None) -> dict[str, Any]:
        """列出规格历史。"""

        graph_spec = self.graph(ontology_id, "spec")
        items = []
        for spec in graph_spec.subjects(RDF.type, MTO.Specification):
            parameter_code = str(_first_literal(graph_spec, spec, MTO.parameterCode) or "")
            if parameter is not None and parameter_code != parameter:
                continue
            previous_node = _first_object(graph_spec, spec, MTO.supersedesSpec)
            previous_id = _local_id_from_node(previous_node)
            items.append(
                {
                    "spec_id": str(_first_literal(graph_spec, spec, MTO.localId) or ""),
                    "parameter": parameter_code,
                    "lower": float(_first_literal(graph_spec, spec, MTO.lowerLimit) or 0),
                    "upper": float(_first_literal(graph_spec, spec, MTO.upperLimit) or 0),
                    "reason": str(_first_literal(graph_spec, spec, MTO.reason) or ""),
                    "effective_from": _first_literal_text(graph_spec, spec, MTO.effectiveFrom) or "",
                    "spec_version": str(_first_literal(graph_spec, spec, MTO.specVersion) or ""),
                    "supersedes": _spec_version_from_id(previous_id, parameter_code) if previous_node else None,
                }
            )
        items.sort(key=lambda item: _version_number(item["spec_version"]))
        return {"items": items}

    def latest_specification(self, ontology_id: str, parameter_code: str) -> dict[str, Any] | None:
        items = self.list_specifications(ontology_id, parameter_code)["items"]
        return items[-1] if items else None

    def save_inference_result(
        self,
        ontology_id: str,
        measurement_id: str,
        *,
        status: str,
        rule: str,
        spec_version: str,
        deviation: float,
        reasoner: str,
        evidence_value: float,
        evidence_lower_limit: float,
        evidence_upper_limit: float,
        inferred_at: str | None = None,
        trace: Any | None = None,
        update_latest: bool = True,
        link_previous: bool = True,
    ) -> dict[str, Any]:
        """保存 Result，并维护 `mto:hasLatestResult` 与 `mto:supersededBy` 链。"""

        graph_result = self.graph(ontology_id, "result")
        measurement_node = _node(ontology_id, "measurement", measurement_id)
        previous = _first_object(graph_result, measurement_node, MTO.hasLatestResult)
        if update_latest:
            for current in list(graph_result.objects(measurement_node, MTO.hasLatestResult)):
                graph_result.remove((measurement_node, MTO.hasLatestResult, current))

        result_no = len(list(graph_result.subjects(MTO.forMeasurement, measurement_node))) + 1
        result_id = f"{measurement_id}_Result_{result_no}"
        result_node = _node(ontology_id, "result", result_id)
        graph_result.add((result_node, RDF.type, MTO.Result))
        graph_result.add((result_node, MTO.forMeasurement, measurement_node))
        if update_latest:
            graph_result.add((measurement_node, MTO.hasLatestResult, result_node))
        if link_previous and previous is not None:
            graph_result.add((previous, MTO.supersededBy, result_node))

        _replace_literal(graph_result, result_node, MTO.localId, result_id)
        _replace_literal(graph_result, result_node, MTO.resultStatus, status)
        _replace_literal(graph_result, result_node, MTO.appliedRule, rule)
        _replace_literal(graph_result, result_node, MTO.againstSpecVersion, spec_version)
        _replace_object(graph_result, result_node, MTO.deviation, _decimal_literal(deviation))
        _replace_literal(graph_result, result_node, MTO.reasoner, reasoner)
        _replace_object(graph_result, result_node, MTO.inferredAt, _datetime_literal(inferred_at or _now_utc()))
        _replace_object(graph_result, result_node, MTO.evidenceValue, _decimal_literal(evidence_value))
        _replace_object(graph_result, result_node, MTO.evidenceLowerLimit, _decimal_literal(evidence_lower_limit))
        _replace_object(graph_result, result_node, MTO.evidenceUpperLimit, _decimal_literal(evidence_upper_limit))
        self._sync_graph_to_remote(ontology_id, "result")
        _log_step(trace, "save_inference_result", reason="维护唯一最新 Result 与 supersededBy 链", result_id=result_id)
        return self._result_record(graph_result, result_node).as_dict()

    def _result_record(self, graph_result: Graph, result_node: URIRef) -> ResultRecord:
        return ResultRecord(
            result_id=str(_first_literal(graph_result, result_node, MTO.localId) or _local_id_from_node(result_node)),
            status=str(_first_literal(graph_result, result_node, MTO.resultStatus) or ""),
            rule=str(_first_literal(graph_result, result_node, MTO.appliedRule) or ""),
            spec_version=str(_first_literal(graph_result, result_node, MTO.againstSpecVersion) or ""),
            deviation=float(_first_literal(graph_result, result_node, MTO.deviation) or 0),
            reasoner=str(_first_literal(graph_result, result_node, MTO.reasoner) or ""),
            inferred_at=_first_literal_text(graph_result, result_node, MTO.inferredAt) or "",
        )

    def has_latest_result(self, ontology_id: str, measurement_id: str, result_id: str) -> bool:
        """判断 Measurement 是否指向某个最新 Result。"""

        graph_result = self.graph(ontology_id, "result")
        return (_node(ontology_id, "measurement", measurement_id), MTO.hasLatestResult, _node(ontology_id, "result", result_id)) in graph_result

    def result_superseded_by(self, ontology_id: str, result_id: str) -> str | None:
        """返回旧 Result 的后继 Result。"""

        graph_result = self.graph(ontology_id, "result")
        next_result = _first_object(graph_result, _node(ontology_id, "result", result_id), MTO.supersededBy)
        return _local_id_from_node(next_result) if next_result is not None else None

    def latest_result_for_measurement(self, ontology_id: str, measurement_id: str) -> ResultRecord | None:
        """读取某条 Measurement 当前最新 Result。"""

        graph_result = self.graph(ontology_id, "result")
        result_node = _first_object(graph_result, _node(ontology_id, "measurement", measurement_id), MTO.hasLatestResult)
        return self._result_record(graph_result, result_node) if result_node is not None else None

    def result_reasoners_for_measurement(self, ontology_id: str, measurement_id: str) -> list[str]:
        """列出某条 Measurement 已保存的全部推理来源。"""

        graph_result = self.graph(ontology_id, "result")
        measurement_node = _node(ontology_id, "measurement", measurement_id)
        reasoners = {
            str(_first_literal(graph_result, result_node, MTO.reasoner) or "")
            for result_node in graph_result.subjects(MTO.forMeasurement, measurement_node)
        }
        return sorted(reasoner for reasoner in reasoners if reasoner)


_DEFAULT_REPOSITORY = BusinessGraphRepository()


def get_default_repository() -> BusinessGraphRepository:
    """返回模块级默认仓储。"""

    return _DEFAULT_REPOSITORY


def load_ontologies(*, reload: bool = True, repository: BusinessGraphRepository | None = None, trace: Any | None = None) -> dict[str, Any]:
    """加载本地本体。"""

    return (repository or _DEFAULT_REPOSITORY).load_ontologies(reload=reload, trace=trace)


def list_ontologies(*, repository: BusinessGraphRepository | None = None, trace: Any | None = None) -> list[dict[str, Any]]:
    """列出本体。"""

    return (repository or _DEFAULT_REPOSITORY).list_ontologies(trace=trace)


def construct_ontology_turtle(ontology_id: str, *, repository: BusinessGraphRepository | None = None, trace: Any | None = None) -> str:
    """从 ontology graph 构造 Turtle。"""

    return (repository or _DEFAULT_REPOSITORY).construct_ontology_turtle(ontology_id, trace=trace)


def construct_reasoning_turtle(ontology_id: str, *, repository: BusinessGraphRepository | None = None, trace: Any | None = None) -> str:
    """构造 Pellet 多参数业务推理 Turtle。"""

    return (repository or _DEFAULT_REPOSITORY).construct_reasoning_turtle(ontology_id, trace=trace)


def register_parameter(ontology_id: str, code: str, **kwargs: Any) -> dict[str, Any]:
    """注册参数。"""

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    return repository.upsert_parameter(ontology_id, code, **kwargs)


def list_parameters(ontology_id: str, *, repository: BusinessGraphRepository | None = None) -> dict[str, Any]:
    """列出参数。"""

    return (repository or _DEFAULT_REPOSITORY).list_parameters(ontology_id)


def reset_cq_fixture(
    ontology_id: str,
    *,
    measurement_ids: list[str],
    parameter_code: str,
    spec_versions: list[str],
    repository: BusinessGraphRepository | None = None,
) -> dict[str, int]:
    """Delete only the fixed CQ fixture scope from data/spec/result graphs."""

    return (repository or _DEFAULT_REPOSITORY).reset_cq_fixture(
        ontology_id,
        measurement_ids=measurement_ids,
        parameter_code=parameter_code,
        spec_versions=spec_versions,
    )


def create_trial(ontology_id: str, trial_id: str, **kwargs: Any) -> dict[str, Any]:
    """创建 Trial。"""

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    return repository.create_trial(ontology_id, trial_id, **kwargs)


def create_batch(ontology_id: str, trial_id: str, batch_id: str, **kwargs: Any) -> dict[str, Any]:
    """创建 Batch。"""

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    return repository.create_batch(ontology_id, trial_id, batch_id, **kwargs)


def list_trials(ontology_id: str, *, repository: BusinessGraphRepository | None = None) -> dict[str, Any]:
    """列出 Trial。"""

    return (repository or _DEFAULT_REPOSITORY).list_trials(ontology_id)


def list_batches(ontology_id: str, trial_id: str | None = None, *, repository: BusinessGraphRepository | None = None) -> dict[str, Any]:
    """列出 Batch。"""

    return (repository or _DEFAULT_REPOSITORY).list_batches(ontology_id, trial_id)


def create_measurement(ontology_id: str, measurement_id: str, **kwargs: Any) -> dict[str, Any]:
    """创建 Measurement。"""

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    return repository.create_measurement(ontology_id, measurement_id, **kwargs)


def list_measurements(ontology_id: str, parameter: str | None = None, *, repository: BusinessGraphRepository | None = None) -> dict[str, Any]:
    """列出 Measurement。"""

    return (repository or _DEFAULT_REPOSITORY).list_measurements(ontology_id, parameter)


def create_specification(ontology_id: str, parameter_code: str, **kwargs: Any) -> dict[str, Any]:
    """创建或复用规格。"""

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    return repository.create_specification(ontology_id, parameter_code, **kwargs)


def list_specifications(ontology_id: str, parameter: str | None = None, *, repository: BusinessGraphRepository | None = None) -> dict[str, Any]:
    """列出规格历史。"""

    return (repository or _DEFAULT_REPOSITORY).list_specifications(ontology_id, parameter)


def save_inference_result(ontology_id: str, measurement_id: str, **kwargs: Any) -> dict[str, Any]:
    """保存推理结果。"""

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    return repository.save_inference_result(ontology_id, measurement_id, **kwargs)


def has_latest_result(ontology_id: str, measurement_id: str, result_id: str, *, repository: BusinessGraphRepository | None = None) -> bool:
    """检查最新 Result 链。"""

    return (repository or _DEFAULT_REPOSITORY).has_latest_result(ontology_id, measurement_id, result_id)


def result_superseded_by(ontology_id: str, result_id: str, *, repository: BusinessGraphRepository | None = None) -> str | None:
    """查询旧 Result 的 supersededBy 后继。"""

    return (repository or _DEFAULT_REPOSITORY).result_superseded_by(ontology_id, result_id)


def create_and_infer(ontology_id: str, measurement_id: str, **kwargs: Any) -> dict[str, Any]:
    """创建 Measurement 并按当前规格执行确定性推理。

    当参数没有规格或明确 `participates_in_inference=false` 时，只保留 Measurement，
    返回 `status=not_inferred`，不写 Result。
    """

    repository = kwargs.pop("repository", None) or _DEFAULT_REPOSITORY
    trace = kwargs.pop("trace", None)
    measurement = repository.create_measurement(ontology_id, measurement_id, **kwargs)
    parameter = repository.get_parameter(ontology_id, measurement["parameter"])
    if parameter is not None and not parameter["participates_in_inference"]:
        _log_step(trace, "create_and_infer", "skipped", "参数不参与推理")
        return {**measurement, "status": "not_inferred", "reason": "parameter does not participate in inference"}

    latest_spec = repository.latest_specification(ontology_id, measurement["parameter"])
    if latest_spec is None:
        _log_step(trace, "create_and_infer", "skipped", "参数没有规格")
        return {**measurement, "status": "not_inferred", "reason": "parameter has no specification"}

    from mvp.core.inference import run_inference

    return run_inference(ontology_id, measurement_id, repository=repository, trace=trace)
