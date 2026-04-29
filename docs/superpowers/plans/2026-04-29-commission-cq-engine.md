# Commission CQ Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable `commission-testing` ontology demo and CQ engineering workbench for commission-order driven testing, task decomposition, deterministic judgement, standard-version upgrade impact analysis, and LLM/template-assisted CQ-to-TBox/RBox drafting.

**Architecture:** Add an independent `commission-testing` ontology and domain core beside the existing `manufacturing-trial` flow. Keep deterministic commission judgement in focused core modules, expose it through API routers, and let Streamlit pages call only API endpoints. LLM output remains draft-only; reviewed drafts can be saved and exported, but generation does not overwrite formal OWL/Turtle.

**Tech Stack:** Python 3.11+, FastAPI, Streamlit, rdflib, Apache Jena Fuseki through the existing `FusekiClient`, pytest, existing `mvp.core.llm` provider abstraction.

---

## Execution Notes

Current planning workspace `E:\company\temp\benti` is not a git repository. If implementation runs in a real git worktree, create a Lore-format commit after each task. If implementation runs in this same directory, replace each commit step with a checkpoint note listing changed files and verification output.

Spec source: `docs/superpowers/specs/2026-04-29-commission-cq-engine-design.md`.

This plan covers P1-P4 together because the customer page, technical page, CQ draft store, and tests share the same `commission-testing` data contracts. Execute tasks in order.

## File Structure

- Create `mvp/ontology/commission-testing.ttl`: independent OWL/Turtle ontology with `# ontology-id: commission-testing` header and the first TBox/RBox for commission testing.
- Create `mvp/rules/commission-testing.yml`: deterministic rule contract for task decomposition, threshold judgement, and review marking.
- Create `mvp/data/commission-testing-demo.json`: editable default demo fixture for `CO-2024-001`.
- Create `docs/cq/commission-testing-cqs.md`: business-readable and machine-executable commission CQ registry.
- Create `mvp/core/commission_reasoning.py`: pure deterministic functions and dataclasses for decomposition, judgement, standard upgrade, and impact computation.
- Create `mvp/core/commission_graph.py`: RDF graph persistence for commission orders, products, projects, tasks, items, records, standards, criteria, results, impacts, and CQ drafts.
- Create `mvp/core/ontology_draft.py`: LLM/template draft generator with `llm_only`, `llm_with_template_fallback`, and `template_only` modes.
- Create `mvp/core/cq_engine.py`: CQ draft lifecycle, CQ Markdown parsing for `CQ-CT-*`, draft save/query/update/publish coordination.
- Create `mvp/api/commission_routes.py`: FastAPI router for commission demo reset, order upsert, decomposition, data records, standards upgrade, and impact query.
- Create `mvp/api/cq_engine_routes.py`: FastAPI router for draft generation, draft CRUD, review state update, and publish/export.
- Modify `mvp/api/main.py`: initialize commission services and include the two new routers.
- Create `mvp/frontend/tabs/tab_commission_customer.py`: customer-facing full process demo.
- Create `mvp/frontend/tabs/tab_cq_engine.py`: developer-facing CQ engineering workbench.
- Modify `mvp/frontend/app.py`: add customer and technical tabs for commission testing and CQ engineering.
- Create `tests/test_commission_reasoning.py`: pure core tests.
- Create `tests/test_commission_graph.py`: in-memory RDF persistence tests.
- Create `tests/test_commission_cq_engine.py`: CQ parser, draft lifecycle, generation mode tests.
- Create `tests/test_commission_api.py`: API tests with in-memory services.
- Modify `tests/test_ontology_registry.py`: assert `commission-testing` discovery and graph IRIs.
- Modify `tests/test_frontend_boundaries.py`: assert new Streamlit tabs route through API utilities instead of core imports.
- Modify `docs/系统演示操作手册.md`: add customer and developer demo scripts for the new flow.

---

### Task 1: Static Assets And Ontology Registration

**Files:**
- Create: `mvp/ontology/commission-testing.ttl`
- Create: `mvp/rules/commission-testing.yml`
- Create: `mvp/data/commission-testing-demo.json`
- Create: `docs/cq/commission-testing-cqs.md`
- Modify: `tests/test_ontology_registry.py`

- [ ] **Step 1: Write the failing registry test**

Append this test to `tests/test_ontology_registry.py`:

```python
def test_commission_testing_ontology_is_discovered():
    descriptors = ontology_registry.discover()
    by_id = {item.ontology_id: item for item in descriptors}

    descriptor = by_id["commission-testing"]

    assert descriptor.label == "委托单试验本体"
    assert descriptor.version == "1.0.0"
    assert descriptor.graph_iri.endswith("/commission-testing")
    assert descriptor.data_graph_iri.endswith("/commission-testing/data")
    assert descriptor.result_graph_iri.endswith("/commission-testing/result")
    assert descriptor.spec_graph_iri.endswith("/commission-testing/spec")
    assert descriptor.ttl_path.name == "commission-testing.ttl"
```

- [ ] **Step 2: Run the failing registry test**

Run:

```powershell
python -m pytest tests/test_ontology_registry.py::test_commission_testing_ontology_is_discovered -q
```

Expected: FAIL with `KeyError: 'commission-testing'`.

- [ ] **Step 3: Create the ontology file**

Create `mvp/ontology/commission-testing.ttl` with this content:

