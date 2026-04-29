"""前端边界与契约约束测试。

这些测试只检查前端源码文本，不导入 Streamlit 运行时，
用于锁定 TC-116 / TC-165 的边界要求：
1. 前端文件必须存在。
2. 前端只能通过 requests 访问 `/api/v1` HTTP API。
3. 前端不得直接依赖 `mvp.core`、`mvp.api` 或 `importlib`。
"""

from __future__ import annotations

from pathlib import Path
import re


FRONTEND_FILES = [
    Path("mvp/frontend/ui_utils.py"),
    Path("mvp/frontend/app.py"),
    Path("mvp/frontend/tabs/tab_customer.py"),
    Path("mvp/frontend/tabs/tab_ontology.py"),
    Path("mvp/frontend/tabs/tab_subjects.py"),
    Path("mvp/frontend/tabs/tab_pellet.py"),
    Path("mvp/frontend/tabs/tab_measure.py"),
    Path("mvp/frontend/tabs/tab_qa.py"),
    Path("mvp/frontend/tabs/tab_equipment_health.py"),
]

FORBIDDEN_PATTERNS = [
    r"\bfrom\s+mvp\.core\b",
    r"\bimport\s+mvp\.core\b",
    r"\bfrom\s+mvp\.api\b",
    r"\bimport\s+mvp\.api\b",
    r"\bimportlib\b",
]


def test_required_frontend_files_exist() -> None:
    """前端任务范围内的目标文件必须全部落地。"""

    missing = [str(path) for path in FRONTEND_FILES if not path.exists()]
    assert not missing, f"missing frontend files: {missing}"


def test_frontend_stays_outside_core_and_api_runtime() -> None:
    """前端不得直接导入核心层、API 层或 importlib。"""

    violations: list[str] = []
    for path in FRONTEND_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, text):
                violations.append(f"{path}: {pattern}")
    assert not violations, f"frontend boundary violations: {violations}"


def test_frontend_uses_requests_and_api_v1_prefix() -> None:
    """前端必须通过 requests 访问 `/api/v1` HTTP API。"""

    missing_requests: list[str] = []
    missing_api_prefix: list[str] = []
    for path in FRONTEND_FILES:
        text = path.read_text(encoding="utf-8")
        if "requests" not in text:
            missing_requests.append(str(path))
        if "/api/v1" not in text and "API_PREFIX" not in text:
            missing_api_prefix.append(str(path))
    assert not missing_requests, f"frontend files without requests usage marker: {missing_requests}"
    assert not missing_api_prefix, f"frontend files without /api/v1 or API_PREFIX marker: {missing_api_prefix}"


def test_measure_tab_exposes_compare_mode_and_reasoner_badges() -> None:
    """Tab 四必须保留对照模式开关与来源徽标文案，满足 TC-114 / TC-140 / TC-166。"""

    text = Path("mvp/frontend/tabs/tab_measure.py").read_text(encoding="utf-8")
    assert "enable_swrl" in text
    assert "Pellet-SWRL" in text
    assert "Python" in text


