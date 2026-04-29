# 公司怎么从"Java Spring + Form/Table"转向"本体 + Python":一份转型实操手册

> 前置阅读：
> - `本体论与军工制造-项目叙事.md`（叙事与方法论）
> - `ontology-palantir-defense-narrative.md`（Palantir 路线与军工映射）
> - `docs/cq/cq-beginner-guide.md`（CQ 入门）
>
> 本文不再讲"为什么要做本体",而是回答一个非常落地的问题：
> **如果我们公司决定把现有 Java Spring + 增删改查表单的产品，
> 改造成"本体 + Python"路线，组织里每个人具体要怎么变？**

---

## 0. 先把判断结论说出来

**这不是一次技术选型替换，而是一次"业务表达方式"的替换。**

- Spring Boot 不会被"替换"——它会被**降级**为：底层数据落库、对接老系统的网关、对接外部接口的 facade。
- Python（FastAPI / Owlready2 / Fuseki / LLM）也不是"替代 Java"——它承担的是**新出现的一层**：业务语义层、推理层、Agent 工具层。
- 真正被替换的，是**思维方式**：
  - 从"做一个新功能 = 加一张表 + 加 CRUD + 加表单"，
  - 变成"加一个业务能力 = 加一组 CQ + 扩本体 + 加 Action Type + UI 围绕对象生成"。

公司能不能转型成功，60% 取决于产品经理愿不愿意改思维，30% 取决于程序员愿不愿意放下"我先建表"，10% 才是技术栈本身。

---

## 1. 旧世界 vs 新世界：一张总览表

| 维度 | 旧世界（Java Spring + Form/Table） | 新世界（本体 + Python + Agent） |
|---|---|---|
| 需求载体 | PRD + 原型图 + 字段清单 | **CQ 注册表** + 业务对象草图 + Action 草图 |
| 建模起点 | ER 图 / 数据库表 | TBox（类、关系、约束） |
| 业务规则的位置 | 散在 Service、SQL、if-else、流程引擎 | 显式挂在 Object / Action / Function 上 |
| "字段"概念 | 表的列 | 对象的 Property，带单位、来源、版本 |
| "流程"概念 | 状态机 + 工作流引擎 | Action Type（带前置校验、副作用、审计） |
| UI 主体 | Form / Table / 增删改查 | **Object View**（围绕一个对象呈现其上下文、关系、动作、解释） |
| 验收方式 | 测试用例 + 手工点击 | **CQ 自动跑通**（SPARQL + Evidence + QA 一致） |
| 变更影响分析 | 靠开发人脑 + 接口文档 | 沿对象关系和规则版本机器算出 |
| AI 能做什么 | 充其量是 Copilot | 在窄工具 + 受控动作 + Evidence 约束下，充当业务面的入口 |
| 复用方式 | 复制代码、改字段 | 复用对象、复用 Action、复用 CQ 模板 |
| 知识沉淀 | 留在老员工脑子里 + Wiki 文档 | **沉淀进本体、Action、CQ、规则版本** |

---

## 2. 产品经理：思维需要转的三道弯

产品经理是这次转型里**变化最剧烈**的角色。
原来的 PM 思维基本是：
"用户要做 X → 设计一个表单 → 提交到一张表 → 提供一个列表查询。"
这套思维在本体路线下会**直接撞墙**。

### 第一道弯：从"画原型"到"先问问题"（CQ-First）

旧 PM 习惯：开会拿到需求，第一反应是打开 Figma / Axure 画一个表单。
新 PM 习惯：开会拿到需求，第一反应是写下：

> "这个系统将来要能回答哪些业务问题？"

这就是 CQ（Competency Question）。一个合格的 CQ 长这样：

```text
CQ-XX-001
- Business question: 某型号 T2024-03 批次的振动测量为什么 Fail？
- Intent: why_fail
- Source: 2026-04 工艺组评审会议纪要
- Priority: P0（涉及放行决定）
- Type: 推理判断
- Demo data: M0117, vibration=8.2g, Spec_v3 上限=7.5g
- Expected: status=Fail_High, rule=Rule_Fail_High, spec_version=Spec_v3
- Acceptance: SPARQL 返回 1 行 ∧ QA evidence 包含 6 个字段
```

PM 不需要写 SPARQL，但**必须能写到 `Acceptance` 这一行**，
也就是必须想清楚："这个需求做完，我看到什么算做完？"

> 旧 PM 写 PRD 是给开发看；
> 新 PM 写 CQ 是给**机器**看——CQ 是会被自动跑、自动回归的契约。

### 第二道弯：从"画表单"到"画对象 + 动作"

旧需求："新增一个'放行申请'表单，包含 12 个字段，提交后写入 release_request 表。"
新需求要拆成两个文档：

1. **对象草图（Object Sketch）**
   ```
   ReleaseRequest
     - 关联到: Batch, Trial, ResponsiblePerson
     - 属性: requestedAt, scope, riskLevel, attachedEvidence[]
     - 状态: Drafted | Submitted | UnderReview | Approved | Rejected
     - 不变量: scope ∈ {型号, 批次, 单件}
   ```

2. **动作草图（Action Sketch）**
   ```
   Action: SubmitReleaseRequest
     - 输入: batch_id, scope, evidence_refs
     - 前置校验:
        * batch 的全部 Critical 测量必须都有 Result
        * 没有任何 Result 处于 Fail_High 且未走偏差流程
     - 副作用: ReleaseRequest 状态 → Submitted, 触发审批
     - 审计: 谁、何时、引用了哪些 Evidence
   ```

**注意：旧 PM 习惯把"前置校验"留给开发猜或者写在备注里。
新 PM 必须把它写出来——因为它会被翻译成 SHACL 约束 + Action 的前置规则，是本体的一部分。**

### 第三道弯：从"列表 + 详情"到"围绕对象的工作面"

这是 UI 思维的根本性变化（详见第 5 节）。
PM 要意识到：**用户不是来"填表"的，是来"操作业务对象"的**。
所以未来的 PM 在 Figma 上画的不再是"录入页/列表页/详情页"三件套，
而是**Object View**：一个对象 + 它的上下文 + 它的关系 + 它能被执行的动作 + 它的解释。

### PM 转型的"三件套交付物"

旧交付物：PRD + 原型 + 字段清单。
新交付物：

| 文档 | 写什么 | 给谁 |
|---|---|---|
| CQ 注册条目 | 这次需求要让系统能回答的问题 | 测试 / 本体工程师 / 业务复核 |
| 对象与动作草图 | 涉及哪些对象、哪些 Action、约束是什么 | 本体工程师 / 后端 |
| Object View 草图 | 用户在哪个对象上工作、看到什么、能做什么 | 前端 / 设计 |

### 频繁需求变更怎么办？（PM 最关心的痛点）

这是本体路线最有威力的地方。处理逻辑分四类：

1. **改"上下限/阈值/规则参数"** → 改 `Specification` 实例 + 版本号，**完全不用改代码**，历史数据自动重算。
2. **改"判定逻辑"**（如增加一个判 Fail 的条件）→ 加一个 `Rule`，旧规则保留版本号，CQ 增加测试条目。**不破坏旧结论**。
3. **加一个新参数 / 新指标** → `Parameter` 动态注册，**不改表、不停机**。
4. **加一个全新场景**（比如新型号、新工艺） → 走 CQ 工厂 → 骨架提取 → 验证闭环 → 增量扩展（截图四阶段）。

