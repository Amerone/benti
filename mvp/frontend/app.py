"""Streamlit 前端主入口。

页面只通过 `requests` 调用 `/api/v1`，
负责顶部状态栏、本体下拉、五个 Tab 和统一 trace 可观测性呈现。
"""

from __future__ import annotations

from pathlib import Path
import sys

import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mvp.frontend.tabs import (
    tab_customer,
    tab_equipment_health,
    tab_measure,
    tab_ontology,
    tab_pellet,
    tab_qa,
    tab_subjects,
)
from mvp.frontend.ui_utils import (
    ACTIVE_ONTOLOGY_KEY,
    API_PREFIX,
    extract_data,
    get_active_ontology,
    get_api_base_url,
    inject_brand_theme,
    init_frontend_state,
    load_health,
    load_ontologies,
    ontology_options,
    render_brand_hero,
    render_ops_rail,
    render_panel_intro,
    render_status_summary,
    set_active_ontology,
    sync_active_ontology,
)

APP_TITLE = "本体演示"


def main() -> None:
    """渲染前端工作台主页。"""

    st.set_page_config(page_title="本体演示", page_icon="◫", layout="wide")
    init_frontend_state()
    inject_brand_theme()

    health_envelope = load_health(record_trace=False)
    health = extract_data(health_envelope, default={}) or {}
    ontologies_envelope = load_ontologies(record_trace=False)
    ontologies = extract_data(ontologies_envelope, default=[]) or []
    sync_active_ontology(ontologies)

    _render_shell_header(health, ontologies)

    audience_tabs = st.tabs(
        [
            "客户讲",
            "技术讲",
            "设备健康",
        ]
    )

    with audience_tabs[0]:
        tab_customer.render(ontology_id=get_active_ontology())
    with audience_tabs[1]:
        _render_technical_tabs(ontologies)
    with audience_tabs[2]:
        tab_equipment_health.render()


def _render_technical_tabs(ontologies: list[dict[str, object]]) -> None:
    """渲染技术讲页面内的原有工程视图。"""

    tabs = st.tabs(
        [
            "本体",
            "主体",
            "推理",
            "测量",
            "问答",
        ]
    )

    with tabs[0]:
        tab_ontology.render(ontologies=ontologies)
    with tabs[1]:
        tab_subjects.render(ontology_id=get_active_ontology())
    with tabs[2]:
        tab_pellet.render(ontology_id=get_active_ontology())
    with tabs[3]:
        tab_measure.render(ontology_id=get_active_ontology())
    with tabs[4]:
        tab_qa.render(ontology_id=get_active_ontology())


def _render_shell_header(health: dict[str, object], ontologies: list[dict[str, object]]) -> None:
    """渲染品牌头、演示控制与状态摘要。"""

    options = ontology_options(ontologies)

    fuseki = (health.get("fuseki") or {}) if isinstance(health.get("fuseki"), dict) else {}
    owlready = (health.get("owlready") or {}) if isinstance(health.get("owlready"), dict) else {}
    reasoner = (health.get("reasoner") or {}) if isinstance(health.get("reasoner"), dict) else {}
    llm = (health.get("llm") or {}) if isinstance(health.get("llm"), dict) else {}
    loaded_graphs = sum(1 for item in ontologies if item.get("loaded"))
    ontology_total = len(options)

    render_brand_hero(
        title=APP_TITLE,
        subtitle="",
        chips=(
            "Manufacturing Ontology Demo",
            "Fuseki · Owlready2 · Pellet",
            "Deterministic + Explainable",
        ),
        note="",
    )

    render_panel_intro(
        kicker="演示控制",
        title="切换当前本体并同步系统状态",
        summary="",
    )

    with st.container(key="shell-controls"):
        st.markdown('<div class="shell-controls__eyebrow">控制</div>', unsafe_allow_html=True)
        selector_col, action_col = st.columns([3, 1], vertical_alignment="bottom")
        with selector_col:
            st.selectbox(
                "演示本体",
                options=options or [""],
                key=ACTIVE_ONTOLOGY_KEY,
                format_func=lambda item: item or "暂无可用本体",
            )
        with action_col:
            if st.button("同步状态", width="stretch"):
                st.rerun()

    render_status_summary(
        [
            {
                "label": "API 入口",
                "value": _api_entry_label(),
                "detail": f"requests-only {API_PREFIX}",
                "tone": "neutral",
            },
            {
                "label": "当前本体",
                "value": get_active_ontology() or "未选择",
                "detail": f"已发现 {ontology_total} 个本体",
                "tone": "neutral",
            },
            {
                "label": "Fuseki",
                "value": "在线" if bool(fuseki.get("available")) else "离线",
                "detail": f"{loaded_graphs} 个 graph 已装载",
                "tone": "success" if bool(fuseki.get("available")) else "failed",
            },
            {
                "label": "推理",
                "value": _reasoner_display(reasoner),
                "detail": _reasoner_detail(reasoner),
                "tone": _status_tone(reasoner.get("pellet")),
            },
            {
                "label": "问答",
                "value": _llm_display(llm),
                "detail": _llm_detail(llm),
                "tone": "success" if bool(llm.get("available")) else "fallback",
            },
        ]
    )
    render_ops_rail(
        [
            {
                "label": "deterministic",
                "value": "on" if bool(reasoner.get("deterministic")) else "off",
                "tone": "success" if bool(reasoner.get("deterministic")) else "failed",
            },
            {
                "label": "owlready",
                "value": _owlready_display(owlready),
                "tone": _owlready_tone(owlready),
            },
            {
                "label": "provider",
                "value": str(llm.get("provider") or "local_fallback"),
                "tone": "success" if bool(llm.get("available")) else "fallback",
            },
        ]
    )


def _status_tone(value: object) -> str:
    lowered = str(value or "").lower()
    if lowered in {"available", "success", "true", "ok"}:
        return "success"
    if lowered in {"fallback", "busy", "skipped"}:
        return "fallback"
    if lowered in {"missing_java", "failed", "false", "down", "unavailable"}:
        return "failed"
    return "neutral"


def _api_entry_label() -> str:
    return get_api_base_url().removeprefix("http://").removeprefix("https://")


def _reasoner_display(reasoner: dict[str, object]) -> str:
    pellet = str(reasoner.get("pellet") or "").lower()
    if pellet == "available":
        return "Pellet 就绪"
    if pellet == "missing_java":
        return "缺少 JRE"
    if pellet == "failed":
        return "Pellet 异常"
    if pellet == "fallback":
        return "Python 对照"
    return "推理待检"


def _reasoner_detail(reasoner: dict[str, object]) -> str:
    source = str(reasoner.get("java_source") or "runtime")
    return f"确定性链路 + {source}"


def _owlready_display(owlready: dict[str, object]) -> str:
    if bool(owlready.get("available")):
        return "ready"
    return "missing"


def _owlready_tone(owlready: dict[str, object]) -> str:
    return "success" if bool(owlready.get("available")) else "failed"


def _llm_display(llm: dict[str, object]) -> str:
    provider = str(llm.get("provider") or "local_fallback")
    if provider == "claude":
        return "Claude"
    if provider == "openai":
        return "OpenAI"
    if provider == "local_fallback":
        return "Local Fallback"
    return provider


def _llm_detail(llm: dict[str, object]) -> str:
    return "在线解释" if bool(llm.get("available")) else "回退解释链路"


if __name__ == "__main__":
    main()
