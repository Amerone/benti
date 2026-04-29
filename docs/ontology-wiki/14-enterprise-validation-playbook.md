# 14 Enterprise Validation Playbook

## 先看推荐

如果你的目标已经不是“做一个概念验证”，而是要搭一套企业级验证体系来验证本体、架构和技术路线，那么更稳的思路不是先做“大而全总本体”，而是先搭一条分层可验证链路：

> 用同一套企业级验证体系，同时验证业务语义是否清晰、数据是否可信、规则是否可复现、动作是否受控、Agent 是否可审计。

我更推荐把企业级验证拆成 6 层：

1. 业务语义验证
2. 本体模型验证
3. 数据质量验证
4. 规则与策略验证
5. 流程与审批验证
6. Agent 与运行时验证

如果你现在就要选一条主路线，我的建议是：

- 默认推荐，适合大多数企业自建平台：  
  `WebProtégé / Protégé + Apache Jena / Fuseki + SHACL + OpenMetadata + OPA + Camunda 8`

- 如果团队明显偏工程化、代码优先、长事务很多：  
  把 `Camunda 8` 换成 `Temporal`

- 如果你已经在 Palantir Foundry 体系里：  
  优先走 `Foundry Ontology + Actions + Functions + AIP / Workshop`

## 企业级验证到底在验证什么

企业里真正要验证的，不是“有没有 ontology 文件”，而是下面 6 件事：

### 1. 语义是否真的统一了

例如“订单状态”“客户等级”“设备可用性”这些概念，跨系统后是不是仍然稳定。

### 2. 约束是否能被机器校验

不是靠人背规则，而是能明确拦住：

- 缺字段
- 错类型
- 非法状态
- 关系不成立

### 3. 规则是否可复现

同一笔业务，今天算一遍和下周算一遍，结论是否一致，规则版本是否可追踪。

### 4. 高风险动作是否受控

不是 Agent 说能写就写，而是要经过：

- 权限验证
- 参数验证
- 前置条件验证
- 审批或 workflow

### 5. 结果是否可解释

系统不仅要给结论，还要给：

- 命中的对象
- 命中的关系
- 命中的规则
- 证据时间点

### 6. 全链路是否可审计

出了问题以后，能不能追到：

- 当时看了什么数据
- 用了哪版本体
- 用了哪版规则
- 谁批准了动作
- 最终改了什么

## 一套企业级验证架构

可以先把推荐架构压成下面这张文字图：

```text
业务用户 / 审批人 / 运营 / 风控 / 合规
                │
                ▼
Agent / Copilot / App UI
                │
                ▼
Capability Gateway
  ├─ schema validation
  ├─ read/write separation
  ├─ authn/authz
  └─ audit envelope
                │
      ┌─────────┼─────────┐
      ▼         ▼         ▼
Workflow     Rule/Policy  Ontology Query/Action
Camunda /    OPA /        Jena / Foundry /
Temporal     deterministic object service
             functions
      │         │         │
      └─────────┼─────────┘
                ▼
Metadata / DQ / Glossary / Lineage
OpenMetadata
                │
                ▼
ERP / CRM / MES / WMS / DWH / APIs / Documents / Events
```

这张图里有 4 个关键原则：

1. Agent 不直接裸连底层系统
2. 本体不单独承担“正确性兜底”
3. 规则判断和高风险动作必须从 Prompt 里拿出来
4. 审计必须覆盖查询、判断、审批和执行整个链路

## 六层验证怎么搭

### 1. 业务语义验证层

这是最前面的业务验收层。

建议交付物至少有：

- competency questions 清单
- 关键对象词汇表
- 状态映射表
- 黄金样例集
- 业务 owner 签字确认

这一层回答的是：

- 本体是不是在表达真实业务，而不是技术人自己的抽象
- 哪些词是统一的，哪些词不能硬统一

### 2. 本体模型验证层

这一层建议分成“建模”和“约束校验”两部分。

建模建议：

- `Protégé` 负责高级 OWL 2 建模
- `WebProtégé` 负责多人协作、评审、变更跟踪