> 旧世界："改个上限要排期 2 周。"
> 新世界："改个上限是录入一条新规格版本，5 分钟生效，历史结论自动给出影响清单。"
>
> **这是产品经理向业务方汇报时最值钱的一句话。**

---

## 3. 程序员：从"建表写 Service"到"建模写规则"

### 3.1 旧岗位 vs 新岗位的对照

| 旧角色 | 新角色 | 核心动作 |
|---|---|---|
| Java 后端 | **领域工程师 / 本体工程师** | 维护 TBox、Action、Function、CQ |
| 前端 | **Object View 工程师** | 围绕对象渲染上下文、关系、动作、证据 |
| DBA | **图谱与版本管理员** | 管 named graph、规格版本、推理图、审计图 |
| 测试 | **CQ 工程师** | 把业务验收翻译成可自动跑的 CQ |
| 架构师 | **本体架构师 / FDE** | 决定哪些是 Object，哪些是 Property，哪些是 Action |
| 算法 / AI | **Agent 工具工程师** | 把 LLM 钉死在窄工具上、做意图识别和 Evidence 解释 |

### 3.2 程序员手上代码风格的变化

**旧代码**（典型 Spring）：
```java
@PostMapping("/measurements")
public Long create(@RequestBody MeasurementDTO dto) {
    Measurement m = mapper.toEntity(dto);
    measurementRepo.save(m);
    if (m.getValue() > spec.getUpper()) {
        m.setStatus("FAIL_HIGH");
    }
    measurementRepo.save(m);
    return m.getId();
}
```

业务规则、写操作、副作用、状态变更全部混在一起，规则口径只在这一处。

**新代码**（本体 + Python）：
```python
# core/actions.py
def record_measurement(action_input: RecordMeasurementInput) -> ActionResult:
    # 1. 写入 ABox（事实）
    measurement_iri = graph.write_measurement(action_input)
    # 2. 触发确定性判定（规则集中在 inference.py，带版本号）
    result = inference.judge(measurement_iri)
    # 3. 写回 result graph（推理链）
    graph.write_result(result, evidence=result.evidence)
    # 4. 审计
    audit.log(action="record_measurement", input=action_input, output=result)
    return ActionResult(measurement_iri, result)
```

判定逻辑不在这里，在 `inference.py`。规格版本在 `Specification` 实例上。
Action 的前置约束在 SHACL 里。审计是统一中间件。
**每个文件只做一件事，规则只有一处，证据自动落档。**

### 3.3 不再做、新要做、必须保留的能力

| 旧能力 | 是否保留 | 说明 |
|---|---|---|
| Spring MVC、Mybatis、JPA | **保留** | 老系统集成、外部接口对接、与 ERP/MES/PDM 的桥 |
| 写 Service 处理一个 Form | **大量减少** | UI 不再走 Form，写操作走 Action |
| 写 if-else 业务规则 | **不再做** | 规则提升为 Function / Rule / 公理 |
| 设计 ER 图、加表加列 | **大幅减少** | 加属性走 TBox / Parameter 注册，不动表结构 |
| 写 SQL | **保留但下沉** | 只用来对接老系统数据；业务查询走 SPARQL |
| 写 SPARQL / SHACL | **新要做** | 取代很多原本写在 Service 里的查询 + 校验 |
| 写 OWL / 公理 | **新要做** | 但用 Protégé / 模板化生成，不用手写 RDF |
| 设计 Action Type | **新要做** | 这是新的"接口设计"，含输入、约束、副作用、审计 |
| 写 CQ + 自动测试 | **新要做** | 取代相当一部分集成测试 |
| 与 LLM 交互（Prompt、工具） | **新要做** | 但只能写"窄工具"，不能写自由 SQL |

### 3.4 新人上手路径建议

给新加入的程序员的 30 天路径：

1. **第 1 周**：理解 TBox/ABox、读完 `manufacturing-trial.ttl`，能讲清 6 个核心对象。
2. **第 2 周**：跑通一个 CQ，从 `cq-beginner-guide.md` 开始，自己写一个 SPARQL。
3. **第 3 周**：实现一个 Action Type（含前置校验、副作用、审计）。
4. **第 4 周**：把一个老的 Spring Service 翻译成"对象 + 动作 + 规则"三件套。

---

## 4. 架构演进：Java Spring 不会消失，会被"夹心"

很多团队最大的误解是"我们要全面用 Python 替换 Java"。**不要这么做。** 正确的姿势是分层：

```
                         ┌────────────────────────┐
        用户 / Agent  →  │  Object View 前端       │
                         └─────────────┬──────────┘
                                       │ OSDK / REST
                         ┌─────────────▼──────────┐
                         │  Action Types / QA      │   ← Python (FastAPI)
                         │  本体 / 规则 / 推理      │   ← Owlready2 / Fuseki / LLM
                         └─────────────┬──────────┘
                                       │ 适配层
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
     ┌────────────┐            ┌────────────┐            ┌────────────┐
     │ Spring Boot │            │ Spring Boot │            │  外部系统   │
     │  老业务系统  │            │  集成网关   │            │ ERP/MES/PDM│
     └────────────┘            └────────────┘            └────────────┘
            │                          │                          │
            ▼                          ▼                          ▼
       MySQL / Oracle              Kafka / MQ                 老接口
```

关键判断：

- **Spring Boot 不死**：它是与老系统、老数据库、强事务、外部接口对接的最佳工具。
- **Python 不去抢这个活**：FastAPI 是给本体层、Action 层、Agent 层用的，不要把它做成"重写一遍 ERP"。
- **数据归属要清楚**：事实数据归源系统（关系库），语义、推理、规则、证据归本体层（图库）。
- **写操作必须走 Action**：哪怕底层最终写到 MySQL，也得经过 Action 的前置校验、副作用、审计。

> 一句话：**Java Spring 是腿，Python 本体层是脑，LLM 是嘴。**
> 不要让脑子去走路，也不要让腿去说话。

---

## 5. UI 的根本性变化：从 Form/Table 到 Object View

这是用户感受最明显的部分，也是产品经理最需要重新学习的部分。

### 5.1 旧 UI 的样子

- 顶部菜单：试验管理 / 批次管理 / 测量录入 / 规格管理 / 报表
- 每个菜单点开：列表页（带搜索、分页、勾选） → 详情页 → 编辑表单 → 提交
- 用户的脑回路：**"我要找到那条记录，然后改它。"**
- 工作单元：**一行表数据**

### 5.2 新 UI 的样子（Object View）

