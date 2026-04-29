from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, XSD

from mvp.core import commission_reasoning as reasoning
from mvp.core.graph import BusinessGraphRepository

ONTOLOGY_ID = "commission-testing"
CTO = Namespace("https://hifar.top/cto#")
INDIVIDUAL_BASE = "https://hifar.top/cto/individual"
DEMO_PATH = Path(__file__).resolve().parents[1] / "data" / "commission-testing-demo.json"


def _node(category: str, local_id: str) -> URIRef:
    return URIRef(f"{INDIVIDUAL_BASE}/{category}/{quote(str(local_id), safe='')}")


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _datetime_literal(value: str | None = None) -> Literal:
    return Literal(value or _now_utc(), datatype=XSD.dateTime)


def _decimal_literal(value: float | int) -> Literal:
    return Literal(Decimal(str(value)), datatype=XSD.decimal)


def _bool_literal(value: bool) -> Literal:
    return Literal(value, datatype=XSD.boolean)


def _text(graph: Graph, subject: URIRef, predicate: URIRef) -> str:
    obj = next(graph.objects(subject, predicate), None)
    if obj is None:
        return ""
    text = str(obj)
    if getattr(obj, "datatype", None) == XSD.dateTime and text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


def _text_any(graph: Graph, subject: URIRef, *predicates: URIRef) -> str:
    for predicate in predicates:
        text = _text(graph, subject, predicate)
        if text:
            return text
    return ""


def _number(graph: Graph, subject: URIRef, predicate: URIRef) -> float:
    obj = next(graph.objects(subject, predicate), None)
    return float(obj.toPython()) if obj is not None else 0.0


def _object(graph: Graph, subject: URIRef, predicate: URIRef) -> URIRef | None:
    obj = next(graph.objects(subject, predicate), None)
    return obj if isinstance(obj, URIRef) else None


def _local_id(node: URIRef | None) -> str:
    if node is None:
        return ""
    return str(node).rsplit("/", 1)[-1]


def _result_no(result_id: str) -> int:
    try:
        return int(result_id.rsplit("_", 1)[-1])
    except ValueError:
        return 0


