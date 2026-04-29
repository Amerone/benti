"""CQ 工程页：通过 `requests` 访问 `/api/v1/cq-engine/...`，
提供生成、保存、查看与审核草案能力，不直接依赖 `mvp.core`。"""

from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st

from mvp.frontend.ui_utils import (
    api_request,
    extract_data,
    render_dataframe,
    render_envelope_feedback,
    render_panel_intro,
    render_trace,
)

TRACE_KEY = "tab-cq-engine"
DEFAULT_BUSINESS_TEXT = (
    "委托单包含产品和多个试验项目；每个试验项目自动分解为一个任务；"
    "测试项记录按标准阈值做确定性判定；标准升级后需要对历史结果重判并标记需复核任务。"
)
GENERATION_MODES = [
    "llm_with_template_fallback",
    "template_only",
    "llm_only",
]


def render() -> None:
    """渲染开发者视角的 CQ 工程工作台。"""

    render_panel_intro(
        kicker="CQ Engineering",
        title="CQ / TBox / RBox 草案工作台",
        summary="先生成草案，再保存、查看 JSON，并可把已检查草案标记为 reviewed。",
    )

    mode_col, _ = st.columns([1.2, 1.8])
    with mode_col:
        generation_mode = st.selectbox(
            "生成模式",
            options=GENERATION_MODES,
            index=0,
            help="llm_with_template_fallback 优先调用 LLM，失败时退回模板；template_only 仅走模板；llm_only 仅走 LLM。",
        )
    business_text = st.text_area("业务文本", value=DEFAULT_BUSINESS_TEXT, height=140)

    if st.button("生成并保存草案", width="stretch"):
        envelope = api_request(
            "POST",
            "/cq-engine/generate",
            json_body={"business_text": business_text, "generation_mode": generation_mode},
            trace_key=TRACE_KEY,
            trace_title="CQ 草案生成",
        )
        render_envelope_feedback(envelope, success_message="CQ 草案已生成。")
        payload = extract_data(envelope, default={}) or {}
        if payload:
            save_envelope = api_request(
                "POST",
                "/cq-engine/drafts",
                json_body={"payload": payload},
                trace_key=TRACE_KEY,
                trace_title="CQ 草案保存",
            )
            render_envelope_feedback(save_envelope, success_message="CQ 草案已保存。")

    drafts_envelope = api_request("GET", "/cq-engine/drafts", record_trace=False)
    drafts = extract_data(drafts_envelope, default={}) or {}
    draft_items = list(drafts.get("items") or [])

    st.markdown("**草案列表**")
    render_dataframe(_draft_rows(draft_items), empty_text="暂无草案。")

    if not draft_items:
        render_trace(TRACE_KEY)
        return

    selected_draft_id = st.selectbox(
        "查看草案",
        options=[str(item.get("draft_id")) for item in draft_items if item.get("draft_id")],
        key="cq-engine.selected-draft",
    )
    selected_draft = next((item for item in draft_items if item.get("draft_id") == selected_draft_id), None)
    if selected_draft is None:
        render_trace(TRACE_KEY)
        return

    review_col, status_col = st.columns([1, 2])
    with review_col:
        if selected_draft.get("draft_status") != "reviewed" and st.button("标记为 reviewed", width="stretch"):
            envelope = api_request(
                "PATCH",
                f"/cq-engine/drafts/{selected_draft_id}",
                json_body={"draft_status": "reviewed"},
                trace_key=TRACE_KEY,
                trace_title="CQ 草案审核状态更新",
            )
            render_envelope_feedback(envelope, success_message="草案已标记为 reviewed。")
            drafts_envelope = api_request("GET", "/cq-engine/drafts", record_trace=False)
            drafts = extract_data(drafts_envelope, default={}) or {}
            draft_items = list(drafts.get("items") or [])
            selected_draft = next((item for item in draft_items if item.get("draft_id") == selected_draft_id), selected_draft)
    with status_col:
        st.caption(
            f"当前草案：{selected_draft.get('draft_id', '-')} | 状态：{selected_draft.get('draft_status', '-')} | "
            f"模式：{(selected_draft.get('payload') or {}).get('generation_mode', '-')}"
        )

    payload = selected_draft.get("payload") or {}
    _render_payload(payload)

    st.markdown("**草案 JSON**")
    st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")
    render_trace(TRACE_KEY)


def _draft_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        payload = item.get("payload") or {}
        rows.append(
            {
                "草案ID": item.get("draft_id"),
                "状态": item.get("draft_status"),
                "生成模式": payload.get("generation_mode") or "-",
                "候选CQ数": len(list(payload.get("candidate_cqs") or [])),
                "类数": len(list(payload.get("candidate_classes") or [])),
                "关系数": len(list(payload.get("candidate_relations") or [])),
                "规则数": len(list(payload.get("candidate_rules") or [])),
            }
        )
    return rows


def _render_payload(payload: dict[str, Any]) -> None:
    st.markdown("**候选 CQ**")
    render_dataframe(list(payload.get("candidate_cqs") or []), empty_text="暂无候选 CQ。")

    st.markdown("**候选类**")
    render_dataframe(list(payload.get("candidate_classes") or []), empty_text="暂无候选类。")

    st.markdown("**候选关系**")
    render_dataframe(list(payload.get("candidate_relations") or []), empty_text="暂无候选关系。")

    st.markdown("**候选属性**")
    render_dataframe(list(payload.get("candidate_properties") or []), empty_text="暂无候选属性。")

    st.markdown("**候选规则**")
    render_dataframe(list(payload.get("candidate_rules") or []), empty_text="暂无候选规则。")

    draft_sparql_tests = list(payload.get("draft_sparql_tests") or [])
    trace_rows = list(payload.get("source_trace") or [])

    extra_cols = st.columns(2)
    with extra_cols[0]:
        st.markdown("**草案 Turtle 摘要**")
        st.code(str(payload.get("draft_turtle") or ""), language="text")
    with extra_cols[1]:
        st.markdown("**草案 SPARQL 测试**")
        render_dataframe(
            [{"测试ID": item} for item in draft_sparql_tests],
            empty_text="暂无草案 SPARQL 测试。",
        )

    st.markdown("**来源链路**")
    render_dataframe(trace_rows, empty_text="暂无来源链路。")
