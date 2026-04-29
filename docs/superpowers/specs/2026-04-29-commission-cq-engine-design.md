# 委托单试验 CQ 工程与新本体设计

日期：2026-04-29

## 背景

当前项目已经实现制造业试验数据管理本体 MVP，包含 FastAPI、Streamlit、Fuseki、Owlready2/Pellet、确定性测量判定、规格变更重算、受控 QA，以及第一批测量判定 CQ。现有能力证明了“测量值 + 规格 + 判定结果 + evidence 解释”的最小闭环，但客户演示仍偏向底层测量场景，尚不足以展示从业务流程出发，用 CQ 反推 TBox/RBox 并驱动本体扩展的工程过程。

本设计新增独立 `commission-testing` 本体，围绕委托单试验业务建立一条可运行演示链：

```text
新建委托单
  -> 自动任务分解
  -> 执行测试并录入实测值
  -> 按标准版本和通过条件自动判定
  -> 发布新标准版本
  -> 自动找出旧标准下的数据并重判
  -> 标记结论翻转任务为需复核
```

同时新增 CQ 工程台，用 LLM 或模板辅助生成候选 CQ、TBox、RBox、规则和 SPARQL 验收草案。LLM 输出只作为候选草案，必须经过人审、校验和发布动作后才进入正式资产。

## 已确认决策

1. 第一版新增独立 `commission-testing` 本体，保留现有 `manufacturing-trial`。
2. 第一版业务场景覆盖“委托单试验 + 测试判定 + 标准升级重判”，不扩展设备健康和外部导入。
3. 演示分为客户演示和开发演示两条线，但底层使用同一套 CQ、本体、规则和样例数据。
4. 第一版目标是可运行样机，而不是只生成文档草案。
5. 页面提供业务侧表单维护和开发侧源码草案查看/编辑。
6. LLM 生成做成开关，支持真实 LLM、真实 LLM 加模板降级、强制模板三种模式。
7. LLM 不直接修改正式 OWL/Turtle；页面维护草案，确认发布后导出 Markdown/Turtle/规则配置。
8. 数值判定继续由确定性规则完成，LLM 只辅助建模和解释候选结构。
9. 默认演示剧本内置 `CO-2024-001`，同时允许页面编辑委托单、产品、试验项目、阈值和实测值。

## 目标

- 客户能看到完整过程：委托单创建、任务分解、测试录入、标准升级、历史数据重判、任务需复核。
- 客户能理解本体优势：业务对象和关系是显式语义网络，标准升级影响可以自动追溯。
- 开发能看到 CQ 如何反推候选 TBox/RBox、规则、SPARQL 和测试。
- 系统能新增并加载 `commission-testing` 本体，不破坏现有本体。
- 系统能把 LLM/模板输出保存为可查询、可修改、可发布的 CQ 工程草案。
- 系统能导出 `commission-testing.ttl`、CQ Markdown、规则配置和 demo fixture。
- 验收测试能证明核心链路不是页面硬编码。

## 非目标

- 不做通用本体工程平台。
- 不支持任意行业、任意流程的自动建模。
- 不让 LLM 自由生成并直接覆盖正式本体。
- 不让 OWL/SWRL 承担第一版数值比较主判定。
- 不做权限、审批流、多用户协同和审计日志。
- 不做 Excel、API 或第三方系统导入。

## 客户演示设计

客户演示入口放在“客户讲”中，新增“委托单试验演示”主线。演示重点不是 RDF/OWL 术语，而是业务闭环。

### 1. 新建委托单

默认剧本：

| 字段 | 值 |
| --- | --- |
| 委托单 | `CO-2024-001` |
| 委托人 | `李工` |
| 产品 | `相控阵雷达导引头` |
| 型号 | `X-01` |
| 试验项目 1 | `高低温振动试验` |
| 试验项目 2 | `电磁兼容试验` |

页面允许编辑这些字段。客户看到的是一张需求申请表，开发侧对应 `CommissionOrder`、`Product`、`TestProject`。

### 2. 自动任务分解

规则：

```text
1 个 TestProject = 1 个 TestTask
```

默认生成：