def test_measure_tab_localizes_form_labels_and_table_headers() -> None:
    """测量页应把页面可见的字段名渲染为中文，内部 API 字段名保持英文。"""

    from mvp.frontend.tabs import tab_measure

    text = Path("mvp/frontend/tabs/tab_measure.py").read_text(encoding="utf-8")
    assert 'text_input("测量ID"' in text
    assert 'text_input("批次"' in text
    assert 'selectbox("参数"' in text
    assert 'number_input("测量值"' in text
    assert 'text_input("操作员"' in text

    compare_rows = tab_measure.localize_measurement_table_rows(
        [
            {
                "reasoner": "Pellet-SWRL",
                "status": "Fail_High",
                "rule": "Rule_Fail_High",
                "deviation": 2.2,
                "spec_version": "Spec_v1",
                "swrl_status": "fallback",
                "pellet_status": "success",
                "saved": True,
            }
        ]
    )
    assert list(compare_rows[0]) == ["推理来源", "判定", "规则", "偏差", "规格版本", "SWRL状态", "Pellet状态", "已保存"]

    measurement_rows = tab_measure.localize_measurement_table_rows(
        [
            {
                "measurement_id": "S0001",
                "batch": "B-001",
                "parameter": "cq_temperature",
                "value": 197.2,
                "status": "Fail_High",
                "rule": "Rule_Fail_High",
                "deviation": 2.2,
                "spec_version": "Spec_v1",
                "reasoner": "python-deterministic",
                "inferred_at": "2026-04-27T07:49:20.496248Z",
                "reasoners": ["pellet-swrl", "python-deterministic"],
            }
        ]
    )
    assert list(measurement_rows[0]) == [
        "测量ID",
        "批次",
        "参数",
        "测量值",
        "判定",
        "规则",
        "偏差",
        "规格版本",
        "推理来源",
        "判定时间",
        "来源列表",
    ]
    assert measurement_rows[0]["测量ID"] == "S0001"

    impact_rows = tab_measure.localize_measurement_table_rows(
        [{"old_status": "Fail_High", "new_status": "Pass", "old_spec": "Spec_v1", "new_spec": "Spec_v2"}]
    )
    assert list(impact_rows[0]) == ["原判定", "新判定", "原规格", "新规格"]

    spec_rows = tab_measure.localize_measurement_table_rows(
        [
            {
                "spec_id": "temperature_Spec_v2",
                "parameter": "temperature",
                "spec_version": "Spec_v2",
                "lower": 180.0,
                "upper": 190.0,
                "reason": "规格收紧",
                "effective_from": "2026-04-23T02:00:00Z",
                "supersedes": "Spec_v1",
            }
        ]
    )
    assert list(spec_rows[0]) == ["规格ID", "参数", "规格版本", "下限", "上限", "变更原因", "生效时间", "上一版本"]


def test_measure_tab_uses_current_form_parameter_for_measurement_list() -> None:
    """测量录入后，下方测量表应跟随表单当前参数，而不是固定第一个参数。"""

    from mvp.frontend.tabs import tab_measure

    assert tab_measure.measurement_list_parameter(
        "vibration_frequency",
        ["cq_temperature", "vibration_frequency"],
    ) == "vibration_frequency"
    assert tab_measure.measurement_list_parameter("", ["cq_temperature"]) == "cq_temperature"


def test_measure_tab_specification_history_is_not_filtered_to_current_form_parameter() -> None:
    """规格历史应展示完整历史，避免切换/新增参数后让旧规格看起来被覆盖。"""

    from mvp.frontend.tabs import tab_measure

    assert tab_measure.specification_history_params("manufacturing-trial", "vibration_frequency") == {
        "ontology_id": "manufacturing-trial",
    }


def test_measure_tab_renders_specification_history() -> None:
    """测量页应展示规格历史，让用户看到 Spec_v2 的上下限。"""

    text = Path("mvp/frontend/tabs/tab_measure.py").read_text(encoding="utf-8")
    assert '"/specifications"' in text
    assert "api_request(" in text
    assert '"**规格历史**"' in text
    assert "暂无规格历史。" in text


def test_top_bar_does_not_reassign_widget_bound_session_state_key() -> None:
    """顶栏 ontology selectbox 不得在实例化后再次写回同名 session_state key。"""

    text = Path("mvp/frontend/app.py").read_text(encoding="utf-8")
    assert 'key=ACTIVE_ONTOLOGY_KEY' in text
    assert 'set_active_ontology(selected)' not in text


def test_top_bar_selectbox_does_not_mix_index_with_bound_session_state() -> None:
    """顶栏 selectbox 绑定 session_state key 时，不应再传 index 默认值。"""

    text = Path("mvp/frontend/app.py").read_text(encoding="utf-8")
    selector_block = text[
        text.index("st.selectbox(") : text.index("with action_col:")
    ]
    assert "key=ACTIVE_ONTOLOGY_KEY" in selector_block
    assert "index=" not in selector_block


def test_app_uses_demo_brand_title_and_shell_navigation() -> None:
    """首页应切换到“本体演示”品牌壳层，并使用精简导航标签。"""

    text = Path("mvp/frontend/app.py").read_text(encoding="utf-8")
    assert 'page_title="本体演示"' in text
    assert "inject_brand_theme()" in text
    assert '"客户讲"' in text
    assert '"技术讲"' in text
    assert '"设备健康"' in text
    assert '"本体"' in text
    assert '"主体"' in text
    assert '"推理"' in text
    assert '"测量"' in text
    assert '"问答"' in text