```turtle
# ontology-id: commission-testing
# ontology-label: 委托单试验本体
# ontology-version: 1.0.0

@prefix cto: <https://hifar.top/cto#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<https://hifar.top/cto/ontology/commission-testing> rdf:type owl:Ontology .

cto:CommissionOrder rdf:type owl:Class ; rdfs:label "委托单"@zh-cn .
cto:Product rdf:type owl:Class ; rdfs:label "产品"@zh-cn .
cto:TestProject rdf:type owl:Class ; rdfs:label "试验项目"@zh-cn .
cto:TestTask rdf:type owl:Class ; rdfs:label "试验任务"@zh-cn .
cto:TestItem rdf:type owl:Class ; rdfs:label "测试项"@zh-cn .
cto:TestDataRecord rdf:type owl:Class ; rdfs:label "测试数据记录"@zh-cn .
cto:PassCriterion rdf:type owl:Class ; rdfs:label "通过条件"@zh-cn .
cto:StandardVersion rdf:type owl:Class ; rdfs:label "标准版本"@zh-cn .
cto:JudgementResult rdf:type owl:Class ; rdfs:label "判定结果"@zh-cn .
cto:ReevaluationImpact rdf:type owl:Class ; rdfs:label "重判影响"@zh-cn .
cto:CQDraft rdf:type owl:Class ; rdfs:label "CQ 工程草案"@zh-cn .

cto:hasProduct rdf:type owl:ObjectProperty ; rdfs:domain cto:CommissionOrder ; rdfs:range cto:Product .
cto:hasTestProject rdf:type owl:ObjectProperty ; rdfs:domain cto:CommissionOrder ; rdfs:range cto:TestProject .
cto:decomposesToTask rdf:type owl:ObjectProperty ; rdfs:domain cto:TestProject ; rdfs:range cto:TestTask .
cto:taskForProject rdf:type owl:ObjectProperty ; rdfs:domain cto:TestTask ; rdfs:range cto:TestProject .
cto:hasTestItem rdf:type owl:ObjectProperty ; rdfs:domain cto:TestTask ; rdfs:range cto:TestItem .
cto:recordsData rdf:type owl:ObjectProperty ; rdfs:domain cto:TestItem ; rdfs:range cto:TestDataRecord .
cto:hasJudgementResult rdf:type owl:ObjectProperty ; rdfs:domain cto:TestDataRecord ; rdfs:range cto:JudgementResult .
cto:evaluatedAgainstCriterion rdf:type owl:ObjectProperty ; rdfs:domain cto:JudgementResult ; rdfs:range cto:PassCriterion .
cto:criterionInStandard rdf:type owl:ObjectProperty ; rdfs:domain cto:PassCriterion ; rdfs:range cto:StandardVersion .
cto:supersedesStandard rdf:type owl:ObjectProperty ; rdfs:domain cto:StandardVersion ; rdfs:range cto:StandardVersion .
cto:previousResult rdf:type owl:ObjectProperty ; rdfs:domain cto:ReevaluationImpact ; rdfs:range cto:JudgementResult .
cto:newResult rdf:type owl:ObjectProperty ; rdfs:domain cto:ReevaluationImpact ; rdfs:range cto:JudgementResult .
cto:impactsTask rdf:type owl:ObjectProperty ; rdfs:domain cto:ReevaluationImpact ; rdfs:range cto:TestTask .

cto:localId rdf:type owl:DatatypeProperty ; rdfs:range xsd:string .
cto:orderNo rdf:type owl:DatatypeProperty ; rdfs:domain cto:CommissionOrder ; rdfs:range xsd:string .
cto:requester rdf:type owl:DatatypeProperty ; rdfs:domain cto:CommissionOrder ; rdfs:range xsd:string .
cto:productName rdf:type owl:DatatypeProperty ; rdfs:domain cto:Product ; rdfs:range xsd:string .
cto:productModel rdf:type owl:DatatypeProperty ; rdfs:domain cto:Product ; rdfs:range xsd:string .
cto:projectName rdf:type owl:DatatypeProperty ; rdfs:domain cto:TestProject ; rdfs:range xsd:string .
cto:taskStatus rdf:type owl:DatatypeProperty ; rdfs:domain cto:TestTask ; rdfs:range xsd:string .
cto:itemCode rdf:type owl:DatatypeProperty ; rdfs:domain cto:TestItem ; rdfs:range xsd:string .
cto:itemName rdf:type owl:DatatypeProperty ; rdfs:domain cto:TestItem ; rdfs:range xsd:string .
cto:measuredValue rdf:type owl:DatatypeProperty ; rdfs:domain cto:TestDataRecord ; rdfs:range xsd:decimal .
cto:unit rdf:type owl:DatatypeProperty ; rdfs:range xsd:string .
cto:operator rdf:type owl:DatatypeProperty ; rdfs:domain cto:PassCriterion ; rdfs:range xsd:string .
cto:threshold rdf:type owl:DatatypeProperty ; rdfs:domain cto:PassCriterion ; rdfs:range xsd:decimal .
cto:standardCode rdf:type owl:DatatypeProperty ; rdfs:domain cto:StandardVersion ; rdfs:range xsd:string .
cto:standardVersion rdf:type owl:DatatypeProperty ; rdfs:domain cto:StandardVersion ; rdfs:range xsd:string .
cto:effectiveFrom rdf:type owl:DatatypeProperty ; rdfs:domain cto:StandardVersion ; rdfs:range xsd:dateTime .
cto:resultStatus rdf:type owl:DatatypeProperty ; rdfs:domain cto:JudgementResult ; rdfs:range xsd:string .
cto:resultReason rdf:type owl:DatatypeProperty ; rdfs:domain cto:JudgementResult ; rdfs:range xsd:string .
cto:judgedAt rdf:type owl:DatatypeProperty ; rdfs:domain cto:JudgementResult ; rdfs:range xsd:dateTime .
cto:flipped rdf:type owl:DatatypeProperty ; rdfs:domain cto:ReevaluationImpact ; rdfs:range xsd:boolean .
cto:draftStatus rdf:type owl:DatatypeProperty ; rdfs:domain cto:CQDraft ; rdfs:range xsd:string .
cto:draftPayload rdf:type owl:DatatypeProperty ; rdfs:domain cto:CQDraft ; rdfs:range xsd:string .
```

- [ ] **Step 4: Create rule and fixture assets**

Create `mvp/rules/commission-testing.yml`:

```yaml
rules:
  - id: decompose_project_to_task
    description: "1 个试验项目生成 1 个试验任务"
    when: "test_project_exists_under_order"
    then: "create_test_task"
  - id: judge_less_equal_threshold
    description: "实测值小于等于阈值时通过"
    when: "measured_value <= threshold"
    then: "Pass"
  - id: judge_greater_than_threshold
    description: "实测值大于阈值时不通过"
    when: "measured_value > threshold"
    then: "Fail"
  - id: mark_task_needs_review_on_flip
    description: "标准升级导致结论翻转时标记任务需复核"
    when: "old_status != new_status"
    then: "taskStatus = NeedsReview"
```

Create `mvp/data/commission-testing-demo.json`:

```json
{
  "ontology_id": "commission-testing",
  "order": {
    "order_no": "CO-2024-001",
    "requester": "李工",
    "product": {
      "name": "相控阵雷达导引头",
      "model": "X-01"
    },
    "projects": [
      {
        "project_id": "P-001",
        "name": "高低温振动试验",
        "task_id": "T-001",
        "items": [
          {
            "item_code": "RCS_MEAN",
            "item_name": "RCS均值",
            "unit": "m²",
            "value": 0.042
          }
        ]
      },
      {
        "project_id": "P-002",
        "name": "电磁兼容试验",
        "task_id": "T-002",
        "items": [
          {
            "item_code": "BER",
            "item_name": "误码率",
            "unit": "",
            "value": 0.00021
          }
        ]
      }
    ]
  },
  "standards": {
    "old": {
      "standard_code": "GJB-7821-2024",
      "standard_version": "V1",
      "effective_from": "2024-01-01T00:00:00Z",
      "criteria": [
        {"item_code": "RCS_MEAN", "operator": "<=", "threshold": 0.05, "unit": "m²"},
        {"item_code": "BER", "operator": "<=", "threshold": 0.001, "unit": ""}
      ]
    },
    "new": {
      "standard_code": "GJB-7821-2024",
      "standard_version": "V2",
      "effective_from": "2024-04-01T00:00:00Z",
      "criteria": [
        {"item_code": "RCS_MEAN", "operator": "<=", "threshold": 0.035, "unit": "m²"},
        {"item_code": "BER", "operator": "<=", "threshold": 0.001, "unit": ""}
      ]
    }
  }
}
```

- [ ] **Step 5: Create commission CQ source**

Create `docs/cq/commission-testing-cqs.md`:

````markdown
# Commission Testing Competency Questions

These CQs are the first executable requirements for commission-order driven testing.

## CQ-CT-001 Which test projects belong to CO-2024-001?

- Business question: 委托单 CO-2024-001 包含哪些试验项目？
- Intent: commission_order_projects
- Source: customer-demo
- Covers: CommissionOrder, TestProject
- Demo data: CO-2024-001, P-001, P-002
- Expected: row_count=2, order_no=CO-2024-001

```sparql
PREFIX cto: <https://hifar.top/cto#>
SELECT ?order_no ?project_id ?project_name WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?order a cto:CommissionOrder ;
      cto:orderNo "CO-2024-001" ;
      cto:orderNo ?order_no ;
      cto:hasTestProject ?project .
    ?project cto:localId ?project_id ;
      cto:projectName ?project_name .
  }
}
```

- Evidence fields: order_no, project_id, project_name
- Generated by: template
- Human review status: reviewed
- Acceptance: SPARQL returns two projects for CO-2024-001.

## CQ-CT-002 Is every test project decomposed into one task?

- Business question: 每个试验项目是否都被分解成一个试验任务？
- Intent: project_task_decomposition
- Source: customer-demo
- Covers: TestProject, TestTask
- Demo data: P-001 -> T-001, P-002 -> T-002
- Expected: row_count=2

```sparql
PREFIX cto: <https://hifar.top/cto#>
SELECT ?project_id ?task_id WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?project a cto:TestProject ;
      cto:localId ?project_id ;
      cto:decomposesToTask ?task .
    ?task cto:localId ?task_id ;
      cto:taskForProject ?project .
  }
}
```

- Evidence fields: project_id, task_id
- Generated by: template
- Human review status: reviewed
- Acceptance: SPARQL returns one task for each demo project.

## CQ-CT-003 Why did T-001 RCS pass under V1?

- Business question: T-001 的 RCS 均值为什么判定为合格？
- Intent: test_item_judgement
- Source: customer-demo
- Covers: TestTask, TestItem, TestDataRecord, PassCriterion, StandardVersion, JudgementResult
- Demo data: T-001, RCS_MEAN=0.042, V1 threshold <=0.05
- Expected: row_count=1, status=Pass, standard_version=V1

```sparql
PREFIX cto: <https://hifar.top/cto#>
SELECT ?task_id ?item_code ?value ?operator ?threshold ?standard_version ?status WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?task cto:localId "T-001" ;
      cto:localId ?task_id ;
      cto:hasTestItem ?item .
    ?item cto:itemCode ?item_code ;
      cto:recordsData ?record .
    ?record cto:measuredValue ?value ;
      cto:hasJudgementResult ?result .
    ?result cto:resultStatus ?status ;
      cto:evaluatedAgainstCriterion ?criterion .
    ?criterion cto:operator ?operator ;
      cto:threshold ?threshold ;
      cto:criterionInStandard ?standard .
    ?standard cto:standardVersion ?standard_version .
  }
  FILTER (?item_code = "RCS_MEAN" && ?standard_version = "V1")
}
```

