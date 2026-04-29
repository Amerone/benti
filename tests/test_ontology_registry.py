from pathlib import Path
import importlib.util

import pytest

from mvp.core.ontology_registry import discover


def _write_ttl(path: Path, header: str) -> None:
    path.write_text(
        header
        + """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix mto: <https://hifar.top/mto#> .

<https://hifar.top/mto/test> a owl:Ontology .
mto:SampleClass a owl:Class ;
    rdfs:label "样例类"@zh .
""",
        encoding="utf-8",
    )


def test_discover_reads_header_metadata_and_graph_iris(tmp_path: Path) -> None:
    (tmp_path / "alpha.swrl").write_text("# rules", encoding="utf-8")
    _write_ttl(
        tmp_path / "alpha.ttl",
        """# ontology-id: alpha
# ontology-label: 甲本体
# ontology-version: 1.2.3
# ontology-swrl: alpha.swrl
""",
    )
    _write_ttl(
        tmp_path / "beta.ttl",
        """# ontology-id: beta
# ontology-label: 乙本体
# ontology-version: 0.1.0
""",
    )

    descriptors = discover(tmp_path)

    assert [item.ontology_id for item in descriptors] == ["alpha", "beta"]
    alpha = descriptors[0]
    assert alpha.label == "甲本体"
    assert alpha.version == "1.2.3"
    assert alpha.ttl_path == tmp_path / "alpha.ttl"
    assert alpha.swrl_path == tmp_path / "alpha.swrl"
    assert alpha.graph_iri == "https://hifar.top/mto/graph/alpha"
    assert alpha.data_graph_iri == "https://hifar.top/mto/graph/alpha/data"
    assert alpha.result_graph_iri == "https://hifar.top/mto/graph/alpha/result"
    assert alpha.spec_graph_iri == "https://hifar.top/mto/graph/alpha/spec"


def test_missing_ontology_id_is_warned_and_skipped(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_ttl(
        tmp_path / "filename-must-not-be-used.ttl",
        """# ontology-label: 无 ID 本体
# ontology-version: 1.0.0
""",
    )

    with caplog.at_level("WARNING"):
        descriptors = discover(tmp_path)

    assert descriptors == []
    assert "missing ontology-id" in caplog.text
    assert "filename-must-not-be-used" in caplog.text


def test_missing_swrl_file_does_not_block_discovery(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_ttl(
        tmp_path / "alpha.ttl",
        """# ontology-id: alpha
# ontology-label: 甲本体
# ontology-version: 1.0.0
# ontology-swrl: absent.swrl
""",
    )

    with caplog.at_level("WARNING"):
        descriptors = discover(tmp_path)

    assert len(descriptors) == 1
    assert descriptors[0].swrl_path is None
    assert "missing swrl" in caplog.text
    assert "absent.swrl" in caplog.text


def test_packaged_ontologies_and_swrl_examples_are_valid() -> None:
    ontology_dir = Path("mvp/ontology")

    descriptors = discover(ontology_dir)
    by_id = {item.ontology_id: item for item in descriptors}

    assert {"manufacturing-trial", "process-window", "equipment-health"} <= set(by_id)
    assert by_id["manufacturing-trial"].swrl_path == ontology_dir / "manufacturing-trial.swrl"

    trial_text = by_id["manufacturing-trial"].ttl_path.read_text(encoding="utf-8")
    for class_name in ["Trial", "Batch", "Parameter", "Measurement", "Specification", "Result"]:
        assert f"mto:{class_name}" in trial_text
        assert "a owl:Class" in trial_text
    for property_name in [
        "hasBatch",
        "forBatch",
        "forParameter",
        "measuredValue",
        "lowerLimit",
        "upperLimit",
        "resultStatus",
        "appliedRule",
    ]:
        assert f"mto:{property_name}" in trial_text
    for chinese_label in ["试验", "批次", "参数", "测量记录", "规格", "判定结果"]:
        assert f'"{chinese_label}"@zh' in trial_text

    process_text = by_id["process-window"].ttl_path.read_text(encoding="utf-8")
    assert process_text.count("a owl:Class") >= 2

    equipment_text = by_id["equipment-health"].ttl_path.read_text(encoding="utf-8")
    assert "设备健康本体" in equipment_text
    for class_name in ["Equipment", "SensorReading", "HealthThreshold", "MaintenanceWorkOrder"]:
        assert f"eho:{class_name}" in equipment_text

    swrl_text = by_id["manufacturing-trial"].swrl_path.read_text(encoding="utf-8")
    assert "Rule_Pass" in swrl_text
    assert "Rule_Fail_Low" in swrl_text
    assert "Rule_Fail_High" in swrl_text

    if importlib.util.find_spec("rdflib") is not None:
        from rdflib import Graph

        Graph().parse(by_id["manufacturing-trial"].ttl_path, format="turtle")
        Graph().parse(by_id["process-window"].ttl_path, format="turtle")
        Graph().parse(by_id["equipment-health"].ttl_path, format="turtle")