- 全局搜索一个对象：批次 `B-T2024-03-017`
- 打开后是一个**围绕这个对象生成的工作面**：
  ```
  ┌─────────────────────────────────────────────────────────────┐
  │  Batch  B-T2024-03-017                         [Actions ▾]  │
  │  型号 T2024-03 · 试制阶段 · 责任工艺 张工 · 创建于 2026-04-12   │
  ├─────────────────────────────────────────────────────────────┤
  │  上下文                                                       │
  │   ↳ 隶属试验  Trial T2024-03 (鉴定试验)                       │
  │   ↳ 适用规格  Spec_v3 (2026-03-28 生效)                      │
  ├─────────────────────────────────────────────────────────────┤
  │  关键测量                                                     │
  │    M0115 振动 6.8 g     Pass     [证据]                      │
  │    M0117 振动 8.2 g     Fail_High [证据] [发起偏差]           │
  │    M0119 温度 188.0℃    Pass     [证据]                      │
  ├─────────────────────────────────────────────────────────────┤
  │  推理 / 解释                                                  │
  │    "本批次为什么不能放行？"                                    │
  │    → M0117 超 Spec_v3 上限 7.5 g, 命中规则 Rule_Fail_High     │
  ├─────────────────────────────────────────────────────────────┤
  │  可执行动作                                                   │
  │    ▸ RecordMeasurement   ▸ SubmitDeviation                   │
  │    ▸ RequestRelease (前置校验未通过, 灰)                      │
  └─────────────────────────────────────────────────────────────┘
  ```

注意几个关键变化：

- **没有"页面"，只有"对象的视图"**。同一个对象会按角色 / 任务呈现不同视图。
- **"提交表单"被"执行动作"替代**。每个动作都带前置校验，无法满足则按钮置灰且给原因。
- **"列表"被"按对象关系导航"替代**。从 `Trial` 点进去能看到下属的所有 `Batch`，再点进去能看到 `Measurement` 和 `Result`。
- **"为什么"是 UI 一等公民**。每个 `Result` 旁边都有 [证据] 按钮，点开就是推理链。
- **AI 入口在每个对象上**。"为什么这条 Fail？""规格如果改成 8.0g，结论会变吗？"——LLM 围绕**当前对象**回答，不在另开聊天页。

### 5.3 旧→新 UI 模式的对照

| 旧 | 新 |
|---|---|
| 录入表单 | Action 卡片（带前置校验提示） |
| 列表页 + 搜索 | 全局对象搜索 + 关系导航 |
| 详情页 | Object View |
| 状态字段 | Object 的状态属性 + 状态机可视化 |
| "导出 Excel" | "导出 Evidence Pack"（带规则版本和证据链） |
| 报表中心 | Saved CQ（保存的业务问题，每次自动跑） |
| 帮助文档 | 围绕对象的 Glossary 弹窗 + 解释 |
| 审批流程 | Action 的多阶段执行（提案 → 校验 → 审批 → 执行） |

### 5.4 给前端工程师的提醒

- **不要再封装"通用 CRUD 表格组件"了**。封装的应该是 `<ObjectHeader>`、`<RelationPanel>`、`<ActionButton>`、`<EvidencePopup>`。
- **状态来自后端，不要在前端再算一遍**。"能不能放行"这种判断永远问 Action 的前置校验，不要在前端写 `if (xxx > 7.5)`。
- **AI 入口不要做成全局右下角的小机器人**。它必须和当前 Object 绑定，并且只能问该对象有 CQ 支持的问题。

---

## 6. CQ 反推本体：实战流程

公司转型最早期，一定会有人问："那本体到底怎么建？我们没有 Palantir FDE。"
答案是：**用 CQ 反推。**

具体到一个新需求，流程如下：

```
1. PM / 业务方  → 写 CQ（5~10 条最关键的业务问题）
                     ↓
2. 本体工程师   → 看 CQ，问自己：要回答它，本体里至少要有什么？
                     ↓
3. 抽出最少必要骨架：Object / Property / Link / Constraint
                     ↓
4. 给每个 CQ 写 SPARQL 草稿，能跑出 Expected
                     ↓
5. 准备 demo ABox（最少样本数据），跑 CQ
                     ↓
6. 失败分类：空集 / 不完整 / 误报 / 超时
                     ↓
7. 定点修补：是 TBox 漏了？ABox 漏了？SPARQL 错了？规则错了？
                     ↓
8. CQ 通过 → 这一批本体骨架"达标"，可以上线
                     ↓
9. 业务再来新问题 → 新增 CQ → 回到第 2 步（增量扩展）
```

这套流程的意义：

- **本体不是被一次"设计"出来的**，是被一组组业务问题"反推"出来的。
- **凡是没有 CQ 支持的本体元素，都是技术债。** 要不删掉，要不补一条 CQ。
- **频繁变更的需求 = 频繁新增 / 调整 CQ**，本体随之演进，不需要"重做系统"。

> 这条规律对 PM 也成立：
> **如果你提的需求写不出 CQ，那它大概率不是一个真正的需求，是一个"我想加个字段"。**

---

## 7. 企业资产怎么沉淀

转型一年后，企业沉淀下来的不再是几百张表 + 几万行 Service 代码，而是这五样东西：

### 7.1 五大企业级语义资产

| 资产 | 是什么 | 价值 |
|---|---|---|
| **本体库**（Ontology Library） | TBox + RBox + SHACL 全集，分领域、分版本 | 新型号、新场景的"语义起点" |
| **CQ 库**（CQ Catalog） | 全企业的 Competency Questions 注册表，按业务域分类 | 每个新项目的"业务问题清单"，避免从零开始 |
| **Action 库**（Action Type Registry） | 全部受控写动作，含前置校验、副作用、审计 | 新应用直接调用，不再重复实现"提交逻辑" |
| **Evidence 库**（Evidence Archive） | 历史结论 + 推理链 + 规格版本，全可重放 | 审查、追溯、对比、回放 |
| **规格版本库**（Specification History） | 所有 Spec 的版本与生效区间 | 任何时间点的判定都能精确复现 |

这五样东西**不属于任何一个项目**，它们属于公司。
新项目接入时，复用率应该至少 60%；
老项目下线时，**这些资产不会随项目消失**。

### 7.2 沉淀的流程化要求

- 每次需求评审 → 必产出 CQ → 入 CQ 库
- 每次本体变更 → 必带触发事件溯源 → 入变更日志
- 每个 Action 上线 → 必经过审计字段评审 → 入 Action 库
- 每次规格变更 → 必版本化 → 入 Spec 历史库
- 每次结论产生 → 必带 Evidence → 入 Evidence 库

### 7.3 为什么这个比 Wiki 文档强 100 倍

- Wiki 文档**会过时**，因为它和系统是分离的。
- 上述五大资产**不会过时**，因为系统每跑一次，资产就被验证 / 增厚一次。
- 老员工离职带不走它们，新员工接手不需要"师傅带"。

> 这就是 Palantir 一直在讲的一句话：
> **"The ontology is the institutional memory."**
> （本体就是组织记忆。）

---

## 8. 推理一下未来：3 年路线图

把转型的故事往前推 3 年，大概会是这样的演进。

### 第 1 年：单点验证 + 思维转身

- 锁定 1~2 个高价值场景（比如本仓库的"试验数据管理"），完整跑通本体闭环。
- PM 完成思维转换：从画原型到写 CQ。
- 形成第一版 CQ 库（几十条），第一版本体（几十个对象），第一批 Action（几十个）。
- Spring 老系统继续跑，但所有"新业务规则"必须落到本体层。
- **关键标志**：当业务方说"改个上限"，没人去找开发改代码。

### 第 2 年：横向复制 + 资产化

