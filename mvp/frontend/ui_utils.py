"""前端公共工具。

本模块集中处理两类职责：
1. 通过 `requests` 访问 `/api/v1` HTTP API，并把响应规整成统一信封。
2. 渲染 trace 面板、stepper、状态徽标、来源说明等 Streamlit 公共 UI。
"""

from __future__ import annotations

from collections.abc import Iterable
import html
import json
import os
from typing import Any

import requests
import streamlit as st

API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
DEFAULT_API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
TRACE_STORE_KEY = "frontend.trace_store"
TRACE_HISTORY_KEY = "frontend.trace_history"
ACTIVE_ONTOLOGY_KEY = "frontend.active_ontology"
API_BASE_URL_KEY = "frontend.api_base_url"
LAST_HEALTH_KEY = "frontend.last_health"
LAST_ONTOLOGIES_KEY = "frontend.last_ontologies"
REQUEST_TIMEOUT = 10.0
MAX_TRACE_HISTORY = 5
DEFAULT_DEMO_ONTOLOGY_ID = "manufacturing-trial"

STATUS_ICON = {
    "success": "🟢",
    "fallback": "🟡",
    "failed": "🔴",
    "skipped": "⚪",
    "started": "🔵",
}


def init_frontend_state() -> None:
    """初始化前端会话状态。

    这里集中维护 API 地址、当前本体和最近的 trace 缓存，
    避免五个 Tab 各自写入不同键导致状态不一致。
    """

    st.session_state.setdefault(API_BASE_URL_KEY, DEFAULT_API_BASE_URL)
    st.session_state.setdefault(TRACE_STORE_KEY, {})
    st.session_state.setdefault(TRACE_HISTORY_KEY, [])
    st.session_state.setdefault(ACTIVE_ONTOLOGY_KEY, "")
    st.session_state.setdefault(LAST_HEALTH_KEY, {})
    st.session_state.setdefault(LAST_ONTOLOGIES_KEY, [])


def get_api_base_url() -> str:
    """返回当前会话中的 API 基地址。"""

    return str(st.session_state.get(API_BASE_URL_KEY, DEFAULT_API_BASE_URL)).rstrip("/")


def build_api_url(path: str) -> str:
    """拼接 `/api/v1` 绝对地址。"""

    normalized_path = path if path.startswith("/") else f"/{path}"
    return f"{get_api_base_url()}{API_PREFIX}{normalized_path}"


def api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    timeout: float = REQUEST_TIMEOUT,
    trace_key: str | None = None,
    trace_title: str | None = None,
    record_trace: bool = True,
) -> dict[str, Any]:
    """通过 `requests` 调用 `/api/v1`，并规整为统一信封。

    当网络异常、服务未启动或返回非 JSON 时，函数会构造一个前端可消费的失败信封，
    保证页面始终能显示错误原因与一条本地 trace，而不是直接崩溃。
    """

    url = build_api_url(path)
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json_body,
            timeout=timeout,
        )
        envelope = _coerce_envelope(response, method=method, url=url)
    except requests.RequestException as exc:
        envelope = _frontend_error_envelope(
            code="HTTP_REQUEST_FAILED",
            message=str(exc),
            method=method,
            url=url,
        )
    if record_trace:
        remember_trace(trace_key or path, trace_title or path, envelope)
    return envelope


def remember_trace(trace_key: str, title: str, envelope: dict[str, Any]) -> None:
    """缓存最近一次 trace，并保留最近 5 条历史供排查下载。"""

    trace_store = dict(st.session_state.get(TRACE_STORE_KEY, {}))
    trace_store[trace_key] = envelope
    st.session_state[TRACE_STORE_KEY] = trace_store

    trace_id = envelope.get("trace_id") or f"local:{trace_key}"
    history = list(st.session_state.get(TRACE_HISTORY_KEY, []))
    history = [
        item
        for item in history
        if not (item.get("trace_id") == trace_id and item.get("trace_key") == trace_key)
    ]
    history.insert(
        0,
        {
            "trace_id": trace_id,
            "trace_key": trace_key,
            "title": title,
            "trace": list(envelope.get("trace") or []),
        },
    )
    st.session_state[TRACE_HISTORY_KEY] = history[:MAX_TRACE_HISTORY]