约束校验建议：

- 用 `SHACL` 定义对象形状、属性约束、关系约束
- 本地验证可以用 `pySHACL`
- 服务端或流水线验证可以用 `Apache Jena SHACL`

这层最重要的不是“类画得多漂亮”，而是约束能不能真正落成机器校验。

### 3. 数据质量验证层

企业级验证一定不能只看 ontology，不看数据质量。

建议至少接一层数据治理与质量能力：

- glossary
- lineage
- ownership
- test suites
- test cases

这层我更推荐接 `OpenMetadata`，因为它把 glossary、lineage、test definition、test suite、test case 放进了同一套治理视图里。

### 4. 规则与策略验证层

这一层负责把最终判断从“模型猜”变成“系统算”。

建议拆成两类：

- 业务资格和决策规则  
  用确定性函数或规则服务实现

- 权限、例外、发布条件、审批前置条件  
  用 `OPA` 这类 policy-as-code 组件实现

如果你的规则是高频变化、跨服务复用、合规要求高，这一层不要继续堆在 Prompt 里。

### 5. 流程与审批验证层

高风险动作必须过这一层。

如果你的场景里有：

- 人工审批
- 跨团队任务
- 表单补录
- 候选人 / 候选组
- 明确 BPMN 流程

更推荐 `Camunda 8`。

如果你的场景更像：

- 长事务
- 跨服务重试
- 强工程编排
- 代码优先
- 对“流程图可视化审批台”要求没那么高

更推荐 `Temporal`。

### 6. Agent 与运行时验证层

这一层的目标不是让模型更聪明，而是让模型更难越权和更容易复盘。

建议最少具备：

- 工具输入输出 schema
- 只读与写入能力分级
- 关键动作 proposal 模式
- 影子运行和人工对照
- 全链路审计日志
- 回放与回归验证

## 技术选型建议

不要先问“哪个产品最强”，先问“你最想先验证哪一层”。

| 主要目标 | 更推荐的路线 | 理由 |
|---|---|---|
| 先验证标准化语义建模与约束校验 | WebProtégé / Protégé + Jena / Fuseki + SHACL | 语义、约束、查询边界最清晰 |
| 先验证审批、任务和受控执行 | Camunda 8 + OPA + 轻量本体服务 | 人机协同和权限边界更强 |
| 先验证代码优先的长流程闭环 | Temporal + OPA + 轻量本体服务 | 持久执行和工程自治更强 |
| 先验证治理、血缘和数据可信度 | OpenMetadata + 本体层 | 能把 glossary、lineage、quality 接上 |
| 已经在 Foundry 生态 | Foundry Ontology + Actions + Functions | 对象、动作、函数和安全模型是一体的 |

## 我的默认推荐

如果你不是已经深度绑定某个平台，我的默认推荐是这套：

### 默认推荐栈

- 建模协作：`WebProtégé`
- 高级建模：`Protégé`
- 语义存储与查询：`Apache Jena / Fuseki`
- 本体约束校验：`SHACL + Jena SHACL`，开发侧可配 `pySHACL`
- 元数据与数据质量：`OpenMetadata`
- 策略控制：`OPA`
- 流程审批：`Camunda 8`
- Agent 接入：自建一层薄 `Capability Gateway`

### 为什么我更倾向这套

因为这套组合把几件最容易混在一起的责任拆开了：

- 本体负责统一业务对象和关系
- SHACL 负责结构与约束验证
- OpenMetadata 负责数据可信度与血缘
- OPA 负责策略边界
- Camunda 负责审批与执行路径
- Gateway 负责工具暴露、schema 校验和审计

这种拆法的好处不是“平台更多”，而是以后出问题时你能快速定位：

- 是语义模型错了
- 是数据质量错了
- 是策略错了
- 是流程错了
- 还是 Agent 调用了不该调的能力

## 什么情况下换路线

### 换成 Temporal

满足下面 3 条以上，可以优先考虑 `Temporal`：

- 工程团队很强，习惯 code-first
- 编排对象主要是微服务和异步任务
- 需要强重试、补偿、长时运行
- 人工审批不是核心矛盾
- 不想把流程中心放在 BPMN 建模工具里

