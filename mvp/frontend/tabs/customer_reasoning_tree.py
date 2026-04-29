"""客户讲页面的推理树展示模型与 HTML 渲染。"""

from __future__ import annotations

import html
from typing import Any

BRANCH_OPTIONS = (
    {
        "branch": "below_lower",
        "label": "低于下限",
        "condition": "value < lower_limit",
        "rule": "Rule_Fail_Low",
        "status": "Fail_Low",
    },
    {
        "branch": "within_limits",
        "label": "规格范围内",
        "condition": "lower_limit <= value <= upper_limit",
        "rule": "Rule_Pass",
        "status": "Pass",
    },
    {
        "branch": "above_upper",
        "label": "高于上限",
        "condition": "value > upper_limit",
        "rule": "Rule_Fail_High",
        "status": "Fail_High",
    },
)


def reasoning_tree_model(explanation: dict[str, Any]) -> dict[str, Any]:
    """把后端 explanation 转成客户页树形展示模型。"""

    abox = explanation.get("abox") if isinstance(explanation.get("abox"), dict) else {}
    spec = explanation.get("spec") if isinstance(explanation.get("spec"), dict) else {}
    result = explanation.get("result") if isinstance(explanation.get("result"), dict) else {}
    active_branch = str(explanation.get("branch") or "")
    matched_rule = str(explanation.get("matched_rule") or "-")
    result_status = str(result.get("status") or "-")
    deviation = result.get("deviation", "-")

    return {
        "title": f"ABOX 数据 {abox.get('measurement_id') or '-'}",
        "detail": (
            f"批次 {abox.get('batch') or '-'}，参数 {abox.get('parameter') or '-'}，"
            f"测量值 {abox.get('value', '-')}"
        ),
        "active": True,
        "children": [
            {
                "title": f"规格 {spec.get('spec_version') or '-'}",
                "detail": f"下限 {spec.get('lower_limit', '-')}，上限 {spec.get('upper_limit', '-')}",
                "active": True,
                "children": [
                    {
                        "title": "规则分支判断",
                        "detail": f"命中路线：{explanation.get('branch_label') or active_branch or '-'}",
                        "active": True,
                        "children": _branch_nodes(active_branch, matched_rule, result_status, deviation),
                    }
                ],
            }
        ],
    }


def render_reasoning_tree_html(explanation: dict[str, Any]) -> str:
    """渲染可直接给 Streamlit markdown 使用的树形 HTML。"""

    if not explanation:
        return ""
    tree = reasoning_tree_model(explanation)
    return f"""
    <style>
    .reason-tree {{
        margin: 1rem 0 0.35rem;
        padding: 1rem;
        border: 1px solid rgba(16, 36, 63, 0.10);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.64);
        overflow-x: auto;
    }}
    .reason-tree ul {{
        display: flex;
        justify-content: center;
        gap: 0.75rem;
        padding: 1.25rem 0 0;
        margin: 0;
        list-style: none;
        position: relative;
    }}
    .reason-tree li {{
        display: flex;
        flex-direction: column;
        align-items: center;
        min-width: 12rem;
        position: relative;
    }}
    .reason-tree li::before {{
        content: "";
        position: absolute;
        top: -1.25rem;
        left: 50%;
        width: 2px;
        height: 1.25rem;
        background: rgba(16, 36, 63, 0.16);
    }}
    .reason-tree > .reason-tree-root::before {{
        display: none;
    }}
    .reason-tree-node {{
        width: 100%;
        min-height: 5.1rem;
        padding: 0.72rem 0.8rem;
        border: 1px solid rgba(16, 36, 63, 0.12);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.72);
        color: var(--brand-ink-soft);
        box-shadow: 0 10px 26px rgba(16, 36, 63, 0.05);
    }}
    .reason-tree-node.is-active {{
        border-color: rgba(255, 106, 61, 0.88);
        background: linear-gradient(135deg, rgba(255, 106, 61, 0.16), rgba(19, 181, 200, 0.10));
        box-shadow: 0 12px 30px rgba(255, 106, 61, 0.16);
        color: var(--brand-ink);
    }}
    .reason-tree-node.is-muted {{
        opacity: 0.46;
        filter: grayscale(0.2);
    }}
    .reason-tree-title {{
        display: block;
        font-weight: 800;
        line-height: 1.25;
        word-break: break-word;
    }}
    .reason-tree-detail {{
        display: block;
        margin-top: 0.38rem;
        color: var(--brand-muted);
        font-size: 0.84rem;
        line-height: 1.45;
        word-break: break-word;
    }}
    .reason-tree-node.is-active .reason-tree-detail {{
        color: var(--brand-ink-soft);
    }}
    @media (max-width: 760px) {{
        .reason-tree ul {{
            flex-direction: column;
            align-items: stretch;
        }}
        .reason-tree li {{
            min-width: 0;
        }}
    }}
    </style>
    <section class="reason-tree">{_render_tree_node(tree, root=True)}</section>
    """


def _branch_nodes(
    active_branch: str,
    matched_rule: str,
    result_status: str,
    deviation: Any,
) -> list[dict[str, Any]]:
    nodes = []
    for option in BRANCH_OPTIONS:
        is_active = option["branch"] == active_branch
        nodes.append(
            {
                "title": option["label"],
                "detail": f"{option['condition']} -> {option['rule']}",
                "branch": option["branch"],
                "active": is_active,
                "children": [
                    {
                        "title": result_status if is_active else option["status"],
                        "detail": (
                            f"{matched_rule}，偏差 {deviation}"
                            if is_active
                            else f"未命中 {option['rule']}"
                        ),
                        "active": is_active,
                        "children": [],
                    }
                ],
            }
        )
    return nodes


def _render_tree_node(node: dict[str, Any], *, root: bool = False) -> str:
    active = bool(node.get("active"))
    classes = "reason-tree-node is-active" if active else "reason-tree-node is-muted"
    title = html.escape(str(node.get("title") or "-"))
    detail = html.escape(str(node.get("detail") or ""))
    children = list(node.get("children") or [])
    children_html = ""
    if children:
        children_html = "<ul>" + "".join(_render_tree_node(child) for child in children) + "</ul>"
    root_class = ' class="reason-tree-root"' if root else ""
    return (
        f"<li{root_class}>"
        f'<article class="{classes}">'
        f'<span class="reason-tree-title">{title}</span>'
        f'<span class="reason-tree-detail">{detail}</span>'
        "</article>"
        f"{children_html}"
        "</li>"
    )