def test_customer_page_formats_abox_reasoning_path() -> None:
    """客户页应把 API 返回的 explanation 渲染成可讲述的 ABOX 推理路径。"""

    from mvp.frontend.tabs import tab_customer

    rows = tab_customer.reasoning_timeline_rows(
        {
            "abox": {
                "measurement_id": "M010",
                "batch": "B01",
                "parameter": "temperature",
                "value": 197.2,
            },
            "spec": {"lower_limit": 180.0, "upper_limit": 195.0, "spec_version": "Spec_v1"},
            "branch": "above_upper",
            "branch_label": "高于上限",
            "matched_rule": "Rule_Fail_High",
            "condition": "value > upper_limit",
            "result": {"status": "Fail_High", "deviation": 2.2},
            "path": [
                {"name": "读取 ABOX 测量事实", "detail": "测量值 197.2"},
                {"name": "输出判定结果", "detail": "Fail_High"},
            ],
        }
    )

    assert rows[0]["阶段"] == "读取 ABOX 测量事实"
    assert rows[0]["说明"] == "测量值 197.2"
    assert rows[-1]["分支"] == "高于上限"
    assert rows[-1]["命中规则"] == "Rule_Fail_High"
    assert rows[-1]["结果"] == "Fail_High"


def test_customer_page_builds_highlighted_reasoning_tree() -> None:
    """客户页应把推理过程建模为树，并只高亮实际命中的路线。"""

    from mvp.frontend.tabs import tab_customer

    tree = tab_customer.reasoning_tree_model(
        {
            "abox": {
                "measurement_id": "M010",
                "batch": "B01",
                "parameter": "temperature",
                "value": 197.2,
            },
            "spec": {"lower_limit": 180.0, "upper_limit": 195.0, "spec_version": "Spec_v1"},
            "branch": "above_upper",
            "branch_label": "高于上限",
            "matched_rule": "Rule_Fail_High",
            "condition": "value > upper_limit",
            "result": {"status": "Fail_High", "deviation": 2.2},
        }
    )

    assert tree["active"] is True
    branch_nodes = tree["children"][0]["children"][0]["children"]
    assert [node["branch"] for node in branch_nodes] == [
        "below_lower",
        "within_limits",
        "above_upper",
    ]
    assert [node["active"] for node in branch_nodes] == [False, False, True]
    assert branch_nodes[2]["children"][0]["active"] is True


def test_customer_page_renders_tree_html_with_active_route() -> None:
    """树形 HTML 应包含高亮路线和弱化的非命中分支。"""

    from mvp.frontend.tabs import tab_customer

    html = tab_customer.render_reasoning_tree_html(
        {
            "abox": {
                "measurement_id": "M010",
                "batch": "B01",
                "parameter": "temperature",
                "value": 197.2,
            },
            "spec": {"lower_limit": 180.0, "upper_limit": 195.0, "spec_version": "Spec_v1"},
            "branch": "above_upper",
            "branch_label": "高于上限",
            "matched_rule": "Rule_Fail_High",
            "condition": "value > upper_limit",
            "result": {"status": "Fail_High", "deviation": 2.2},
        }
    )

    assert 'class="reason-tree-node is-active"' in html
    assert 'class="reason-tree-node is-muted"' in html
    assert "Rule_Fail_High" in html
    assert "高于上限" in html
    assert "Fail_High" in html


def test_equipment_health_page_is_bound_to_new_ontology() -> None:
    """新增本体应有对应 Streamlit 页面，且页面只通过 API 使用 equipment-health。"""

    from mvp.frontend.tabs import tab_equipment_health

    text = Path("mvp/frontend/tabs/tab_equipment_health.py").read_text(encoding="utf-8")
    assert tab_equipment_health.EQUIPMENT_ONTOLOGY_ID == "equipment-health"
    assert '"/parameters"' in text
    assert '"/specifications"' in text
    assert '"/measurements"' in text


