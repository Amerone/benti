"""委托单试验页：通过 `requests` 访问 `/api/v1/commission/...`，
展示 CO-2024-001 的订单、任务、判定与标准升级影响，不直接依赖 `mvp.core`。"""

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
    render_trace,
)

TRACE_KEY = "tab-commission-customer"
DEMO_ORDER_NO = "CO-2024-001"
DEMO_STANDARD_CODE = "GJB-7821-2024"


def render() -> None:
    """渲染客户视角的委托单试验流程。"""

    render_panel_intro(
        kicker="Commission Demo",
        title="委托单试验与标准升级影响",
        summary="订单、试验项目、任务、测试项、判定结果和标准升级影响全部通过 API 回读，便于客户直接理解业务链路。",
    )

    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("初始化 / 重置 CO-2024-001", width="stretch"):
            envelope = api_request(
                "POST",
                "/commission/demo/reset",
                trace_key=TRACE_KEY,
                trace_title="委托单演示初始化",
            )
            render_envelope_feedback(envelope, success_message="委托单演示数据已初始化。")
    with action_cols[1]:
        if st.button("触发标准升级 V2", width="stretch"):
            envelope = api_request(
                "POST",
                f"/commission/standards/{DEMO_STANDARD_CODE}/upgrade",
                trace_key=TRACE_KEY,
                trace_title="委托单标准升级重判",
            )
            render_envelope_feedback(envelope, success_message="标准升级与历史结果重判已完成。")

    _render_commission_order_form()
    _render_data_record_form()

    query_order_no = st.text_input("查询委托单", value=DEMO_ORDER_NO, key="commission.query-order-no")
    order_no = query_order_no.strip() or DEMO_ORDER_NO
    order_envelope = api_request("GET", f"/commission/orders/{order_no}", record_trace=False)
    order = extract_data(order_envelope, default={}) or {}
    impact_envelope = api_request("GET", "/commission/impacts/latest", record_trace=False)
    impact = extract_data(impact_envelope, default={}) or {}

    _render_story(order, impact)
    render_trace(TRACE_KEY)


