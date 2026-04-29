"""客户讲页面：ABOX 数据录入与推理路径讲述。

本页通过 `requests` 访问 `/api/v1/parameters`、`/api/v1/measurements`，
把 API 返回的结构化 explanation 展示为客户可理解的规则分支过程。
"""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

from mvp.frontend.ui_utils import (
    api_request,
    extract_data,
    render_envelope_feedback,
    render_panel_intro,
    render_reason_caption,
    render_trace,
)
from mvp.frontend.tabs.customer_reasoning_tree import (
    reasoning_tree_model,
    render_reasoning_tree_html,
)

TRACE_KEY = "tab-customer.abox"


def reasoning_timeline_rows(explanation: dict[str, Any]) -> list[dict[str, Any]]:
    """把后端 explanation 转成客户讲述表格。"""

    if not explanation:
        return []

    branch_label = str(explanation.get("branch_label") or explanation.get("branch") or "-")
    matched_rule = str(explanation.get("matched_rule") or "-")
    result = explanation.get("result") or {}
    status = str(result.get("status") or "-") if isinstance(result, dict) else "-"
    rows: list[dict[str, Any]] = []
    for step in list(explanation.get("path") or []):
        rows.append(
            {
                "阶段": str(step.get("name") or "-"),
                "说明": str(step.get("detail") or "-"),
                "分支": branch_label,
                "命中规则": matched_rule,
                "结果": status,
            }
        )
    return rows


def render(*, ontology_id: str) -> None:
    """渲染客户讲页面。"""

    render_panel_intro(
        kicker="Customer Story",
        title="客户讲：ABOX 数据如何得到判定",
        summary="",
    )

    if not ontology_id:
        st.warning("请先选择本体。")
        render_trace(TRACE_KEY)
        return

    parameters_envelope = api_request("GET", "/parameters", params={"ontology_id": ontology_id}, record_trace=False)
    parameter_items = list((extract_data(parameters_envelope, default={}) or {}).get("items") or [])
    parameter_codes = [str(item.get("code")) for item in parameter_items if item.get("code")]

    if not parameter_codes:
        st.info("当前本体还没有可录入的参数。")
        if st.button("初始化客户演示参数", width="stretch"):
            _seed_customer_parameter(ontology_id)
            st.rerun()
        render_trace(TRACE_KEY)
        return

    st.markdown("**ABOX 数据录入**")
    with st.form("customer-abox-form"):
        input_cols = st.columns(4)
        measurement_id = input_cols[0].text_input("数据编号", value="C001")
        batch = input_cols[1].text_input("对象/批次", value="B03")
        parameter = input_cols[2].selectbox("指标", options=parameter_codes, index=0)
        value = input_cols[3].number_input("数值", value=197.2, format="%.4f")
        submit = st.form_submit_button("录入并展示推理过程")

    current_envelope: dict[str, Any] | None = None
    if submit:
        current_envelope = api_request(
            "POST",
            "/measurements",
            json_body={
                "ontology_id": ontology_id,
                "measurement_id": measurement_id,
                "batch": batch,
                "parameter": parameter,
                "value": value,
            },
            trace_key=TRACE_KEY,
            trace_title="客户讲 ABOX 推理",
        )
        render_envelope_feedback(current_envelope, success_message="ABOX 数据已完成判定。")

    data = extract_data(current_envelope or {}, default={}) or {}
    explanation = data.get("explanation") or {}
    _render_decision_summary(data, explanation)
    render_trace(TRACE_KEY)


def _render_decision_summary(data: dict[str, Any], explanation: dict[str, Any]) -> None:
    if not data:
        st.info("提交一条 ABOX 数据后，这里会展示命中规则、分支和结果。")
        return

    result = explanation.get("result") if isinstance(explanation.get("result"), dict) else {}
    abox = explanation.get("abox") if isinstance(explanation.get("abox"), dict) else {}
    spec = explanation.get("spec") if isinstance(explanation.get("spec"), dict) else {}

    metric_cols = st.columns(4)
    metric_cols[0].metric("数据", str(abox.get("measurement_id") or data.get("measurement_id") or "-"))
    metric_cols[1].metric("分支", str(explanation.get("branch_label") or "-"))
    metric_cols[2].metric("规则", str(explanation.get("matched_rule") or data.get("rule") or "-"))
    metric_cols[3].metric("结果", str(result.get("status") or data.get("status") or "-"))

    render_reason_caption(
        [
            f"value={abox.get('value', data.get('value', '-'))}",
            f"spec={spec.get('spec_version', data.get('spec_version', '-'))}",
            f"condition={explanation.get('condition') or '-'}",
        ]
    )
    tree_html = render_reasoning_tree_html(explanation)
    if tree_html:
        st.markdown(tree_html, unsafe_allow_html=True)
    else:
        st.info("暂无推理过程。")


def _seed_customer_parameter(ontology_id: str) -> None:
    parameter = api_request(
        "POST",
        "/parameters",
        json_body={
            "ontology_id": ontology_id,
            "code": "temperature",
            "name": "注塑温度",
            "unit": "°C",
            "value_type": "number",
            "participates_in_inference": True,
        },
        trace_key=TRACE_KEY,
        trace_title="客户讲参数初始化",
    )
    render_envelope_feedback(parameter)
    specification = api_request(
        "POST",
        "/specifications",
        json_body={
            "ontology_id": ontology_id,
            "parameter": "temperature",
            "lower": 180,
            "upper": 195,
            "reason": "客户演示默认规格",
            "effective_from": "2026-04-28T00:00:00Z",
        },
        trace_key=TRACE_KEY,
        trace_title="客户讲规格初始化",
    )
    render_envelope_feedback(specification, success_message="客户演示参数已初始化。")
