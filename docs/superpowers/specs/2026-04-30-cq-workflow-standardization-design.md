# CQ Workflow Standardization Design

## Goal

Standardize the project CQ workflow by borrowing the practical parts of SAMOD and eXtreme Design: small story-driven ontology increments, executable Competency Questions, explicit context/constraint checks, and release gates backed by SPARQL, SHACL, and pytest.

## Current State

The project already has an executable CQ path:

- `docs/cq/commission-testing-cqs.md` stores human-readable CQs.
- `mvp/core/cq_engine.py` parses CQ Markdown, runs SPARQL, validates expected rows, and manages draft releases.
- `tests/test_commission_cq_engine.py` and `tests/test_commission_cq_integration.py` protect parsing, draft lifecycle, and selected integration behavior.

The missing pieces are:

- No SHACL shapes are executed as part of CQ validation.
- CQ lifecycle metadata is not normalized into a reusable workflow contract.
- Release publication validates payload shape but not the full CQ quality gate.
- The process is documented in scattered planning docs, not as a reusable operating workflow.

## Borrowed Process

The project will use this constrained workflow:

1. **Story**: capture one customer/business scenario as the unit of work.
2. **CQ**: derive one or a coherent small set of natural-language questions from the story.
3. **Context**: state demo data, business terms, and expected evidence fields.
4. **Formalization**: attach executable SPARQL for answerability and SHACL for structural validity.
5. **Unit Gate**: run CQ parser tests, SPARQL expected-result checks, and SHACL validation via pytest.
6. **Release Gate**: block publish unless generated drafts contain reviewable CQs, SPARQL tests, and a conforming SHACL result.
7. **Documentation**: record the workflow and validation contract near the CQ docs.

## Architecture

Add a small core module, `mvp/core/cq_workflow.py`, responsible for CQ quality-gate orchestration. It must not replace `cq_engine.py`; it wraps existing parser/runner behavior and adds SHACL validation as a separate concern.

Add `mvp/shapes/commission-testing-shacl.ttl` as the first project SHACL shapes graph. The shapes should focus on real demo expectations that matter to the current commission workflow:

- commission orders must have `cto:orderNo`;
- test projects must have `cto:localId` and at least one `cto:decomposesToTask`;
- test tasks must have `cto:localId` and `cto:taskStatus`;
- judgement results must have `cto:resultStatus`;
- reevaluation impacts must link old/new results and impacted task.

Use `pyshacl` for real SHACL validation. Add it to `requirements.txt` because SHACL is now an explicit project capability.

## Data Flow

For local tests:

1. Build a demo `rdflib.Graph` using existing commission graph fixture helpers.
2. Load `mvp/shapes/commission-testing-shacl.ttl`.
3. Run SHACL validation.
4. Run existing CQ SPARQL checks.
5. Return a combined quality-gate report.

For API/draft release:

1. Validate draft payload fields.
2. Require at least one candidate CQ and one draft SPARQL test.
3. Validate draft Turtle syntax.
4. Run SHACL against draft Turtle when shapes are available.
5. Store gate evidence in the release manifest.

## Error Handling

Raise `CQEngineError` for release-blocking gate failures. Reports should include explicit failure categories:

- `metadata`;
- `sparql`;
- `shacl`;
- `turtle`;
- `release`.

This keeps API error mapping unchanged while making diagnostics actionable.

## Testing Strategy

Use TDD:

- first add tests that fail because SHACL gate/report support does not exist;
- implement minimal gate functions;
- add release-manifest assertions;
- run targeted CQ tests, then the full pytest suite and compile check.

## References

- SAMOD: https://essepuntato.it/samod/
- eXtreme Design: https://www.ida.liu.se/~evabl45/files/XD.pdf
- W3C SHACL: https://www.w3.org/TR/shacl/