class CommissionGraphService:
    def __init__(self, repository: BusinessGraphRepository | None = None) -> None:
        self.repository = repository or BusinessGraphRepository()

    def upsert_order(self, order: dict[str, Any]) -> dict[str, Any]:
        self.repository.load_ontologies(reload=False)
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        self._validate_order_payload(order)
        self._reject_cross_order_resource_conflicts(data_graph, order)
        self._remove_order_resources(data_graph, order["order_no"])

        old_standard = self._load_demo()["standards"]["old"]
        self._write_standard(data_graph, old_standard)
        order_node = self._write_order(data_graph, order)
        tasks = reasoning.decompose_projects(
            [
                reasoning.TestProjectInput(
                    project_id=project["project_id"],
                    name=project["name"],
                    task_id=project["task_id"],
                )
                for project in order["projects"]
            ]
        )
        task_by_project = {task.project_id: task for task in tasks}
        item_count = 0
        for project in order["projects"]:
            task = task_by_project[project["project_id"]]
            project_node = self._write_project(data_graph, order_node, project)
            task_node = self._write_task(data_graph, project_node, task.task_id, task.name, "Pending")
            for item in project.get("items", []):
                self._write_item(data_graph, task_node, task.task_id, item)
                item_count += 1

        self._sync()
        return {
            "ontology_id": ONTOLOGY_ID,
            "order_no": order["order_no"],
            "task_count": len(tasks),
            "item_count": item_count,
            "record_count": 0,
            "result_count": 0,
        }

    def add_data_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        task_id = str(payload["task_id"])
        item_code = str(payload["item_code"])
        task_node = self._find_by_literal(data_graph, CTO.localId, task_id, rdf_type=CTO.TestTask)
        if task_node is None:
            raise ValueError(f"task not found: {task_id}")
        item_node = self._find_item_for_task(data_graph, task_node, item_code)
        if item_node is None:
            raise ValueError(f"item not found for task {task_id}: {item_code}")

        standard_node = self._latest_standard_node(data_graph)
        if standard_node is None:
            self._write_standard(data_graph, self._load_demo()["standards"]["old"])
            standard_node = self._latest_standard_node(data_graph)
        criteria = self._criteria_for_standard(data_graph, standard_node)
        if item_code not in criteria:
            raise ValueError(f"criterion not found for item: {item_code}")

        record_id = str(payload.get("data_record_id") or f"DR-{task_id}-{item_code}")
        record_payload = {
            "item_code": item_code,
            "value": payload["value"],
            "unit": payload.get("unit", _text(data_graph, item_node, CTO.unit)),
        }
        result = reasoning.evaluate_record(
            record_id,
            task_id,
            item_code,
            float(payload["value"]),
            criteria[item_code],
            measured_unit=record_payload.get("unit"),
            result_no=1,
        )

        old_record_node = _object(data_graph, item_node, CTO.recordsData)
        if old_record_node is not None:
            nodes_to_remove = [old_record_node, *self._result_nodes_for_record(data_graph, old_record_node)]
            self._remove_nodes(data_graph, nodes_to_remove)

        record_node = self._write_record(data_graph, item_node, record_id, record_payload)
        result_node = self._write_result(data_graph, record_node, result, item_code)
        task_status = self._derive_task_status(data_graph, task_node)
        self._set_task_status(data_graph, task_node, task_status)
        self._sync()
        return {
            "task_id": task_id,
            "item_code": item_code,
            "data_record_id": record_id,
            "value": float(payload["value"]),
            "unit": record_payload.get("unit", ""),
            "result": self._serialize_result(data_graph, result_node),
            "task_status": task_status,
        }

    def reset_demo(self) -> dict[str, Any]:
        self.repository.load_ontologies(reload=False)
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        self._clear_demo_resources(data_graph)

        demo = self._load_demo()
        order = demo["order"]
        old_standard = demo["standards"]["old"]
        order_node = self._write_order(data_graph, order)
        self._write_standard(data_graph, old_standard)

        tasks = reasoning.decompose_projects(
            [
                reasoning.TestProjectInput(
                    project_id=project["project_id"],
                    name=project["name"],
                    task_id=project["task_id"],
                )
                for project in order["projects"]
            ]
        )
        task_by_project = {task.project_id: task for task in tasks}
        criteria = self._criteria_by_item_code(old_standard)
        result_count = 0
        record_count = 0

        for project in order["projects"]:
            task = task_by_project[project["project_id"]]
            project_node = self._write_project(data_graph, order_node, project)
            task_node = self._write_task(data_graph, project_node, task.task_id, task.name, "Completed")
            for item in project["items"]:
                record_count += 1
                item_node = self._write_item(data_graph, task_node, task.task_id, item)
                record_id = f"DR-{task.task_id}-{item['item_code']}"
                record_node = self._write_record(data_graph, item_node, record_id, item)
                criterion = criteria[item["item_code"]]
                result = reasoning.evaluate_record(
                    record_id,
                    task.task_id,
                    item["item_code"],
                    item["value"],
                    criterion,
                    measured_unit=item.get("unit"),
                    result_no=1,
                )
                self._write_result(data_graph, record_node, result, criterion.item_code)
                result_count += 1

        self._sync()
        return {
            "ontology_id": ONTOLOGY_ID,
            "order_no": order["order_no"],
            "task_count": len(tasks),
            "record_count": record_count,
            "result_count": result_count,
        }

    def get_order(self, order_no: str) -> dict[str, Any]:
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        order_node = self._find_by_literal(data_graph, CTO.orderNo, order_no)
        if order_node is None:
            raise ValueError(f"order not found: {order_no}")

        product_node = _object(data_graph, order_node, CTO.hasProduct)
        projects = [self._serialize_project(data_graph, project) for project in self._project_nodes_for_order(data_graph, order_node)]
        return {
            "ontology_id": ONTOLOGY_ID,
            "order_no": order_no,
            "requester": _text(data_graph, order_node, CTO.requester),
            "product": {
                "name": _text(data_graph, product_node, CTO.productName),
                "model": _text(data_graph, product_node, CTO.productModel),
            },
            "active_standard": self._serialize_standard(self._latest_standard_node(data_graph)),
            "projects": projects,
        }

    def get_task(self, task_id: str) -> dict[str, Any]:
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        task_node = self._find_by_literal(data_graph, CTO.localId, task_id, rdf_type=CTO.TestTask)
        if task_node is None:
            raise ValueError(f"task not found: {task_id}")
        project_node = _object(data_graph, task_node, CTO.taskForProject)
        items = [self._serialize_task_item(data_graph, item) for item in self._item_nodes_for_task(data_graph, task_node)]
        impacts = [self._serialize_impact(data_graph, impact) for impact in self._impact_nodes_for_task(data_graph, task_node)]
        return {
            "task_id": task_id,
            "project_id": _text(data_graph, project_node, CTO.localId),
            "project_name": _text(data_graph, project_node, CTO.projectName),
            "task_status": _text(data_graph, task_node, CTO.taskStatus),
            "items": items,
            "impacts": impacts,
        }

    def decompose_order(self, order_no: str) -> dict[str, Any]:
        order = self.get_order(order_no)
        tasks = []
        for project in order["projects"]:
            tasks.append(
                {
                    "task_id": project["task_id"],
                    "project_id": project["project_id"],
                    "name": project["name"],
                    "status": project["task_status"],
                }
            )
        return {"order_no": order_no, "tasks": tasks}

    def latest_impact(self) -> dict[str, Any]:
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        impacts = []
        for impact_node in self._impact_nodes(data_graph):
            impact = dict(self._serialize_impact(data_graph, impact_node))
            impact.pop("impact_id", None)
            impacts.append(impact)
        impacts.sort(key=lambda item: (item["task_id"], item["item_code"]))
        if not impacts:
            return {"changed": []}
        latest_version = impacts[0]["new_standard"]
        return {
            "ontology_id": ONTOLOGY_ID,
            "standard_code": self._load_demo()["standards"]["new"]["standard_code"],
            "upgraded_to": latest_version,
            "changed": impacts,
        }

    def upgrade_standard_to_demo_v2(self) -> dict[str, Any]:
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        demo = self._load_demo()
        new_standard = demo["standards"]["new"]
        self._write_standard(data_graph, new_standard)
        criteria = self._criteria_by_item_code(new_standard)
        changed: list[dict[str, Any]] = []

        for task_node in self._task_nodes(data_graph):
            task_id = _text(data_graph, task_node, CTO.localId)
            task_changed: list[tuple[URIRef, dict[str, Any]]] = []
            has_flip = False
            for item_node in self._item_nodes_for_task(data_graph, task_node):
                record_node = _object(data_graph, item_node, CTO.recordsData)
                if record_node is None:
                    continue
                item_code = _text(data_graph, item_node, CTO.itemCode)
                results = self._result_nodes_for_record(data_graph, record_node)
                old_result_node = self._latest_result_for_standard(data_graph, results, "V1") or self._latest_result_node(
                    data_graph, results
                )
                if old_result_node is None:
                    continue
                current_v2 = self._latest_result_for_standard(data_graph, results, "V2")
                if current_v2 is None:
                    record_id = _text(data_graph, record_node, CTO.localId)
                    result = reasoning.evaluate_record(
                        record_id,
                        task_id,
                        item_code,
                        _number(data_graph, record_node, CTO.measuredValue),
                        criteria[item_code],
                        measured_unit=_text(data_graph, record_node, CTO.unit),
                        result_no=len(results) + 1,
                    )
                    current_v2 = self._write_result(data_graph, record_node, result, item_code)
                    results = self._result_nodes_for_record(data_graph, record_node)

                old_result = self._read_result(data_graph, old_result_node)
                new_result = self._read_result(data_graph, current_v2)
                impact = reasoning.compare_results(old_result, new_result)
                impact_node = self._write_impact(data_graph, task_node, item_code, impact)
                if impact.flipped:
                    has_flip = True
                task_changed.append(
                    (
                        impact_node,
                        {
                            "task_id": task_id,
                            "data_record_id": impact.data_record_id,
                            "item_code": item_code,
                            "old_status": impact.old_status,
                            "new_status": impact.new_status,
                            "flipped": impact.flipped,
                            "task_status": impact.task_status,
                            "old_standard": old_result.standard_version,
                            "new_standard": new_result.standard_version,
                        },
                    )
                )

            completion_status = self._derive_task_status(data_graph, task_node)
            task_status = completion_status if completion_status != "Completed" else ("NeedsReview" if has_flip else "Completed")
            self._set_task_status(data_graph, task_node, task_status)
            for impact_node, task_change in task_changed:
                self._set_impact_task_status(data_graph, impact_node, task_status)
                task_change["task_status"] = task_status
                changed.append(task_change)

        changed.sort(key=lambda item: (item["task_id"], item["item_code"]))
        self._sync()
        return {
            "ontology_id": ONTOLOGY_ID,
            "standard_code": new_standard["standard_code"],
            "upgraded_to": new_standard["standard_version"],
            "changed": changed,
        }

    def _load_demo(self) -> dict[str, Any]:
        return json.loads(DEMO_PATH.read_text(encoding="utf-8"))

    def _write_order(self, data_graph: Graph, order: dict[str, Any]) -> URIRef:
        order_node = _node("order", order["order_no"])
        product_node = _node("product", order["order_no"])
        data_graph.add((order_node, RDF.type, CTO.CommissionOrder))
        data_graph.add((product_node, RDF.type, CTO.Product))
        data_graph.set((order_node, CTO.localId, Literal(order["order_no"])))
        data_graph.set((order_node, CTO.orderNo, Literal(order["order_no"])))
        data_graph.set((order_node, CTO.requester, Literal(order["requester"])))
        data_graph.set((order_node, CTO.hasProduct, product_node))
        data_graph.set((product_node, CTO.localId, Literal(f"PRODUCT-{order['order_no']}")))
        data_graph.set((product_node, CTO.productName, Literal(order["product"]["name"])))
        data_graph.set((product_node, CTO.productModel, Literal(order["product"]["model"])))
        return order_node

    def _write_project(self, data_graph: Graph, order_node: URIRef, project: dict[str, Any]) -> URIRef:
        project_node = _node("project", project["project_id"])
        data_graph.add((project_node, RDF.type, CTO.TestProject))
        data_graph.add((order_node, CTO.hasTestProject, project_node))
        data_graph.set((project_node, CTO.localId, Literal(project["project_id"])))
        data_graph.set((project_node, CTO.projectName, Literal(project["name"])))
        return project_node

    def _write_task(self, data_graph: Graph, project_node: URIRef, task_id: str, task_name: str, status: str) -> URIRef:
        task_node = _node("task", task_id)
        data_graph.add((task_node, RDF.type, CTO.TestTask))
        data_graph.set((project_node, CTO.decomposesToTask, task_node))
        data_graph.set((task_node, CTO.taskForProject, project_node))
        data_graph.set((task_node, CTO.localId, Literal(task_id)))
        data_graph.set((task_node, CTO.taskName, Literal(task_name)))
        data_graph.set((task_node, CTO.taskStatus, Literal(status)))
        return task_node

    def _write_item(self, data_graph: Graph, task_node: URIRef, task_id: str, item: dict[str, Any]) -> URIRef:
        item_node = _node("item", f"{task_id}-{item['item_code']}")
        data_graph.add((item_node, RDF.type, CTO.TestItem))
        data_graph.add((task_node, CTO.hasTestItem, item_node))
        data_graph.set((item_node, CTO.localId, Literal(f"ITEM-{task_id}-{item['item_code']}")))
        data_graph.set((item_node, CTO.itemCode, Literal(item["item_code"])))
        data_graph.set((item_node, CTO.itemName, Literal(item["item_name"])))
        data_graph.set((item_node, CTO.unit, Literal(item.get("unit", ""))))
        return item_node

    def _write_record(self, data_graph: Graph, item_node: URIRef, record_id: str, item: dict[str, Any]) -> URIRef:
        record_node = _node("record", record_id)
        data_graph.add((record_node, RDF.type, CTO.TestDataRecord))
        data_graph.set((item_node, CTO.recordsData, record_node))
        data_graph.set((record_node, CTO.localId, Literal(record_id)))
        data_graph.set((record_node, CTO.recordItemCode, Literal(item["item_code"])))
        data_graph.set((record_node, CTO.unit, Literal(item.get("unit", ""))))
        data_graph.set((record_node, CTO.measuredValue, _decimal_literal(item["value"])))
        return record_node

    def _write_standard(self, data_graph: Graph, standard: dict[str, Any]) -> URIRef:
        standard_node = _node("standard", f"{standard['standard_code']}-{standard['standard_version']}")
        data_graph.add((standard_node, RDF.type, CTO.StandardVersion))
        data_graph.set((standard_node, CTO.localId, Literal(f"{standard['standard_code']}-{standard['standard_version']}")))
        data_graph.set((standard_node, CTO.standardCode, Literal(standard["standard_code"])))
        data_graph.set((standard_node, CTO.standardVersion, Literal(standard["standard_version"])))
        data_graph.set((standard_node, CTO.effectiveFrom, _datetime_literal(standard["effective_from"])))
        previous = self._previous_standard_node(data_graph, standard["standard_code"], standard["standard_version"])
        if previous is not None:
            data_graph.set((standard_node, CTO.supersedesStandard, previous))
        for criterion in standard["criteria"]:
            criterion_node = _node(
                "criterion",
                f"{standard['standard_code']}-{standard['standard_version']}-{criterion['item_code']}",
            )
            data_graph.add((criterion_node, RDF.type, CTO.PassCriterion))
            data_graph.set((criterion_node, CTO.localId, Literal(_local_id(criterion_node))))
            data_graph.set((criterion_node, CTO.itemCode, Literal(criterion["item_code"])))
            data_graph.set((criterion_node, CTO.operator, Literal(criterion["operator"])))
            data_graph.set((criterion_node, CTO.threshold, _decimal_literal(criterion["threshold"])))
            data_graph.set((criterion_node, CTO.unit, Literal(criterion.get("unit", ""))))
            data_graph.set((criterion_node, CTO.criterionInStandard, standard_node))
        return standard_node

    def _criteria_for_standard(
        self,
        data_graph: Graph,
        standard_node: URIRef | None,
    ) -> dict[str, reasoning.PassCriterionInput]:
        if standard_node is None:
            return {}
        standard_code = _text(data_graph, standard_node, CTO.standardCode)
        standard_version = _text(data_graph, standard_node, CTO.standardVersion)
        criteria: dict[str, reasoning.PassCriterionInput] = {}
        for criterion_node in data_graph.subjects(CTO.criterionInStandard, standard_node):
            if not isinstance(criterion_node, URIRef):
                continue
            item_code = _text(data_graph, criterion_node, CTO.itemCode)
            criteria[item_code] = reasoning.PassCriterionInput(
                item_code=item_code,
                operator=_text(data_graph, criterion_node, CTO.operator),
                threshold=_number(data_graph, criterion_node, CTO.threshold),
                unit=_text(data_graph, criterion_node, CTO.unit),
                standard_code=standard_code,
                standard_version=standard_version,
            )
        return criteria

    def _write_result(
        self,
        data_graph: Graph,
        record_node: URIRef,
        result: reasoning.JudgementResult,
        item_code: str,
    ) -> URIRef:
        result_node = _node("result", result.result_id)
        criterion_node = _node("criterion", f"{result.standard_code}-{result.standard_version}-{item_code}")
        data_graph.add((result_node, RDF.type, CTO.JudgementResult))
        data_graph.add((record_node, CTO.hasJudgementResult, result_node))
        data_graph.set((result_node, CTO.localId, Literal(result.result_id)))
        data_graph.set((result_node, CTO.resultStatus, Literal(result.status)))
        data_graph.set((result_node, CTO.resultReason, Literal(result.reason)))
        data_graph.set((result_node, CTO.resultStandardCode, Literal(result.standard_code)))
        data_graph.set((result_node, CTO.resultStandardVersion, Literal(result.standard_version)))
        data_graph.set((result_node, CTO.judgedAt, _datetime_literal()))
        data_graph.set((result_node, CTO.evaluatedAgainstCriterion, criterion_node))
        return result_node

    def _write_impact(
        self,
        data_graph: Graph,
        task_node: URIRef,
        item_code: str,
        impact: reasoning.ReevaluationImpact,
    ) -> URIRef:
        impact_node = _node("impact", impact.impact_id)
        old_result_node = _node("result", impact.old_result_id)
        new_result_node = _node("result", impact.new_result_id)
        data_graph.add((impact_node, RDF.type, CTO.ReevaluationImpact))
        data_graph.set((impact_node, CTO.localId, Literal(impact.impact_id)))
        data_graph.set((impact_node, CTO.impactItemCode, Literal(item_code)))
        data_graph.set((impact_node, CTO.previousResult, old_result_node))
        data_graph.set((impact_node, CTO.newResult, new_result_node))
        data_graph.set((impact_node, CTO.impactsTask, task_node))
        data_graph.set((impact_node, CTO.flipped, _bool_literal(impact.flipped)))
        return impact_node

    def _criteria_by_item_code(self, standard: dict[str, Any]) -> dict[str, reasoning.PassCriterionInput]:
        criteria: dict[str, reasoning.PassCriterionInput] = {}
        for criterion in standard["criteria"]:
            criteria[criterion["item_code"]] = reasoning.PassCriterionInput(
                item_code=criterion["item_code"],
                operator=criterion["operator"],
                threshold=criterion["threshold"],
                unit=criterion.get("unit", ""),
                standard_code=standard["standard_code"],
                standard_version=standard["standard_version"],
            )
        return criteria

    def _project_nodes_for_order(self, data_graph: Graph, order_node: URIRef) -> list[URIRef]:
        nodes = [node for node in data_graph.objects(order_node, CTO.hasTestProject) if isinstance(node, URIRef)]
        return sorted(nodes, key=lambda node: _text(data_graph, node, CTO.localId))

    def _task_nodes(self, data_graph: Graph) -> list[URIRef]:
        nodes = [node for node in data_graph.subjects(RDF.type, CTO.TestTask) if isinstance(node, URIRef)]
        return sorted(nodes, key=lambda node: _text(data_graph, node, CTO.localId))

    def _item_nodes_for_task(self, data_graph: Graph, task_node: URIRef) -> list[URIRef]:
        nodes = [node for node in data_graph.objects(task_node, CTO.hasTestItem) if isinstance(node, URIRef)]
        return sorted(nodes, key=lambda node: _text(data_graph, node, CTO.itemCode))

    def _find_item_for_task(self, data_graph: Graph, task_node: URIRef, item_code: str) -> URIRef | None:
        for item_node in self._item_nodes_for_task(data_graph, task_node):
            if _text(data_graph, item_node, CTO.itemCode) == item_code:
                return item_node
        return None

    def _derive_task_status(self, data_graph: Graph, task_node: URIRef) -> str:
        item_nodes = self._item_nodes_for_task(data_graph, task_node)
        if not item_nodes:
            return "Pending"
        for item_node in item_nodes:
            record_node = _object(data_graph, item_node, CTO.recordsData)
            if record_node is None:
                return "Pending"
            if self._latest_result_node(data_graph, self._result_nodes_for_record(data_graph, record_node)) is None:
                return "Pending"
        return "Completed"

    def _impact_nodes_for_task(self, data_graph: Graph, task_node: URIRef) -> list[URIRef]:
        nodes = [node for node in data_graph.subjects(CTO.impactsTask, task_node) if isinstance(node, URIRef)]
        return sorted(nodes, key=lambda node: _text(data_graph, node, CTO.localId))

    def _impact_nodes(self, data_graph: Graph) -> list[URIRef]:
        nodes = [node for node in data_graph.subjects(RDF.type, CTO.ReevaluationImpact) if isinstance(node, URIRef)]
        return sorted(nodes, key=lambda node: _text(data_graph, node, CTO.localId))

    def _result_nodes_for_record(self, data_graph: Graph, record_node: URIRef) -> list[URIRef]:
        nodes = [node for node in data_graph.objects(record_node, CTO.hasJudgementResult) if isinstance(node, URIRef)]
        return sorted(nodes, key=lambda node: _result_no(_text(data_graph, node, CTO.localId)))

    def _latest_result_node(self, data_graph: Graph, result_nodes: list[URIRef]) -> URIRef | None:
        return result_nodes[-1] if result_nodes else None

    def _latest_result_for_standard(self, data_graph: Graph, result_nodes: list[URIRef], standard_version: str) -> URIRef | None:
        matches = [
            node
            for node in result_nodes
            if _text_any(data_graph, node, CTO.resultStandardVersion, CTO.standardVersion) == standard_version
        ]
        return matches[-1] if matches else None

    def _latest_standard_node(self, data_graph: Graph) -> URIRef | None:
        standards = [node for node in data_graph.subjects(RDF.type, CTO.StandardVersion) if isinstance(node, URIRef)]
        if not standards:
            return None
        standards.sort(key=lambda node: (_text(data_graph, node, CTO.effectiveFrom), _text(data_graph, node, CTO.standardVersion)))
        return standards[-1]

    def _previous_standard_node(self, data_graph: Graph, standard_code: str, standard_version: str) -> URIRef | None:
        if standard_version == "V1":
            return None
        current = self._find_standard_node(data_graph, standard_code, "V1")
        return current

    def _find_standard_node(self, data_graph: Graph, standard_code: str, standard_version: str) -> URIRef | None:
        for node in data_graph.subjects(RDF.type, CTO.StandardVersion):
            if (
                isinstance(node, URIRef)
                and _text(data_graph, node, CTO.standardCode) == standard_code
                and _text(data_graph, node, CTO.standardVersion) == standard_version
            ):
                return node
        return None

    def _serialize_standard(self, standard_node: URIRef | None) -> dict[str, Any] | None:
        if standard_node is None:
            return None
        data_graph = self.repository.graph(ONTOLOGY_ID, "data")
        return {
            "standard_code": _text(data_graph, standard_node, CTO.standardCode),
            "standard_version": _text(data_graph, standard_node, CTO.standardVersion),
            "effective_from": _text(data_graph, standard_node, CTO.effectiveFrom),
        }

    def _serialize_project(self, data_graph: Graph, project_node: URIRef) -> dict[str, Any]:
        task_node = _object(data_graph, project_node, CTO.decomposesToTask)
        items = [self._serialize_order_item(data_graph, item) for item in self._item_nodes_for_task(data_graph, task_node)]
        return {
            "project_id": _text(data_graph, project_node, CTO.localId),
            "name": _text(data_graph, project_node, CTO.projectName),
            "task_id": _text(data_graph, task_node, CTO.localId),
            "task_status": _text(data_graph, task_node, CTO.taskStatus),
            "items": items,
        }

    def _serialize_order_item(self, data_graph: Graph, item_node: URIRef) -> dict[str, Any]:
        record_node = _object(data_graph, item_node, CTO.recordsData)
        if record_node is None:
            return {
                "item_code": _text(data_graph, item_node, CTO.itemCode),
                "item_name": _text(data_graph, item_node, CTO.itemName),
                "unit": _text(data_graph, item_node, CTO.unit),
                "value": None,
                "data_record_id": "",
                "current_result": None,
            }
        current_result_node = self._latest_result_node(data_graph, self._result_nodes_for_record(data_graph, record_node))
        return {
            "item_code": _text(data_graph, item_node, CTO.itemCode),
            "item_name": _text(data_graph, item_node, CTO.itemName),
            "unit": _text(data_graph, item_node, CTO.unit),
            "value": _number(data_graph, record_node, CTO.measuredValue),
            "data_record_id": _text(data_graph, record_node, CTO.localId),
            "current_result": self._serialize_result(data_graph, current_result_node),
        }

    def _serialize_task_item(self, data_graph: Graph, item_node: URIRef) -> dict[str, Any]:
        record_node = _object(data_graph, item_node, CTO.recordsData)
        if record_node is None:
            return {
                "item_code": _text(data_graph, item_node, CTO.itemCode),
                "item_name": _text(data_graph, item_node, CTO.itemName),
                "unit": _text(data_graph, item_node, CTO.unit),
                "value": None,
                "data_record_id": "",
                "current_result": None,
                "results": [],
            }
        result_nodes = self._result_nodes_for_record(data_graph, record_node)
        current_result_node = self._latest_result_node(data_graph, result_nodes)
        return {
            "item_code": _text(data_graph, item_node, CTO.itemCode),
            "item_name": _text(data_graph, item_node, CTO.itemName),
            "unit": _text(data_graph, item_node, CTO.unit),
            "value": _number(data_graph, record_node, CTO.measuredValue),
            "data_record_id": _text(data_graph, record_node, CTO.localId),
            "current_result": self._serialize_result(data_graph, current_result_node),
            "results": [self._serialize_result(data_graph, node) for node in result_nodes],
        }

    def _serialize_result(self, data_graph: Graph, result_node: URIRef | None) -> dict[str, Any] | None:
        if result_node is None:
            return None
        return {
            "result_id": _text(data_graph, result_node, CTO.localId),
            "status": _text(data_graph, result_node, CTO.resultStatus),
            "reason": _text(data_graph, result_node, CTO.resultReason),
            "standard_code": _text_any(data_graph, result_node, CTO.resultStandardCode, CTO.standardCode),
            "standard_version": _text_any(data_graph, result_node, CTO.resultStandardVersion, CTO.standardVersion),
        }

    def _serialize_impact(self, data_graph: Graph, impact_node: URIRef) -> dict[str, Any]:
        old_result_node = _object(data_graph, impact_node, CTO.previousResult)
        new_result_node = _object(data_graph, impact_node, CTO.newResult)
        old_result = self._serialize_result(data_graph, old_result_node)
        new_result = self._serialize_result(data_graph, new_result_node)
        record_node = next(data_graph.subjects(CTO.hasJudgementResult, old_result_node), None)
        task_node = _object(data_graph, impact_node, CTO.impactsTask)
        task_status = _text_any(data_graph, impact_node, CTO.impactTaskStatus, CTO.taskStatus) or _text(data_graph, task_node, CTO.taskStatus)
        return {
            "impact_id": _text(data_graph, impact_node, CTO.localId),
            "task_id": _text(data_graph, task_node, CTO.localId),
            "data_record_id": _text(data_graph, record_node, CTO.localId),
            "item_code": _text_any(data_graph, impact_node, CTO.impactItemCode, CTO.itemCode),
            "old_status": old_result["status"],
            "new_status": new_result["status"],
            "flipped": str(next(data_graph.objects(impact_node, CTO.flipped), Literal(False)).toPython()).lower() == "true",
            "task_status": task_status,
            "old_standard": old_result["standard_version"],
            "new_standard": new_result["standard_version"],
        }

    def _find_by_literal(
        self,
        data_graph: Graph,
        predicate: URIRef,
        value: str,
        *,
        rdf_type: URIRef | None = None,
    ) -> URIRef | None:
        for subject in data_graph.subjects(predicate, Literal(value)):
            if isinstance(subject, URIRef) and (rdf_type is None or (subject, RDF.type, rdf_type) in data_graph):
                return subject
        return None

    def _nodes_by_literal(
        self,
        data_graph: Graph,
        predicate: URIRef,
        value: str,
        *,
        rdf_type: URIRef | None = None,
    ) -> list[URIRef]:
        return [
            subject
            for subject in data_graph.subjects(predicate, Literal(value))
            if isinstance(subject, URIRef) and (rdf_type is None or (subject, RDF.type, rdf_type) in data_graph)
        ]

    def _read_result(self, data_graph: Graph, result_node: URIRef) -> reasoning.JudgementResult:
        record_node = next(data_graph.subjects(CTO.hasJudgementResult, result_node))
        task_id = self._task_id_for_record(data_graph, record_node)
        return reasoning.JudgementResult(
            result_id=_text(data_graph, result_node, CTO.localId),
            data_record_id=_text(data_graph, record_node, CTO.localId),
            task_id=task_id,
            item_code=_text_any(data_graph, record_node, CTO.recordItemCode, CTO.itemCode),
            status=_text(data_graph, result_node, CTO.resultStatus),
            reason=_text(data_graph, result_node, CTO.resultReason),
            standard_code=_text_any(data_graph, result_node, CTO.resultStandardCode, CTO.standardCode),
            standard_version=_text_any(data_graph, result_node, CTO.resultStandardVersion, CTO.standardVersion),
        )

    def _task_id_for_record(self, data_graph: Graph, record_node: URIRef) -> str:
        item_node = next(data_graph.subjects(CTO.recordsData, record_node))
        task_node = next(data_graph.subjects(CTO.hasTestItem, item_node))
        return _text(data_graph, task_node, CTO.localId)

    def _set_task_status(self, data_graph: Graph, task_node: URIRef, status: str) -> None:
        data_graph.set((task_node, CTO.taskStatus, Literal(status)))

    def _set_impact_task_status(self, data_graph: Graph, impact_node: URIRef, status: str) -> None:
        data_graph.set((impact_node, CTO.impactTaskStatus, Literal(status)))

    def _sync(self) -> None:
        self.repository._sync_graph_to_remote(ONTOLOGY_ID, "data")

    def _validate_order_payload(self, order: dict[str, Any]) -> None:
        required = ("order_no", "requester", "product", "projects")
        for field in required:
            if not order.get(field):
                raise ValueError(f"order field is required: {field}")
        product = order["product"]
        for field in ("name", "model"):
            if not product.get(field):
                raise ValueError(f"product field is required: {field}")
        project_ids: set[str] = set()
        task_ids: set[str] = set()
        for project in order["projects"]:
            for field in ("project_id", "name", "task_id"):
                if not project.get(field):
                    raise ValueError(f"project field is required: {field}")
            if project["project_id"] in project_ids:
                raise ValueError(f"duplicate project id in order: {project['project_id']}")
            project_ids.add(project["project_id"])
            if project["task_id"] in task_ids:
                raise ValueError(f"duplicate task id in order: {project['task_id']}")
            task_ids.add(project["task_id"])
            item_codes: set[str] = set()
            for item in project.get("items", []):
                for field in ("item_code", "item_name"):
                    if not item.get(field):
                        raise ValueError(f"item field is required: {field}")
                if item["item_code"] in item_codes:
                    raise ValueError(f"duplicate item code in task {project['task_id']}: {item['item_code']}")
                item_codes.add(item["item_code"])

    def _reject_cross_order_resource_conflicts(self, data_graph: Graph, order: dict[str, Any]) -> None:
        order_no = str(order["order_no"])
        for project in order["projects"]:
            project_id = str(project["project_id"])
            for project_node in self._nodes_by_literal(data_graph, CTO.localId, project_id, rdf_type=CTO.TestProject):
                owner = self._order_no_for_project(data_graph, project_node)
                if owner != order_no:
                    raise ValueError(f"project id {project_id} already belongs to order {owner or '<unknown>'}")

            task_id = str(project["task_id"])
            for task_node in self._nodes_by_literal(data_graph, CTO.localId, task_id, rdf_type=CTO.TestTask):
                owner = self._order_no_for_task(data_graph, task_node)
                if owner != order_no:
                    raise ValueError(f"task id {task_id} already belongs to order {owner or '<unknown>'}")

    def _order_no_for_project(self, data_graph: Graph, project_node: URIRef) -> str:
        order_node = next(data_graph.subjects(CTO.hasTestProject, project_node), None)
        return _text(data_graph, order_node, CTO.orderNo) if isinstance(order_node, URIRef) else ""

    def _order_no_for_task(self, data_graph: Graph, task_node: URIRef) -> str:
        project_node = _object(data_graph, task_node, CTO.taskForProject)
        if project_node is None:
            return ""
        return self._order_no_for_project(data_graph, project_node)

    def _remove_order_resources(self, data_graph: Graph, order_no: str) -> None:
        order_node = self._find_by_literal(data_graph, CTO.orderNo, order_no)
        if order_node is None:
            return
        nodes: set[URIRef] = {order_node}
        product_node = _object(data_graph, order_node, CTO.hasProduct)
        if product_node is not None:
            nodes.add(product_node)
        for project_node in self._project_nodes_for_order(data_graph, order_node):
            nodes.add(project_node)
            task_node = _object(data_graph, project_node, CTO.decomposesToTask)
            if task_node is None:
                continue
            nodes.add(task_node)
            nodes.update(self._impact_nodes_for_task(data_graph, task_node))
            for item_node in self._item_nodes_for_task(data_graph, task_node):
                nodes.add(item_node)
                record_node = _object(data_graph, item_node, CTO.recordsData)
                if record_node is not None:
                    nodes.add(record_node)
                    nodes.update(self._result_nodes_for_record(data_graph, record_node))
        self._remove_nodes(data_graph, nodes)

    def _remove_nodes(self, data_graph: Graph, nodes: set[URIRef] | list[URIRef]) -> None:
        node_set = set(nodes)
        triples_to_remove = []
        for subject, predicate, obj in data_graph:
            if subject in node_set or (isinstance(obj, URIRef) and obj in node_set):
                triples_to_remove.append((subject, predicate, obj))
        for triple in triples_to_remove:
            data_graph.remove(triple)

    def _clear_demo_resources(self, data_graph: Graph) -> None:
        demo_prefixes = tuple(f"{INDIVIDUAL_BASE}/{category}/" for category in _DEMO_RESOURCE_CATEGORIES)
        demo_nodes: set[URIRef] = set()
        for subject in data_graph.subjects():
            if isinstance(subject, URIRef) and str(subject).startswith(demo_prefixes):
                demo_nodes.add(subject)
        triples_to_remove = []
        for subject, predicate, obj in data_graph:
            if subject in demo_nodes or (isinstance(obj, URIRef) and obj in demo_nodes):
                triples_to_remove.append((subject, predicate, obj))
        for triple in triples_to_remove:
            data_graph.remove(triple)


_DEMO_RESOURCE_CATEGORIES = (
    "order",
    "product",
    "project",
    "task",
    "item",
    "record",
    "standard",
    "criterion",
    "result",
    "impact",
)
