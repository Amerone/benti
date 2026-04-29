from __future__ import annotations

import importlib
import os
import threading
import time

import pytest
from rdflib import Graph, RDF, OWL, URIRef


TURTLE_TEXT = """
@prefix ex: <https://example.test/onto#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Thing a owl:Class ;
    rdfs:label "测试类" .
ex:Part a owl:Class ;
    rdfs:label "部件" .

ex:partOf a owl:ObjectProperty ;
    rdfs:domain ex:Part ;
    rdfs:range ex:Thing .
ex:score a owl:DatatypeProperty ;
    rdfs:domain ex:Thing ;
    rdfs:range xsd:decimal .
ex:item-1 a ex:Thing .
"""


def _reasoner():
    return importlib.import_module("mvp.core.owlready_reasoner")


def test_turtle_to_rdfxml_writes_parseable_temp_file():
    reasoner = _reasoner()

    payload = reasoner._turtle_to_rdfxml(TURTLE_TEXT)

    assert payload.path.exists()
    assert "rdf:RDF" in payload.text

    graph = Graph()
    graph.parse(data=payload.text, format="xml")
    assert (URIRef("https://example.test/onto#Thing"), RDF.type, OWL.Class) in graph

    payload.cleanup()
    assert not payload.path.exists()


def test_load_and_reason_keeps_subjects_when_pellet_fails(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()

    def fake_pellet(*_args, **_kwargs):
        raise FileNotFoundError("java executable not found")

    monkeypatch.setattr(reasoner, "_run_pellet", fake_pellet)

    result = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True, force=True)

    assert result["pellet_status"] == "missing_java"
    assert "java executable not found" in result["pellet_error"]
    assert {item["iri"] for item in result["classes"]} >= {"https://example.test/onto#Thing"}
    assert {item["iri"] for item in result["object_properties"]} >= {"https://example.test/onto#partOf"}
    assert {item["iri"] for item in result["data_properties"]} >= {"https://example.test/onto#score"}


def test_failed_pellet_result_is_not_cached(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()
    calls = 0

    def flaky_pellet(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("first pellet failure")

    monkeypatch.setattr(reasoner, "_run_pellet", flaky_pellet)

    failed = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True)
    recovered = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True)
    cached = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True)

    assert failed["pellet_status"] == "failed"
    assert failed["cache_hit"] is False
    assert recovered["pellet_status"] == "success"
    assert recovered["cache_hit"] is False
    assert cached["pellet_status"] == "success"
    assert cached["cache_hit"] is True
    assert calls == 2


def test_subject_properties_include_domain_and_range_for_graph_view(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()

    result = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=False)

    object_property = next(
        item for item in result["object_properties"] if item["iri"] == "https://example.test/onto#partOf"
    )
    data_property = next(
        item for item in result["data_properties"] if item["iri"] == "https://example.test/onto#score"
    )

    assert object_property["domain"] == [
        {"iri": "https://example.test/onto#Part", "name": "Part", "label": "部件"}
    ]
    assert object_property["range"] == [
        {"iri": "https://example.test/onto#Thing", "name": "Thing", "label": "测试类"}
    ]
    assert data_property["domain"] == [
        {"iri": "https://example.test/onto#Thing", "name": "Thing", "label": "测试类"}
    ]
    assert data_property["range"] == [
        {"iri": "http://www.w3.org/2001/XMLSchema#decimal", "name": "decimal", "label": "decimal"}
    ]


def test_same_sha1_cache_key_serializes_concurrent_pellet_calls(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()
    calls = 0
    calls_lock = threading.Lock()

    def fake_pellet(*_args, **_kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)

    monkeypatch.setattr(reasoner, "_run_pellet", fake_pellet)

    results: list[dict] = []

    def worker():
        results.append(reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True))

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == 1
    assert [item["pellet_status"] for item in results] == ["success", "success"]
    assert any(item["cache_hit"] for item in results)


def test_lock_timeout_returns_busy_without_second_pellet_call(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()
    calls = 0
    calls_lock = threading.Lock()

    def slow_pellet(*_args, **_kwargs):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.08)

    monkeypatch.setattr(reasoner, "_run_pellet", slow_pellet)
    results: list[dict] = []

    first = threading.Thread(
        target=lambda: results.append(
            reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True, lock_timeout_ms=1000)
        )
    )
    first.start()
    time.sleep(0.01)
    busy = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True, lock_timeout_ms=1)
    first.join()

    assert busy["pellet_status"] == "busy"
    assert busy["retry_after_ms"] > 0
    assert calls == 1