def get_last_trace(trace_key: str) -> dict[str, Any] | None:
    """读取某个页面动作最近一次缓存的响应信封。"""

    return st.session_state.get(TRACE_STORE_KEY, {}).get(trace_key)


def get_active_ontology() -> str:
    """返回当前选中的本体 ID。"""

    return str(st.session_state.get(ACTIVE_ONTOLOGY_KEY, "")).strip()


def set_active_ontology(ontology_id: str) -> None:
    """更新当前本体选择。"""

    st.session_state[ACTIVE_ONTOLOGY_KEY] = ontology_id or ""


def extract_data(envelope: dict[str, Any], default: Any = None) -> Any:
    """提取统一信封中的 `data`。"""

    if envelope.get("ok"):
        return envelope.get("data", default)
    return default


def extract_error_message(envelope: dict[str, Any]) -> str:
    """提取统一信封中的错误文本。"""

    error = envelope.get("error") or {}
    return str(error.get("message") or "请求失败")


def render_envelope_feedback(
    envelope: dict[str, Any] | None,
    *,
    success_message: str | None = None,
) -> None:
    """按统一信封渲染成功或失败反馈。"""

    if not envelope:
        return
    if envelope.get("ok"):
        if success_message:
            st.success(success_message)
        return
    st.error(f"{extract_error_message(envelope)}（{(envelope.get('error') or {}).get('code', 'UNKNOWN')}）")


def format_status_badge(label: str, status: str, detail: str = "") -> str:
    """把状态映射为带图标的简短文案。"""

    icon = STATUS_ICON.get(status, "⚪")
    suffix = f" · {detail}" if detail else ""
    return f"{icon} {label}: {status}{suffix}"


def render_status_badge(label: str, status: str, detail: str = "") -> None:
    """渲染单个状态徽标。"""

    st.markdown(format_status_badge(label, status, detail))


def health_badge(name: str, value: Any, detail: str = "") -> None:
    """把健康检查字段转成统一徽标。"""

    if isinstance(value, bool):
        status = "success" if value else "failed"
        render_status_badge(name, status, detail)
        return
    lowered = str(value or "").lower()
    if lowered in {"available", "success", "true", "ok"}:
        render_status_badge(name, "success", detail or str(value))
    elif lowered in {"fallback", "busy"}:
        render_status_badge(name, "fallback", detail or str(value))
    elif lowered in {"missing_java", "failed", "false", "down", "unavailable"}:
        render_status_badge(name, "failed", detail or str(value))
    else:
        render_status_badge(name, "skipped", detail or str(value or "unknown"))


def render_stepper(trace: list[dict[str, Any]] | None, *, empty_text: str = "等待执行") -> None:
    """根据 trace 渲染当前步骤进度条。

    API 并不会显式返回“总步骤数”，这里采用可见步骤数作为分母，
    让用户至少知道当前动作已走过哪些关键节点。
    """

    trace = list(trace or [])
    if not trace:
        st.progress(0.0, text=f"0/0 {empty_text}")
        return
    current = len(trace)
    total = len(trace)
    last_step = trace[-1]
    status = str(last_step.get("status") or "success")
    icon = STATUS_ICON.get(status, "⚪")
    st.progress(1.0, text=f"{current}/{total} {icon} {last_step.get('step', 'unknown')}")


def render_reason_caption(parts: Iterable[str]) -> None:
    """渲染来源、模板、降级原因等说明气泡。"""

    visible = [part for part in parts if part]
    if visible:
        st.caption(" · ".join(visible))


