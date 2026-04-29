"""Tab 三：Pellet 推理。

本页通过 `requests` 访问 `/api/v1/ontologies/{id}/reason`，
负责展示推理状态、耗时、busy/失败降级原因和 trace。
"""

from __future__ import annotations

import requests
import streamlit as st

from mvp.frontend.ui_utils import (
    api_request,
    extract_data,
    get_last_trace,
    render_envelope_feedback,
    render_panel_intro,
    render_reason_caption,
    render_trace,
)

TRACE_KEY = "tab-pellet"


def render(*, ontology_id: str) -> None:
    """渲染 Pellet 推理页。"""

    render_panel_intro(
        kicker="Reasoning Lane",
        title="执行推理",
        summary="",
    )

    if not ontology_id:
        st.warning("请先选择本体。")
        render_trace(TRACE_KEY)
        return

    run_col, force_col = st.columns([2, 1], vertical_alignment="bottom")
    with force_col:
        force = st.toggle("强制重跑", value=False, key="pellet.force")
    with run_col:
        if st.button("执行 Pellet", width="stretch"):
            envelope = api_request(
                "POST",
                f"/ontologies/{ontology_id}/reason",
                json_body={"force": force},
                trace_key=TRACE_KEY,
                trace_title="Pellet 推理",
            )
            render_envelope_feedback(envelope, success_message="推理请求已返回。")

    envelope = get_last_trace(TRACE_KEY) or {}
    data = extract_data(envelope, default={}) or {}

    metric_cols = st.columns(4)
    metric_cols[0].metric("本体", ontology_id)
    metric_cols[1].metric("Pellet 状态", str(data.get("pellet_status") or "unknown"))
    metric_cols[2].metric("耗时 ms", str(data.get("pellet_ms") or "-"))
    metric_cols[3].metric("新增推断", str(data.get("inferred_triple_count") or 0))

    render_reason_caption(
        [
            f"pellet_status={data.get('pellet_status') or 'unknown'}",
            f"retry_after_ms={data.get('retry_after_ms') or '-'}",
            str(data.get("pellet_error") or ""),
        ]
    )

    if data.get("pellet_status") == "busy":
        st.warning("Pellet 正在被其他请求占用，请稍后重试。")
    elif data.get("pellet_status") in {"failed", "missing_java"}:
        st.error(str(data.get("pellet_error") or "Pellet 执行失败。"))
    elif envelope.get("ok"):
        st.success("Pellet 状态已返回。")
    else:
        st.info("点击“执行 Pellet”后，这里会显示最近一次推理结果。")

    render_trace(TRACE_KEY)