def test_swrl_compare_mode_exposes_fallback_without_blocking_subjects(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()

    pellet_kwargs: list[dict] = []

    def fake_pellet(*_args, **kwargs):
        pellet_kwargs.append(kwargs)

    monkeypatch.setattr(reasoner, "_run_pellet", fake_pellet)

    result = reasoner.load_and_reason(
        "demo",
        TURTLE_TEXT,
        run_pellet=True,
        enable_swrl=True,
        swrl_text="Thing(?x) -> Thing(?x)",
        force=True,
    )

    assert result["pellet_status"] == "success"
    assert result["swrl_enabled"] is True
    assert result["swrl_status"] == "fallback"
    assert "Owlready2" in result["swrl_error"]
    assert pellet_kwargs and pellet_kwargs[0]["enable_swrl"] is True
    assert result["classes"]


def test_pellet_java_version_error_is_normalized(monkeypatch):
    reasoner = _reasoner()
    reasoner.clear_reasoner_cache()

    def fake_pellet(*_args, **_kwargs):
        raise RuntimeError(
            'Java error message is:\n'
            'Exception in thread "main" java.lang.UnsupportedClassVersionError: '
            'org/apache/jena/riot/lang/LangRDFXML has been compiled by a more recent version '
            'of the Java Runtime (class file version 69.0), this version of the Java Runtime '
            'only recognizes class file versions up to 65.0'
        )

    monkeypatch.setattr(reasoner, "_run_pellet", fake_pellet)

    result = reasoner.load_and_reason("demo", TURTLE_TEXT, run_pellet=True, force=True)

    assert result["pellet_status"] == "failed"
    assert "Java 运行时版本不兼容" in result["pellet_error"]
    assert "class file version 69.0" in result["pellet_error"]


def test_describe_java_runtime_prefers_embedded_jre(monkeypatch, tmp_path):
    reasoner = _reasoner()
    java_name = "java.exe" if os.name == "nt" else "java"
    embedded_java = tmp_path / "runtime" / "jre" / "temurin-25.0.2+10" / "bin" / java_name
    embedded_java.parent.mkdir(parents=True)
    embedded_java.write_text("", encoding="utf-8")

    monkeypatch.delenv("PELLET_JAVA_EXE", raising=False)
    monkeypatch.delenv("PELLET_JAVA_HOME", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(reasoner.shutil, "which", lambda _name: None)

    runtime = reasoner.describe_java_runtime(tmp_path)

    assert runtime["java_exe"] == str(embedded_java.resolve())
    assert runtime["source"] == "embedded_jre"


def test_describe_java_runtime_prefers_explicit_executable_override(monkeypatch, tmp_path):
    reasoner = _reasoner()
    java_name = "java.exe" if os.name == "nt" else "java"
    embedded_java = tmp_path / "runtime" / "jre" / "temurin-25.0.2+10" / "bin" / java_name
    embedded_java.parent.mkdir(parents=True)
    embedded_java.write_text("", encoding="utf-8")

    override_java = tmp_path / "custom-java" / "bin" / java_name
    override_java.parent.mkdir(parents=True)
    override_java.write_text("", encoding="utf-8")

    monkeypatch.setenv("PELLET_JAVA_EXE", str(override_java))
    monkeypatch.setattr(reasoner.shutil, "which", lambda _name: None)

    runtime = reasoner.describe_java_runtime(tmp_path)

    assert runtime["java_exe"] == str(override_java.resolve())
    assert runtime["source"] == "PELLET_JAVA_EXE"


def test_run_pellet_binds_owlready_to_embedded_java(monkeypatch, tmp_path):
    reasoner = _reasoner()
    java_name = "java.exe" if os.name == "nt" else "java"
    embedded_java = tmp_path / "runtime" / "jre" / "temurin-25.0.2+10" / "bin" / java_name
    embedded_java.parent.mkdir(parents=True)
    embedded_java.write_text("", encoding="utf-8")

    monkeypatch.setattr(reasoner, "_PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("PELLET_JAVA_EXE", raising=False)
    monkeypatch.delenv("PELLET_JAVA_HOME", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(reasoner.shutil, "which", lambda _name: None)

    captured = {}

    def fake_sync_reasoner_pellet(*args, **kwargs):
        captured["java_exe"] = reasoner.owlready2.JAVA_EXE

    monkeypatch.setattr(reasoner, "sync_reasoner_pellet", fake_sync_reasoner_pellet)

    reasoner._run_pellet(
        world=None,
        ontology=object(),
        enable_swrl=False,
        swrl_text=None,
        swrl_path=None,
    )

    assert captured["java_exe"] == str(embedded_java.resolve())


def test_run_pellet_reports_embedded_jre_hint_when_java_is_missing(monkeypatch, tmp_path):
    reasoner = _reasoner()

    monkeypatch.setattr(reasoner, "_PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("PELLET_JAVA_EXE", raising=False)
    monkeypatch.delenv("PELLET_JAVA_HOME", raising=False)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    monkeypatch.setattr(reasoner.shutil, "which", lambda _name: None)

    with pytest.raises(FileNotFoundError) as exc_info:
        reasoner._run_pellet(
            world=None,
            ontology=object(),
            enable_swrl=False,
            swrl_text=None,
            swrl_path=None,
        )

    assert "runtime" in str(exc_info.value)
    assert "PELLET_JAVA_EXE" in str(exc_info.value)
