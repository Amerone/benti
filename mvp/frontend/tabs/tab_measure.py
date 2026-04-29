"""Tab 四：测量与规格变更。

本页通过 `requests` 访问 `/api/v1/measurements`、`/api/v1/specifications`、
`/api/v1/specifications/change`、
`/api/v1/parameters` 与 `/api/v1/impacts/latest`，不直接触碰核心推理实现。
"""

from __future__ import annotations

import requests
import streamlit as st
from typing import Any

from mvp.frontend.ui_utils import (
    api_request,
    extract_data,
    render_dataframe,
    render_envelope_feedback,
    render_panel_intro,
    render_reason_caption,
    render_trace,
)

TRACE_KEY_MEASUREMENT = "tab-measure.measurement"
TRACE_KEY_SPEC = "tab-measure.spec"

MEASUREMENT_COLUMN_LABELS = {
    "measurement_id": "测量ID",
    "batch": "批次",
    "parameter": "参数",
    "spec_id": "规格ID",
    "value": "测量值",
    "operator": "操作员",
    "lower": "下限",
    "upper": "上限",
    "reason": "变更原因",
    "effective_from": "生效时间",
    "supersedes": "上一版本",
    "status": "判定",
    "rule": "规则",
    "deviation": "偏差",
    "spec_version": "规格版本",
    "reasoner": "推理来源",
    "reasoners": "来源列表",
    "source_badges": "来源徽标",
    "inferred_at": "判定时间",
    "swrl_status": "SWRL状态",
    "pellet_status": "Pellet状态",
    "saved": "已保存",
    "old_status": "原判定",
    "previous_status": "原判定",
    "new_status": "新判定",
    "old_spec": "原规格",
    "new_spec": "新规格",
    "old_rule": "原规则",
    "previous_rule": "原规则",
    "new_rule": "新规则",
    "old_deviation": "原偏差",
    "previous_deviation": "原偏差",
    "new_deviation": "新偏差",
}


def localize_measurement_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把测量页表格字段名转换为中文表头，保留每行字段顺序。"""

    return [
        {MEASUREMENT_COLUMN_LABELS.get(str(key), str(key)): value for key, value in row.items()}
        for row in rows
    ]


def measurement_list_parameter(current_parameter: str, parameter_codes: list[str]) -> str:
    """返回测量列表应使用的参数，优先跟随表单当前选择。"""

    if current_parameter:
        return current_parameter
    return parameter_codes[0] if parameter_codes else ""


def specification_history_params(ontology_id: str, current_parameter: str | None = None) -> dict[str, str]:
    """规格历史展示完整历史，避免切换参数时旧规格看起来被覆盖。"""

    return {"ontology_id": ontology_id}


def _reasoner_badge(reasoner: str) -> str:
    """把后端 reasoner 值映射成前端可读徽标文案。"""

    mapping = {
        "python-deterministic": "Python",
        "pellet-swrl": "Pellet-SWRL",
    }
    return mapping.get(str(reasoner or ""), str(reasoner or "-"))


def _measurement_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把测量列表补齐来源徽标列，便于验收查看双来源结果。"""

    rows: list[dict[str, Any]] = []
    for item in items:
        row = dict(item)
        reasoners = list(item.get("reasoners") or [])
        if not reasoners and item.get("reasoner"):
            reasoners = [str(item["reasoner"])]
        badges = [_reasoner_badge(reasoner) for reasoner in reasoners if reasoner]
        row["source_badges"] = " / ".join(dict.fromkeys(badges)) if badges else "-"
        rows.append(row)
    return rows


def _compare_result_rows(compare_result: dict[str, Any]) -> list[dict[str, Any]]:
    """把对照模式响应整理成单行表格，便于页面直接复核。"""

    if not compare_result:
        return []
    return [
        {
            "reasoner": _reasoner_badge(str(compare_result.get("reasoner") or "")),
            "status": compare_result.get("status"),
            "rule": compare_result.get("rule"),
            "deviation": compare_result.get("deviation"),
            "spec_version": compare_result.get("spec_version"),
            "swrl_status": compare_result.get("swrl_status"),
            "pellet_status": compare_result.get("pellet_status"),
            "saved": compare_result.get("saved"),
        }
    ]


