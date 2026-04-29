"""Tab 一：本体加载与切换。

本页通过 `requests` 访问 `/api/v1/ontologies` 与 `/api/v1/ontologies/load`，
负责展示已发现本体、触发加载以及在客户端维护当前本体选择。
"""

from __future__ import annotations

import requests
import streamlit as st

from mvp.frontend.ui_utils import (
    ACTIVE_ONTOLOGY_KEY,
    api_request,
    extract_data,
    get_active_ontology,
    render_dataframe,
    render_envelope_feedback,
    render_panel_intro,
    render_reason_caption,
    render_trace,
    set_active_ontology,
)

TRACE_KEY = "tab-ontology"


def render(*, ontologies: list[dict[str, object]]) -> None:
    """渲染本体加载与切换页。"""

    render_panel_intro(
        kicker="Ontology Control",
        title="装载与切换",
        summary="",
    )

    options = [str(item.get("ontology_id")) for item in ontologies if item.get("ontology_id")]
    current = get_active_ontology()
    selector_col, load_col = st.columns([3, 1], vertical_alignment="bottom")
    with selector_col:
        selected = st.selectbox(
            "切换当前本体",
            options=options or [""],
            index=(options.index(current) if current in options else 0),
            key=f"{ACTIVE_ONTOLOGY_KEY}.tab1",
            format_func=lambda item: item or "暂无可用本体",
        )
        if selected != current:
            set_active_ontology(selected)
    with load_col:
        if st.button("重新装载本体", width="stretch"):
            envelope = api_request(
                "POST",
                "/ontologies/load",
                json_body={"reload": True},
                trace_key=TRACE_KEY,
                trace_title="本体加载",
            )
            render_envelope_feedback(envelope, success_message="本体装载已完成。")

    latest = api_request(
        "GET",
        "/ontologies",
        trace_key=TRACE_KEY,
        trace_title="本体列表刷新",
        record_trace=False,
    )
    latest_items = extract_data(latest, default=ontologies) or ontologies

    render_reason_caption(
        [
            f"当前本体={get_active_ontology() or '未选择'}",
            f"发现本体数={len(latest_items)}",
            "切换状态仅保存在前端 session_state",
        ]
    )

    st.markdown("**已发现本体**")
    render_dataframe(latest_items, empty_text="尚未发现任何本体。")

    if latest_items:
        loaded = [item for item in latest_items if item.get("loaded")]
        failed = [item for item in latest_items if not item.get("loaded")]
        info_col, warn_col = st.columns(2)
        with info_col:
            st.info(f"已加载本体：{len(loaded)}")
        with warn_col:
            if failed:
                st.warning(f"待装载本体：{len(failed)}")
            else:
                st.success("当前显示的本体均已加载。")

    render_trace(TRACE_KEY)