| 试验项目 | 试验任务 |
| --- | --- |
| 高低温振动试验 | `T-001` |
| 电磁兼容试验 | `T-002` |

页面展示业务动作“生成试验任务”。开发侧展示 `hasTestProject`、`decomposesToTask`、`taskForProject` 等关系。

### 3. 执行测试并录入数据

默认测试数据：

| 任务 | 测试项 | 实测值 | 旧标准条件 | 旧判定 |
| --- | --- | --- | --- | --- |
| `T-001` | `RCS均值` | `0.042 m²` | `<= 0.05` | `Pass` |
| `T-002` | `误码率` | `0.00021` | `<= 0.001` | `Pass` |

页面明确说明：合格/不合格由 `PassCriterion` 和确定性规则计算，LLM 不参与裁决。

### 4. 展示 LLM 辅助 CQ 反推

客户侧只展示可理解结果，不展示完整技术细节：

- 业务问题被转成 CQ。
- CQ 反推需要哪些类、关系、属性和规则。
- 专家确认后进入系统。

示例 CQ：

- 标准升级后，哪些历史测试结论发生翻转？
- `T-001` 为什么从合格变成需复核？
- 这个判定使用了哪个标准版本和通过条件？

页面显示 LLM 开关：

- `llm_only`：必须真实 LLM 成功。
- `llm_with_template_fallback`：优先真实 LLM，失败时自动模板生成。
- `template_only`：强制模板生成，保证演示稳定。

### 5. 标准升级

发布新标准：

| 字段 | 旧值 | 新值 |
| --- | --- | --- |
| 标准 | `GJB-7821-2024-V1` | `GJB-7821-2024-V2` |
| RCS 阈值 | `<= 0.05` | `<= 0.035` |
| 误码率阈值 | `<= 0.001` | `<= 0.001` |

系统自动查找使用旧标准的历史测试数据，用新标准重新计算。

### 6. 影响追溯

重判结果：

| 测试项 | 实测值 | 旧判定 | 新判定 | 影响 |
| --- | --- | --- | --- | --- |
| RCS均值 | `0.042 m²` | `Pass` | `Fail` | `T-001` 标记 `NeedsReview` |
| 误码率 | `0.00021` | `Pass` | `Pass` | 无翻转 |

客户演示收束点：

- 标准、判据、任务、数据、结果之间有显式语义关系。
- 标准升级后系统能自动定位历史影响。
- 结论翻转不是覆盖旧结果，而是生成可追溯的新结果和影响记录。

## 开发演示设计

开发演示入口放在“技术讲”中，新增“CQ 工程台”和“委托单本体”视图。

开发演示证明以下事实：

1. 客户页不是静态剧本，底层有 `commission-testing` 本体和 ABox 数据。
2. CQ 草案可维护、可查询、可修改。
3. TBox/RBox 候选项能追溯到 CQ 和业务输入。
4. Turtle、SPARQL、规则配置和测试报告可导出。
5. 标准升级重判由确定性 core 完成，结果写回图谱。

## TBox 第一版

| 类名 | 中文名 | 说明 | 示例 |
| --- | --- | --- | --- |
| `CommissionOrder` | 委托单 | 一张需求申请表 | `CO-2024-001` |
| `Product` | 产品 | 被测试的实物 | 相控阵雷达导引头 |
| `TestProject` | 试验项目 | 要做的大项测试 | 高低温振动试验 |
| `TestTask` | 试验任务 | 分解后的执行任务 | `T-001` |
| `TestItem` | 测试项 | 具体测试指标 | RCS均值、误码率 |
| `TestDataRecord` | 测试数据记录 | 实测值与判定事实 | `0.042 m² -> Pass` |
| `PassCriterion` | 通过条件 | 合格线、比较符和单位 | `<= 0.05` |
| `StandardVersion` | 标准版本 | 标准版本号和生效时间 | `GJB-7821-2024-V2` |
| `JudgementResult` | 判定结果 | 某条数据在某标准下的结论 | `Pass`、`Fail` |
| `ReevaluationImpact` | 重判影响 | 标准升级后的影响记录 | `Pass -> Fail` |