- Evidence fields: task_id, item_code, value, operator, threshold, standard_version, status
- Generated by: template
- Human review status: reviewed
- Acceptance: SPARQL proves RCS_MEAN 0.042 passed against V1 <=0.05.

## CQ-CT-004 Which historical results flipped after V2?

- Business question: 标准从 V1 升级到 V2 后，哪些历史测试结论发生翻转？
- Intent: standard_upgrade_flips
- Source: customer-demo
- Covers: StandardVersion, ReevaluationImpact, JudgementResult, TestTask
- Demo data: RCS_MEAN flips Pass -> Fail, BER remains Pass
- Expected: row_count=1, old_status=Pass, new_status=Fail, task_status=NeedsReview

```sparql
PREFIX cto: <https://hifar.top/cto#>
SELECT ?task_id ?old_status ?new_status ?task_status WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?impact a cto:ReevaluationImpact ;
      cto:flipped true ;
      cto:impactsTask ?task ;
      cto:previousResult ?old_result ;
      cto:newResult ?new_result .
    ?task cto:localId ?task_id ;
      cto:taskStatus ?task_status .
    ?old_result cto:resultStatus ?old_status .
    ?new_result cto:resultStatus ?new_status .
  }
}
```

- Evidence fields: task_id, old_status, new_status, task_status
- Generated by: template
- Human review status: reviewed
- Acceptance: SPARQL returns only the flipped task T-001.

## CQ-CT-005 Why does T-001 need review?

- Business question: 为什么 T-001 被标记为需复核？
- Intent: task_review_reason
- Source: customer-demo
- Covers: TestTask, ReevaluationImpact, JudgementResult
- Demo data: T-001 old Pass, new Fail
- Expected: row_count=1, task_status=NeedsReview

```sparql
PREFIX cto: <https://hifar.top/cto#>
SELECT ?task_id ?task_status ?old_status ?new_status WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?task cto:localId "T-001" ;
      cto:localId ?task_id ;
      cto:taskStatus ?task_status .
    ?impact cto:impactsTask ?task ;
      cto:flipped true ;
      cto:previousResult ?old_result ;
      cto:newResult ?new_result .
    ?old_result cto:resultStatus ?old_status .
    ?new_result cto:resultStatus ?new_status .
  }
}
```

- Evidence fields: task_id, task_status, old_status, new_status
- Generated by: template
- Human review status: reviewed
- Acceptance: SPARQL explains T-001 review status from a flipped impact.
````

- [ ] **Step 6: Re-run the registry test**

Run:

```powershell
python -m pytest tests/test_ontology_registry.py::test_commission_testing_ontology_is_discovered -q
```

Expected: PASS.

- [ ] **Step 7: Commit or checkpoint**

In a real git worktree:

```bash
git add mvp/ontology/commission-testing.ttl mvp/rules/commission-testing.yml mvp/data/commission-testing-demo.json docs/cq/commission-testing-cqs.md tests/test_ontology_registry.py
git commit -m "Introduce commission testing ontology seed assets

Add the independent commission-testing ontology and fixed demo
assets so later CQ and reasoning work can target a stable domain
without disturbing manufacturing-trial.

Confidence: high
Scope-risk: narrow
Tested: python -m pytest tests/test_ontology_registry.py::test_commission_testing_ontology_is_discovered -q"
```

In this non-git directory, write a checkpoint note with the same changed files and test output.

---

### Task 2: Pure Commission Reasoning Core

**Files:**
- Create: `mvp/core/commission_reasoning.py`
- Create: `tests/test_commission_reasoning.py`

- [ ] **Step 1: Write failing pure reasoning tests**

Create `tests/test_commission_reasoning.py`:

```python
from mvp.core import commission_reasoning as cr


def test_decompose_projects_creates_one_task_per_project():
    projects = [
        cr.TestProjectInput(project_id="P-001", name="高低温振动试验", task_id="T-001"),
        cr.TestProjectInput(project_id="P-002", name="电磁兼容试验", task_id="T-002"),
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
        unit="m²",
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
        unit="m²",
        standard_code="GJB-7821-2024",
        standard_version="V2",
    )

    result = cr.evaluate_record("DR-001", "T-001", "RCS_MEAN", 0.042, criterion)

    assert result.status == "Fail"
    assert result.reason == "0.042 > 0.035"
    assert result.standard_version == "V2"


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_commission_reasoning.py -q
```

Expected: FAIL with `ImportError` or missing `commission_reasoning`.

- [ ] **Step 3: Implement the pure reasoning module**

Create `mvp/core/commission_reasoning.py` with dataclasses and functions matching the tests. Required public API:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestProjectInput:
    project_id: str
    name: str
    task_id: str


@dataclass(frozen=True)
class TestTask:
    task_id: str
    project_id: str
    name: str
    status: str = "Pending"


@dataclass(frozen=True)
class PassCriterionInput:
    item_code: str
    operator: str
    threshold: float
    unit: str
    standard_code: str
    standard_version: str


@dataclass(frozen=True)
class JudgementResult:
    result_id: str
    data_record_id: str
    task_id: str
    item_code: str
    status: str
    reason: str
    standard_code: str
    standard_version: str


@dataclass(frozen=True)
class ReevaluationImpact:
    impact_id: str
    data_record_id: str
    task_id: str
    old_result_id: str
    new_result_id: str
    old_status: str
    new_status: str
    flipped: bool
    task_status: str


def decompose_projects(projects: list[TestProjectInput]) -> list[TestTask]:
    return [
        TestTask(task_id=project.task_id, project_id=project.project_id, name=project.name)
        for project in projects
    ]


def evaluate_record(
    data_record_id: str,
    task_id: str,
    item_code: str,
    measured_value: float,
    criterion: PassCriterionInput,
    *,
    result_no: int = 1,
) -> JudgementResult:
    if criterion.operator != "<=":
        raise ValueError(f"unsupported operator: {criterion.operator}")
    if measured_value <= criterion.threshold:
        status = "Pass"
        reason = f"{measured_value:g} <= {criterion.threshold:g}"
    else:
        status = "Fail"
        reason = f"{measured_value:g} > {criterion.threshold:g}"
    return JudgementResult(
        result_id=f"{data_record_id}_Result_{result_no}",
        data_record_id=data_record_id,
        task_id=task_id,
        item_code=item_code,
        status=status,
        reason=reason,
        standard_code=criterion.standard_code,
        standard_version=criterion.standard_version,
    )


def compare_results(old: JudgementResult, new: JudgementResult) -> ReevaluationImpact:
    if old.data_record_id != new.data_record_id:
        raise ValueError("old and new results must refer to the same data record")
    flipped = old.status != new.status
    return ReevaluationImpact(
        impact_id=f"{old.data_record_id}_Impact_{old.standard_version}_to_{new.standard_version}",
        data_record_id=old.data_record_id,
        task_id=new.task_id,
        old_result_id=old.result_id,
        new_result_id=new.result_id,
        old_status=old.status,
        new_status=new.status,
        flipped=flipped,
        task_status="NeedsReview" if flipped else "Completed",
    )
```

- [ ] **Step 4: Run pure reasoning tests**

Run:

```powershell
python -m pytest tests/test_commission_reasoning.py -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit or checkpoint**

Real git:

```bash
git add mvp/core/commission_reasoning.py tests/test_commission_reasoning.py
git commit -m "Define deterministic commission testing reasoning

Commission judgement and standard upgrade impact calculation are
kept in a pure core module so API and UI layers can remain thin.

Confidence: high
Scope-risk: narrow
Tested: python -m pytest tests/test_commission_reasoning.py -q"
```

Non-git checkpoint: list the two files and the `5 passed` output.

---

### Task 3: Commission Graph Persistence

**Files:**
- Create: `mvp/core/commission_graph.py`
- Create: `tests/test_commission_graph.py`

- [ ] **Step 1: Write graph persistence tests**

Create `tests/test_commission_graph.py`:

