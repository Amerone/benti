# CQ 驱动测量判定闭环设计

日期：2026-04-27

## 背景

当前项目已经实现制造业试验数据管理本体 MVP，包含 FastAPI、Streamlit、Fuseki、Owlready2/Pellet、确定性测量判定和受控 QA。现有 QA 已支持 `why_fail`、`spec_change_impact`、`parameter_or_batch_summary` 三类白名单模板，但 CQ（competency questions，胜任力问题）还没有成为本体建模和验收的一等资产。

本设计把 CQ 定位为“本体需求、图谱查询、推理证据、QA 解释、自动验收”之间的核心连接物。第一版只覆盖测量判定闭环，避免扩大到自由问答或完整 CQ 治理平台。

参考依据：

- `mvp/core/qa.py`：现有受控 QA 模板和 evidence 约束。
- `plan/framework-design.md`：现有图划分、QA 边界和验收约定。
- `docs/ontology-wiki/14-enterprise-validation-playbook.md`：企业级验证中将 competency questions 作为业务语义验证交付物。
- Stanford Protégé Ontology Development 101：本体范围应由本体需要回答的问题驱动。
- Journal of Web Semantics CQ 论文：CQ 是约束本体知识范围的自然语言需求，并应能转化为查询或验证。

## 已确认决策

1. CQ 的第一角色是本体建模与验收的核心需求资产。
2. 第一批 CQ 只覆盖测量判定闭环。
3. CQ 必须是机器可执行注册表，而不是只做人审的文档。
4. CQ 源文件采用业务/本体评审可维护的 Markdown。
5. CQ 验证优先跑真实 Fuseki/SPARQL 集成环境。
6. CQ runner 自动初始化固定 demo 数据，不依赖 Fuseki 残留状态。
7. 第一版采用“Markdown + 专用 runner + pytest 集成”方案。

## 目标

第一版交付后，项目应具备以下能力：

- 业务人员可以阅读并评审 CQ Markdown。
- 开发测试可以从同一份 CQ Markdown 解析出 SPARQL、期望结果和 evidence 字段。
- CQ runner 可以自动准备固定 demo 数据，执行真实 Fuseki SPARQL，并校验结果。
- QA 的 `why_fail` evidence 与 CQ SPARQL 返回字段保持一致。
- 后续新增 CQ 时，必须同时写清业务问题、SPARQL 和验收断言，避免文档与测试漂移。

## 非目标

第一版不做以下事项：

- 不把 CQ 同步为 RDF/Turtle 个体。
- 不支持自由自然语言问答。
- 不把 Markdown 设计成复杂 DSL。
- 不清空整个 Fuseki dataset。
- 不覆盖规格变更影响 CQ；该类 CQ 留到第二批，因为它依赖 Result 替代链和 impact 数据。

## CQ 文档

新增业务源文件：

```text
docs/cq/measurement-judgement-cqs.md
```

每条 CQ 使用固定 Markdown 结构：

````md
## CQ-MJ-001 某测量为什么 Fail_High？

- Business question: M007 为什么 Fail？
- Intent: why_fail
- Covers: Measurement, Specification, Result
- Demo data: M007, temperature=197.2, Spec_v1 upper=195
- Expected: row_count=1, status=Fail_High, rule=Rule_Fail_High, deviation=2.2

```sparql
SELECT ...
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M007 为什么 Fail？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields
````

第一批 CQ：

- `CQ-MJ-001`：M007 高于上限，为什么 `Fail_High`。
- `CQ-MJ-002`：M008 低于下限，为什么 `Fail_Low`。
- `CQ-MJ-003`：M009 在规格范围内，为什么 `Pass`。

## Markdown 解析契约

每条 CQ 必须包含：

- 二级标题：`## CQ-MJ-001 标题`
- `Business question`
- `Intent`
- `Covers`
- `Demo data`
- `Expected`
- 一个且仅一个 `sparql` fenced code block
- `Evidence fields`
- `Linked QA example`
- `Acceptance`

解析规则：

- 标题中的 `CQ-MJ-001` 是唯一 ID，重复时报错。
- 元数据行必须是 `- Key: value`。
- 缺失必填字段时报错，并指出 CQ ID 和字段名。
- `Expected` 第一版只支持简单断言：`row_count=1`、`status=...`、`rule=...`、`spec_version=...`、`deviation=...`。
- `Evidence fields` 使用逗号分隔字段名。
- `Demo data` 不解析为复杂 DSL；第一版按 CQ ID 使用固定 fixture。

## Runner 设计

新增模块：

```text
mvp/core/cq.py
```

核心职责：

- 读取 `docs/cq/measurement-judgement-cqs.md`。
- 解析 CQ ID、元数据、SPARQL、expected 断言和 evidence 字段。
- 初始化 CQ 固定 demo 数据到真实 Fuseki。
- 执行 CQ SPARQL。
- 校验 SPARQL 返回行数和 expected 断言。
- 校验 linked QA example 的 evidence 字段与 SPARQL 返回一致。

