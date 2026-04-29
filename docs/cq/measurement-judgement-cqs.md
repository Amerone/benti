# Measurement Judgement Competency Questions

These competency questions define the first executable requirements for the measurement judgement loop. Each CQ is business-readable and machine-executable: the SPARQL block is the validation query rendered by the CQ runner, `Expected` is the assertion set, and `Evidence fields` is the contract shared with QA evidence.

## CQ-MJ-001 Why is M007 Fail_High?

- Business question: M007 为什么 Fail？
- Intent: why_fail
- Covers: Measurement, Specification, Result
- Demo data: M007, cq_temperature=197.2, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Fail_High, rule=Rule_Fail_High, spec_version=Spec_v1, deviation=2.2

```sparql
PREFIX mto: <https://hifar.top/mto#>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?m a mto:Measurement ;
       mto:localId "M007" ;
       mto:localId ?measurement_id ;
       mto:measuredValue ?value .
  }
  GRAPH <{{result_graph_iri}}> {
    ?m mto:hasLatestResult ?r .
    ?r mto:resultStatus ?status ;
       mto:appliedRule ?rule ;
       mto:againstSpecVersion ?spec_version ;
       mto:evidenceLowerLimit ?lower_limit ;
       mto:evidenceUpperLimit ?upper_limit ;
       mto:deviation ?deviation ;
       mto:reasoner ?reasoner ;
       mto:inferredAt ?inferred_at .
  }
}
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M007 为什么 Fail？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.

## CQ-MJ-002 Why is M008 Fail_Low?

- Business question: M008 为什么 Fail？
- Intent: why_fail
- Covers: Measurement, Specification, Result
- Demo data: M008, cq_temperature=179.1, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Fail_Low, rule=Rule_Fail_Low, spec_version=Spec_v1, deviation=0.9

```sparql
PREFIX mto: <https://hifar.top/mto#>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?m a mto:Measurement ;
       mto:localId "M008" ;
       mto:localId ?measurement_id ;
       mto:measuredValue ?value .
  }
  GRAPH <{{result_graph_iri}}> {
    ?m mto:hasLatestResult ?r .
    ?r mto:resultStatus ?status ;
       mto:appliedRule ?rule ;
       mto:againstSpecVersion ?spec_version ;
       mto:evidenceLowerLimit ?lower_limit ;
       mto:evidenceUpperLimit ?upper_limit ;
       mto:deviation ?deviation ;
       mto:reasoner ?reasoner ;
       mto:inferredAt ?inferred_at .
  }
}
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M008 为什么 Fail？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.

## CQ-MJ-003 Why is M009 Pass?

- Business question: M009 为什么 Pass？
- Intent: why_judgement
- Covers: Measurement, Specification, Result
- Demo data: M009, cq_temperature=188.0, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Pass, rule=Rule_Pass, spec_version=Spec_v1, deviation=0.0

```sparql
PREFIX mto: <https://hifar.top/mto#>
SELECT ?measurement_id ?value ?status ?rule ?spec_version ?lower_limit ?upper_limit ?deviation ?reasoner ?inferred_at WHERE {
  GRAPH <{{data_graph_iri}}> {
    ?m a mto:Measurement ;
       mto:localId "M009" ;
       mto:localId ?measurement_id ;
       mto:measuredValue ?value .
  }
  GRAPH <{{result_graph_iri}}> {
    ?m mto:hasLatestResult ?r .
    ?r mto:resultStatus ?status ;
       mto:appliedRule ?rule ;
       mto:againstSpecVersion ?spec_version ;
       mto:evidenceLowerLimit ?lower_limit ;
       mto:evidenceUpperLimit ?upper_limit ;
       mto:deviation ?deviation ;
       mto:reasoner ?reasoner ;
       mto:inferredAt ?inferred_at .
  }
}
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M009 为什么 Pass？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.