- 把第一年的本体扩展到 3~5 个相邻场景（试验 → 工艺 → 质检 → 偏差 → 放行）。
- CQ 库进入 200+，本体对象进入 100+，Action 进入 100+。
- 出现"跨场景"的 CQ：比如"这个偏差对哪些其他批次有影响"。
- LLM 全面接入，但所有 Agent 都被钉在 Action / CQ 上。
- **关键标志**：新型号项目立项时，第一件事是从 CQ 库里勾选可复用的 CQ，而不是开 Kick-off 写 PRD。

### 第 3 年：组织运营本体（Operational Ontology）

- 本体覆盖型号设计 / 工艺 / 试验 / 质检 / 供应链 / 售后 / 审查 全链路。
- 出现"型号本体生命周期"：每个型号的本体作为它的"数字主线"，跨阶段一致。
- AI Agent 不再只是问答，而是**主动巡检**：
  - "这周哪些 Result 在新规格下结论会变？"
  - "这批偏差和历史哪几次模式相似？"
  - "这个供应商替代会不会撞到任何已发布的工艺窗口？"
- 与外协单位、上级单位通过本体接口共享语义，不再交换字段表。
- **关键标志**：当审查方要求出一份证据链，系统 5 分钟内导出 Evidence Pack，并附完整规格版本历史与推理链。

### 不会发生的事（要提前打预防针）

- **不会**出现"AI 全自动判 Pass/Fail"。LLM 永远不直接出业务结论。
- **不会**消灭 Java 程序员。但 Java 工作内容会向"集成、性能、底层"集中。
- **不会**消灭表单。但表单成为 Action 的 UI 表现之一，不再是业务的中心。
- **不会**一次到位。本体是被业务事件"喂大"的，不可能闭门设计完。

---

## 9. 最后给三类人的一句话

- **给老板**：你买的不是一个 IT 系统，你买的是一份"组织记忆"和一层"AI 时代的业务护城河"。这个护城河不在代码里，在本体、CQ、Action、Evidence 里。
- **给产品经理**：你以前的工作产出是 PRD，现在是 CQ。你以前画表单，现在画对象。你以前担心需求变更，现在欢迎需求变更——因为它让本体长大。
- **给程序员**：你以前是写"如何把数据塞进表格"的人，现在是写"如何把业务规则显式化、可执行、可审计"的人。这个新角色更像建筑师，不像泥瓦匠。它更难，但它的成果**不会随版本迭代被覆盖掉**。

> 转型的本质，不是换语言、换框架、换数据库。
> **转型的本质是：让企业的业务知识，第一次以可执行、可校验、可复用的形式留在系统里。**

---

## 10. 本体怎么改、规则怎么作废、复杂判断和写入怎么落

> 这一章回答四个最实操的问题：
> 1. 业务方说"这个上限/这个对象/这个字段要改"，工程上怎么改本体？
> 2. 一条规则不再适用了，怎么"作废"它而不破坏历史结论？
> 3. 复杂判断逻辑（多参数、多对象、跨阶段、含时间/批次）放在哪里？
> 4. 判定通过后要触发的写入（落档、推动状态、通知）在哪里实现？
> 顺带回答一个常被问到的问题：**这个 MVP 程序需要被改造成一个"本体编辑器"吗？**

### 10.1 修改本体的四种粒度（从轻到重）

修改本体不是一件事，而是**四件不同重量级的事**。混在一起谈是大多数团队踩坑的根源。

| 粒度 | 例子 | 改在哪 | 谁能改 | 是否要发版 |
|---|---|---|---|---|
| L1 实例数据（ABox） | 录入一条新测量、给批次补一个责任人 | `data graph`，走 Action | 操作员 | 否，运行时即生效 |
| L2 业务参数（Spec / Parameter） | 把振动上限从 7.5 改 8.0；新增一个"湿度"参数 | `spec graph` / 参数注册 API | 工艺/质量授权岗 | 否，**版本化生效** |
| L3 规则与判定逻辑 | 加一条"连续 3 次接近上限要 Warn"；把"过期 24h 自动作废"改 48h | `inference.py` / SWRL / Function | 本体工程师 + 业务复核 | 是，但只发"规则版本" |
| L4 本体骨架（TBox / RBox / SHACL） | 新增 `Deviation` 对象、`Batch ↔ Lot` 多对多关系、新增约束 | `manufacturing-trial.ttl` 等 | 本体架构师 | 是，走 git + 评审 + CQ 回归 |

**关键判断**：90% 的"业务变更"应该落在 L1 / L2，**不需要任何一行代码改动**。只有真正的"语义变化"才进 L3 / L4。
如果你发现 L4 改动很频繁，那大概率是当初本体抽象错了，要回去补 CQ 反推骨架，而不是继续改 TBox。

### 10.2 修改本体的标准操作流程（SOP）

无论哪一级，改动**都要跑同一条流水线**——这是本体路线区别于"改个表加个字段"的核心：

```
触发事件（业务来源、合规要求、型号变更）
    ↓
新增 / 修改 CQ 条目        ← 必须先有 CQ，否则不动手
    ↓
评估变更等级 L1 / L2 / L3 / L4
    ↓
做改动（数据 / 规格 / 规则 / TBox）
    ↓
跑 CQ 回归套件             ← 旧 CQ 必须仍能通过，新 CQ 必须能通过
    ↓
失败分类与定点修复          ← 截图阶段三的"失败驱动修复"
    ↓
写变更日志（含触发事件溯源）  ← 资产沉淀
    ↓
合并 / 发布
```

> **"无 CQ 溯源的改动 = 技术债"**——这是图里写的红字，也应该是公司本体治理的硬规定。

### 10.3 怎么作废一条规则（最容易出错的地方）

**永远不要"删除"一条规则。** 删除等于擦掉历史。
作废要做的是**版本化下线**，让旧结论仍然能被复现，新数据走新规则。

#### 作废操作的四个动作

1. **打 retired 标记**：在规则定义里加 `retiredAt`、`retiredReason`、`replacedBy`。
   ```ttl
   mto:Rule_Fail_High_v1
       a mto:Rule ;
       mto:effectiveFrom "2024-01-01"^^xsd:date ;
       mto:effectiveTo   "2026-04-15"^^xsd:date ;
       mto:retiredReason "工艺改版,上限不再单点判定" ;
       mto:replacedBy mto:Rule_Fail_High_v2 .
   ```
2. **不动历史 Result**：所有引用 `Rule_Fail_High_v1` 的旧结果保留原样，因为它们的 `appliedRule` 字段就是 v1。
3. **新数据走新规则**：判定引擎按"测量时间 / 批次时间"匹配规则的有效区间。
4. **可选：批量重判**：如果业务要求"按新规则把历史也重算一遍"，走**显式重判 Action**（`RecomputeAgainstRuleVersion`），并把"原结论"和"新结论"双双留档，而不是覆盖。

#### 错误做法 vs 正确做法

| 错误做法 | 正确做法 |
|---|---|
| 直接改 `inference.py` 里的阈值 | 加一条 `Specification` 的新版本 + `effectiveFrom` |
| 把 SWRL 文件里旧规则删掉 | 把旧规则标 retired，新增 v2，引擎按版本路由 |
| 给 `Result` 表 update 一遍状态 | 不改老 Result，新建一组新 Result 指向 v2 规则 |
| 事后再补一份 changelog | 改动**之前**先开 CQ，事中自动落变更日志 |