建议核心对象：

```text
CompetencyQuestion
  id
  title
  metadata
  sparql
  expected
  evidence_fields

CQParseError
CQRunner
```

## 数据初始化

CQ runner 每次执行都创建可重复数据基线。

执行顺序：

```text
1. load_ontologies(reload=true)
   只覆盖 ontology graph，不碰 data/result/spec graph

2. 清理 CQ 专用 demo 数据
   删除 M007/M008/M009、temperature、Spec_v1 及相关 Result

3. 写入参数和规格
   parameter=temperature
   Spec_v1 lower=180 upper=195

4. 写入三条测量
   M007 temperature=197.2 -> Fail_High
   M008 temperature=179.1 -> Fail_Low
   M009 temperature=188.0 -> Pass

5. 调用 inference.run_inference()
   生成 Result 和 evidence 字段
```

图契约：

- Measurement 写入 data graph。
- Specification 写入 spec graph。
- Result 写入 result graph。
- CQ SPARQL 必须显式查询 named graph。
- 不允许依赖默认图。

统一 evidence 字段：

```text
measurement_id
value
status
rule
spec_version
lower_limit
upper_limit
deviation
reasoner
inferred_at
```

如果现有仓储不支持精确删除 CQ fixture，新增一个 CQ 专用 reset 方法，只删除 CQ runner 负责的固定数据范围，不清空整个 graph。

## 执行流程

```text
pytest 启动 CQ 集成测试
  -> CQ runner 读取 Markdown
  -> graph.load_ontologies(reload=true)
  -> 清理并写入 CQ fixture
  -> inference.run_inference()
  -> 执行 CQ SPARQL
  -> 校验 expected assertion
  -> 调用 qa.answer() 或 /api/v1/qa
  -> 校验 QA evidence 与 CQ SPARQL 返回一致
```

第一版可以直接调用 `qa.answer()`，避免 API 网络栈干扰 CQ 语义验证。后续可增加 `/api/v1/qa` 的端到端覆盖。

## 错误处理

- Markdown 结构错误：抛出 `CQParseError`，包含 CQ ID、字段名和原因。
- CQ ID 重复：解析失败。
- SPARQL 缺失或多个代码块：解析失败。
- Fuseki 不可用：集成测试 `pytest.skip`，skip 原因提示先运行 `docker compose up -d`。
- SPARQL 返回 0 行：测试失败，提示检查 fixture、named graph IRI 或查询模板。
- SPARQL 返回多行但 `row_count=1`：测试失败，提示数据污染或查询条件过宽。
- QA evidence 缺字段：测试失败，提示 `qa.py`、adapter 或图写入契约漂移。

## 测试设计

新增解析测试：

```text
tests/test_cq_parser.py
```

覆盖：

- CQ 文档可解析。
- CQ ID 唯一。
- 必填字段完整。
- SPARQL 代码块数量正确。
- Expected 断言格式受支持。

新增集成测试：

```text
tests/test_cq_integration.py
```

覆盖：

- Fuseki 可用时自动初始化 demo 数据。
- 三条 CQ 的 SPARQL 均返回 `row_count=1`。
- `CQ-MJ-001` 返回 `Fail_High / Rule_Fail_High / deviation=2.2`。
- `CQ-MJ-002` 返回 `Fail_Low / Rule_Fail_Low / deviation=0.9`。
- `CQ-MJ-003` 返回 `Pass / Rule_Pass / deviation=0.0`。
- linked QA example 的 `intent=why_fail`。
- QA evidence 包含 CQ 声明的全部 evidence fields。
- QA evidence 的关键值与 CQ SPARQL 行一致。

验证命令：

```powershell
python -m pytest tests/test_cq_parser.py -q
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

## 文档更新

README 或操作手册需要补充：

- CQ 是什么。
- CQ 文件在哪里维护。
- 如何新增 CQ。
- 如何运行 CQ parser 测试。
- 如何启动 Fuseki 并运行 CQ 集成测试。

## 验收标准

第一版完成时必须满足：

- `docs/cq/measurement-judgement-cqs.md` 存在并包含三条基础 CQ。
- `tests/test_cq_parser.py` 稳定通过。
- Fuseki 可用时 `tests/test_cq_integration.py` 通过。
- Fuseki 不可用时 CQ 集成测试明确 skip，不影响普通单测。
- QA evidence 与 CQ SPARQL 字段一致。
- 文档说明新增 CQ 时必须包含可执行 SPARQL 和 expected 断言。

## 后续扩展

第二批可以加入：

- 规格变更影响 CQ。
- Result 替代链 CQ。
- 参数注册后是否参与判定的 CQ。
- CQ 同步为 RDF 个体，进入单独 validation graph。
- CQ coverage 报告：哪些类、属性、规则、QA intent 已被 CQ 覆盖。
