"""Owlready2/Pellet 语义加载与推理。

本模块只接受来自 Fuseki `CONSTRUCT` 的 Turtle 文本，不直接读取本地 TTL 文件。
它负责把 Turtle 先转成 Owlready2 更稳定支持的 RDF/XML，再加载到独立 World，
并在可选情况下执行 Pellet。Pellet 失败、Java 缺失或 SWRL 对照模式受限时，都
不能阻断 classes / individuals / properties 主体返回。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import hashlib
import os
import shutil
import tempfile
import threading
import time
from typing import Any

import owlready2
from owlready2 import World, sync_reasoner_pellet
from rdflib import Graph

DEFAULT_LOCK_TIMEOUT_MS = 30_000
DEFAULT_RETRY_AFTER_MS = 2_000
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_JAVA_EXE_ENV_VARS = ("PELLET_JAVA_EXE",)
_JAVA_HOME_ENV_VARS = ("PELLET_JAVA_HOME", "JAVA_HOME")

_CACHE_LOCK = threading.Lock()
_REASONER_CACHE: dict[str, dict[str, Any]] = {}
_REASONER_LOCKS: dict[str, threading.Lock] = {}


@dataclass(frozen=True)
class RdfXmlPayload:
    """RDF/XML 临时载荷。

    `_turtle_to_rdfxml()` 既返回 RDF/XML 文本，也返回可供 Owlready2 `World.load()`
    使用的临时文件路径。调用方完成加载后应显式执行 `cleanup()` 清理临时文件。
    """

    path: Path
    text: str

    def cleanup(self) -> None:
        """删除临时 RDF/XML 文件。"""

        try:
            self.path.unlink(missing_ok=True)
        except TypeError:
            if self.path.exists():
                self.path.unlink()


def clear_reasoner_cache() -> None:
    """清理模块级缓存与锁。

    该函数主要用于测试隔离；运行时不会自动调用，以保留同一进程内的 Pellet
    结果复用能力。
    """

    with _CACHE_LOCK:
        _REASONER_CACHE.clear()
        _REASONER_LOCKS.clear()


def describe_java_runtime(project_root: Path | None = None) -> dict[str, Any]:
    """Resolve the Java runtime for Owlready2/Pellet.

    Resolution order is:
    1. Explicit executable via `PELLET_JAVA_EXE`
    2. Project-local embedded runtime under `runtime/jre`
    3. Java home via `PELLET_JAVA_HOME` / `JAVA_HOME`
    4. System `PATH`
    """

    root = Path(project_root) if project_root is not None else _PROJECT_ROOT
    embedded_root = root / "runtime" / "jre"
    expected_path = embedded_root / "bin" / _java_executable_name()

    for env_var in _JAVA_EXE_ENV_VARS:
        candidate = _resolve_configured_path(os.getenv(env_var), root)
        if candidate is not None and candidate.is_file():
            return _java_runtime_info(candidate, env_var, embedded_root)

    for candidate in _iter_embedded_java_candidates(embedded_root):
        if candidate.is_file():
            return _java_runtime_info(candidate, "embedded_jre", embedded_root)

    for env_var in _JAVA_HOME_ENV_VARS:
        home = _resolve_configured_path(os.getenv(env_var), root)
        candidate = None if home is None else home / "bin" / _java_executable_name()
        if candidate is not None and candidate.is_file():
            return _java_runtime_info(candidate, env_var, embedded_root)

    system_java = shutil.which(_java_executable_name())
    if system_java:
        return _java_runtime_info(Path(system_java), "PATH", embedded_root)

    return {
        "java_exe": None,
        "source": None,
        "embedded_root": str(embedded_root),
        "embedded_expected_path": str(expected_path),
        "error": (
            "Java runtime not found. Expected an embedded JRE at "
            f"{expected_path}, or set PELLET_JAVA_EXE / PELLET_JAVA_HOME."
        ),
    }


def configure_owlready_java_exe(project_root: Path | None = None) -> dict[str, Any]:
    """Point Owlready2 to the resolved Java runtime."""

    runtime = describe_java_runtime(project_root)
    if runtime["java_exe"]:
        owlready2.JAVA_EXE = runtime["java_exe"]
    return runtime


def _java_executable_name() -> str:
    return "java.exe" if os.name == "nt" else "java"


def _resolve_configured_path(raw: str | None, project_root: Path) -> Path | None:
    if not raw:
        return None
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate


def _iter_embedded_java_candidates(embedded_root: Path) -> list[Path]:
    java_name = _java_executable_name()
    candidates: list[Path] = [embedded_root / "bin" / java_name]
    if embedded_root.exists():
        for child in sorted(embedded_root.iterdir()):
            if child.is_dir():
                candidates.append(child / "bin" / java_name)
    return candidates


def _java_runtime_info(java_exe: Path, source: str, embedded_root: Path) -> dict[str, Any]:
    return {
        "java_exe": str(java_exe.resolve()),
        "source": source,
        "embedded_root": str(embedded_root),
        "embedded_expected_path": str(embedded_root / "bin" / _java_executable_name()),
        "error": None,
    }


def _turtle_to_rdfxml(turtle_text: str, *, trace: Any | None = None) -> RdfXmlPayload:
    """将 Fuseki `CONSTRUCT` 返回的 Turtle 文本转换为 RDF/XML 临时文件。

    之所以做这一步，是因为 Owlready2 对 RDF/XML 的加载路径更稳定。函数同时返回
    文本和临时文件，便于测试校验转换结果，也便于 `World.load()` 直接消费。
    """

    graph = Graph()
    graph.parse(data=turtle_text, format="turtle")
    rdfxml_text = graph.serialize(format="xml")

    fd, file_name = tempfile.mkstemp(prefix="owlready-", suffix=".rdf")
    os.close(fd)
    payload = RdfXmlPayload(path=Path(file_name), text=str(rdfxml_text))
    payload.path.write_text(payload.text, encoding="utf-8")
    _trace_log(
        trace,
        "turtle_to_rdfxml",
        "success",
        reason="将 Fuseki Turtle 输入转换为 Owlready2 可稳定加载的 RDF/XML。",
        triple_count=len(graph),
        rdfxml_path=str(payload.path),
    )
    return payload


def load_and_reason(
    ontology_id: str,
    turtle_text: str,
    *,
    run_pellet: bool = True,
    cache_key: str | None = None,
    trace: Any | None = None,
    force: bool = False,
    lock_timeout_ms: int = DEFAULT_LOCK_TIMEOUT_MS,
    retry_after_ms: int = DEFAULT_RETRY_AFTER_MS,
    enable_swrl: bool = False,
    swrl_text: str | None = None,
    swrl_path: str | Path | None = None,
) -> dict[str, Any]:
    """从 Turtle 文本加载本体主体，并按需执行 Pellet。

    参数：
    - `ontology_id`：当前请求的本体 ID，仅用于结果标识与 trace。
    - `turtle_text`：必须来自 Fuseki `CONSTRUCT` 的 Turtle 文本。
    - `run_pellet`：是否执行 Pellet。
    - `cache_key`：可选稳定指纹；若未提供，则使用 Turtle 文本与开关组合做 SHA1。
    - `trace`：可选链路记录对象；不存在时自动退化为 no-op。
    - `force`：为 `True` 时跳过缓存。
    - `enable_swrl` / `swrl_text` / `swrl_path`：SWRL 对照模式接口。若 Owlready2 当前
      路径不适合完整导入，会给出明确 fallback，但不影响确定性主体结果。

    返回值总是包含 `classes` / `individuals` / `object_properties` / `data_properties`
    以及 `pellet_status` / `pellet_ms` / `pellet_error` 等字段。锁等待超时时返回
    `pellet_status="busy"` 和 `retry_after_ms`，供 HTTP 层包装成 200。
    """

    effective_cache_key = _build_cache_key(
        turtle_text=turtle_text,
        cache_key=cache_key,
        run_pellet=run_pellet,
        enable_swrl=enable_swrl,
        swrl_text=swrl_text,
        swrl_path=swrl_path,
    )

    if run_pellet and not force:
        cached = _cache_get(effective_cache_key)
        if cached is not None:
            cached["cache_hit"] = True
            return cached

    if not run_pellet:
        return _load_reasoner_result(
            ontology_id=ontology_id,
            turtle_text=turtle_text,
            run_pellet=False,
            cache_key=effective_cache_key,
            trace=trace,
            enable_swrl=enable_swrl,
            swrl_text=swrl_text,
            swrl_path=swrl_path,
        )

    lock = _get_lock(effective_cache_key)
    acquired = lock.acquire(timeout=max(lock_timeout_ms, 0) / 1000)
    if not acquired:
        _trace_log(
            trace,
            "sync_reasoner_pellet",
            "failed",
            reason="同一 Turtle 指纹的 Pellet 调用仍在执行，锁等待超时。",
            pellet_status="busy",
            retry_after_ms=retry_after_ms,
        )
        return {
            "ontology_id": ontology_id,
            "loaded_by": "owlready2",
            "reasoner": "pellet",
            "classes": [],
            "individuals": [],
            "object_properties": [],
            "data_properties": [],
            "pellet_status": "busy",
            "pellet_ms": None,
            "pellet_error": "lock timeout",
            "retry_after_ms": retry_after_ms,
            "cache_key": effective_cache_key,
            "cache_hit": False,
            "swrl_enabled": enable_swrl,
            "swrl_status": "disabled" if not enable_swrl else "fallback",
            "swrl_error": None if not enable_swrl else _swrl_fallback_message(swrl_path),
        }

    try:
        if not force:
            cached = _cache_get(effective_cache_key)
            if cached is not None:
                cached["cache_hit"] = True
                return cached

        result = _load_reasoner_result(
            ontology_id=ontology_id,
            turtle_text=turtle_text,
            run_pellet=True,
            cache_key=effective_cache_key,
            trace=trace,
            enable_swrl=enable_swrl,
            swrl_text=swrl_text,
            swrl_path=swrl_path,
        )
        if not force and _is_cacheable_reasoner_result(result):
            _cache_put(effective_cache_key, result)
        return copy.deepcopy(result)
    finally:
        lock.release()


def _load_reasoner_result(
    *,
    ontology_id: str,
    turtle_text: str,
    run_pellet: bool,
    cache_key: str,
    trace: Any | None,
    enable_swrl: bool,
    swrl_text: str | None,
    swrl_path: str | Path | None,
) -> dict[str, Any]:
    rdfxml_payload = _turtle_to_rdfxml(turtle_text, trace=trace)
    try:
        world = World()
        ontology = _load_ontology(world, rdfxml_payload.path, trace=trace)
        java_runtime = describe_java_runtime()

        swrl_status = "disabled"
        swrl_error = None
        if enable_swrl:
            swrl_status = "fallback"
            swrl_error = _swrl_fallback_message(swrl_path)

        pellet_status = "not_run"
        pellet_error = None
        pellet_ms = None

        if run_pellet:
            started = time.perf_counter()
            try:
                _run_pellet(
                    world=world,
                    ontology=ontology,
                    enable_swrl=enable_swrl,
                    swrl_text=swrl_text,
                    swrl_path=swrl_path,
                )
                pellet_status = "success"
                _trace_log(
                    trace,
                    "sync_reasoner_pellet",
                    "success",
                    reason="Pellet 已完成 OWL 推理；主体采集继续从当前 World 读取。",
                    enable_swrl=enable_swrl,
                    swrl_status=swrl_status,
                )
            except FileNotFoundError as exc:
                pellet_status = "missing_java"
                pellet_error = str(exc)
                _trace_log(
                    trace,
                    "sync_reasoner_pellet",
                    "failed",
                    reason="Java 或 Pellet 可执行环境缺失，保留主体结果并降级返回。",
                    error=pellet_error,
                )
            except Exception as exc:  # pragma: no cover
                pellet_status = "failed"
                pellet_error = _normalize_pellet_error(exc)
                _trace_log(
                    trace,
                    "sync_reasoner_pellet",
                    "failed",
                    reason="Pellet 执行失败，但不影响返回 classes/properties 主体。",
                    error=pellet_error,
                )
            pellet_ms = int((time.perf_counter() - started) * 1000)

        subjects = _collect_subjects(ontology, trace=trace)
        return {
            "ontology_id": ontology_id,
            "loaded_by": "owlready2",
            "reasoner": "pellet" if run_pellet else "owlready2",
            "classes": subjects["classes"],
            "individuals": subjects["individuals"],
            "object_properties": subjects["object_properties"],
            "data_properties": subjects["data_properties"],
            "pellet_status": pellet_status,
            "pellet_ms": pellet_ms,
            "pellet_error": pellet_error,
            "java_exe": java_runtime.get("java_exe"),
            "java_source": java_runtime.get("source"),
            "retry_after_ms": None,
            "cache_key": cache_key,
            "cache_hit": False,
            "swrl_enabled": enable_swrl,
            "swrl_status": swrl_status,
            "swrl_error": swrl_error,
        }
    finally:
        rdfxml_payload.cleanup()


def _normalize_pellet_error(exc: Exception) -> str:
    """把常见 Pellet/Java 底层异常整理成更可执行的运行提示。"""

    message = str(exc)
    if "UnsupportedClassVersionError" in message and "class file version" in message:
        return (
            "Pellet/Jena 与当前 Java 运行时版本不兼容。"
            "请升级 Java 到与依赖 class file version 匹配的版本，或改用与当前 Java 兼容的 Pellet/Jena 依赖。\n"
            f"{message}"
        )
    return message


def _load_ontology(world: World, rdfxml_path: Path, *, trace: Any | None = None):
    ontology_iri = f"https://example.test/generated/{rdfxml_path.stem}.owl"
    ontology = world.get_ontology(ontology_iri).load(fileobj=rdfxml_path.open("rb"))
    _trace_log(
        trace,
        "owlready_load",
        "success",
        reason="通过临时 RDF/XML 文件加载 Owlready2 World。",
        rdfxml_path=str(rdfxml_path),
        ontology_iri=ontology_iri,
    )
    return ontology


def _run_pellet(
    *,
    world: World,
    ontology: Any,
    enable_swrl: bool,
    swrl_text: str | None,
    swrl_path: str | Path | None,
) -> None:
    """执行 Pellet。

    SWRL 对照模式当前仅保留接口与 trace/返回结构，不在此路径中直接导入 raw SWRL。
    这样可以先满足 MVP 的可测开关要求，同时避免因为 Owlready2 对 SWRL 文本导入
    能力有限而破坏 Python 侧的确定性业务结果。
    """

    _ = world, enable_swrl, swrl_text, swrl_path
    runtime = configure_owlready_java_exe()
    if not runtime["java_exe"]:
        raise FileNotFoundError(runtime["error"])
    sync_reasoner_pellet([ontology], infer_property_values=True, infer_data_property_values=True)


def _collect_subjects(ontology: Any, *, trace: Any | None = None) -> dict[str, list[dict[str, Any]]]:
    result = {
        "classes": sorted((_entity_to_dict(item) for item in ontology.classes()), key=_sort_key),
        "individuals": sorted((_entity_to_dict(item) for item in ontology.individuals()), key=_sort_key),
        "object_properties": sorted(
            (_entity_to_dict(item) for item in ontology.object_properties()),
            key=_sort_key,
        ),
        "data_properties": sorted(
            (_entity_to_dict(item) for item in ontology.data_properties()),
            key=_sort_key,
        ),
    }
    _trace_log(
        trace,
        "collect_subjects",
        "success",
        reason="从当前 Owlready2 ontology 采集类、个体和属性，供 UI/API 展示。",
        class_count=len(result["classes"]),
        individual_count=len(result["individuals"]),
        object_property_count=len(result["object_properties"]),
        data_property_count=len(result["data_properties"]),
    )
    return result


def _entity_to_dict(entity: Any) -> dict[str, Any]:
    labels = getattr(entity, "label", []) or []
    item = {"iri": getattr(entity, "iri", str(entity))}
    if getattr(entity, "name", None):
        item["name"] = entity.name
    if labels:
        item["label"] = str(labels[0])
    domain = _entity_reference_list(getattr(entity, "domain", []) or [])
    range_items = _entity_reference_list(getattr(entity, "range", []) or [])
    types = _entity_reference_list(getattr(entity, "is_a", []) or [])
    if domain:
        item["domain"] = domain
    if range_items:
        item["range"] = range_items
    if types:
        item["types"] = types
    return item


def _entity_reference_list(values: Any) -> list[dict[str, str]]:
    refs = []
    for value in list(values or []):
        ref = _entity_reference(value)
        if ref is None:
            continue
        refs.append(ref)
    refs.sort(key=lambda item: (item["label"], item["iri"]))
    return refs


def _entity_reference(value: Any) -> dict[str, str] | None:
    iri = getattr(value, "iri", None)
    if iri:
        name = str(getattr(value, "name", "") or str(iri).rstrip("/#").split("/")[-1].split("#")[-1])
        labels = getattr(value, "label", []) or []
        return {
            "iri": str(iri),
            "name": name,
            "label": str(labels[0]) if labels else name,
        }

    datatype = _datatype_reference(value)
    if datatype is not None:
        return datatype
    return None


def _datatype_reference(value: Any) -> dict[str, str] | None:
    datatype_map = {
        str: "string",
        int: "integer",
        float: "decimal",
        bool: "boolean",
    }
    name = datatype_map.get(value)
    if name is None:
        return None
    return {
        "iri": f"http://www.w3.org/2001/XMLSchema#{name}",
        "name": name,
        "label": name,
    }


def _sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("label", "")), str(item.get("iri", "")))


def _build_cache_key(
    *,
    turtle_text: str,
    cache_key: str | None,
    run_pellet: bool,
    enable_swrl: bool,
    swrl_text: str | None,
    swrl_path: str | Path | None,
) -> str:
    raw = "\n".join(
        [
            cache_key or turtle_text,
            f"run_pellet={run_pellet}",
            f"enable_swrl={enable_swrl}",
            swrl_text or "",
            str(swrl_path or ""),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _get_lock(cache_key: str) -> threading.Lock:
    with _CACHE_LOCK:
        lock = _REASONER_LOCKS.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _REASONER_LOCKS[cache_key] = lock
        return lock


def _cache_get(cache_key: str) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        cached = _REASONER_CACHE.get(cache_key)
    return None if cached is None else copy.deepcopy(cached)


def _cache_put(cache_key: str, result: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _REASONER_CACHE[cache_key] = copy.deepcopy(result)


def _is_cacheable_reasoner_result(result: dict[str, Any]) -> bool:
    return result.get("pellet_status") == "success"


def _swrl_fallback_message(swrl_path: str | Path | None) -> str:
    suffix = f"（来源: {swrl_path}）" if swrl_path else ""
    return (
        "Owlready2 当前 MVP 路径不直接导入原始 SWRL 文本；"
        "已保留对照模式开关与返回结构，主体结果仍以当前 World 为准。"
        f"{suffix}"
    )


def _trace_log(
    trace: Any | None,
    name: str,
    status: str,
    *,
    reason: str,
    **detail: Any,
) -> None:
    if trace is None or not hasattr(trace, "log"):
        return

    try:
        trace.log(name, status, reason=reason, **detail)
    except TypeError:
        try:
            trace.log(name, status, reason, detail)
        except TypeError:
            try:
                trace.log(name=name, status=status, reason=reason, detail=detail)
            except Exception:
                return