> 一句话：**作废的本质是"加一个墓碑"，不是"删一行代码"。**
> 军工和合规场景这条线绝对不能让步。

### 10.4 复杂判断逻辑放在哪里

业务越往后走，判断会从"单参数上下限"演化成各种复杂形态：

- **多参数耦合**：温度 OK 且压力 OK，但温度 × 压力 > 阈值要警示
- **跨对象**：批次内三个测量都通过，但批次责任人未签字也不能放行
- **时序 / 历史**：连续 3 次接近上限触发预警；30 天内同型号偏差累计 > N 升级
- **业务上下文**：试制阶段允许 X，定型阶段不允许 X
- **deontic（合规）**：合规条款 17.3 要求"超限必须 24h 内开偏差单"

这些不能也不该全塞进 `inference.py` 一个文件。**按复杂度分四档放：**

| 复杂度 | 放哪里 | 例子 |
|---|---|---|
| A. 简单数值判定 | `inference.py` 确定性函数（保底） | 上下限 Pass / Fail_High / Fail_Low |
| B. 显式逻辑可声明 | **SWRL 规则** / SHACL 约束 | "测量必须有 Parameter 和 Specification" |
| C. 多对象多步推理 | **SPARQL CONSTRUCT / Function** | "批次的所有 Critical 测量都 Pass 才允许放行" |
| D. 含时间 / 历史 / 业务上下文 | **Python Function（命名 + 版本化）** | "30 天内累计偏差 > N 升级"、"试制 vs 定型差异判定" |

**关键约束**——无论哪一档：

- **必须命名、必须版本化**：`Function: BatchReleaseEligibility v1`，不能匿名 lambda。
- **必须返回结构化 evidence**：返回的不只是 true/false，而是 `{result, rule, evidence_paths, deviation, applied_version}`，跟 `Result` 一致。
- **必须可被 CQ 测试**："这个判定为什么得出 X" 要能用 SPARQL / QA 拿到证据。
- **禁止藏在 UI / 中间件 / Action 内部的临时 if-else 里**——一旦藏，规则又要重新散落。

#### 一个推荐的"判断逻辑分层模式"

```
Action（业务入口，例：SubmitReleaseRequest）
   ├─ 前置校验：调 Function 集合（C/D 档）
   │     ├─ Function: AllCriticalMeasurementsPass(batch)        ← SPARQL
   │     ├─ Function: NoOpenDeviation(batch)                    ← SPARQL
   │     ├─ Function: ResponsibleSignedOff(batch)               ← SPARQL
   │     └─ Function: ComplianceClause17_3Satisfied(batch)      ← Python
   ├─ 主体写入：写 ABox + 写 Result + 写 Evidence
   └─ 触发副作用（10.5 节）
```

> **判断逻辑应该长成"一棵函数树"，根是 Action，叶是确定性函数；
> 不是长成"一坨 if-else 沼泽"。**

### 10.5 判定后的写入和副作用：Action Type 框架

复杂判断真正的落地难点不是"算出 Pass/Fail"，而是"算完之后要做什么"。
这部分必须由 **Action Type** 统一承担，**禁止散落在 Service 或前端**。

一个 Action Type 的标准骨架：

```python
@action(name="SubmitReleaseRequest", version="v2")
class SubmitReleaseRequest:
    # 1. 输入契约（强类型 + Schema）
    class Input(BaseModel):
        batch_id: str
        scope: Literal["model", "batch", "unit"]
        evidence_refs: list[str]

    # 2. 前置校验（调用 Function 树, 全部命中才放行）
    preconditions = [
        Fn("AllCriticalMeasurementsPass", arg="batch_id"),
        Fn("NoOpenDeviation",            arg="batch_id"),
        Fn("ResponsibleSignedOff",       arg="batch_id"),
    ]

    # 3. 主写入（事务边界,失败整体回滚)
    def execute(self, input, ctx):
        request_iri = graph.write_release_request(input)
        graph.link(request_iri, "appliesTo", input.batch_id)
        return request_iri

    # 4. 副作用 / 触发器(显式声明,不藏代码里)
    triggers = [
        OnSuccess.notify(role="QualityHead", template="release_submitted"),
        OnSuccess.write_event(topic="release.submitted"),
        OnSuccess.start_workflow("ReleaseApproval"),
        OnFailure.audit(level="WARN"),
    ]

    # 5. 审计（自动,所有 Action 默认开启)
    audit = AuditPolicy(actor=True, input=True, output=True, evidence=True)
```

**这个骨架让"判断 + 写入 + 副作用"变成一种可治理的资产**：

- 任何写操作都进 Action Type，**不允许 controller 或 service 直接写图**。
- 副作用是**声明式**的（`triggers`），可被列出、被审计、被开关。
- 失败 / 成功路径都自动落审计，无需手写日志。
- Action 自身有版本，老版本继续支持老调用方，符合"作废靠版本化"的统一原则。

> 等价对照：旧 Spring 里我们写 `@Transactional` Service + `@EventListener` 监听 + AOP 日志切面；
> 在本体路线下，这些**全部内化在 Action Type 的声明里**，业务读起来像合同条款，而不是代码。

### 10.6 那么——本程序要被改造成"本体编辑器"吗？

**短答：要，但不是现在；而且永远不要做成"通用 OWL 编辑器"。**

长答分三层：

#### 第一阶段（当前 MVP 阶段）：不要做编辑器

- 本体改动用 **Protégé + git** 完成，命令行 + PR 评审。
- 规格 / 参数改动用现有 API（`/api/v1/parameters`、`spec graph` 写入）。
- CQ 用 markdown 文件 + `tests/test_cq_integration.py` 跑回归。

理由很直接：**本体在前 6 个月会反复重构**，给一个还在剧烈变化的语义层做"可视化编辑器"，做出来的工具自己都跟不上节奏，最后变成谁都不敢碰的烂尾页面。

#### 第二阶段（本体稳定到 80%+ 后）：做"受控编辑面"，不是"本体编辑器"

应该做的是：把那些**业务方真正需要自助修改的东西**做成**受控的、有约束的、带版本和审计的**编辑面：

| 编辑面 | 改什么 | 边界 |
|---|---|---|
| 规格管理界面 | Specification 的上下限、有效区间、版本说明 | 不改对象，不改关系 |
| 参数管理界面 | Parameter 的元数据、单位、是否参与推理 | 不改判定规则 |
| 规则版本管理界面 | Rule 的 `effectiveFrom/To`、retiredReason、replacedBy | 不允许新增任意 Python 代码 |
| Action 审批流配置 | 哪个 Action 需要谁审批 | 不改 Action 本体 |
| CQ 注册面 | 业务问题 + 期望 + Demo data | 不直接生成 SPARQL |

**这五个编辑面 ≠ 本体编辑器。** 它们是**对本体的受控写入入口**，每一处写入背后仍然是一个 Action Type，仍然有前置校验和审计。

#### 第三阶段（本体 + Agent 生态成熟后）：做"AI 协作建模面"

这一阶段才考虑做"看起来像 Palantir Foundry 的 Object Manager"的工具：