## RBox 第一版

| 关系 | Domain | Range | 说明 |
| --- | --- | --- | --- |
| `hasProduct` | `CommissionOrder` | `Product` | 委托单对应产品 |
| `hasTestProject` | `CommissionOrder` | `TestProject` | 委托单包含试验项目 |
| `decomposesToTask` | `TestProject` | `TestTask` | 试验项目分解为任务 |
| `taskForProject` | `TestTask` | `TestProject` | 任务来源项目 |
| `hasTestItem` | `TestTask` | `TestItem` | 任务包含测试项 |
| `recordsData` | `TestItem` | `TestDataRecord` | 测试项产生数据记录 |
| `hasJudgementResult` | `TestDataRecord` | `JudgementResult` | 数据记录对应判定结果 |
| `evaluatedAgainstCriterion` | `JudgementResult` | `PassCriterion` | 判定使用的通过条件 |
| `criterionInStandard` | `PassCriterion` | `StandardVersion` | 通过条件属于哪个标准版本 |
| `supersedesStandard` | `StandardVersion` | `StandardVersion` | 新标准替代旧标准 |
| `previousResult` | `ReevaluationImpact` | `JudgementResult` | 重判前结果 |
| `newResult` | `ReevaluationImpact` | `JudgementResult` | 重判后结果 |
| `impactsTask` | `ReevaluationImpact` | `TestTask` | 重判影响哪个任务 |

## 关键数据属性

| 属性 | Domain | 类型 | 说明 |
| --- | --- | --- | --- |
| `localId` | 多类 | `xsd:string` | 业务 ID |
| `orderNo` | `CommissionOrder` | `xsd:string` | 委托单编号 |
| `requester` | `CommissionOrder` | `xsd:string` | 委托人 |
| `productModel` | `Product` | `xsd:string` | 产品型号 |
| `taskStatus` | `TestTask` | `xsd:string` | `Pending`、`Completed`、`NeedsReview` |
| `itemCode` | `TestItem` | `xsd:string` | 测试项编码 |
| `measuredValue` | `TestDataRecord` | `xsd:decimal` | 实测值 |
| `unit` | `TestItem` / `PassCriterion` | `xsd:string` | 单位 |
| `operator` | `PassCriterion` | `xsd:string` | 比较符，例如 `<=` |
| `threshold` | `PassCriterion` | `xsd:decimal` | 阈值 |
| `standardCode` | `StandardVersion` | `xsd:string` | 标准编号 |
| `standardVersion` | `StandardVersion` | `xsd:string` | 版本号 |
| `effectiveFrom` | `StandardVersion` | `xsd:dateTime` | 生效时间 |
| `resultStatus` | `JudgementResult` | `xsd:string` | `Pass` / `Fail` |
| `resultReason` | `JudgementResult` | `xsd:string` | 判定说明 |
| `judgedAt` | `JudgementResult` | `xsd:dateTime` | 判定时间 |
| `flipped` | `ReevaluationImpact` | `xsd:boolean` | 结论是否翻转 |

## CQ 第一版

客户可讲 CQ：

| CQ | 业务问题 | 覆盖 |
| --- | --- | --- |
| `CQ-CT-001` | 委托单 `CO-2024-001` 包含哪些试验项目？ | `CommissionOrder`、`TestProject` |
| `CQ-CT-002` | 每个试验项目是否都被分解成一个试验任务？ | `TestProject`、`TestTask` |
| `CQ-CT-003` | `T-001` 的 RCS 均值为什么判定为合格？ | `TestDataRecord`、`PassCriterion`、`JudgementResult` |
| `CQ-CT-004` | 标准从 `V1` 升级到 `V2` 后，哪些历史测试结论发生翻转？ | `StandardVersion`、`ReevaluationImpact` |
| `CQ-CT-005` | 为什么 `T-001` 被标记为需复核？ | `TestTask`、`ReevaluationImpact` |

开发验收 CQ：