```python
from mvp.core import commission_graph as cg
from mvp.core.graph import BusinessGraphRepository


def test_seed_demo_writes_order_project_task_record_and_result_chain():
    repo = BusinessGraphRepository()
    service = cg.CommissionGraphService(repository=repo)

    summary = service.reset_demo()

    assert summary["order_no"] == "CO-2024-001"
    assert summary["task_count"] == 2
    assert summary["record_count"] == 2
    assert summary["result_count"] == 2

    order = service.get_order("CO-2024-001")
    assert order["product"]["model"] == "X-01"
    assert [project["task_id"] for project in order["projects"]] == ["T-001", "T-002"]


def test_standard_upgrade_preserves_old_results_and_records_flip():
    repo = BusinessGraphRepository()
    service = cg.CommissionGraphService(repository=repo)
    service.reset_demo()

    impact = service.upgrade_standard_to_demo_v2()

    flipped = [item for item in impact["changed"] if item["flipped"]]
    unchanged = [item for item in impact["changed"] if not item["flipped"]]

    assert flipped == [
        {
            "task_id": "T-001",
            "data_record_id": "DR-T-001-RCS_MEAN",
            "item_code": "RCS_MEAN",
            "old_status": "Pass",
            "new_status": "Fail",
            "task_status": "NeedsReview",
            "old_standard": "V1",
            "new_standard": "V2",
        }
    ]
    assert unchanged[0]["task_id"] == "T-002"
    assert unchanged[0]["new_status"] == "Pass"
    assert service.get_task("T-001")["task_status"] == "NeedsReview"
    assert service.get_task("T-002")["task_status"] == "Completed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
python -m pytest tests/test_commission_graph.py -q
```

Expected: FAIL with missing `commission_graph`.

- [ ] **Step 3: Implement graph service boundaries**

Create `mvp/core/commission_graph.py`. Implement:

```python
ONTOLOGY_ID = "commission-testing"
CTO = Namespace("https://hifar.top/cto#")
INDIVIDUAL_BASE = "https://hifar.top/cto/individual"
DEMO_PATH = Path(__file__).resolve().parents[1] / "data" / "commission-testing-demo.json"

class CommissionGraphService:
    def __init__(self, repository: BusinessGraphRepository | None = None) -> None:
        self.repository = repository or BusinessGraphRepository()

    def reset_demo(self) -> dict[str, Any]:
        # Load ontology, clear commission-testing data/result/spec graph scope,
        # read DEMO_PATH, write old standard criteria, order/product/projects,
        # create tasks, records, and V1 judgement results.

    def get_order(self, order_no: str) -> dict[str, Any]:
        # Return order, product, projects, tasks, items, records, and current results.

    def get_task(self, task_id: str) -> dict[str, Any]:
        # Return task_id, project_id, task_status.

    def upgrade_standard_to_demo_v2(self) -> dict[str, Any]:
        # Write V2 standard and criteria, create new JudgementResult nodes,
        # create ReevaluationImpact nodes, update task statuses.
```

Use existing `BusinessGraphRepository.graph(ontology_id, kind)` for named graph storage. Store all commission demo facts in the `data` graph so the CQ SPARQL in `docs/cq/commission-testing-cqs.md` uses one graph consistently. When writing remote Fuseki is needed later, call the repository's `_sync_graph_to_remote(ONTOLOGY_ID, "data")` only inside this service after graph mutations.

For node IRIs use:

```python
def _node(category: str, local_id: str) -> URIRef:
    return URIRef(f"{INDIVIDUAL_BASE}/{category}/{quote(str(local_id), safe='')}")
```

For reset, remove every triple from the `commission-testing` data graph only:

```python
data_graph = self.repository.graph(ONTOLOGY_ID, "data")
data_graph.remove((None, None, None))
```

The implementation must write these required triples:

```text
Order:
  CO-2024-001 rdf:type cto:CommissionOrder
  cto:orderNo, cto:requester, cto:hasProduct, cto:hasTestProject

Project/Task:
  TestProject cto:decomposesToTask TestTask
  TestTask cto:taskForProject TestProject
  TestTask cto:taskStatus "Completed" after V1 result creation

Record/Result:
  TestItem cto:recordsData TestDataRecord
  TestDataRecord cto:hasJudgementResult JudgementResult
  JudgementResult cto:evaluatedAgainstCriterion PassCriterion

Impact:
  ReevaluationImpact cto:previousResult old_result
  ReevaluationImpact cto:newResult new_result
  ReevaluationImpact cto:impactsTask task
  ReevaluationImpact cto:flipped true/false
```

- [ ] **Step 4: Run graph tests**

Run:

```powershell
python -m pytest tests/test_commission_graph.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit or checkpoint**

Real git:

```bash
git add mvp/core/commission_graph.py tests/test_commission_graph.py
git commit -m "Persist commission testing demo graph

Write the commission-testing demo as RDF facts so customer and
developer views can query a shared semantic graph instead of page
state.

Confidence: medium
Scope-risk: moderate
Tested: python -m pytest tests/test_commission_graph.py -q"
```

Non-git checkpoint: list changed files and `2 passed`.

---

### Task 4: CQ Parser, Draft Lifecycle, And Generation Modes

**Files:**
- Create: `mvp/core/ontology_draft.py`
- Create: `mvp/core/cq_engine.py`
- Create: `tests/test_commission_cq_engine.py`

- [ ] **Step 1: Write CQ engine tests**

Create `tests/test_commission_cq_engine.py`:

```python
from pathlib import Path

from mvp.core import cq_engine, ontology_draft
from mvp.core.graph import BusinessGraphRepository
from mvp.core.llm.base import LLMProvider


class UnavailableProvider(LLMProvider):
    name = "unavailable-test"
    default_model = "none"

    def available(self) -> bool:
        return False

    def chat(self, prompt: str, **kwargs):
        raise AssertionError("chat must not be called when unavailable")


def test_parse_commission_cqs():
    questions = cq_engine.parse_commission_cq_markdown(Path("docs/cq/commission-testing-cqs.md"))

    assert [item.id for item in questions] == [
        "CQ-CT-001",
        "CQ-CT-002",
        "CQ-CT-003",
        "CQ-CT-004",
        "CQ-CT-005",
    ]
    assert questions[0].metadata["Intent"] == "commission_order_projects"
    assert "GRAPH <{{data_graph_iri}}>" in questions[0].sparql


def test_template_only_generation_returns_reviewable_draft():
    result = ontology_draft.generate_commission_draft(
        business_text="委托单自动分解任务，标准升级后重判历史数据。",
        generation_mode="template_only",
        provider=UnavailableProvider(),
    )

    assert result["generation_mode"] == "template_only"
    assert {item["name"] for item in result["candidate_classes"]} >= {"CommissionOrder", "TestTask"}
    assert {item["name"] for item in result["candidate_relations"]} >= {"decomposesToTask", "supersedesStandard"}
    assert "CQ-CT-004" in {item["id"] for item in result["candidate_cqs"]}
    assert "commission-testing" in result["draft_turtle"]


def test_llm_with_template_fallback_uses_template_when_provider_unavailable():
    result = ontology_draft.generate_commission_draft(
        business_text="标准升级后找出结论翻转任务。",
        generation_mode="llm_with_template_fallback",
        provider=UnavailableProvider(),
    )

    assert result["generation_mode"] == "llm_with_template_fallback"
    assert result["source_trace"][0]["generator"] == "template"


def test_llm_only_fails_when_provider_unavailable():
    try:
        ontology_draft.generate_commission_draft(
            business_text="标准升级后找出结论翻转任务。",
            generation_mode="llm_only",
            provider=UnavailableProvider(),
        )
    except ontology_draft.DraftGenerationError as exc:
        assert "LLM provider unavailable" in str(exc)
    else:
        raise AssertionError("llm_only must fail when provider is unavailable")