- 本体架构师在界面上画对象 / 关系 / 约束 → 工具生成 TTL / SHACL 草稿
- LLM 协助：根据已有 CQ 自动建议骨架、自动写 SPARQL 草案、自动出 demo data
- **但**：所有改动仍走 git + CQ 回归 + 评审，**界面只是更友好的草稿入口**
- **永远不**把"业务规则改写"变成 UI 上的拖拉拽——规则要进版本控制，不能被一键改掉

#### 本程序自身的改造路径

回到本仓库具体怎么走：

```
当前 MVP                  →  第二阶段（约 6~12 个月)        →  第三阶段
─────────────────────       ─────────────────────────       ──────────────
Streamlit 演示工作台        Streamlit / 正式前端             Object View 工作面
直接编辑 .ttl + git         规格/参数/规则版本管理界面        本体协作建模面
inference.py 改 Python      规则版本化注册 (DB 化或 git 化)   AI 协助生成本体草稿
手写 SPARQL                 受控编辑面 + Action 审计         LLM 自动出 SPARQL/CQ
docs/cq/*.md                CQ 注册中心 + 自动回归           CQ 工厂自动化
```

**不要在第一阶段就上第三阶段的工具——这是国内大量"知识图谱平台"项目的最常见死法。**
工具的复杂度必须**永远滞后于本体的稳定度**，先用最朴素的 git + Protégé + markdown CQ 跑通三个真实场景，再考虑做面。

### 10.7 给三类人的速查表

- **PM 速查**：业务变更先问"这是 L1/L2/L3/L4 哪一级？"。L1/L2 不要走开发排期，自己走规格 / 参数管理面。L3 必须先写新 CQ。L4 必须开本体评审会。
- **程序员速查**：90% 的判断写成 Function（命名 + 版本化），10% 写到 Action Type 的 preconditions 里。**任何一个 if-else 出现在 controller / service 里就是 bug。**
- **架构师速查**：编辑器永远晚于本体。先靠 Protégé + git 把本体磨稳定，再用受控编辑面承接高频业务变更，最后才考虑 AI 协助建模。**反过来做必死。**

---

## 11. LLM / AI 在这套模型里到底起什么作用

> 这章回答一个高频被问到的问题：
> "我们引入了本体，那 LLM 还做什么？是用来从 CQ 反推 TBox/RBox 的吗？"
>
> **短答**：不是核心，是外围加速器。CQ → TBox/RBox 是 LLM 的用法之一，但既不是它最重要的工作，也不是它能"自动"完成的工作。

### 11.1 一句话定位

> **LLM 负责"理解、规划、解释"，本体和确定性规则负责"取数、计算、校验、执行"。**
>
> 这是 `docs/ontology-wiki/12-llm-rigor-and-correctness.md` 的红线，本仓库 `mvp/core/qa.py` 严格按这条线写。

把 LLM 从架构里抽掉，本体仍然能跑、判定仍然准确、CQ 仍然能验收。
但加上它，业务面更好用、建模更快、问答更自然。

### 11.2 按"运行时 / 建模时"两阶段拆开

LLM 的角色其实分两个完全不同的阶段，混在一起会越说越乱。

#### 阶段 A：运行时（Runtime）—— LLM 是"翻译官 + 接待员"

用户每天用系统时，LLM 做这 4 件事：

| LLM 做什么 | 例子 | 边界 |
|---|---|---|
| **意图识别** | 用户问"M007 为啥 Fail" → 路由到 `why_fail` 这个白名单 intent | 只能命中白名单 intent，命不中走兜底 |
| **参数抽取** | 从自然语言里抽出 `measurement_id=M007` | 抽出来的参数交给 SPARQL，不直接执行 |
| **查询规划** | 从 CQ 模板里挑一个最匹配的 SPARQL | 模板预先注册，**不是 LLM 现写 SQL** |
| **结果解释** | 把 SPARQL 返回的 evidence 翻译成中文："因为测得 197.2℃ 超 Spec_v1 上限 195℃，偏差 2.2℃" | **结论不变**，只是换说法 |

**LLM 在运行时绝对不做的 4 件事**（高严谨场景的护栏）：

1. 不直接产出业务结论（Pass/Fail 由 `inference.py` 的确定性规则给出）
2. 不直接执行写操作（写操作必须走 Action Type）
3. 不自由生成 SPARQL（只能从模板里选）
4. 不承担审计（审计由 Action + Evidence 链承担）

> 一句话：**运行时的 LLM 是嘴，不是脑，更不是手。**

#### 阶段 B：建模时（Build-time）—— LLM 是"FDE 助手"

工程师 / PM 在搭本体、写 CQ 时调用，做这 5 件事。**这才是"CQ → TBox/RBox"那条路径所在的位置**：

| LLM 做什么 | 例子 | 仍然必须由人决定的 |
|---|---|---|
| 从访谈纪要 / 老文档抽 CQ 候选 | "这段会议纪要里我提了 8 个候选 CQ" | 哪些是真正的业务验收 |
| 从 CQ 反推 TBox/RBox 候选骨架 | "要回答这个 CQ，至少要有 `Measurement、Specification、Result、appliedRule` 4 个对象 + 3 条关系" | 是否符合企业语义边界 |
| 写 SPARQL 草稿 | 给定 CQ + 骨架，生成查询初稿 | 跑 fixture 跑通才算数 |
| 找术语冲突 | "你新建的 `Lot` 和已有的 `Batch` 看起来是同一个东西" | 业务方拍板 |
| 草拟 Action 模板 | 根据 CQ 写出 Action 的输入、前置校验、副作用骨架 | 工程师 review、签 PR |

**这条路径永远是"AI 提议 → 人 review → git 留痕 → CQ 回归"**，不是"AI 自动改本体"。

把 "LLM 自动改 TBox/RBox" 做成自动循环，是国内很多本体项目的死法之一——本体一旦失去人审，语义就开始漂移，没几周就和业务脱节。

### 11.3 一张图看 LLM 的两个用法

```
                ┌────────────────────────────────────────────┐
                │              LLM 的两个用法                  │
                └────────────────────────────────────────────┘
                          │                       │
              ┌───────────┘                       └───────────┐
              ▼                                               ▼
   ┌─────────────────────┐                       ┌─────────────────────┐
   │   建模时 / Build      │                       │   运行时 / Runtime    │
   │  (FDE 助手, 离线)     │                       │  (翻译官, 在线)        │
   └─────────────────────┘                       └─────────────────────┘
   - 抽 CQ                                       - 意图识别 (白名单)
   - 反推 TBox / RBox 草稿                       - 参数抽取
   - 写 SPARQL 草稿                              - 模板路由 (不是写 SQL)
   - 找术语冲突                                   - Evidence → 中文解释
   - 草拟 Action 模板
              │                                               │
              ▼                                               ▼
       人 review + git PR                          Action / 确定性规则 / 图查询
       CQ 回归测试                                  (LLM 不参与判定与写入)
              │                                               │
              ▼                                               ▼
        合并入主线                                   返回结构化 Evidence + 解释
```

### 11.4 LLM 的 4 个"做"和 4 个"不做"——必须背下来的护栏

