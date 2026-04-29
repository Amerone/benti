"""运行时参数注册模块。

参数是图谱中的业务个体，不依赖数据库 schema 变更。该模块提供薄外观，统一校验
参数输入并委托 `graph` 层写入 data named graph，保证列表和推理读取的是同一份数据。
"""

from __future__ import annotations

from typing import Any


def register_parameter(
    ontology_id: str,
    *,
    code: str,
    name: str | None = None,
    unit: str | None = None,
    value_type: str = "number",
    participates_in_inference: bool = True,
    repository: Any | None = None,
    trace: Any | None = None,
) -> dict[str, Any]:
    """注册或复用参数。"""

    if not code:
        raise ValueError("code is required")
    if not value_type:
        raise ValueError("value_type is required")

    from mvp.core import graph

    repo = repository or graph.get_default_repository()
    return repo.upsert_parameter(
        ontology_id,
        code,
        name=name,
        unit=unit,
        value_type=value_type,
        participates_in_inference=participates_in_inference,
        trace=trace,
    )


def list_parameters(
    ontology_id: str,
    *,
    repository: Any | None = None,
    trace: Any | None = None,
) -> dict[str, Any]:
    """列出指定本体下的参数。"""

    from mvp.core import graph

    repo = repository or graph.get_default_repository()
    if trace is not None and hasattr(trace, "log"):
        trace.log("list_parameters", "success", reason="从 data 图读取参数列表")
    return repo.list_parameters(ontology_id)
