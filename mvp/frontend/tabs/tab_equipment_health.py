"""设备健康本体页面。

本页通过 `requests` 访问 `/api/v1/parameters`、`/api/v1/specifications`
和 `/api/v1/measurements`，为新增的 equipment-health 本体提供独立演示入口。
"""

from __future__ import annotations

from typing import Any

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

EQUIPMENT_ONTOLOGY_ID = "equipment-health"
TRACE_KEY_SEED = "tab-equipment-health.seed"
TRACE_KEY_MEASURE = "tab-equipment-health.measure"


def render() -> None:
    """渲染 equipment-health 对应页面。"""

    render_panel_intro(
        kicker="Equipment Health Ontology",
        title="设备健康本体",
        summary="",
    )

    seed_col, refresh_col = st.columns([2, 1], vertical_alignment="bottom")
    with seed_col:
        if st.button("初始化设备健康演示数据", width="stretch"):
            _seed_equipment_health_demo()
    with refresh_col:
        if st.button("刷新设备健康页", width="stretch"):
            st.rerun()

    parameter_items = _load_parameters()
    render_dataframe(_parameter_rows(parameter_items), empty_text="暂无设备健康参数。")

    st.markdown("**设备 ABOX 读数录入**")
    parameter_codes = [str(item.get("code")) for item in parameter_items if item.get("code")]
    if not parameter_codes:
        st.info("请先初始化设备健康演示数据，或在下方技术页为 equipment-health 注册参数。")
        render_trace(TRACE_KEY_SEED)
        return

    with st.form("equipment-health-reading-form"):
        cols = st.columns(4)
        measurement_id = cols[0].text_input("读数ID", value="EH002")
        equipment_id = cols[1].text_input("设备/批次", value="PUMP-01")
        parameter = cols[2].selectbox("健康指标", options=parameter_codes, index=0)
        value = cols[3].number_input("读数", value=8.4, format="%.4f")
        submit = st.form_submit_button("提交设备读数")

    if submit:
        envelope = api_request(
            "POST",
            "/measurements",
            json_body={
                "ontology_id": EQUIPMENT_ONTOLOGY_ID,
                "measurement_id": measurement_id,
                "batch": equipment_id,
                "parameter": parameter,
                "value": value,
            },
            trace_key=TRACE_KEY_MEASURE,
            trace_title="设备健康读数",
        )
        render_envelope_feedback(envelope, success_message="设备读数已完成判定。")
        _render_equipment_result(extract_data(envelope, default={}) or {})

    measurements = api_request(
        "GET",
        "/measurements",
        params={"ontology_id": EQUIPMENT_ONTOLOGY_ID, "parameter": parameter_codes[0]},
        record_trace=False,
    )
    items = list((extract_data(measurements, default={}) or {}).get("items") or [])
    render_reason_caption(
        [
            f"ontology_id={EQUIPMENT_ONTOLOGY_ID}",
            f"parameter={parameter_codes[0]}",
            f"readings={len(items)}",
        ]
    )
    render_dataframe(items, empty_text="暂无设备读数。")
    render_trace(TRACE_KEY_SEED)
    render_trace(TRACE_KEY_MEASURE)


def _seed_equipment_health_demo() -> None:
    parameter = api_request(
        "POST",
        "/parameters",
        json_body={
            "ontology_id": EQUIPMENT_ONTOLOGY_ID,
            "code": "vibration_velocity",
            "name": "振动速度",
            "unit": "mm/s",
            "value_type": "number",
            "participates_in_inference": True,
        },
        trace_key=TRACE_KEY_SEED,
        trace_title="设备健康参数初始化",
    )
    render_envelope_feedback(parameter)

    specification = api_request(
        "POST",
        "/specifications",
        json_body={
            "ontology_id": EQUIPMENT_ONTOLOGY_ID,
            "parameter": "vibration_velocity",
            "lower": 0,
            "upper": 7.1,
            "reason": "设备健康示例阈值",
            "effective_from": "2026-04-28T00:00:00Z",
        },
        trace_key=TRACE_KEY_SEED,
        trace_title="设备健康规格初始化",
    )
    render_envelope_feedback(specification)

    reading = api_request(
        "POST",
        "/measurements",
        json_body={
            "ontology_id": EQUIPMENT_ONTOLOGY_ID,
            "measurement_id": "EH001",
            "batch": "PUMP-01",
            "parameter": "vibration_velocity",
            "value": 8.4,
        },
        trace_key=TRACE_KEY_SEED,
        trace_title="设备健康样例读数",
    )
    render_envelope_feedback(reading, success_message="设备健康演示数据已初始化。")


def _load_parameters() -> list[dict[str, Any]]:
    envelope = api_request(
        "GET",
        "/parameters",
        params={"ontology_id": EQUIPMENT_ONTOLOGY_ID},
        record_trace=False,
    )
    return list((extract_data(envelope, default={}) or {}).get("items") or [])


def _parameter_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "参数编码": item.get("code"),
            "参数名称": item.get("name"),
            "单位": item.get("unit"),
            "参与推理": item.get("participates_in_inference"),
        }
        for item in items
    ]


def _render_equipment_result(data: dict[str, Any]) -> None:
    if not data:
        return
    explanation = data.get("explanation") if isinstance(data.get("explanation"), dict) else {}
    result = explanation.get("result") if isinstance(explanation.get("result"), dict) else {}
    cols = st.columns(3)
    cols[0].metric("规则", str(explanation.get("matched_rule") or data.get("rule") or "-"))
    cols[1].metric("分支", str(explanation.get("branch_label") or "-"))
    cols[2].metric("结果", str(result.get("status") or data.get("status") or "-"))