| 做 | 不做 |
|---|---|
| 意图理解（白名单内） | 直接产出事实（金额、库存、判定结果） |
| 查询规划（从模板里选） | 直接执行业务规则（合规、放行、授信） |
| 参数收集（从对话里抽出 ID） | 直接拼写高风险写操作（改状态、放行、批准） |
| 结果解释（Evidence → 自然语言） | 单独承担审计（审计由系统而不是 LLM 负责） |

这 4 行可以打印贴墙。任何让 LLM 越过右侧的设计，都是把企业暴露在"看起来很对但其实是幻觉"的风险下。

### 11.5 回到那个具体问题：CQ 反向修改 TBox/RBox 是 LLM 的核心吗？

**不是核心，是一条具体路径**。精确表述：

- **CQ 反推 TBox/RBox** 是 LLM 在**建模时**"五大助手任务"之一，价值高，但**永远靠人 review + CQ 回归兜底**。
- **LLM 真正高频出现的地方是运行时**——把 evidence 翻译给业务人员看。这一面工作量更大、价值更稳、风险更低。
- 一句话概括建模时的 LLM：**它是会打字的 FDE 实习生，不是 FDE 本人。**

### 11.6 本仓库当前 LLM 落到了哪一步

对照本项目代码：

| LLM 角色 | 项目里的位置 | 状态 |
|---|---|---|
| 运行时 - 意图识别 | `mvp/core/qa.py`（白名单 intent） | ✅ 已落地 |
| 运行时 - 参数抽取 | `qa.py` 的轻量抽取 | ✅ 已落地 |
| 运行时 - SPARQL 模板路由 | `qa.py` 选 CQ 模板 | ✅ 已落地 |
| 运行时 - Evidence 翻译 | `qa.py` 调 LLM provider | ✅ 已落地，**有本地 fallback** |
| 建模时 - CQ 反推骨架 | 还在 `docs/cq/*.md` 手写阶段 | ⏳ 规划中 |
| 建模时 - SPARQL 草稿 | 暂未集成 | ⏳ 规划中 |
| 建模时 - 术语冲突检测 | 暂未集成 | ⏳ 规划中 |

> 现阶段本仓库的 LLM 是**运行时的翻译官**；
> 建模时的 "CQ → 本体反推" 是路线图的一部分，**有意先不上**——理由还是 §10.6 那句：
> **"工具复杂度必须永远滞后于本体的稳定度。"**

### 11.7 给三类人的速查（LLM 篇）

- **PM 速查**：跟业务方讲 AI 时，不要说"我们用 AI 判合格"。要说"AI 帮你听懂问题、找证据、讲清楚理由；判合格的是规则和规格"。这是合规和军工场景里唯一能站住脚的话术。
- **程序员速查**：写代码时心里只装一句话：**LLM 调用前必须有 schema，调用后返回必须有 evidence**。任何"让 LLM 直接判 / 直接写"的诱惑，都用 Action + Function 顶回去。
- **架构师速查**：LLM 是外围，本体是核心。规划演进时，先长本体，后长 LLM 的工具面；不要因为 LLM 看起来万能就把它放到正确性链路的顶端。**LLM 永远在链路的入口（理解）和出口（解释），不能在链路的中间（决策）。**

### 11.8 读（SPARQL）和写（Action）：都是人写为主、LLM 只出草稿

很多人会以为"既然 LLM 这么强，让它现场拼 SPARQL、现场拼 Action 就完了"。
**这条路在高严谨场景里走不通。** SPARQL 和 Action 都必须是**被命名、被版本化、被审计的资产**，由人写、人 review、进 git、跟着 CQ 一起回归测试。LLM 只在最前面出草稿、最后做解释。

#### 11.8.1 本体层的三类一等公民

把本体层（运行时）的资产摊开看，长这样：

| 资产类型 | 用途 | 例子 | 维护在哪 | 谁主写 |
|---|---|---|---|---|
| **Object Type / Property / Link / SHACL** | 定义"世界长什么样" | `Measurement`、`hasResult`、单位约束 | `manufacturing-trial.ttl`（Protégé / 文本编辑） | 本体架构师 |
| **SPARQL 模板**（≈ Palantir Function-read） | **读**：回答 CQ、取证据、做聚合 | `CQ-MJ-001` 的查询 | CQ 文件 + `qa.py` 注册表（文本 / 代码） | 后端工程师 |
| **Action Type**（写 + 副作用） | **写**：录入测量、变更规格、提交放行 | `RecordMeasurement`、`SubmitReleaseRequest` | `mvp/core/actions.py`（代码） | 后端工程师 |

> 三者并列才完整：**Object 回答"有什么"、SPARQL 回答"怎么取出来"、Action 回答"怎么改变它"**。
> 缺任何一类，本体就只是个 .ttl 文件，不是运营层。

#### 11.8.2 SPARQL 模板的生命周期

```
1. PM 写 CQ：业务问题 + Expected + Evidence fields
        ↓
2. LLM 看 CQ + TBox 出 SPARQL 草稿               ← AI 加速
        ↓
3. 工程师 review、改字段、补 named graph 占位符
        ↓
4. 跑 fixture：fixture → SPARQL → 是否得到 Expected 行
        ↓
5. 跑 QA 链路：Evidence 字段是否完整、解释是否对
        ↓
6. 模板登记到 CQ 文件 + 注册到 qa.py 的模板路由
        ↓
7. 进 git，进 CI 回归套件
        ↓
8. 后续任何本体改动都必须保证这条 SPARQL 仍能跑通
```

每条 SPARQL 模板必须配齐五件套：CQ、Demo fixture、Evidence 字段清单、Expected、集成测试条目。

#### 11.8.3 Action Type 的生命周期（与 SPARQL 完全平行）

```
1. PM 提需求并写 CQ：哪些操作要被允许、什么时候被允许、谁能做
        ↓
2. LLM 看 CQ + TBox 出 Action 草稿               ← AI 加速
        - 输入 schema、前置校验候选、副作用候选
        ↓
3. 工程师 review、收紧前置校验、声明 triggers、补审计
        ↓
4. 跑 fixture：违规输入是否被拒、合规输入是否成功落档
        ↓
5. 跑端到端：Action → 写 ABox → 触发推理 → 写 Result → CQ 仍能查到
        ↓
6. 登记到 Action Type Registry，绑定权限和审批策略
        ↓
7. 进 git、进 CI、进权限矩阵
        ↓
8. 后续本体改动必须保证 Action 仍能通过自身回归
```

> 一句话：**Action 和 SPARQL 是孪生兄弟——一个负责"读"的契约，一个负责"写"的契约，两者都是人写为主、LLM 起草**。

#### 11.8.4 为什么不让 LLM 现场拼 SPARQL / Action

| 风险 | 解释 |
|---|---|
| 不可审计 | 现场拼出来的查询 / 写操作没有名字、没版本、没 CQ 绑定，出问题查不到根因 |
| 不稳定 | 同一业务问题，不同时刻 LLM 可能给出语义微妙不同的版本，结论漂移 |
| 不安全 | 自由 SPARQL ≈ 自由 SQL，自由 Action ≈ 任意写图，密级 / 权限会被绕过 |
| 不可回归 | 没登记的查询 / 写，下次改本体时无人知道它存在，悄悄就坏了 |

护栏统一长这样：