def inject_brand_theme() -> None:
    """注入全局品牌化样式，收敛首屏层级、导航和表单视觉。"""

    st.markdown(
        """
        <style>
        :root {
            --brand-ink: #10243f;
            --brand-ink-soft: #344863;
            --brand-muted: #6f7a89;
            --brand-line: rgba(16, 36, 63, 0.10);
            --brand-paper: rgba(255, 255, 255, 0.72);
            --brand-accent: #ff6a3d;
            --brand-accent-alt: #13b5c8;
            --brand-success: #2f9d6a;
            --brand-danger: #d74b5c;
            --brand-warning: #f6b042;
            --brand-shadow: 0 24px 60px rgba(16, 36, 63, 0.08);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 106, 61, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(19, 181, 200, 0.12), transparent 24%),
                linear-gradient(180deg, #f7f1e8 0%, #f3f5f8 46%, #eef2f5 100%);
            color: var(--brand-ink);
        }

        [data-testid="stHeader"] {
            background: rgba(247, 241, 232, 0.78);
            backdrop-filter: blur(14px);
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1320px;
            padding-top: 2.6rem;
            padding-bottom: 4rem;
        }

        html, body, [class*="css"] {
            font-family: "Bahnschrift", "Avenir Next", "Segoe UI", "Microsoft YaHei UI", sans-serif;
        }

        h1, h2, h3 {
            color: var(--brand-ink);
            letter-spacing: -0.03em;
        }

        p, label, [data-testid="stCaptionContainer"] {
            color: var(--brand-muted);
        }

        .brand-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
            gap: 1.2rem;
            padding: 1.7rem 1.8rem;
            border: 1px solid rgba(255, 255, 255, 0.55);
            border-radius: 30px;
            background:
                linear-gradient(135deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.62)),
                linear-gradient(120deg, rgba(255, 106, 61, 0.08), rgba(19, 181, 200, 0.06));
            box-shadow: var(--brand-shadow);
            margin-bottom: 1rem;
        }

        .brand-kicker {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: rgba(16, 36, 63, 0.06);
            color: var(--brand-ink-soft);
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        .brand-title {
            margin: 0.85rem 0 0.45rem;
            font-size: clamp(2.8rem, 5vw, 4.8rem);
            line-height: 0.95;
            color: var(--brand-ink);
        }

        .brand-subtitle {
            max-width: 48rem;
            margin: 0;
            color: var(--brand-ink-soft);
            font-size: 1.03rem;
            line-height: 1.65;
        }

        .brand-side {
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 0.8rem;
        }

        .brand-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
        }

        .brand-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.45rem 0.75rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.74);
            border: 1px solid rgba(16, 36, 63, 0.08);
            color: var(--brand-ink-soft);
            font-size: 0.84rem;
            font-weight: 600;
        }

        .brand-chip--accent {
            background: linear-gradient(135deg, rgba(255, 106, 61, 0.14), rgba(19, 181, 200, 0.12));
            color: var(--brand-ink);
        }

        .brand-note {
            padding: 1rem 1.05rem;
            border-radius: 20px;
            background: rgba(16, 36, 63, 0.92);
            color: rgba(255, 255, 255, 0.88);
            font-size: 0.92rem;
            line-height: 1.6;
        }

        .st-key-shell-controls {
            margin: 0.75rem 0 0.95rem;
            padding: 1rem 1.05rem 0.85rem;
            border-radius: 24px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background:
                linear-gradient(135deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.64)),
                linear-gradient(135deg, rgba(255, 106, 61, 0.04), rgba(19, 181, 200, 0.04));
            box-shadow: 0 16px 36px rgba(16, 36, 63, 0.05);
        }

        .st-key-shell-controls [data-testid="stHorizontalBlock"] {
            align-items: end;
        }

        .shell-controls__eyebrow {
            margin-bottom: 0.5rem;
            color: var(--brand-accent);
            font-size: 0.74rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.16em;
        }

        .shell-controls__hint {
            margin: 0 0 0.9rem;
            color: var(--brand-ink-soft);
            font-size: 0.94rem;
            line-height: 1.55;
        }

        .status-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.75rem 0 1.1rem;
        }

        .status-card {
            padding: 1rem 1rem 0.95rem;
            border-radius: 22px;
            border: 1px solid var(--brand-line);
            background: var(--brand-paper);
            box-shadow: 0 16px 36px rgba(16, 36, 63, 0.05);
        }

        .status-label {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--brand-muted);
            font-weight: 700;
        }

        .status-value {
            display: block;
            margin-top: 0.5rem;
            color: var(--brand-ink);
            font-size: 1.1rem;
            font-weight: 700;
            line-height: 1.2;
            word-break: break-word;
        }

        .status-detail {
            display: block;
            margin-top: 0.35rem;
            color: var(--brand-muted);
            font-size: 0.86rem;
            line-height: 1.45;
        }

        .status-card.success { border-top: 4px solid var(--brand-success); }
        .status-card.failed { border-top: 4px solid var(--brand-danger); }
        .status-card.fallback { border-top: 4px solid var(--brand-warning); }
        .status-card.neutral { border-top: 4px solid var(--brand-accent-alt); }

        .ops-rail {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin: -0.15rem 0 1.15rem;
        }

        .ops-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.48rem 0.72rem;
            border-radius: 999px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background: rgba(255, 255, 255, 0.6);
            color: var(--brand-ink-soft);
            font-size: 0.82rem;
            line-height: 1.3;
        }

        .ops-pill::before {
            content: "";
            width: 0.55rem;
            height: 0.55rem;
            border-radius: 999px;
            background: var(--brand-accent-alt);
            box-shadow: 0 0 0 4px rgba(19, 181, 200, 0.12);
            flex: 0 0 auto;
        }

        .ops-pill.success::before {
            background: var(--brand-success);
            box-shadow: 0 0 0 4px rgba(47, 157, 106, 0.12);
        }

        .ops-pill.failed::before {
            background: var(--brand-danger);
            box-shadow: 0 0 0 4px rgba(215, 75, 92, 0.12);
        }

        .ops-pill.fallback::before {
            background: var(--brand-warning);
            box-shadow: 0 0 0 4px rgba(246, 176, 66, 0.12);
        }

        .ops-pill__label {
            color: var(--brand-muted);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.72rem;
        }

        .ops-pill__value {
            color: var(--brand-ink);
            font-weight: 700;
        }

        .panel-intro {
            margin: 0.2rem 0 1rem;
            padding: 1.05rem 1.1rem 1rem;
            border-radius: 22px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background: rgba(255, 255, 255, 0.52);
        }

        .panel-kicker {
            font-size: 0.76rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--brand-accent);
            font-weight: 700;
        }

        .panel-title {
            margin: 0.32rem 0 0.15rem;
            color: var(--brand-ink);
            font-size: 1.55rem;
            font-weight: 800;
        }

        .panel-summary {
            margin: 0;
            color: var(--brand-ink-soft);
            line-height: 1.6;
        }

        .note-box {
            padding: 1rem 1.05rem;
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(16, 36, 63, 0.96), rgba(31, 56, 92, 0.94));
            color: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 14px 32px rgba(16, 36, 63, 0.12);
        }

        .note-box strong {
            color: #ffffff;
        }

        .stButton > button,
        .stDownloadButton > button {
            min-height: 50px;
            border-radius: 18px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background: linear-gradient(135deg, var(--brand-ink), #223a5b);
            color: #ffffff;
            font-weight: 700;
            box-shadow: 0 12px 30px rgba(16, 36, 63, 0.16);
        }

        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border-color: transparent;
            background: linear-gradient(135deg, #112a49, #29486f);
            color: #ffffff;
        }

        .stToggle label,
        .stCheckbox label {
            color: var(--brand-ink-soft) !important;
            font-weight: 600;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > div,
        .stNumberInput > div,
        .stTextInput > div,
        .stTextArea textarea {
            border-radius: 18px !important;
            background: rgba(255, 255, 255, 0.82) !important;
            border-color: rgba(16, 36, 63, 0.09) !important;
        }

        .stForm {
            padding: 1rem 1rem 0.8rem;
            border-radius: 24px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background: rgba(255, 255, 255, 0.68);
            box-shadow: 0 16px 36px rgba(16, 36, 63, 0.05);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            overflow-x: auto;
            flex-wrap: nowrap;
            padding: 0.35rem;
            border-radius: 999px;
            border: 1px solid rgba(16, 36, 63, 0.09);
            background: rgba(255, 255, 255, 0.56);
            margin-bottom: 1rem;
        }

        .stTabs [data-baseweb="tab"] {
            flex: 0 0 auto;
            height: auto;
            padding: 0.72rem 1rem;
            border-radius: 999px;
            color: var(--brand-muted);
            font-weight: 700;
            white-space: nowrap;
        }

        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, var(--brand-ink), #263f62);
            color: #ffffff;
        }

        div[data-testid="stMetric"] {
            padding: 1rem 1rem 0.85rem;
            border-radius: 22px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background: rgba(255, 255, 255, 0.68);
            box-shadow: 0 14px 32px rgba(16, 36, 63, 0.05);
        }

        div[data-testid="stMetricValue"] {
            color: var(--brand-ink);
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid rgba(16, 36, 63, 0.08);
            box-shadow: 0 16px 36px rgba(16, 36, 63, 0.05);
        }

        div[data-testid="stExpander"] {
            border-radius: 20px;
            border: 1px solid rgba(16, 36, 63, 0.08);
            background: rgba(255, 255, 255, 0.62);
            overflow: hidden;
        }

        .stAlert {
            border-radius: 18px;
            border: 1px solid rgba(16, 36, 63, 0.08);
        }

        @media (max-width: 1024px) {
            .brand-hero {
                grid-template-columns: 1fr;
            }

            .status-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 640px) {
            [data-testid="stMainBlockContainer"] {
                padding-top: 1.6rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .brand-title {
                font-size: 3rem;
            }

            .brand-note {
                padding: 0.88rem 0.9rem;
                font-size: 0.88rem;
            }

            .st-key-shell-controls {
                padding: 0.8rem 0.85rem 0.7rem;
            }

            .status-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.7rem;
            }

            .status-card {
                padding: 0.85rem 0.85rem 0.78rem;
            }

            .status-value {
                font-size: 1rem;
            }
        }

        @media (max-width: 360px) {
            .status-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_hero(*, title: str, subtitle: str, chips: Iterable[str], note: str) -> None:
    """渲染顶部品牌头。"""

    safe_chips = "".join(
        f'<span class="brand-chip{" brand-chip--accent" if index == 0 else ""}">{html.escape(str(chip))}</span>'
        for index, chip in enumerate(chips)
    )
    subtitle_block = f'<p class="brand-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    note_block = f'<div class="brand-note">{html.escape(note)}</div>' if note else ""
    st.markdown(
        f"""
        <section class="brand-hero">
          <div>
            <span class="brand-kicker">Ontology Showcase</span>
            <h1 class="brand-title">{html.escape(title)}</h1>
            {subtitle_block}
          </div>
          <div class="brand-side">
            <div class="brand-chip-row">{safe_chips}</div>
            {note_block}
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_status_summary(cards: Iterable[dict[str, str]]) -> None:
    """以卡片网格方式渲染系统状态摘要。"""

    html_cards = []
    for item in cards:
        tone = html.escape(str(item.get("tone") or "neutral"))
        label = html.escape(str(item.get("label") or ""))
        value = html.escape(str(item.get("value") or ""))
        detail = html.escape(str(item.get("detail") or ""))
        html_cards.append(
            f'<article class="status-card {tone}">'
            f'<span class="status-label">{label}</span>'
            f'<span class="status-value">{value}</span>'
            f'<span class="status-detail">{detail}</span>'
            "</article>"
        )
    st.markdown(f'<section class="status-grid">{"".join(html_cards)}</section>', unsafe_allow_html=True)


def render_panel_intro(*, kicker: str, title: str, summary: str) -> None:
    """渲染每个页签顶部的介绍块。"""

    summary_block = f'<p class="panel-summary">{html.escape(summary)}</p>' if summary else ""
    st.markdown(
        f"""
        <section class="panel-intro">
          <div class="panel-kicker">{html.escape(kicker)}</div>
          <div class="panel-title">{html.escape(title)}</div>
          {summary_block}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_ops_rail(items: Iterable[dict[str, str]]) -> None:
    """把运行元信息渲染成胶囊式操作条，而不是弱化的 caption。"""

    pills = []
    for item in items:
        label = html.escape(str(item.get("label") or ""))
        value = html.escape(str(item.get("value") or ""))
        tone = html.escape(str(item.get("tone") or "neutral"))
        pills.append(
            f'<span class="ops-pill {tone}">'
            f'<span class="ops-pill__label">{label}</span>'
            f'<span class="ops-pill__value">{value}</span>'
            "</span>"
        )
    st.markdown(f'<section class="ops-rail">{"".join(pills)}</section>', unsafe_allow_html=True)


def render_note_box(title: str, body: str) -> None:
    """渲染深色提示块，用于强调关键操作或限制。"""

    if not title and not body:
        return
    st.markdown(
        f'<div class="note-box"><strong>{html.escape(title)}</strong><br>{html.escape(body)}</div>',
        unsafe_allow_html=True,
    )


def render_trace(trace_key: str, *, title: str = "🔍 本次执行链路") -> None:
    """渲染可折叠 trace 面板与下载按钮。"""

    envelope = get_last_trace(trace_key)
    trace = list((envelope or {}).get("trace") or [])
    render_stepper(trace)
    with st.expander(title, expanded=bool(trace)):
        if not envelope:
            st.info("暂无执行链路。")
            return
        payload = {
            "trace_id": envelope.get("trace_id"),
            "trace": trace,
            "error": envelope.get("error"),
        }
        st.download_button(
            label="下载 trace JSON",
            data=json.dumps(payload, ensure_ascii=False, indent=2),
            file_name=f"{(envelope.get('trace_id') or trace_key).replace(':', '_')}.json",
            mime="application/json",
            key=f"download-trace-{trace_key}",
        )
        if not trace:
            st.info("本次响应未返回 trace。")
            return
        for index, step in enumerate(trace, start=1):
            icon = STATUS_ICON.get(str(step.get("status") or ""), "⚪")
            reason = step.get("reason") or "未提供原因"
            elapsed = step.get("elapsed_ms")
            suffix = f" · {elapsed}ms" if elapsed is not None else ""
            st.markdown(f"{index}. {icon} `{step.get('step', 'unknown')}` - {reason}{suffix}")
            detail = step.get("detail") or {}
            if detail:
                st.caption(json.dumps(detail, ensure_ascii=False, sort_keys=True))


def render_dataframe(items: list[dict[str, Any]], *, empty_text: str = "暂无数据") -> None:
    """用统一空态渲染表格。"""

    if not items:
        st.info(empty_text)
        return
    st.dataframe(items, width="stretch")


def load_health(record_trace: bool = False) -> dict[str, Any]:
    """读取 `/health`，并缓存最近一次结果。"""

    envelope = api_request("GET", "/health", record_trace=record_trace)
    st.session_state[LAST_HEALTH_KEY] = envelope
    return envelope


def load_ontologies(record_trace: bool = False) -> dict[str, Any]:
    """读取 `/ontologies`，并缓存最近一次结果。"""

    envelope = api_request("GET", "/ontologies", record_trace=record_trace)
    st.session_state[LAST_ONTOLOGIES_KEY] = extract_data(envelope, default=[]) or []
    return envelope


def sync_active_ontology(ontologies: list[dict[str, Any]]) -> None:
    """根据本体列表修正当前选择，避免切到已不存在的 ID。"""

    ids = [str(item.get("ontology_id") or "") for item in ontologies if item.get("ontology_id")]
    current = get_active_ontology()
    if current in ids:
        return
    if DEFAULT_DEMO_ONTOLOGY_ID in ids:
        set_active_ontology(DEFAULT_DEMO_ONTOLOGY_ID)
        return
    set_active_ontology(ids[0] if ids else "")


def ontology_options(ontologies: list[dict[str, Any]]) -> list[str]:
    """提取本体 ID 列表，供下拉框复用。"""

    return [str(item.get("ontology_id")) for item in ontologies if item.get("ontology_id")]


def _coerce_envelope(response: requests.Response, *, method: str, url: str) -> dict[str, Any]:
    """把 HTTP 响应规整为统一信封。"""

    try:
        payload = response.json()
    except ValueError:
        payload = {
            "ok": response.ok,
            "data": {"raw_text": response.text},
            "error": None if response.ok else {"code": f"HTTP_{response.status_code}", "message": response.text},
            "trace_id": None,
            "trace": [],
        }
    if not isinstance(payload, dict):
        payload = {"ok": response.ok, "data": payload, "error": None, "trace_id": None, "trace": []}
    payload.setdefault("ok", response.ok)
    payload.setdefault("data", None)
    payload.setdefault("error", None if response.ok else {"code": f"HTTP_{response.status_code}", "message": response.reason})
    payload.setdefault("trace_id", None)
    payload.setdefault("trace", [])
    payload["_meta"] = {
        "http_status": response.status_code,
        "method": method.upper(),
        "url": url,
    }
    return payload


def _frontend_error_envelope(*, code: str, message: str, method: str, url: str) -> dict[str, Any]:
    """构造前端本地失败信封。"""

    return {
        "ok": False,
        "data": None,
        "error": {"code": code, "message": message},
        "trace_id": None,
        "trace": [
            {
                "step": "http_request",
                "status": "failed",
                "reason": "前端通过 requests 访问 /api/v1 失败",
                "detail": {"method": method.upper(), "url": url},
                "elapsed_ms": None,
            }
        ],
        "_meta": {"http_status": None, "method": method.upper(), "url": url},
    }