def test_subject_graph_builds_relation_network_from_subject_payload() -> None:
    """主体页应能把 classes/properties/individuals 组装成关系网。"""

    from mvp.frontend.tabs.subject_graph import build_subject_graph_model

    model = build_subject_graph_model(
        {
            "classes": [
                {"iri": "https://hifar.top/mto#Trial", "name": "Trial", "label": "试验"},
                {"iri": "https://hifar.top/mto#Batch", "name": "Batch", "label": "批次"},
            ],
            "individuals": [
                {
                    "iri": "https://hifar.top/mto/individual/manufacturing-trial/trial/T001",
                    "name": "T001",
                    "label": "T001",
                    "types": [{"iri": "https://hifar.top/mto#Trial", "name": "Trial", "label": "试验"}],
                }
            ],
            "object_properties": [
                {
                    "iri": "https://hifar.top/mto#hasBatch",
                    "name": "hasBatch",
                    "label": "包含批次",
                    "domain": [{"iri": "https://hifar.top/mto#Trial", "name": "Trial", "label": "试验"}],
                    "range": [{"iri": "https://hifar.top/mto#Batch", "name": "Batch", "label": "批次"}],
                }
            ],
            "data_properties": [],
        }
    )

    assert [node["label"] for node in model["nodes"]] == ["试验", "批次", "T001"]
    assert model["edges"] == [
        {"source": "https://hifar.top/mto#Trial", "target": "https://hifar.top/mto#Batch", "label": "包含批次", "kind": "object"},
        {
            "source": "https://hifar.top/mto/individual/manufacturing-trial/trial/T001",
            "target": "https://hifar.top/mto#Trial",
            "label": "type",
            "kind": "type",
        },
    ]


def test_subject_graph_renders_svg_network() -> None:
    """主体页关系网应以 SVG 图谱展示节点和关系边。"""

    from mvp.frontend.tabs.subject_graph import render_subject_graph_html

    html = render_subject_graph_html(
        {
            "classes": [
                {"iri": "https://hifar.top/mto#Trial", "name": "Trial", "label": "试验"},
                {"iri": "https://hifar.top/mto#Batch", "name": "Batch", "label": "批次"},
            ],
            "individuals": [],
            "object_properties": [
                {
                    "iri": "https://hifar.top/mto#hasBatch",
                    "name": "hasBatch",
                    "label": "包含批次",
                    "domain": [{"iri": "https://hifar.top/mto#Trial", "name": "Trial", "label": "试验"}],
                    "range": [{"iri": "https://hifar.top/mto#Batch", "name": "Batch", "label": "批次"}],
                }
            ],
            "data_properties": [],
        }
    )

    assert "<svg" in html
    assert "subject-graph-edge" in html
    assert "包含批次" in html
    assert "试验" in html
    assert "批次" in html


def test_subject_tab_exposes_graph_view() -> None:
    """技术讲-主体页应新增关系网图谱视图，并保留原明细表。"""

    text = Path("mvp/frontend/tabs/tab_subjects.py").read_text(encoding="utf-8")
    assert '"关系网"' in text
    assert "render_subject_graph_html(" in text
    assert "unsafe_allow_html=True" in text


def test_app_bootstraps_project_root_for_streamlit_script_entry() -> None:
    """直接以 `streamlit run mvp/frontend/app.py` 启动时，应显式补齐项目根目录。"""

    text = Path("mvp/frontend/app.py").read_text(encoding="utf-8")
    assert "PROJECT_ROOT = Path(__file__).resolve().parents[2]" in text
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in text


def test_status_summary_uses_compact_html_block(monkeypatch) -> None:
    """状态摘要卡片应输出紧凑 HTML，避免被 Markdown 当作普通文本渲染。"""

    from mvp.frontend import ui_utils

    captured: dict[str, object] = {}

    def fake_markdown(body: str, unsafe_allow_html: bool = False) -> None:
        captured["body"] = body
        captured["unsafe_allow_html"] = unsafe_allow_html

    monkeypatch.setattr(ui_utils.st, "markdown", fake_markdown)
    ui_utils.render_status_summary(
        [
            {
                "label": "Fuseki",
                "value": "在线",
                "detail": "3 个 graph 已装载",
                "tone": "success",
            }
        ]
    )

    body = str(captured["body"])
    assert body.startswith('<section class="status-grid"><article class="status-card success">')
    assert "\n" not in body
    assert captured["unsafe_allow_html"] is True