### 换成 Palantir 路线

满足下面条件时，优先考虑 `Foundry Ontology`：

- 已经是 Foundry 客户
- 你要验证的是 operational ontology，而不是纯语义网工具链
- 想把对象、动作、函数、权限和应用开发放在同一平台里

这里有一个重要判断：

> 这条路线更适合验证“对象化运行”和“受控动作闭环”，不等于它在验证纯 OWL / RDF 标准路线本身。

## 企业级验证应该怎么推进

### Phase 0: 选一个高价值决策场景

不要从“企业总本体”开始，先从一个高价值闭环开始。

### Phase 1: 建最小验证资产

至少交付：

- 3 到 8 个核心对象
- 10 到 20 条 competency questions
- 5 到 15 条 SHACL shapes
- 5 到 10 条关键规则
- 1 到 3 个受控动作

### Phase 2: 跑影子验证

新链路不直接替代旧链路，而是并行跑：

- 旧系统结论
- 新本体链路结论
- 人工复核结论

把差异收集起来。

### Phase 3: 只开放受控动作

先开放：

- 发起申请
- 生成建议
- 进入审批

不要一开始就让 Agent 直接执行终态写入。

### Phase 4: 扩到第二个场景

第二个场景最有价值，因为它能验证：

- 对象是否可复用
- 规则边界是否稳定
- 你的架构是不是只是给第一个场景写了个专用中台

## 企业级验收指标

建议至少跟踪下面 6 组指标：

1. 语义指标  
   术语冲突数、状态映射数、对象复用率

2. 约束指标  
   SHACL 通过率、无效对象拦截率、非法关系拦截率

3. 数据指标  
   关键数据质量通过率、血缘覆盖率、owner 完整率

4. 决策指标  
   与人工 / 现行规则一致率、误判率、例外率

5. 流程指标  
   审批时长、人工接管率、回退率、执行成功率

6. 治理指标  
   审计覆盖率、证据完整率、规则版本可追溯率

## 这一页应该记住什么

只记住 6 句话：

1. 企业级验证不是验证“有没有本体文件”，而是验证语义、数据、规则、流程、Agent 是否形成可控闭环。
2. 本体负责统一业务对象和关系，但不单独承担全部正确性。
3. 企业级验证必须把 SHACL、数据质量、策略和 workflow 一起设计进去。
4. 默认推荐路线是标准语义层 + 治理层 + 策略层 + 审批层分层组合。
5. Camunda 8 更适合强审批和人机协同，Temporal 更适合代码优先和长时编排。
6. 如果已经在 Palantir 生态，优先验证 Foundry Ontology 的对象化运行闭环，而不是重复造一套平行平台。

## 参考资料

1. Protégé  
   https://protege.stanford.edu/

2. WebProtégé  
   https://github.com/protegeproject/webprotege

3. SHACL 1.2 Core  
   https://www.w3.org/TR/shacl12-core/

4. Apache Jena SHACL  
   https://jena.apache.org/documentation/shacl/

5. Apache Jena Fuseki  
   https://jena.apache.org/documentation/fuseki2/

6. OpenMetadata Data Quality  
   https://docs.open-metadata.org/v1.12.x/api-reference/data-quality

7. OpenMetadata Lineage  
   https://docs.open-metadata.org/v1.12.x/api-reference/lineage

8. Open Policy Agent  
   https://www.openpolicyagent.org/docs

9. Camunda 8 Processes  
   https://docs.camunda.io/docs/components/concepts/processes/

10. Camunda 8 Authorization  
    https://docs.camunda.io/docs/components/admin/authorization/

11. Temporal Documentation  
    https://docs.temporal.io/

12. Palantir Ontology Overview  
    https://www.palantir.com/docs/foundry/ontology/overview

13. Palantir Action Types Overview  
    https://www.palantir.com/docs/foundry/action-types/overview

14. Palantir Ontology System  
    https://www.palantir.com/docs/foundry/architecture-center/ontology-system
