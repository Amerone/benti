# 委托单 CQ 工程测试完成度评估

日期：2026-04-29

本报告从测试视角判断 `commission-testing` 系统是否满足当前需求。结论分为三类：

- 通过：自动化测试或 API/页面探针能证明功能满足。
- 演示级通过：固定演示剧本满足，但还不是通用产品能力。
- 未满足：当前系统没有对应 API、页面能力或测试证据。

## 测试方法

本轮没有修改生产代码。测试条件来自需求与设计文档：

- 委托单：`CO-2024-001`
- 产品：相控阵雷达导引头，型号 `X-01`
- 试验项目：高低温振动试验、电磁兼容试验
- 自动任务：`T-001`、`T-002`
- 测试项：`RCS_MEAN`、`BER`
- 标准升级：`GJB-7821-2024 V1 -> V2`
- 关键期望：`RCS_MEAN 0.042` 从 `Pass` 翻转为 `Fail`，`T-001` 变为 `NeedsReview`

## 验证命令

已执行：

```powershell
python -m pytest -q
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

结果：

```text
150 passed
1 passed
```

已执行 API 能力探针，确认存在：

```text
/api/v1/commission/demo/reset
/api/v1/commission/orders/{order_no}
/api/v1/commission/orders/{order_no}/decompose
/api/v1/commission/standards/{standard_code}/upgrade
/api/v1/commission/impacts/latest
/api/v1/cq-engine/generate
/api/v1/cq-engine/drafts
/api/v1/cq-engine/drafts/{draft_id}
/api/v1/commission/orders
/api/v1/commission/data-records
/api/v1/cq-engine/drafts/{draft_id}/publish
```

当前仍确认缺失：

```text
正式本体结构在线编辑接口
本体版本发布/回滚接口
CQ 草案正文在线编辑接口
```

已执行 Streamlit 页面探针，确认页面可渲染，并存在关键控件：

```text
初始化 / 重置 CO-2024-001
触发标准升级 V2
生成并保存草案
生成模式
```

## 需求完成度矩阵

| 编号 | 需求 | 测试条件 | 当前证据 | 结论 |
| --- | --- | --- | --- | --- |
| R1 | 新增独立 `commission-testing` 本体 | 本体可被发现、加载，并有独立图 IRI | `tests/test_ontology_registry.py`；全量测试通过 | 通过 |
| R2 | 客户能看到完整委托单流程 | 初始化 `CO-2024-001` 后能看到委托单、产品、试验项目、任务、测试项、结果 | API 探针返回 `task_count=2`、`record_count=2`、`result_count=2`；页面存在初始化按钮 | 演示级通过 |
| R3 | 1 个试验项目自动生成 1 个试验任务 | `P-001/P-002 -> T-001/T-002` | `/commission/orders/CO-2024-001/decompose` 返回两个任务 | 通过 |
| R4 | 执行测试并录入数据 | 每个任务有测试项和实测值，并按 V1 判定 | 固定 fixture 中有 `RCS_MEAN=0.042`、`BER=0.00021`，API 返回 V1 结果 | 演示级通过 |
| R5 | 系统自动判断合格/不合格 | `RCS_MEAN <= 0.05` 判 `Pass`，`BER <= 0.001` 判 `Pass` | `tests/test_commission_reasoning.py`、API flow | 通过 |
| R6 | 标准升级后自动重判历史数据 | V2 把 RCS 阈值从 `<=0.05` 收紧到 `<=0.035` | API 返回 `T-001: Pass -> Fail, NeedsReview`；`T-002` 不翻转 | 通过 |
| R7 | 旧结果、新结果和影响记录均可查询 | 重判后查询 latest impact | `/commission/impacts/latest` 与 upgrade 结果一致 | 通过 |
| R8 | CQ 反推 TBox/RBox 草案 | `template_only` 生成候选 CQ、类、关系、属性、规则、SPARQL 测试 | `tests/test_commission_cq_engine.py`；API draft flow | 通过 |
| R9 | CQ 可执行验收 | CQ Markdown 可解析，SPARQL 能在 Fuseki 上执行 | `tests/test_commission_cq_integration.py -q -rs`：`1 passed` | 通过 |
| R10 | LLM 生成做成开关 | 支持 `llm_only`、`llm_with_template_fallback`、`template_only` | 单元测试覆盖三种模式；页面有“生成模式”控件 | 通过 |
| R11 | LLM 不直接覆盖正式 OWL/Turtle | 生成结果保存为 `CQDraft` 草案 | draft API 保存/list/update，正式 ontology 文件未被生成流程覆盖 | 通过 |
| R12 | CQ 草案可维护、查询、修改 | 保存草案、查询草案、修改状态为 `reviewed`，并发布 reviewed 草案 | `/cq-engine/drafts`、`PATCH /drafts/{draft_id}`、`POST /drafts/{draft_id}/publish`；页面有生成保存和 reviewed 操作 | 通过 |
| R13 | 页面可以维护、查询、修改本体 | 本体页面能加载和查询，能维护/修改正式本体结构 | 当前有 ontology load/list/subjects 能力；没有正式本体编辑、版本发布、回滚 API | 未满足 |
| R14 | 新建任意委托单 | 用 API 创建非 `CO-2024-001` 委托单 | `POST /commission/orders` 已通过 TDD 覆盖；页面表单尚未接入 | 部分通过 |
| R15 | 任意试验任务录入新测试数据 | 用 API 录入新的 commission 测试数据记录并判定 | `POST /commission/data-records` 已通过 TDD 覆盖；页面录入表单尚未接入 | 部分通过 |
| R16 | CQ 草案发布/导出 | reviewed 草案发布为可导出的 Turtle/CQ/规则资产 | `POST /cq-engine/drafts/{draft_id}/publish` 已通过 TDD 覆盖；尚未写正式文件和版本历史 | 部分通过 |
| R17 | 客户演示与开发演示文档 | 客户讲、开发讲、傻瓜式操作、价值说明存在 | `docs/commission-cq-*` 与 `docs/系统演示操作手册.md` | 通过 |
| R18 | 前端不直接依赖 core | Streamlit tabs 只走 API 工具 | `tests/test_frontend_boundaries.py` | 通过 |

## 功能完成度判断

### 演示闭环完成度：高

当前系统已经能支撑客户演示主线：

```text
初始化委托单
  -> 自动分解任务
  -> 展示测试项和 V1 判定
  -> 发布 V2 标准
  -> 自动重判历史结果
  -> T-001 标记 NeedsReview
  -> CQ 工程台生成并保存草案