def test_draft_lifecycle_persists_review_status():
    repo = BusinessGraphRepository()
    service = cq_engine.CQDraftService(repository=repo)
    payload = ontology_draft.generate_commission_draft(
        business_text="委托单自动分解任务。",
        generation_mode="template_only",
        provider=UnavailableProvider(),
    )

    draft = service.save_draft(payload)
    updated = service.update_status(draft["draft_id"], "reviewed")

    assert updated["draft_status"] == "reviewed"
    assert service.list_drafts()["items"][0]["draft_id"] == draft["draft_id"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_commission_cq_engine.py -q
```

Expected: FAIL with missing `cq_engine` or `ontology_draft`.

- [ ] **Step 3: Implement `ontology_draft.py`**

Create `mvp/core/ontology_draft.py` with:

```python
class DraftGenerationError(RuntimeError):
    pass

VALID_GENERATION_MODES = {"llm_only", "llm_with_template_fallback", "template_only"}

def generate_commission_draft(
    *,
    business_text: str,
    generation_mode: str,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    # Validate generation_mode.
    # If template_only, return _template_draft(...).
    # If llm_only and provider unavailable, raise DraftGenerationError.
    # If llm_with_template_fallback and provider unavailable, return _template_draft(...).
    # If provider available, build a constrained prompt and parse JSON; if parsing fails in
    # fallback mode, return _template_draft(...); if parsing fails in llm_only, raise.
```

The `_template_draft` output must include exactly these keys:

```python
{
    "generation_mode": generation_mode,
    "candidate_cqs": [
        {"id": "CQ-CT-001", "question": "委托单 CO-2024-001 包含哪些试验项目？"},
        {"id": "CQ-CT-002", "question": "每个试验项目是否都被分解成一个试验任务？"},
        {"id": "CQ-CT-003", "question": "T-001 的 RCS 均值为什么判定为合格？"},
        {"id": "CQ-CT-004", "question": "标准从 V1 升级到 V2 后，哪些历史测试结论发生翻转？"},
        {"id": "CQ-CT-005", "question": "为什么 T-001 被标记为需复核？"},
    ],
    "candidate_classes": [
        {"name": "CommissionOrder", "label": "委托单"},
        {"name": "Product", "label": "产品"},
        {"name": "TestProject", "label": "试验项目"},
        {"name": "TestTask", "label": "试验任务"},
        {"name": "TestItem", "label": "测试项"},
        {"name": "TestDataRecord", "label": "测试数据记录"},
        {"name": "PassCriterion", "label": "通过条件"},
        {"name": "StandardVersion", "label": "标准版本"},
        {"name": "JudgementResult", "label": "判定结果"},
        {"name": "ReevaluationImpact", "label": "重判影响"},
    ],
    "candidate_relations": [
        {"name": "hasProduct", "domain": "CommissionOrder", "range": "Product"},
        {"name": "hasTestProject", "domain": "CommissionOrder", "range": "TestProject"},
        {"name": "decomposesToTask", "domain": "TestProject", "range": "TestTask"},
        {"name": "supersedesStandard", "domain": "StandardVersion", "range": "StandardVersion"},
    ],
    "candidate_properties": [
        {"name": "taskStatus", "domain": "TestTask", "range": "xsd:string"},
        {"name": "measuredValue", "domain": "TestDataRecord", "range": "xsd:decimal"},
        {"name": "threshold", "domain": "PassCriterion", "range": "xsd:decimal"},
    ],
    "candidate_rules": [
        {"id": "decompose_project_to_task", "then": "create_test_task"},
        {"id": "judge_less_equal_threshold", "then": "Pass"},
        {"id": "mark_task_needs_review_on_flip", "then": "taskStatus = NeedsReview"},
    ],
    "draft_turtle": "# ontology-id: commission-testing\n",
    "draft_sparql_tests": ["CQ-CT-001", "CQ-CT-004"],
    "source_trace": [{"generator": "template", "business_text": business_text}],
}
```

- [ ] **Step 4: Implement `cq_engine.py`**

Create `mvp/core/cq_engine.py` with:

```python
@dataclass(frozen=True)
class CommissionCQ:
    id: str
    title: str
    metadata: dict[str, str]
    sparql: str
    expected: dict[str, str]
    evidence_fields: list[str]

class CQEngineError(ValueError):
    pass

def parse_commission_cq_markdown(path: str | Path = "docs/cq/commission-testing-cqs.md") -> list[CommissionCQ]:
    # Match sections with regex r"^##\s+(CQ-CT-\d{3})\s+(.+?)\s*$".
    # Require Business question, Intent, Source, Covers, Demo data, Expected,
    # Evidence fields, Generated by, Human review status, Acceptance.
    # Require exactly one sparql fenced block.
```

Add `CQDraftService`:

```python
class CQDraftService:
    def __init__(self, repository: BusinessGraphRepository | None = None) -> None:
        self.repository = repository or BusinessGraphRepository()

    def save_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        draft_id = f"draft-{uuid.uuid4().hex[:12]}"
        # Write cto:CQDraft with cto:localId, cto:draftStatus "draft",
        # cto:draftPayload JSON string into commission-testing data graph.
        return {"draft_id": draft_id, "draft_status": "draft", "payload": payload}

    def list_drafts(self) -> dict[str, Any]:
        # Return {"items": [...]} sorted by draft_id.

    def update_status(self, draft_id: str, draft_status: str) -> dict[str, Any]:
        # Accept only draft, reviewed, published, rejected.
        # Replace cto:draftStatus and return the updated draft.
```

- [ ] **Step 5: Run CQ engine tests**

Run:

```powershell
python -m pytest tests/test_commission_cq_engine.py -q
```

Expected: `5 passed`.

- [ ] **Step 6: Commit or checkpoint**

Real git:

```bash
git add mvp/core/ontology_draft.py mvp/core/cq_engine.py tests/test_commission_cq_engine.py
git commit -m "Add commission CQ draft engine

LLM-assisted modeling is constrained behind explicit generation
modes and a draft lifecycle so generated content stays reviewable
before becoming formal ontology assets.

Confidence: medium
Scope-risk: moderate
Rejected: Direct LLM writes to Turtle | violates review and demo stability constraints
Tested: python -m pytest tests/test_commission_cq_engine.py -q"
```

Non-git checkpoint: list changed files and `5 passed`.

---

### Task 5: Commission And CQ API Routers

**Files:**
- Create: `mvp/api/commission_routes.py`
- Create: `mvp/api/cq_engine_routes.py`
- Modify: `mvp/api/main.py`
- Create: `tests/test_commission_api.py`

- [ ] **Step 1: Write API tests**

Create `tests/test_commission_api.py`:

```python
from fastapi.testclient import TestClient

from mvp.api.main import create_app
from mvp.core.graph import BusinessGraphRepository
from mvp.core.llm.base import LLMProvider


class UnavailableProvider(LLMProvider):
    name = "unavailable-test"
    default_model = "none"

    def available(self) -> bool:
        return False

    def chat(self, prompt: str, **kwargs):
        raise AssertionError("chat must not be called")


def _client():
    app = create_app(repository=BusinessGraphRepository(), llm_provider=UnavailableProvider())
    return TestClient(app)


def test_commission_demo_reset_and_upgrade_flow():
    client = _client()

    reset = client.post("/api/v1/commission/demo/reset")
    assert reset.status_code == 200
    assert reset.json()["data"]["order_no"] == "CO-2024-001"

    order = client.get("/api/v1/commission/orders/CO-2024-001")
    assert order.status_code == 200
    assert order.json()["data"]["product"]["model"] == "X-01"

    upgrade = client.post("/api/v1/commission/standards/GJB-7821-2024/upgrade")
    assert upgrade.status_code == 200
    changed = upgrade.json()["data"]["changed"]
    assert any(item["task_id"] == "T-001" and item["flipped"] for item in changed)

    latest = client.get("/api/v1/commission/impacts/latest")
    assert latest.status_code == 200
    assert latest.json()["data"]["changed"][0]["new_standard"] == "V2"


def test_cq_engine_template_generation_and_draft_review():
    client = _client()

    generated = client.post(
        "/api/v1/cq-engine/generate",
        json={
            "business_text": "委托单自动分解任务，标准升级后重判历史数据。",
            "generation_mode": "template_only",
        },
    )
    assert generated.status_code == 200
    payload = generated.json()["data"]
    assert payload["generation_mode"] == "template_only"

    saved = client.post("/api/v1/cq-engine/drafts", json={"payload": payload})
    assert saved.status_code == 200
    draft_id = saved.json()["data"]["draft_id"]

    reviewed = client.patch(f"/api/v1/cq-engine/drafts/{draft_id}", json={"draft_status": "reviewed"})
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["draft_status"] == "reviewed"
```

- [ ] **Step 2: Run API tests to verify failure**

Run:

```powershell
python -m pytest tests/test_commission_api.py -q
```

Expected: FAIL with 404 responses or missing router modules.

- [ ] **Step 3: Create `commission_routes.py`**

Create `mvp/api/commission_routes.py` with a `create_router()` function:

```python
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from mvp.api import envelope


def create_router() -> APIRouter:
    router = APIRouter(prefix="/commission", tags=["commission"])

    @router.post("/demo/reset")
    async def reset_demo(request: Request):
        result = await run_in_threadpool(request.app.state.commission_graph.reset_demo)
        request.app.state.latest_commission_impact = {"changed": []}
        return envelope.ok(result, trace=request.state.trace)

    @router.get("/orders/{order_no}")
    async def get_order(order_no: str, request: Request):
        result = await run_in_threadpool(request.app.state.commission_graph.get_order, order_no)
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/orders/{order_no}/decompose")
    async def decompose(order_no: str, request: Request):
        result = await run_in_threadpool(request.app.state.commission_graph.decompose_order, order_no)
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/standards/{standard_code}/upgrade")
    async def upgrade_standard(standard_code: str, request: Request):
        result = await run_in_threadpool(request.app.state.commission_graph.upgrade_standard_to_demo_v2)
        request.app.state.latest_commission_impact = result
        return envelope.ok(result, trace=request.state.trace)

    @router.get("/impacts/latest")
    async def latest_impact(request: Request):
        result = getattr(request.app.state, "latest_commission_impact", {"changed": []})
        return envelope.ok(result, trace=request.state.trace)

    return router
```

If `decompose_order` is not yet present in `CommissionGraphService`, add it as a thin method returning the task list already created by `reset_demo()`.

- [ ] **Step 4: Create `cq_engine_routes.py`**

Create `mvp/api/cq_engine_routes.py`:

```python
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from mvp.api import envelope
from mvp.core import ontology_draft


class GenerateDraftRequest(BaseModel):
    business_text: str = Field(description="业务流程、术语或样例描述")
    generation_mode: str = Field(default="llm_with_template_fallback")


class SaveDraftRequest(BaseModel):
    payload: dict[str, Any]


class UpdateDraftStatusRequest(BaseModel):
    draft_status: str


def create_router() -> APIRouter:
    router = APIRouter(prefix="/cq-engine", tags=["cq-engine"])

    @router.post("/generate")
    async def generate(payload: GenerateDraftRequest, request: Request):
        result = await run_in_threadpool(
            ontology_draft.generate_commission_draft,
            business_text=payload.business_text,
            generation_mode=payload.generation_mode,
            provider=request.app.state.llm_provider,
        )
        return envelope.ok(result, trace=request.state.trace)

    @router.get("/drafts")
    async def list_drafts(request: Request):
        result = await run_in_threadpool(request.app.state.cq_draft_service.list_drafts)
        return envelope.ok(result, trace=request.state.trace)

    @router.post("/drafts")
    async def save_draft(payload: SaveDraftRequest, request: Request):
        result = await run_in_threadpool(request.app.state.cq_draft_service.save_draft, payload.payload)
        return envelope.ok(result, trace=request.state.trace)

    @router.patch("/drafts/{draft_id}")
    async def update_draft(draft_id: str, payload: UpdateDraftStatusRequest, request: Request):
        result = await run_in_threadpool(
            request.app.state.cq_draft_service.update_status,
            draft_id,
            payload.draft_status,
        )
        return envelope.ok(result, trace=request.state.trace)

    return router
```

- [ ] **Step 5: Wire routers in `main.py`**

In `mvp/api/main.py`, import the new routers and services near existing imports:

```python
from mvp.api import commission_routes, cq_engine_routes
from mvp.core.commission_graph import CommissionGraphService
from mvp.core.cq_engine import CQDraftService
```

Inside `create_app()` after `app.state.latest_impacts = {}` add:

```python
    app.state.commission_graph = CommissionGraphService(repository=active_repository)
    app.state.cq_draft_service = CQDraftService(repository=active_repository)
    app.state.latest_commission_impact = {"changed": []}
```

Before `app.include_router(router)`, include:

```python
    router.include_router(commission_routes.create_router())
    router.include_router(cq_engine_routes.create_router())
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
python -m pytest tests/test_commission_api.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit or checkpoint**

Real git:

```bash
git add mvp/api/commission_routes.py mvp/api/cq_engine_routes.py mvp/api/main.py tests/test_commission_api.py
git commit -m "Expose commission testing and CQ draft APIs

The new routers keep domain behavior outside the API entry point
while making the customer demo and CQ workbench available through
the same /api/v1 envelope contract as existing features.

Confidence: medium
Scope-risk: moderate
Tested: python -m pytest tests/test_commission_api.py -q"
```

Non-git checkpoint: list files and `2 passed`.

---

### Task 6: Customer And Developer Streamlit Tabs

**Files:**
- Create: `mvp/frontend/tabs/tab_commission_customer.py`
- Create: `mvp/frontend/tabs/tab_cq_engine.py`
- Modify: `mvp/frontend/tabs/__init__.py`
- Modify: `mvp/frontend/app.py`
- Modify: `tests/test_frontend_boundaries.py`

- [ ] **Step 1: Write frontend boundary tests**

Append to `tests/test_frontend_boundaries.py`:

```python
def test_commission_frontend_tabs_do_not_import_core_modules():
    frontend_paths = [
        Path("mvp/frontend/tabs/tab_commission_customer.py"),
        Path("mvp/frontend/tabs/tab_cq_engine.py"),
    ]
    forbidden = [
        "from mvp.core",
        "import mvp.core",
        "BusinessGraphRepository",
        "CommissionGraphService",
        "CQDraftService",
    ]

    for path in frontend_paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
```

If this test file does not already import `Path`, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Run boundary test to verify failure**

Run:

```powershell
python -m pytest tests/test_frontend_boundaries.py::test_commission_frontend_tabs_do_not_import_core_modules -q
```

Expected: FAIL because the files do not exist.

- [ ] **Step 3: Create customer tab**

Create `mvp/frontend/tabs/tab_commission_customer.py` with:

```python
from __future__ import annotations

from typing import Any

import streamlit as st

from mvp.frontend.ui_utils import api_request, extract_data, render_dataframe, render_envelope_feedback, render_panel_intro, render_trace

TRACE_KEY = "tab-commission-customer"


def render() -> None:
    render_panel_intro(
        kicker="Commission Testing",
        title="委托单试验全流程",
        summary="",
    )
    if st.button("初始化 CO-2024-001 演示剧本", width="stretch"):
        envelope = api_request("POST", "/commission/demo/reset", trace_key=TRACE_KEY, trace_title="委托单演示初始化")
        render_envelope_feedback(envelope, success_message="演示剧本已初始化。")

    order_envelope = api_request("GET", "/commission/orders/CO-2024-001", record_trace=False)
    order = extract_data(order_envelope, default={}) or {}
    _render_order(order)

    if st.button("发布 V2 标准并重判历史数据", width="stretch"):
        envelope = api_request(
            "POST",
            "/commission/standards/GJB-7821-2024/upgrade",
            trace_key=TRACE_KEY,
            trace_title="标准升级重判",
        )
        render_envelope_feedback(envelope, success_message="标准升级重判已完成。")

    impact_envelope = api_request("GET", "/commission/impacts/latest", record_trace=False)
    impact = extract_data(impact_envelope, default={}) or {}
    st.markdown("**标准升级影响**")
    render_dataframe(list(impact.get("changed") or []), empty_text="暂无标准升级影响。")
    render_trace(TRACE_KEY)


def _render_order(order: dict[str, Any]) -> None:
    if not order:
        st.info("请先初始化演示剧本。")
        return
    product = order.get("product") or {}
    st.markdown(f"**委托单：{order.get('order_no', '-')}**")
    st.caption(f"委托人：{order.get('requester', '-')} | 产品：{product.get('name', '-')} | 型号：{product.get('model', '-')}")
    rows: list[dict[str, Any]] = []
    for project in list(order.get("projects") or []):
        rows.append(
            {
                "试验项目": project.get("name"),
                "任务": project.get("task_id"),
                "状态": project.get("task_status"),
                "测试项": ", ".join(item.get("item_name", "") for item in list(project.get("items") or [])),
            }
        )
    render_dataframe(rows, empty_text="暂无任务。")
```

- [ ] **Step 4: Create CQ engine tab**

Create `mvp/frontend/tabs/tab_cq_engine.py` with:

```python
from __future__ import annotations

import json
from typing import Any

import streamlit as st

from mvp.frontend.ui_utils import api_request, extract_data, render_dataframe, render_envelope_feedback, render_panel_intro, render_trace

TRACE_KEY = "tab-cq-engine"


def render() -> None:
    render_panel_intro(
        kicker="CQ Engineering",
        title="CQ 反推 TBox / RBox 草案",
        summary="",
    )
    generation_mode = st.selectbox(
        "LLM 生成模式",
        options=["llm_with_template_fallback", "template_only", "llm_only"],
        index=0,
    )
    business_text = st.text_area(
        "业务描述",
        value="委托单包含产品和多个试验项目；每个试验项目自动分解为一个任务；标准升级后重判历史数据并标记需复核任务。",
        height=120,
    )
    if st.button("生成候选 CQ / TBox / RBox", width="stretch"):
        envelope = api_request(
            "POST",
            "/cq-engine/generate",
            json_body={"business_text": business_text, "generation_mode": generation_mode},
            trace_key=TRACE_KEY,
            trace_title="CQ 工程草案生成",
        )
        render_envelope_feedback(envelope, success_message="候选草案已生成。")
        payload = extract_data(envelope, default={}) or {}
        if payload:
            save = api_request("POST", "/cq-engine/drafts", json_body={"payload": payload}, trace_key=TRACE_KEY, trace_title="草案保存")
            render_envelope_feedback(save, success_message="草案已保存。")

    drafts = extract_data(api_request("GET", "/cq-engine/drafts", record_trace=False), default={}) or {}
    rows = _draft_rows(list(drafts.get("items") or []))
    render_dataframe(rows, empty_text="暂无草案。")
    if rows:
        selected = st.selectbox("查看草案", options=[row["draft_id"] for row in rows])
        draft = next((item for item in list(drafts.get("items") or []) if item.get("draft_id") == selected), None)
        if draft:
            st.code(json.dumps(draft.get("payload") or {}, ensure_ascii=False, indent=2), language="json")
    render_trace(TRACE_KEY)


def _draft_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "draft_id": item.get("draft_id"),
            "draft_status": item.get("draft_status"),
            "generation_mode": (item.get("payload") or {}).get("generation_mode"),
        }
        for item in items
    ]
```

- [ ] **Step 5: Wire tabs into Streamlit app**

Modify `mvp/frontend/tabs/__init__.py` to import:

```python
from mvp.frontend.tabs import tab_commission_customer, tab_cq_engine
```

Modify `mvp/frontend/app.py` imports:

```python
    tab_commission_customer,
    tab_cq_engine,
```

Modify customer tabs in `main()` from three tabs to four:

```python
    audience_tabs = st.tabs(
        [
            "客户讲",
            "委托单试验",
            "技术讲",
            "设备健康",
        ]
    )

    with audience_tabs[0]:
        tab_customer.render(ontology_id=get_active_ontology())
    with audience_tabs[1]:
        tab_commission_customer.render()
    with audience_tabs[2]:
        _render_technical_tabs(ontologies)
    with audience_tabs[3]:
        tab_equipment_health.render()
```

Modify `_render_technical_tabs()` to add CQ 工程台:

```python
    tabs = st.tabs(
        [
            "本体",
            "CQ 工程台",
            "主体",
            "推理",
            "测量",
            "问答",
        ]
    )

    with tabs[0]:
        tab_ontology.render(ontologies=ontologies)
    with tabs[1]:
        tab_cq_engine.render()
```

Shift the existing subject/pellet/measure/qa blocks to indices 2-5.

- [ ] **Step 6: Run frontend boundary test**

Run:

```powershell
python -m pytest tests/test_frontend_boundaries.py::test_commission_frontend_tabs_do_not_import_core_modules -q
```

Expected: PASS.

- [ ] **Step 7: Run focused frontend import check**

Run:

```powershell
python -m compileall mvp/frontend
```

Expected: compile completes without syntax errors.

- [ ] **Step 8: Commit or checkpoint**

Real git:

```bash
git add mvp/frontend/tabs/tab_commission_customer.py mvp/frontend/tabs/tab_cq_engine.py mvp/frontend/tabs/__init__.py mvp/frontend/app.py tests/test_frontend_boundaries.py
git commit -m "Add commission customer and CQ engineering tabs

The Streamlit additions keep customer and developer demos separate
while preserving the existing frontend boundary of using API calls
instead of importing core modules.

Confidence: medium
Scope-risk: moderate
Tested: python -m pytest tests/test_frontend_boundaries.py::test_commission_frontend_tabs_do_not_import_core_modules -q
Tested: python -m compileall mvp/frontend"
```

Non-git checkpoint: list changed files and verification output.

---

### Task 7: CQ SPARQL Integration

**Files:**
- Create: `tests/test_commission_cq_integration.py`
- Modify: `mvp/core/cq_engine.py`

- [x] **Step 1: Write integration test**

Create `tests/test_commission_cq_integration.py`:

```python
import os

import pytest

from mvp.core import commission_graph, cq_engine
from mvp.core.graph import BusinessGraphRepository
from mvp.core.sparql_client import FusekiClient, FusekiError


def _repo_or_skip() -> BusinessGraphRepository:
    client = FusekiClient(timeout=float(os.getenv("FUSEKI_TEST_TIMEOUT", "15")))
    if not client.ping():
        pytest.skip("Fuseki unavailable; run `docker compose up -d` before commission CQ integration tests")
    return BusinessGraphRepository(client=client)


def test_commission_cqs_execute_against_fuseki():
    repo = _repo_or_skip()
    graph_service = commission_graph.CommissionGraphService(repository=repo)
    runner = cq_engine.CommissionCQRunner(repository=repo)

    try:
        graph_service.reset_demo()
        graph_service.upgrade_standard_to_demo_v2()
    except FusekiError as exc:
        if exc.code == "FUSEKI_HTTP_401":
            pytest.skip("Fuseki requires write credentials; set FUSEKI_USER/FUSEKI_PASSWORD")
        raise

    results = [runner.run_question(question) for question in cq_engine.parse_commission_cq_markdown()]

    assert [result.question.id for result in results] == [
        "CQ-CT-001",
        "CQ-CT-002",
        "CQ-CT-003",
        "CQ-CT-004",
        "CQ-CT-005",
    ]
    assert len(results[0].rows) == 2
    assert results[2].rows[0]["status"] == "Pass"
    assert results[3].rows[0]["task_status"] == "NeedsReview"
```

- [x] **Step 2: Run integration test to verify failure**

Run:

```powershell
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

Expected: FAIL when Fuseki is available because `CommissionCQRunner` is missing, or SKIP if Fuseki is unavailable.

- [x] **Step 3: Add runner to `cq_engine.py`**

Add:

```python
@dataclass(frozen=True)
class CommissionCQRunResult:
    question: CommissionCQ
    rows: list[dict[str, Any]]


class CommissionCQRunner:
    def __init__(self, *, repository: BusinessGraphRepository, ontology_id: str = "commission-testing") -> None:
        self.repository = repository
        self.ontology_id = ontology_id

    def run_question(self, question: CommissionCQ) -> CommissionCQRunResult:
        rows = self._select_rows(render_commission_sparql(question, self.ontology_id))
        validate_commission_expected(question, rows)
        return CommissionCQRunResult(question=question, rows=rows)

    def _select_rows(self, sparql: str) -> list[dict[str, Any]]:
        if self.repository.client is None:
            raise RuntimeError("CommissionCQRunner requires a repository with a Fuseki client")
        return [
            {str(key): normalize_sparql_value(value) for key, value in row.items()}
            for row in self.repository.client.select(sparql)
        ]
```

Add helpers:

```python
def render_commission_sparql(question: CommissionCQ | str, ontology_id: str) -> str:
    sparql = question.sparql if isinstance(question, CommissionCQ) else str(question)
    return sparql.replace("{{data_graph_iri}}", graph.graph_iri(ontology_id, "data"))


def normalize_sparql_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def validate_commission_expected(question: CommissionCQ, rows: list[dict[str, Any]]) -> None:
    expected_count = int(question.expected["row_count"])
    if len(rows) != expected_count:
        raise AssertionError(f"{question.id} expected {expected_count} rows, got {len(rows)}")
    if not rows:
        return
    row = rows[0]
    for key, expected in question.expected.items():
        if key == "row_count":
            continue
        actual = row.get(key)
        if str(actual) != expected:
            raise AssertionError(f"{question.id} expected {key}={expected}, got {actual}")
```

- [x] **Step 4: Run integration test**

Run:

```powershell
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

Expected with Fuseki available: PASS. Expected without Fuseki: SKIP with unavailable message.

- [x] **Step 5: Commit or checkpoint**

Real git:

```bash
git add mvp/core/cq_engine.py tests/test_commission_cq_integration.py
git commit -m "Validate commission CQs against Fuseki

Commission CQs now execute as real SPARQL checks over the
commission-testing data graph so the demo has regression evidence
for order, judgement, and standard-upgrade impact chains.

Confidence: medium
Scope-risk: narrow
Tested: python -m pytest tests/test_commission_cq_integration.py -q -rs"
```

Non-git checkpoint: list files and PASS/SKIP output.

---

### Task 8: Documentation And Demonstration Scripts

**Files:**
- Modify: `docs/系统演示操作手册.md`
- Modify: `README.md`

- [x] **Step 1: Update README CQ section**

Add this section after the existing CQ validation section in `README.md`:

```markdown
## 委托单试验 CQ 工程

`commission-testing` 是独立于 `manufacturing-trial` 的新本体，用于演示从委托单业务流程出发，借助 CQ 反推候选 TBox/RBox、规则和 SPARQL 验收。

第一版演示链：

```text
CO-2024-001
  -> 试验项目 P-001/P-002
  -> 任务 T-001/T-002
  -> RCS/误码率实测值
  -> V1 判定
  -> V2 标准升级
  -> 历史数据重判
  -> T-001 标记 NeedsReview
```

关键文件：

- `mvp/ontology/commission-testing.ttl`
- `docs/cq/commission-testing-cqs.md`
- `mvp/rules/commission-testing.yml`
- `mvp/data/commission-testing-demo.json`

验证命令：

```powershell
python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py -q
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

如果 Fuseki 未启动，集成测试会 skip；发布演示前应在可写 Fuseki 环境跑通一次。
```

- [x] **Step 2: Update demo manual**

Add a new section to `docs/系统演示操作手册.md` after the five-minute script:

```markdown
## 委托单试验本体演示

### 客户演示

1. 打开 `委托单试验` 页签。
2. 点击“初始化 CO-2024-001 演示剧本”。
3. 展示委托单、产品、两个试验项目和两个自动任务。
4. 点击“发布 V2 标准并重判历史数据”。
5. 展示 RCS 均值从 `Pass` 翻转为 `Fail`，任务 `T-001` 自动变为 `NeedsReview`。
6. 说明误码率阈值未变，所以 `T-002` 仍为 `Pass`。

客户讲解重点：

- 委托单、产品、试验项目、任务、测试项、数据、标准、判据和结果是显式语义网络。
- 标准升级后系统自动找出旧标准下的数据并重判。
- 结论翻转不会覆盖旧结果，而是形成可追溯影响记录。

### 开发演示

1. 打开 `技术讲 -> CQ 工程台`。
2. 选择 `llm_with_template_fallback` 或 `template_only`。
3. 点击“生成候选 CQ / TBox / RBox”。
4. 查看候选 CQ、类、关系、属性、规则和草案 JSON。
5. 打开 `docs/cq/commission-testing-cqs.md` 展示可执行 CQ。
6. 运行：

```powershell
python -m pytest tests/test_commission_cq_engine.py -q
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

开发讲解重点：

- LLM 只生成候选草案，不直接覆盖正式 OWL。
- `template_only` 保证无网络或无 Key 时仍可演示。
- CQ SPARQL 是自动回归资产，不是普通问答样例。
```

- [x] **Step 3: Run doc-adjacent checks**

Run:

```powershell
python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py -q
```

Expected: all selected tests PASS.

- [x] **Step 4: Commit or checkpoint**

Real git:

```bash
git add README.md docs/系统演示操作手册.md
git commit -m "Document commission testing CQ demo

The README and demo manual now describe the customer and developer
paths for the commission-testing ontology so the new CQ workflow can
be rehearsed and validated consistently.

Confidence: high
Scope-risk: narrow
Tested: python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py -q"
```

Non-git checkpoint: list files and verification output.

---

### Task 9: Full Verification Pass

**Files:**
- No new files.
- Verify all files changed in Tasks 1-8.

- [x] **Step 1: Run offline focused tests**

Run:

```powershell
python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py tests/test_frontend_boundaries.py tests/test_ontology_registry.py -q
```

Expected: PASS.

- [x] **Step 2: Run compile check**

Run:

```powershell
python -m compileall mvp tests
```

Expected: compile completes with no syntax errors.

- [x] **Step 3: Run optional Fuseki integration**

Run when Fuseki is available:

```powershell
docker compose up -d
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

Expected: PASS when Fuseki is reachable and writable. If it skips because Fuseki is unavailable, record the skip reason and run it before customer demo.

- [x] **Step 4: Manual API smoke**

Start API:

```powershell
uvicorn mvp.api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/commission/demo/reset
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/v1/commission/standards/GJB-7821-2024/upgrade
Invoke-RestMethod http://127.0.0.1:8000/api/v1/commission/impacts/latest
```

Expected: latest impact includes `T-001`, `old_status=Pass`, `new_status=Fail`, `task_status=NeedsReview`.

- [x] **Step 5: Manual Streamlit smoke**

Start frontend:

```powershell
streamlit run mvp/frontend/app.py --server.port 8501
```

Open `http://127.0.0.1:8501`.

Expected:

- `委托单试验` tab initializes `CO-2024-001`.
- Standard upgrade shows `T-001` flip.
- `技术讲 -> CQ 工程台` with `template_only` creates and displays a draft.

- [x] **Step 6: Final commit or checkpoint**

Real git:

```bash
git status --short
git commit --allow-empty -m "Verify commission CQ engine demo

The commission-testing path has been verified across pure reasoning,
graph persistence, API routing, frontend boundaries, and optional
Fuseki CQ execution.

Confidence: medium
Scope-risk: moderate
Tested: python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py tests/test_frontend_boundaries.py tests/test_ontology_registry.py -q
Tested: python -m compileall mvp tests
Not-tested: Fuseki integration if local Fuseki was unavailable"
```

Non-git checkpoint: record exact command outputs and any skipped Fuseki integration.

Verification notes, 2026-04-29:

- `python -m pytest tests/test_commission_cq_integration.py -q -rs`: `1 passed`.
- `python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py -q`: `36 passed`.
- `python -m pytest tests/test_commission_reasoning.py tests/test_commission_graph.py tests/test_commission_cq_engine.py tests/test_commission_api.py tests/test_frontend_boundaries.py tests/test_ontology_registry.py -q`: `69 passed`.
- `python -m compileall mvp tests`: completed with no syntax errors.
- `docker compose up -d`: remote image pull for `apache/jena-fuseki:5.1.0` failed, but the already running local Fuseki was reachable and the commission CQ integration test passed against it.
- Manual API smoke on fresh port `8020`: `/commission/demo/reset`, `/commission/standards/GJB-7821-2024/upgrade`, and `/commission/impacts/latest` returned `T-001`, `Pass -> Fail`, `NeedsReview`.
- Manual Streamlit smoke via `streamlit.testing.v1.AppTest` against API `8010`: clicked reset, standard upgrade, selected `template_only`, generated/saved draft, and verified `impact_count=2`, `draft_count=3`.

## Self-Review

Spec coverage:

- New independent `commission-testing` ontology: Task 1.
- Customer full process demo: Tasks 3, 5, 6, 8.
- Developer CQ engineering demo: Tasks 4, 5, 6, 8.
- LLM mode switch with template fallback: Task 4 and Task 5.
- Page maintenance/query/modify draft surface: Task 4, Task 5, Task 6.
- Runnable standard upgrade rejudgement: Task 2 and Task 3.
- CQ/SPARQL validation: Task 7.
- Documentation split for customer and developer demos: Task 8.

Type consistency:

- The plan consistently uses `commission-testing`, `CO-2024-001`, `T-001`, `T-002`, `RCS_MEAN`, `BER`, `V1`, `V2`, `Pass`, `Fail`, and `NeedsReview`.
- Generation modes are consistently `llm_only`, `llm_with_template_fallback`, and `template_only`.
- Draft statuses are consistently `draft`, `reviewed`, `published`, and `rejected`.

Scope:

- The plan does not include equipment health, external imports, permissions, multi-user approval, or LLM writes to formal OWL.
