"""Tab 二：Owlready2 主体浏览。

本页通过 `requests` 访问 `/api/v1/ontologies/{id}/subjects`，
只展示来自 API 的主体结果，不直接读取本地 TTL。
"""

from __future__ import annotations

import requests
import streamlit as st

from mvp.frontend.ui_utils import (
    api_request,
    extract_data,
    render_dataframe,
    render_envelope_feedback,
    render_panel_intro,
    render_reason_caption,
    render_trace,
)
from mvp.frontend.tabs.subject_graph import render_subject_graph_html

TRACE_KEY = "tab-subjects"


def render(*, ontology_id: str) -> None:
    """渲染主体浏览页。"""

    render_panel_intro(
        kicker="Subject Explorer",
        title="主体总览",
        summary="",
    )

    if not ontology_id:
        st.warning("请先在顶部状态栏或 Tab 一选择本体。")
        render_trace(TRACE_KEY)
        return

    filter_col, limit_col, action_col = st.columns([3, 1, 1], vertical_alignment="bottom")
    with filter_col:
        keyword = st.text_input("名称过滤", placeholder="例如：Batch", key="subjects.q")
    with limit_col:
        limit = st.number_input("返回上限", min_value=10, max_value=500, value=200, step=10, key="subjects.limit")
    with action_col:
        if st.button("刷新主体", width="stretch"):
            envelope = api_request(
                "GET",
                f"/ontologies/{ontology_id}/subjects",
                params={"q": keyword, "limit": int(limit)},
                trace_key=TRACE_KEY,
                trace_title="主体浏览",
            )
            render_envelope_feedback(envelope, success_message="主体已刷新。")

    envelope = api_request(
        "GET",
        f"/ontologies/{ontology_id}/subjects",
        params={"q": keyword, "limit": int(limit)},
        trace_key=TRACE_KEY,
        trace_title="主体浏览",
        record_trace=False,
    )
    data = extract_data(envelope, default={}) or {}

    render_reason_caption(
        [
            f"ontology_id={ontology_id}",
            f"loaded_by={data.get('loaded_by') or 'unknown'}",
            f"pellet_status={data.get('pellet_status') or 'unknown'}",
            "主体内容来自 Fuseki + Owlready2",
        ]
    )

    subject_tabs = st.tabs(["关系网", "类", "个体", "对象属性", "数据属性"])
    with subject_tabs[0]:
        graph_html = render_subject_graph_html(data)
        if graph_html:
            st.markdown(graph_html, unsafe_allow_html=True)
        else:
            st.info("暂无可展示的关系网。")
    with subject_tabs[1]:
        render_dataframe(list(data.get("classes") or []), empty_text="暂无 class。")
    with subject_tabs[2]:
        render_dataframe(list(data.get("individuals") or []), empty_text="暂无 individual。")
    with subject_tabs[3]:
        render_dataframe(list(data.get("object_properties") or []), empty_text="暂无 object property。")
    with subject_tabs[4]:
        render_dataframe(list(data.get("data_properties") or []), empty_text="暂无 data property。")

    render_trace(TRACE_KEY)