def render(*, ontology_id: str) -> None:
    """渲染测量录入、规格变更和差异报告页。"""

    render_panel_intro(
        kicker="Measurement Lane",
        title="测量与规格变更",
        summary="",
    )

    if not ontology_id:
        st.warning("请先选择本体。")
        render_trace(TRACE_KEY_MEASUREMENT)
        render_trace(TRACE_KEY_SPEC)
        return

    parameters_envelope = api_request("GET", "/parameters", params={"ontology_id": ontology_id}, record_trace=False)
    parameters = extract_data(parameters_envelope, default={}) or {}
    parameter_items = list(parameters.get("items") or [])
    parameter_codes = [str(item.get("code")) for item in parameter_items if item.get("code")]

    st.markdown("**录入测量值**")
    with st.form("measurement-form"):
        measurement_cols = st.columns(4)
        measurement_id = measurement_cols[0].text_input("测量ID", value="M007")
        batch = measurement_cols[1].text_input("批次", value="B03")
        parameter = measurement_cols[2].selectbox("参数", options=parameter_codes or [""], index=0)
        value = measurement_cols[3].number_input("测量值", value=197.2, format="%.4f")
        operator = st.text_input("操作员", value="Streamlit")
        enable_swrl = st.checkbox(
            "启用 Pellet-SWRL 对照模式",
            value=False,
            help="提交测量后并行生成 Python 与 Pellet-SWRL 两条结果，用于验收比对。",
        )
        submit_measurement = st.form_submit_button("提交测量")

    if submit_measurement:
        envelope = api_request(
            "POST",
            "/measurements",
            json_body={
                "ontology_id": ontology_id,
                "measurement_id": measurement_id,
                "batch": batch,
                "parameter": parameter,
                "value": value,
                "operator": operator,
                "enable_swrl": enable_swrl,
            },
            trace_key=TRACE_KEY_MEASUREMENT,
            trace_title="测量录入",
        )
        render_envelope_feedback(envelope, success_message="测量提交完成。")
        compare_rows = _compare_result_rows((extract_data(envelope, default={}) or {}).get("compare_result") or {})
        if compare_rows:
            st.caption("对照模式已写入并行结果，来源徽标会同步显示在下方列表。")
            render_dataframe(localize_measurement_table_rows(compare_rows), empty_text="暂无对照模式结果。")

    measurement_result = api_request(
        "GET",
        "/measurements",
        params={"ontology_id": ontology_id, "parameter": measurement_list_parameter(parameter, parameter_codes)},
        record_trace=False,
    )
    measurement_items = extract_data(measurement_result, default={}) or {}
    render_reason_caption(
        [
            f"ontology_id={ontology_id}",
            f"parameter_count={len(parameter_codes)}",
            "结果来源以 reasoner 字段为准",
            "来源徽标：Python / Pellet-SWRL",
        ]
    )
    render_dataframe(
        localize_measurement_table_rows(_measurement_rows(list(measurement_items.get("items") or []))),
        empty_text="暂无测量数据。",
    )
    render_trace(TRACE_KEY_MEASUREMENT)

    st.divider()
    st.markdown("**规格变更与影响复核**")
    spec_col, impact_col = st.columns([1.2, 1.4], vertical_alignment="top")
    with spec_col:
        with st.form("spec-change-form"):
            spec_cols = st.columns(2)
            spec_parameter = spec_cols[0].selectbox("参数", options=parameter_codes or [""], index=0, key="spec.parameter")
            reason = spec_cols[1].text_input("变更原因", value="产线收紧")
            range_cols = st.columns(2)
            lower = range_cols[0].number_input("下限", value=180.0, format="%.4f")
            upper = range_cols[1].number_input("上限", value=190.0, format="%.4f")
            submit_spec = st.form_submit_button("提交规格变更")

    if submit_spec:
        envelope = api_request(
            "POST",
            "/specifications/change",
            json_body={
                "ontology_id": ontology_id,
                "parameter": spec_parameter,
                "lower": lower,
                "upper": upper,
                "reason": reason,
            },
            trace_key=TRACE_KEY_SPEC,
            trace_title="规格变更",
        )
        render_envelope_feedback(envelope, success_message="规格变更请求已完成。")

    impact_envelope = api_request(
        "GET",
        "/impacts/latest",
        params={"ontology_id": ontology_id, "parameter": spec_parameter if parameter_codes else ""},
        record_trace=False,
    )
    impact_data = extract_data(impact_envelope, default={}) or {}
    changed = list(impact_data.get("changed") or [])
    render_reason_caption(
        [
            f"latest_spec={impact_data.get('new_spec') or '-'}",
            f"changed={len(changed)}",
            "差异报告优先展示 latest impact",
        ]
    )
    with impact_col:
        render_dataframe(localize_measurement_table_rows(changed), empty_text="暂无差异报告。")

    specifications_envelope = api_request(
        "GET",
        "/specifications",
        params=specification_history_params(ontology_id, spec_parameter),
        record_trace=False,
    )
    specifications_data = extract_data(specifications_envelope, default={}) or {}
    specification_rows = list(specifications_data.get("items") or [])
    st.markdown("**规格历史**")
    render_reason_caption(
        [
            f"current_parameter={spec_parameter or '-'}",
            "history_scope=all_parameters",
            f"spec_count={len(specification_rows)}",
            "规格版本保留历史，不覆盖旧版本",
        ]
    )
    render_dataframe(localize_measurement_table_rows(specification_rows), empty_text="暂无规格历史。")
    render_trace(TRACE_KEY_SPEC)
