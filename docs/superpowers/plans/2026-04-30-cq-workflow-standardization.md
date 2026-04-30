# CQ Workflow Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scope-B CQ workflow gate that combines SAMOD/XD-inspired process documentation with SPARQL, SHACL, and pytest validation.

**Architecture:** Keep `mvp/core/cq_engine.py` as the existing commission CQ parser/release service. Add `mvp/core/cq_workflow.py` as the orchestration layer for SHACL validation and release evidence. Add a dedicated shapes graph at `mvp/shapes/commission-testing-shacl.ttl`.

**Tech Stack:** Python, rdflib, pySHACL, pytest, Markdown CQ specs, Turtle SHACL shapes.

---

### Task 1: Add SHACL Quality Gate Tests

**Files:**
- Create: `tests/test_cq_workflow.py`
- Create: `mvp/shapes/commission-testing-shacl.ttl`
- Create: `mvp/core/cq_workflow.py`

- [ ] **Step 1: Write failing SHACL report tests**

Create `tests/test_cq_workflow.py` with tests for a conforming graph and a broken graph.

- [ ] **Step 2: Run the new test file**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cq_workflow.py -q`

Expected: FAIL because `mvp.core.cq_workflow` does not exist.

- [ ] **Step 3: Implement minimal SHACL validation**

Create `mvp/core/cq_workflow.py` with `CQWorkflowError`, `CQQualityGateReport`, and `validate_shacl_graph`.

- [ ] **Step 4: Add commission SHACL shapes**

Create `mvp/shapes/commission-testing-shacl.ttl` covering the current commission demo model.

- [ ] **Step 5: Run the new test file**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cq_workflow.py -q`

Expected: PASS.

### Task 2: Add Release Gate Evidence

**Files:**
- Modify: `mvp/core/cq_engine.py`
- Modify: `tests/test_commission_cq_engine.py`
- Modify: `tests/test_commission_api.py`

- [ ] **Step 1: Write failing release evidence tests**

Assert that published release manifests contain `quality_gate` with `metadata`, `turtle`, and `shacl` status.

- [ ] **Step 2: Run targeted tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_commission_cq_engine.py tests/test_commission_api.py -q`

Expected: FAIL because release manifests do not include gate evidence.

- [ ] **Step 3: Integrate quality gate into publish**

Use `cq_workflow.validate_draft_quality_gate` inside `CQDraftService.publish_draft` before writing release files.

- [ ] **Step 4: Store quality gate in manifest**

Add the gate report to `_build_release_manifest` without changing existing exported file names.

- [ ] **Step 5: Run targeted tests again**

Run: `.venv\Scripts\python.exe -m pytest tests/test_commission_cq_engine.py tests/test_commission_api.py -q`

Expected: PASS.

### Task 3: Document the Standard Workflow

**Files:**
- Create: `docs/cq/cq-process.md`
- Modify: `README.md`
- Modify: `requirements.txt`

- [ ] **Step 1: Add workflow documentation**

Document the project CQ flow: story, CQ, context, formalization, unit gate, release gate, publication.

- [ ] **Step 2: Link from README**

Add a short pointer near existing CQ documentation.

- [ ] **Step 3: Add pySHACL dependency**

Add `pyshacl>=0.30` to `requirements.txt`.

### Task 4: Full Verification

**Files:**
- No additional files.

- [ ] **Step 1: Install dependency if missing**

Run: `.venv\Scripts\python.exe -m pip install pyshacl>=0.30`

- [ ] **Step 2: Run targeted CQ tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_cq_workflow.py tests/test_commission_cq_engine.py tests/test_commission_api.py -q`

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run: `.venv\Scripts\python.exe -m pytest -q`

Expected: PASS.

- [ ] **Step 4: Compile sources**

Run: `.venv\Scripts\python.exe -m compileall mvp tests`

Expected: exit code 0.