def _render_commission_order_form() -> None:
    with st.expander("新建 / 更新委托单", expanded=False):
        with st.form("commission-order-form"):
            order_cols = st.columns(3)
            order_no = order_cols[0].text_input("委托单号", value="CO-UI-001")
            requester = order_cols[1].text_input("委托人", value="QA")
            product_model = order_cols[2].text_input("产品型号", value="X-UI")
            product_name = st.text_input("产品名称", value="相控阵雷达导引头")

            project_rows = st.data_editor(
                [
                    {
                        "project_id": "P-UI-001",
                        "project_name": "高低温振动试验",
                        "task_id": "T-UI-001",
                        "item_code": "RCS_MEAN",
                        "item_name": "RCS均值",
                        "unit": "m²",
                    },
                    {
                        "project_id": "P-UI-002",
                        "project_name": "电磁兼容试验",
                        "task_id": "T-UI-002",
                        "item_code": "BER",
                        "item_name": "误码率",
                        "unit": "",
                    },
                ],
                num_rows="dynamic",
                width="stretch",
                key="commission-order-project-rows",
            )

            submitted = st.form_submit_button("保存委托单", width="stretch")

        if submitted:
            try:
                payload = build_commission_order_payload_from_rows(
                    order_no=order_no,
                    requester=requester,
                    product_name=product_name,
                    product_model=product_model,
                    rows=list(project_rows or []),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                envelope = api_request("POST", "/commission/orders", json_body=payload, trace_key=TRACE_KEY, trace_title="委托单保存")
                render_envelope_feedback(envelope, success_message="委托单已保存。")


def _render_data_record_form() -> None:
    with st.expander("录入测试数据", expanded=False):
        with st.form("commission-data-record-form"):
            task_cols = st.columns(3)
            task_id = task_cols[0].text_input("任务ID", value="T-UI-001", key="commission.record-task-id")
            item_code = task_cols[1].text_input("测试项编码", value="RCS_MEAN", key="commission.record-item-code")
            data_record_id = task_cols[2].text_input("数据记录ID", value="DR-T-UI-001-RCS", key="commission.record-id")
            value_cols = st.columns(2)
            measured_value = value_cols[0].number_input("实测值", value=0.034, format="%.6f")
            unit = value_cols[1].text_input("单位", value="m²", key="commission.record-unit")
            submitted = st.form_submit_button("录入并判定", width="stretch")

        if submitted:
            payload = build_commission_data_record_payload(
                task_id=task_id,
                item_code=item_code,
                value=measured_value,
                unit=unit,
                data_record_id=data_record_id,
            )
            envelope = api_request(
                "POST",
                "/commission/data-records",
                json_body=payload,
                trace_key=TRACE_KEY,
                trace_title="测试数据录入",
            )
            render_envelope_feedback(envelope, success_message="测试数据已录入并完成判定。")


def build_commission_order_payload(
    *,
    order_no: str,
    requester: str,
    product_name: str,
    product_model: str,
    project_id: str,
    project_name: str,
    task_id: str,
    item_code: str,
    item_name: str,
    unit: str,
) -> dict[str, Any]:
    return build_commission_order_payload_from_rows(
        order_no=order_no,
        requester=requester,
        product_name=product_name,
        product_model=product_model,
        rows=[
            {
                "project_id": project_id,
                "project_name": project_name,
                "task_id": task_id,
                "item_code": item_code,
                "item_name": item_name,
                "unit": unit,
            }
        ],
    )


def build_commission_order_payload_from_rows(
    *,
    order_no: str,
    requester: str,
    product_name: str,
    product_model: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    projects: list[dict[str, Any]] = []
    project_index: dict[tuple[str, str], dict[str, Any]] = {}
    task_by_project_id: dict[str, str] = {}
    for row in rows:
        project_id = str(row.get("project_id") or "").strip()
        task_id = str(row.get("task_id") or "").strip()
        item_code = str(row.get("item_code") or "").strip()
        if not project_id or not task_id or not item_code:
            continue
        existing_task_id = task_by_project_id.get(project_id)
        if existing_task_id is not None and existing_task_id != task_id:
            raise ValueError(f"project_id {project_id} uses multiple task_id values")
        task_by_project_id[project_id] = task_id
        key = (project_id, task_id)
        if key not in project_index:
            project = {
                "project_id": project_id,
                "name": str(row.get("project_name") or "").strip(),
                "task_id": task_id,
                "items": [],
            }
            project_index[key] = project
            projects.append(project)
        project_index[key]["items"].append(
            {
                "item_code": item_code,
                "item_name": str(row.get("item_name") or "").strip(),
                "unit": str(row.get("unit") or "").strip(),
            }
        )

    return {
        "order_no": order_no.strip(),
        "requester": requester.strip(),
        "product": {"name": product_name.strip(), "model": product_model.strip()},
        "projects": projects,
    }


def build_commission_data_record_payload(
    *,
    task_id: str,
    item_code: str,
    value: float,
    unit: str,
    data_record_id: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": task_id.strip(),
        "item_code": item_code.strip(),
        "value": float(value),
        "unit": unit.strip(),
    }
    if data_record_id.strip():
        payload["data_record_id"] = data_record_id.strip()
    return payload


def _render_story(order: dict[str, Any], impact: dict[str, Any]) -> None:
    if not order:
        st.info("请先初始化 CO-2024-001 演示数据。")
        return

    product = order.get("product") or {}
    active_standard = order.get("active_standard") or {}
    projects = list(order.get("projects") or [])
    impact_rows = _impact_rows(list(impact.get("changed") or []))

    metrics = st.columns(5)
    metrics[0].metric("订单号", str(order.get("order_no") or "-"))
    metrics[1].metric("委托方", str(order.get("requester") or "-"))
    metrics[2].metric("产品 / 型号", f"{product.get('name', '-')} / {product.get('model', '-')}")
    metrics[3].metric("试验项目数", str(len(projects)))
    metrics[4].metric("当前标准", str(active_standard.get("standard_version") or "-"))

    st.markdown("**业务链路摘要**")
    st.caption(
        "委托单 -> 产品 -> 试验项目 -> 自动分解任务 -> 测试项 / 数据记录 -> 判定结果 -> 标准升级影响。"
    )

    st.markdown("**试验项目与任务**")
    render_dataframe(_project_rows(projects), empty_text="暂无试验项目。")

    st.markdown("**测试项与判定结果**")
    render_dataframe(_item_rows(projects), empty_text="暂无测试项结果。")

    st.markdown("**标准升级影响**")
    render_dataframe(impact_rows, empty_text="尚未执行标准升级。")

    flipped_rcs = next((row for row in impact_rows if row.get("测试项编码") == "RCS_MEAN"), None)
    if flipped_rcs:
        st.warning(
            f"RCS_MEAN 在任务 {flipped_rcs['任务']} 上由 {flipped_rcs['旧结果']} 翻转为 {flipped_rcs['新结果']}，"
            f"任务状态变为 {flipped_rcs['任务状态']}。"
        )


def _project_rows(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for project in projects:
        item_codes = [str(item.get("item_code") or "-") for item in list(project.get("items") or [])]
        rows.append(
            {
                "试验项目": project.get("name"),
                "项目ID": project.get("project_id"),
                "任务": project.get("task_id"),
                "任务状态": project.get("task_status"),
                "测试项": " / ".join(item_codes) if item_codes else "-",
            }
        )
    return rows


def _item_rows(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for project in projects:
        for item in list(project.get("items") or []):
            current_result = item.get("current_result") or {}
            rows.append(
                {
                    "试验项目": project.get("name"),
                    "任务": project.get("task_id"),
                    "测试项编码": item.get("item_code"),
                    "测试项": item.get("item_name"),
                    "测量值": item.get("value"),
                    "单位": item.get("unit") or "-",
                    "数据记录": item.get("data_record_id"),
                    "结果": current_result.get("status") or "-",
                    "判定依据": current_result.get("reason") or "-",
                    "标准版本": current_result.get("standard_version") or "-",
                }
            )
    return rows


def _impact_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "任务": item.get("task_id"),
                "测试项编码": item.get("item_code"),
                "数据记录": item.get("data_record_id"),
                "旧结果": item.get("old_status"),
                "新结果": item.get("new_status"),
                "旧标准": item.get("old_standard"),
                "新标准": item.get("new_standard"),
                "翻转": "是" if item.get("flipped") else "否",
                "任务状态": item.get("task_status"),
            }
        )
    return rows