def test_app_uses_shell_controls_and_ops_rail() -> None:
    """首屏应包含命令条容器与运行条，减少零散控件和灰字说明。"""

    text = Path("mvp/frontend/app.py").read_text(encoding="utf-8")
    assert 'st.container(key="shell-controls")' in text
    assert "render_ops_rail(" in text


def test_owlready_ops_rail_uses_availability_not_unknown_version() -> None:
    """Owlready 已可用但无版本号时，运行条不应显示 unknown。"""

    from mvp.frontend import app

    assert app._owlready_display({"available": True, "version": "unknown"}) == "ready"
    assert app._owlready_tone({"available": True, "version": "unknown"}) == "success"
    assert app._owlready_display({"available": False, "version": None}) == "missing"
    assert app._owlready_tone({"available": False, "version": None}) == "failed"


def test_brand_theme_keeps_two_column_status_cards_on_standard_mobile() -> None:
    """390px 级别移动端优先保持两列状态卡，只在更窄宽度下退回单列。"""

    text = Path("mvp/frontend/ui_utils.py").read_text(encoding="utf-8")
    assert "@media (max-width: 640px)" in text
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in text
    assert "@media (max-width: 360px)" in text
    assert "grid-template-columns: 1fr;" in text


def test_sync_active_ontology_prefers_manufacturing_trial_default(monkeypatch) -> None:
    """新增本体后，首屏默认仍应优先进入原制造试验演示上下文。"""

    from mvp.frontend import ui_utils

    session_state: dict[str, object] = {}
    monkeypatch.setattr(ui_utils.st, "session_state", session_state, raising=False)

    ui_utils.sync_active_ontology(
        [
            {"ontology_id": "equipment-health"},
            {"ontology_id": "manufacturing-trial"},
            {"ontology_id": "process-window"},
        ]
    )

    assert session_state[ui_utils.ACTIVE_ONTOLOGY_KEY] == "manufacturing-trial"


def test_frontend_drops_meta_descriptive_copy() -> None:
    """页面应去除风格解释和冗长提示，保留功能性标题与操作文案。"""

    app_text = Path("mvp/frontend/app.py").read_text(encoding="utf-8")
    measure_text = Path("mvp/frontend/tabs/tab_measure.py").read_text(encoding="utf-8")
    qa_text = Path("mvp/frontend/tabs/tab_qa.py").read_text(encoding="utf-8")

    assert "更大胆的品牌壳层只改变表达方式" not in app_text
    assert "把当前演示上下文锁定到目标本体" not in app_text
    assert "首屏控件只保留真正影响演示上下文的入口" not in app_text
    assert "这条链路最接近真实业务" not in measure_text
    assert "适合演示临时变量与试验扩展" not in qa_text


def test_qa_parameter_rows_repair_legacy_text_and_format_created_at() -> None:
    """问答页参数列表应修复历史乱码并把 created_at 渲染到毫秒。"""

    from mvp.frontend.tabs.tab_qa import localize_parameter_table_rows, parameter_table_rows

    rows = parameter_table_rows(
        [
            {
                "code": "temperature",
                "name": "????",
                "unit": "?C",
                "value_type": "number",
                "participates_in_inference": True,
                "created_at": "2026-04-23T08:50:52.465168Z",
            },
            {
                "code": "ui_param_147940",
                "name": "UIéª\u008cæ\u0094¶å\u008f\u0082æ\u0095°",
                "unit": "Hz",
                "value_type": "number",
                "participates_in_inference": True,
                "created_at": "2026-04-23T09:06:03.888717Z",
            },
        ]
    )

    assert rows[0]["name"] == "注塑温度"
    assert rows[0]["unit"] == "°C"
    assert rows[0]["created_at"] == "2026-04-23 08:50:52 465"
    assert rows[1]["name"] == "UI验收参数"
    assert rows[1]["created_at"] == "2026-04-23 09:06:03 888"

    localized = localize_parameter_table_rows(rows[:1])
    assert list(localized[0]) == ["参数编码", "参数名称", "单位", "值类型", "参与推理", "创建时间"]
