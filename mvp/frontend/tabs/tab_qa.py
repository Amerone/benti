"""Tab 五：参数注册与问答。

本页通过 `requests` 访问 `/api/v1/parameters` 与 `/api/v1/qa`，
展示参数注册、LLM/fallback 来源、SPARQL 与 evidence。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import requests
import streamlit as st

from mvp.frontend.ui_utils import (
    api_request,
    extract_data,
    get_last_trace,
    render_dataframe,
    render_envelope_feedback,
    render_panel_intro,
    render_reason_caption,
    render_trace,
)

TRACE_KEY_PARAMETER = "tab-qa.parameter"
TRACE_KEY_QA = "tab-qa.answer"
PARAMETER_COLUMN_LABELS = {
    "code": "参数编码",
    "name": "参数名称",
    "unit": "单位",
    "value_type": "值类型",
    "participates_in_inference": "参与推理",
    "created_at": "创建时间",
}
KNOWN_PARAMETER_NAMES = {
    "temperature": "注塑温度",
    "cq_temperature": "CQ 注塑温度",
}
KNOWN_PARAMETER_UNITS = {
    "temperature": "°C",
    "cq_temperature": "°C",
}
_LEGACY_MOJIBAKE_MARKERS = ("Ã", "Â", "æ", "å", "é", "è", "ç")


def parameter_table_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """规整参数表展示值，不修改 API 返回的原始数据。"""

    rows: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        code = str(row.get("code") or "")
        row["name"] = _parameter_name(code, row.get("name"))
        row["unit"] = _parameter_unit(code, row.get("unit"))
        row["created_at"] = _format_created_at(row.get("created_at"))
        rows.append(row)
    return rows


def localize_parameter_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把运行时参数表字段名转换为中文表头。"""

    return [
        {PARAMETER_COLUMN_LABELS.get(str(key), str(key)): value for key, value in row.items()}
        for row in rows
    ]


def _parameter_name(code: str, value: Any) -> str:
    text = _repair_legacy_mojibake(str(value or ""))
    if _is_lost_placeholder(text):
        return KNOWN_PARAMETER_NAMES.get(code, code)
    return text


def _parameter_unit(code: str, value: Any) -> str:
    text = _repair_legacy_mojibake(str(value or ""))
    if text == "?C":
        return KNOWN_PARAMETER_UNITS.get(code, text)
    return text


def _format_created_at(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return f"{parsed:%Y-%m-%d %H:%M:%S} {parsed.microsecond // 1000:03d}"


def _repair_legacy_mojibake(text: str) -> str:
    if not _looks_like_legacy_mojibake(text):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if _text_quality_score(repaired) > _text_quality_score(text) else text


def _looks_like_legacy_mojibake(text: str) -> bool:
    return any(marker in text for marker in _LEGACY_MOJIBAKE_MARKERS) or any(
        0x80 <= ord(char) <= 0x9F for char in text
    )


def _is_lost_placeholder(text: str) -> bool:
    return bool(text) and set(text) == {"?"}


def _text_quality_score(text: str) -> int:
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    control_count = sum(1 for char in text if 0x80 <= ord(char) <= 0x9F)
    marker_count = sum(text.count(marker) for marker in _LEGACY_MOJIBAKE_MARKERS)
    return cjk_count * 4 - control_count * 4 - marker_count


def render(*, ontology_id: str) -> None:
    """渲染参数注册与问答页。"""

    render_panel_intro(
        kicker="Explainability Lane",
        title="参数注册与问答",
        summary="",
    )

    if not ontology_id:
        st.warning("请先选择本体。")
        render_trace(TRACE_KEY_PARAMETER)
        render_trace(TRACE_KEY_QA)
        return

    st.markdown("**运行时新增参数**")
    with st.form("register-parameter-form"):
        parameter_cols = st.columns(5)
        code = parameter_cols[0].text_input("参数编码", value="vibration_frequency")
        name = parameter_cols[1].text_input("参数名称", value="振动频率")
        unit = parameter_cols[2].text_input("单位", value="Hz")
        value_type = parameter_cols[3].text_input("值类型", value="number")
        participates = parameter_cols[4].toggle("参与推理", value=True)
        submit_parameter = st.form_submit_button("注册参数")

    if submit_parameter:
        envelope = api_request(
            "POST",
            "/parameters",
            json_body={
                "ontology_id": ontology_id,
                "code": code,
                "name": name,
                "unit": unit,
                "value_type": value_type,
                "participates_in_inference": participates,
            },
            trace_key=TRACE_KEY_PARAMETER,
            trace_title="参数注册",
        )
        render_envelope_feedback(envelope, success_message="参数注册请求已完成。")

    parameter_list = api_request("GET", "/parameters", params={"ontology_id": ontology_id}, record_trace=False)
    parameter_items = list((extract_data(parameter_list, default={}) or {}).get("items") or [])
    render_dataframe(localize_parameter_table_rows(parameter_table_rows(parameter_items)), empty_text="暂无参数。")
    render_trace(TRACE_KEY_PARAMETER)

    st.divider()
    qa_form_col, qa_answer_col = st.columns([1.05, 1.25], vertical_alignment="top")
    with qa_form_col:
        st.markdown("**自然语言问答**")
        with st.form("qa-form"):
            question = st.text_area("问题", value="M007 为什么 Fail？", height=100)
            submit_qa = st.form_submit_button("提交问题")

    qa_envelope: dict[str, object] | None = None
    if submit_qa:
        qa_envelope = api_request(
            "POST",
            "/qa",
            json_body={"ontology_id": ontology_id, "question": question},
            trace_key=TRACE_KEY_QA,
            trace_title="问答解释",
        )
        render_envelope_feedback(qa_envelope, success_message="问答结果已返回。")

    current_qa = qa_envelope or get_last_trace(TRACE_KEY_QA) or {}
    qa_data = extract_data(current_qa, default={}) or {}
    answer = str(qa_data.get("answer") or "")
    source = str(qa_data.get("source") or "")
    evidence = qa_data.get("evidence") or {}
    sparql = qa_data.get("sparql")

    render_reason_caption(
        [
            f"source={source or 'local_fallback'}",
            f"provider={qa_data.get('provider') or 'fallback'}",
            f"intent={qa_data.get('intent') or 'unknown'}",
        ]
    )

    with qa_answer_col:
        if answer:
            st.success(answer)
        else:
            st.info("提交问题后将在这里显示解释。")

        with st.expander("查看 SPARQL / Evidence", expanded=False):
            st.markdown("**SPARQL**")
            st.code(str(sparql or ""), language="sparql")
            st.markdown("**Evidence**")
            st.code(json.dumps(evidence, ensure_ascii=False, indent=2), language="json")

    render_trace(TRACE_KEY_QA)