```python
# qa.py 的模式：LLM 只在两端，中间永远是登记好的模板/Action
def answer(question: str):
    intent, params = llm_classify(question)        # LLM：识别意图、抽参数
    template = SPARQL_TEMPLATES[intent]            # 系统：从注册表取
    sparql   = render(template, params)            # 系统：模板渲染
    rows     = fuseki.query(sparql)                # 系统：执行
    return llm_explain(rows)                       # LLM：把结构化结果讲成人话

def execute_action(name: str, params: dict, actor):
    action = ACTION_REGISTRY[name]                 # 系统：从注册表取
    action.check_preconditions(params, actor)      # 系统：前置校验
    result = action.execute(params, actor)         # 系统：写 ABox / 触发副作用
    audit.log(name, params, actor, result)         # 系统：审计
    return result
```

**LLM 出现在两端（理解 / 解释），中间永远是登记好的资产。**

---

## 12. 工具栈与角色分工：不是每个人都要深入 Protégé

这一章直面一个常见误解：

> "搞本体是不是意味着以后人人都要会 Protégé？开发人员是不是从写代码改成在 Protégé 里画图？"

**不是。** Protégé 只是众多工具中的一个，而且只覆盖**本体的"骨架编辑"那一段**。下面把工具栈和角色分工摊开。

### 12.1 工具的真实分工

| 资产 / 任务 | 用什么工具 | 为什么 |
|---|---|---|
| TBox / RBox（类、属性、关系、约束） | **Protégé** 或直接编辑 `.ttl` | 图形化看公理结构、用推理器做一致性检查 |
| SHACL Shape | Protégé 插件 / 文本 / 单独 `.shacl` 文件 | 受约束的本体校验定义 |
| **SPARQL 模板** | 文本 + 代码（注册到 `qa.py`） | **不写在 Protégé 里**——它是查询契约，不是结构 |
| **Action Type** | Python 代码（`mvp/core/actions.py`） | **不写在 Protégé 里**——它带副作用、审计、权限 |
| **Function（判断逻辑）** | Python 代码 | 同上，是可执行资产 |
| **CQ** | Markdown 文件（`docs/cq/*.md`） | 业务方和工程师共同读，不需要工具 |
| 推理 / 测试 | `pytest`、Pellet、Fuseki | 跑回归 |
| 数据录入 / Action 调用 | 业务前端（Object View） | 给业务人员用，不需要懂 Protégé |
| 集成 / 老系统对接 | Java Spring | 不动 |

**关键判断**：

> **Protégé 是"骨架编辑器"，不是"本体 IDE"。**
> 本体里 80% 的资产（SPARQL、Action、Function、CQ、测试）都不在 Protégé 里。

### 12.2 各角色到底要学什么（按学习曲线排序）

| 角色 | 要会的工具 | Protégé 要会到什么程度 | 主要产出物 |
|---|---|---|---|
| **业务方 / 操作员** | Object View（前端） | **完全不需要** | 用，不开发 |
| **PM / 业务分析师** | Markdown、读 TBox 图 | **能读懂图，不需要会画** | CQ 注册条目、对象草图、Action 草图 |
| **前端开发** | OSDK / REST、组件库 | **完全不需要** | Object View、Action 卡片、Evidence 弹窗 |
| **后端开发（最重）** | Python + SPARQL + 读 TTL + 部分 SHACL | **会用、能改少量类**，但不是主力 | Action Type、SPARQL 模板、Function、CQ 测试 |
| **本体架构师 / FDE** | Protégé 深用、SHACL、SPARQL、reasoner | **必须深入** | TBox / RBox / SHACL、本体演进、骨架评审 |
| **QA / 测试** | `pytest`、CQ 框架、Fuseki | **能读懂** | CQ 自动化用例、回归套件 |
| **DBA / 图谱管理员** | Fuseki、named graph、备份 | **不需要** | 图存储运维、版本快照 |
| **AI / Agent 工程师** | LLM 提供商、Prompt、模板路由 | **能读懂** | 意图识别、Evidence → 解释 |

> 真正"必须深入 Protégé"的，**只有本体架构师 / FDE 这一个角色**——他大概占整个团队的 5%~10%。
> 后端开发**必须会读 TTL、能跑 reasoner**，但日常 80% 时间在写 Python（Action / Function / SPARQL 模板），**不在 Protégé 里**。

### 12.3 后端开发的真实工作变化

回到这个最具体的问题："开发人员从写代码变成在 Protégé 里画图吗？"

**不会。** 后端开发依然 80% 时间在写代码，只是写的代码"层级更高、更声明式"：

| 旧 Spring 工作 | 新本体路线对应 | 工具 |
|---|---|---|
| 设计表 + ER 图 | 评审 TBox（本体架构师主写，后端只 review） | 读 `.ttl`，偶尔开 Protégé |
| 写 `@Entity`、Mapper | **没有** | — |
| 写 `@Service` 业务逻辑 | 写 **Function**（命名、版本化的判断逻辑） | Python |
| 写 `@Controller` + DTO | 写 **Action Type**（输入 schema + 前置校验 + 副作用 + 审计） | Python |
| 写 `@Repository` SQL | 写 **SPARQL 模板**并注册 | 文本 + Python 注册 |
| 写流程 / 状态机 | Action 的 triggers + 显式状态机 | Python（声明式） |
| 写集成测试 | 写 **CQ 测试**（自动跑 SPARQL + Evidence + QA） | `pytest` + Markdown CQ |
| 接老系统接口 | Spring 网关层（保留） | Java Spring（**不动**） |

> **不是"少写代码"，是"少写 if-else，多写声明式资产"。**
> 后端依然是后端，只是从"写流水账"变成"写契约"。

### 12.4 谁需要"深入 Protégé"，谁不需要

**需要深入（5%~10% 的人）**：

- 本体架构师 / FDE
- 极少数同时承担"骨架演进 + Action 设计"的资深后端

**需要会读、偶尔会改（30%~40%）**：

- 普通后端：能看懂 `.ttl`，能在 Protégé 里加一个属性、跑一次推理一致性检查
- QA：能看懂 TBox 来理解 CQ 的语义边界

**不需要碰（50%+）**：

- PM：读 TBox 图就够了，自己不画
- 前端：完全不碰
- 业务方 / 操作员：完全不碰
- DBA：完全不碰
- AI 工程师：能读就行

### 12.5 工具栈的"反向常识"

> "本体路线 = 人人 Protégé" 是错觉。
> **真正的姿势是："1~2 个深度 Protégé 用户 + 一组 Python 后端 + 一支懂对象的前端 + 全员会写 CQ"。**
> 把 Protégé 推给所有人，会让团队卡在工具学习上而不是业务上，这是国内本体项目失败的另一种典型死法。

### 12.6 三类人的"工具速查"

- **PM**：装一个 Protégé 看图就够了，**不要去改类**。你的主战场是 Markdown 和 CQ。
- **后端**：把 80% 时间放在 Python（Action / Function / SPARQL 模板）和 CQ 测试上；Protégé 用来 review 本体架构师的 PR、跑一致性检查，不是日常编辑器。
- **本体架构师 / FDE**：你是 Protégé 的主要用户，但你也必须能读 Action / Function / SPARQL，知道下游怎么用骨架。**只懂 OWL 不懂工程，本体会建得很漂亮但用不起来**——这是这条路线最经典的反面教材。