```

测试证据充分，核心链路不是静态页面硬编码。

### CQ 工程完成度：中高

已经具备：

- CQ Markdown 注册表
- CQ 解析和 Expected 校验
- SPARQL/Fuseki 集成回归
- LLM/template 三模式
- 草案保存、查询、状态修改
- reviewed 草案发布为导出包

尚缺：

- 草案正文在线编辑
- 发布导出结果写入正式文件或对象存储
- 发布后的版本和回滚记录

### 产品化 CRUD 完成度：中

当前已经从“固定剧本 + 可验证工程样机”推进到“具备基础 API 扩展点”，但还不是完整业务系统。

主要缺口：

- 页面还不能创建任意委托单。
- 页面还不能录入任意 commission 测试数据。
- 不能在线修改正式本体结构。
- 不能发布/回滚正式本体版本。

## 结论

如果验收目标是“给客户演示完整本体优势和 CQ 工程闭环”，当前系统可以判定为完成。

如果验收目标是“作为可配置、可维护、可录入的业务系统上线试点”，当前系统已经补齐基础 API，但仍需补齐页面表单、正式本体维护、发布文件落地和版本回滚。

本轮已按 TDD 补齐三个高优先级 API 缺口：

1. `POST /api/v1/commission/orders`：新建/更新委托单、产品、试验项目。
2. `POST /api/v1/commission/data-records`：录入任意测试数据并自动判定。
3. `POST /api/v1/cq-engine/drafts/{draft_id}/publish`：把 reviewed 草案发布为可导出的版本化资产。

建议下一轮继续按 TDD 补齐：

1. 委托单页面表单：创建/修改任意委托单、产品、试验项目和测试项。
2. 测试数据页面表单：选择任务和测试项后录入实测值。
3. CQ 草案编辑器：编辑草案 JSON/Markdown 后再 reviewed/publish。
4. 本体发布历史：记录发布版本、导出文件位置和回滚入口。