- CQ 必须能查到 `CommissionOrder -> Product -> TestProject -> TestTask` 链。
- 每条 `TestDataRecord` 必须绑定 `TestItem`、`PassCriterion`、`StandardVersion` 和 `JudgementResult`。
- 标准升级后不能覆盖旧结果，必须保留旧结果、新结果和影响记录。
- 结论翻转时相关 `TestTask.taskStatus` 必须变为 `NeedsReview`。
- LLM 或模板生成的候选类、关系和规则必须保留来源追溯。

CQ Markdown 每条记录必须包含：

- `Business question`
- `Intent`
- `Source`
- `Covers`
- `Demo data`
- `Expected`
- 一个 `sparql` 代码块
- `Evidence fields`
- `Generated by`
- `Human review status`
- `Acceptance`

## LLM 辅助生成设计

### 输入

页面输入：

- 业务流程描述。
- 术语表。
- 默认样例数据。
- 标准升级说明。
- 生成模式。

### 生成模式

| 模式 | 行为 | 用途 |
| --- | --- | --- |
| `llm_only` | 真实 LLM 不可用则失败 | 开发展示真实模型调用 |
| `llm_with_template_fallback` | 先调真实 LLM，失败后模板生成 | 默认演示模式 |
| `template_only` | 不调 LLM，直接模板生成 | 现场稳定兜底 |

### 输出结构

```json
{
  "candidate_cqs": [],
  "candidate_classes": [],
  "candidate_relations": [],
  "candidate_properties": [],
  "candidate_rules": [],
  "draft_turtle": "",
  "draft_sparql_tests": [],
  "source_trace": []
}
```

`source_trace` 必须记录：

- 来源业务输入片段。
- 来源 CQ。
- 生成模式。
- LLM provider 或模板名称。
- 人审状态。

### 人审和发布

候选草案状态：

```text
draft -> reviewed -> published -> rejected
```

发布动作导出文件，但不在生成阶段直接覆盖正式 OWL：

- `mvp/ontology/commission-testing.ttl`
- `docs/cq/commission-testing-cqs.md`
- `mvp/rules/commission-testing.yml`
- `mvp/data/commission-testing-demo.json`

## Core 模块设计

新增模块建议：

```text
mvp/core/commission_graph.py
mvp/core/commission_reasoning.py
mvp/core/cq_engine.py
mvp/core/ontology_draft.py
```

职责：

- `commission_graph.py`：委托单领域图谱读写，管理 order/product/project/task/item/data/result/impact。
- `commission_reasoning.py`：任务分解、数据判定、标准升级重判、任务状态翻转。
- `cq_engine.py`：CQ 草案、来源、状态、发布和导出。
- `ontology_draft.py`：LLM/模板输出解析为候选 TBox/RBox/规则/SPARQL。

边界原则：

- API 层只做请求适配，不写领域推理逻辑。
- Streamlit 只调用 API，不直接读写 core。
- LLM 输出不直接进入正式本体。
- 标准升级重判必须保留历史结果，不覆盖旧结果。

## API 设计

新增 `/api/v1` 路由：

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `POST` | `/cq-engine/generate` | 根据业务输入生成候选 CQ/TBox/RBox/规则 |
| `GET` | `/cq-engine/drafts` | 查询草案列表 |
| `POST` | `/cq-engine/drafts` | 保存草案 |
| `PATCH` | `/cq-engine/drafts/{draft_id}` | 修改草案或人审状态 |
| `POST` | `/cq-engine/drafts/{draft_id}/publish` | 发布并导出文件 |
| `POST` | `/commission/demo/reset` | 初始化可编辑演示剧本 |
| `POST` | `/commission/orders` | 新建或更新委托单 |
| `POST` | `/commission/orders/{order_no}/decompose` | 自动任务分解 |
| `POST` | `/commission/data-records` | 录入测试数据并判定 |
| `POST` | `/commission/standards/{standard_code}/upgrade` | 发布新标准并重判历史 |
| `GET` | `/commission/impacts/latest` | 查询最近影响报告 |

## 前端设计

客户讲新增：

- `委托单全流程`
- `标准升级影响追溯`
- `本体优势总结`

技术讲新增：

- `CQ 工程台`
- `TBox/RBox 草案`
- `ABox 样例数据`
- `SPARQL 验收`
- `导出文件`

业务侧使用表单维护：

- 委托单。
- 产品。
- 试验项目。
- 测试项。
- 标准版本。
- 判据。
- 实测值。

开发侧展示和编辑草案：

- CQ Markdown。
- Turtle 草案。
- SPARQL 验证草案。
- 规则配置。
- 测试报告。

## 规则配置

第一版规则配置示例：

```yaml
rules:
  - id: decompose_project_to_task
    description: 1 个试验项目生成 1 个试验任务
    when: test_project_exists_under_order
    then: create_test_task

  - id: judge_less_equal_threshold
    description: 实测值小于等于阈值时通过
    when: measured_value <= threshold
    then: Pass

  - id: judge_greater_than_threshold
    description: 实测值大于阈值时不通过
    when: measured_value > threshold
    then: Fail

  - id: mark_task_needs_review_on_flip
    description: 标准升级导致结论翻转时标记任务需复核
    when: old_status != new_status
    then: taskStatus = NeedsReview
```

## 验收测试

解析测试：

- `commission-testing` CQ Markdown 可解析。
- CQ ID 唯一。
- 必填字段完整。
- SPARQL 块数量正确。
- Expected 断言格式受支持。

Core 测试：

- 委托单可创建并绑定产品。
- 两个试验项目可自动分解为两个任务。
- RCS `0.042 <= 0.05` 在 V1 下判定 `Pass`。
- RCS `0.042 > 0.035` 在 V2 下重判 `Fail`。
- 误码率阈值未变时重判仍为 `Pass`。
- RCS 结论翻转后 `T-001.taskStatus = NeedsReview`。
- 旧结果、新结果和影响记录同时存在。

集成测试：

- Fuseki 可用时初始化 demo ABox。
- CQ SPARQL 能查到委托单、产品、项目、任务链。
- CQ SPARQL 能查到判据、标准版本和判定结果。
- 标准升级后 CQ 能查到翻转影响和需复核任务。

前端边界测试：

- 客户页和技术页只调用 API。
- 页面不直接导入或调用 core 模块。
- LLM 不可用时 `llm_with_template_fallback` 返回模板草案。
- `template_only` 模式不触发 provider 调用。

## 分期实施

### P1：commission-testing 可运行主线

- 新增本体。
- 新增领域 core。
- 新增规则配置。
- 新增固定和可编辑 demo 数据。
- 跑通委托单、任务分解、数据判定、标准升级重判、任务需复核。

### P2：CQ 工程台

- 新增 CQ 草案结构。
- 新增 LLM/模板生成开关。
- 新增草案维护和发布导出。
- 第一版只支持本委托单试验领域。

### P3：双层页面

- 客户页展示完整业务过程和本体优势。
- 技术页展示 CQ、TBox/RBox、Turtle/SPARQL、规则配置和测试报告。
- 页面支持维护、查询和修改草案。

### P4：验收与文档

- 新增 CQ Markdown。
- 新增 parser/core/integration/UI 边界测试。
- 更新演示手册。
- 文档分为客户演示和开发演示两部分。

## 风险控制

- 新本体独立，避免破坏现有 `manufacturing-trial`。
- LLM 仅生成候选草案，不直接改正式 OWL。
- 真实 LLM 失败时有模板降级。
- 数值判定由确定性规则执行。
- 标准升级保留旧结果，不覆盖历史。
- 第一版不扩展设备健康和外部导入，控制范围。
- 发布动作前必须经过校验和人审状态检查。

## 验收标准

第一版完成时必须满足：

- `commission-testing` 出现在本体列表中，并能加载。
- 客户页能完成委托单到标准升级重判的完整演示。
- 技术页能展示 CQ 反推 TBox/RBox、规则和 SPARQL 草案。
- LLM 开关三种模式可用。
- 模板降级可以在无 LLM 环境下完成演示。
- RCS 标准升级后产生 `Pass -> Fail` 翻转。
- `T-001` 被标记为 `NeedsReview`。
- 旧结果、新结果和影响记录均可查询。
- CQ 测试能验证委托单链路、判定链路和标准升级影响链路。
