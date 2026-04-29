# 10 Pilot Blueprint

## 先看结论

如果你现在想用一个真实业务来验证“本体到底值不值得做”，最稳的方式不是先做企业总本体，而是：

> 选一个高价值、可观测、跨系统、可受控写回的决策场景，做一个最小语义闭环试点。

这个试点要回答的不是“本体有没有哲学价值”，而是更现实的 4 个问题：

1. 决策是否更稳了？
2. 解释是否更清楚了？
3. 人工复核是否减少了？
4. 流程和 Agent 是否更容易围绕统一业务对象工作了？

## 第一件事：先定义你到底在验证什么

不要把目标写成：

- “建设本体平台”
- “统一企业语义”
- “做知识图谱”

这些目标太大，试点很容易失焦。

更好的验证目标应该长这样：

> 在某个真实业务决策场景里，用最小 Ontology 把跨系统业务对象、关系、规则和动作显式化，并验证它是否比当前做法更准、更稳、更可解释。

## 什么样的业务适合做试点

不是所有业务都适合拿来验证本体。

一个好的示例业务，最好同时满足下面 6 条里的 4 条以上：

### 1. 有明确决策

不是泛泛“看数据”，而是明确要回答：

- 能不能加急
- 能不能放行
- 要不要升级
- 应不应该审批通过

### 2. 涉及多个系统

至少跨两个来源：

- ERP
- CRM
- MES
- 工单系统
- 数仓
- 外部 API

如果只在单表里就能做完，未必需要本体。

### 3. 语义经常冲突

例如：

- 同一个“订单状态”在不同系统里含义不一致
- 同一个“客户等级”有多个口径
- 同一个“设备可用性”有不同定义

这通常是本体最能体现价值的地方。

### 4. 有可观测结果

最好能在 2 到 8 周内看到结果，比如：

- 审批时长下降
- 误判率下降
- 人工复核率下降
- 异常升级准确率提升

### 5. 有业务 owner

没有业务 owner 的试点很容易沦为技术演示。

至少要有人愿意确认：

- 规则对不对
- 对象定义对不对
- 动作边界对不对

### 6. 能形成最小闭环

闭环不要求很大，但至少要包含：

- 读事实
- 做判断
- 给解释
- 发起或执行一个受控动作

这才叫验证“可行”，否则只是建了个语义模型。

## 哪些业务最适合

优先级通常可以按下面排序：

### 第一梯队

- 订单是否允许加急发货
- 异常告警是否需要升级
- 工单是否允许跳级处理
- 检修作业是否允许放行
- 客户是否满足特殊审批条件

这些业务有几个共同点：

- 规则不简单
- 跨系统取数
- 状态语义容易冲突
- 决策结果需要解释

### 第二梯队

- 合同履约风险识别
- 售后赔付资格判断
- 供应商例外审批
- 产线停机处置优先级

### 不建议一开始拿来做试点的

- 全公司主数据统一
- 全企业知识图谱
- 纯搜索问答
- 完全没有动作出口的只读分析

这些要么太大，要么闭环不明显。

## 可行性验证怎么做

一个够用的试点流程通常分 7 步。

### 第一步：写清试点假设

格式可以直接写成：

> 如果我们把“订单加急资格”建成对象、关系、规则和动作的最小 Ontology，并接入 Agent / Workflow，那么人工判断时间会下降 30%，误判率会下降 20%，且每次判断都能给出可审计解释。

没有假设，后面就没法验收。

### 第二步：定义最小对象集

只保留支撑这个决策所必需的对象。

例如“订单加急”场景：

- `Order`
- `Customer`
- `Shipment`
- `Warehouse`
- `InventoryPosition`

不要一开始加：

- 全量产品层级
- 全量组织树
- 全量财务对象

### 第三步：定义关键关系和状态

例如：

- `Order -> Customer`
- `Order -> Shipment`
- `Shipment -> Warehouse`
- `Order -> InventoryPosition`

状态只保留对判断真的有影响的那部分。

### 第四步：抽规则

规则通常分三层：

1. 资格规则  
   例如库存是否足够、客户等级是否满足、是否命中禁运限制。

2. 约束规则  
   例如高风险订单必须人工审批。

3. 动作规则  
   例如只有满足条件时才能发起 `Request Expedite`。

### 第五步：定义受控动作

动作至少要有一个，不然很难形成闭环。

例如：

- `Request Expedite`
- `Approve Expedite`
- `Reject Expedite`

### 第六步：接应用和流程

这一步至少要做到：

- 人可以看到对象上下文
- Agent 可以查询对象和函数结果
- 高风险动作走 workflow 或审批

### 第七步：设定对照实验

把现有做法和试点做法并行跑一段时间。

至少对比：

- 平均决策耗时
- 人工复核比例
- 错判或回退比例
- 解释完整度
- 审计取证成本

## 成功指标怎么定

建议分成 4 组指标。

### 1. 业务指标

- 审批时长
- 异常处理时长
- 误判率
- 升级准确率
- SLA 达成率

### 2. 语义指标

- 同义字段归并数量
- 跨系统状态映射数量
- 规则显式化比例
- 被复用的对象 / 动作数量

### 3. Agent 指标

- 需要人工追问的次数
- 调错工具的次数
- 无法解释的结论占比
- 可直接执行的动作成功率

### 4. 治理指标

- 关键对象是否有 owner
- 规则是否可追溯
- 动作是否可审计
- 写操作是否都走受控入口

## 技术选型怎么做

技术选型不要先问“最强是什么”，先问“你在验证哪种本体路线”。

通常分 3 条路。

## 路线一：语义网标准优先

适合你当前最想验证的是：

- OWL / RDF / SHACL 这套方式是否真的能表达你的业务规则
- 你是否需要显式推理与一致性校验
- 你想低成本 PoC

### 推荐组合

- 建模：Protégé / WebProtégé
- 推理与程序接入：Owlready2
- RDF / SPARQL 服务：Apache Jena Fuseki
- 流程编排：n8n 或 Camunda
- 元数据治理：OpenMetadata 或现有目录平台
- 应用层：Python / TypeScript 最小服务

### 优点

- 标准明确
- 成本相对可控
- 很适合做“规则能不能被形式化表达”的验证

### 缺点

- 对工程团队要求更高
- 业务用户直接消费体验通常不如产品化平台
- 动作层和对象视图层需要你自己补

## 路线二：Operational Ontology 优先

适合你当前最想验证的是：

- 业务对象、动作、权限、应用、Agent 能否在一个平台里协同
- 你已经在 Palantir 生态里
- 你想验证的是产品化 operational ontology，而不是纯 OWL 工程

### 推荐组合

- 语义与动作层：Palantir Foundry Ontology
- 应用层：Object Views / Object Explorer / Workshop
- 程序接入：OSDK
- 流程与动作：Action Types + 平台内流程
- 数据接入：Foundry 数据服务与现有系统集成

### 优点

- 对象、动作、权限、应用、Agent 接得更顺
- 更适合验证“业务对象化 + 受控动作 + Agent 协同”
- 更接近大企业真实运行方式

### 缺点

- 平台前提更强
- 成本和组织门槛更高
- 不是标准语义网路线本身的直接验证

## 路线三：业务闭环优先

适合你当前最想验证的是：

- 业务闭环是否值得，而不是先验证 OWL 严格推理
- 你需要先向业务证明“对象化 + 动作化”的价值
- 你暂时没有 Palantir，也不想先上完整语义网栈

### 推荐组合

- 业务对象层：自定义 domain object service
- 规则层：Python / Java 规则服务
- 关系存储：Postgres + 图补充，或 Neo4j
- 流程层：n8n / Camunda / Temporal
- 元数据治理：OpenMetadata / Purview / 现有平台
- Agent 层：现有 LLM + 工具调用

### 优点

- 上手最快
- 最容易先做出业务闭环
- 对组织阻力最低

### 缺点

- 容易退化成“写了一层业务中台”
- 如果不注意，最后并没有真正验证 ontology，而只是做了对象服务

### 一个务实建议

如果你是第一次试点，我通常建议：

- 没有 Palantir：优先走“语义网标准优先”或“业务闭环优先”
- 已经在 Palantir：直接走“Operational Ontology 优先”

## 技术选型的决策表

| 问题 | 更推荐 |
|---|---|
| 先验证规则能否形式化表达 | Protégé + Owlready2 + Fuseki |
| 先验证业务对象 + 动作闭环 | 自定义对象服务 + Workflow |
| 已有 Palantir 基础设施 | Foundry Ontology |
| 需要多人协作建模 | WebProtégé |
| 需要轻量自动化试点 | n8n |
| 需要强流程治理与审批 | Camunda / Temporal |
| 需要目录、血缘、术语治理 | OpenMetadata / Purview |

## 推荐架构怎么搭

一个够用的试点架构通常长这样：

```text
业务用户 / 审批人 / 分析师
            │
            ▼
Agent / Copilot / App UI
            │
            ▼
Ontology Query & Action Layer
    ├─ object query
    ├─ rule / function evaluation
    └─ controlled actions
            │
     ┌──────┼──────┐
     ▼      ▼      ▼
Metadata   Workflow  Audit
Catalog    / Approval / Logs
            │
            ▼
ERP / CRM / MES / WMS / Data Warehouse / APIs
```

### 这一版架构里最关键的原则

1. Agent 不直接裸写底层系统
2. 关键动作必须有统一 action 入口
3. 元数据管理是旁路治理支撑，不是动作层替代品
4. 本体层必须站在真实业务对象上，不是站在源表上

## 示例业务需要什么条件才算闭环

一个试点业务，如果要形成真正闭环，至少要满足下面 5 个条件：

### 1. 有输入事实

能从真实系统读到数据，而不是手工造演示数据。

### 2. 有显式判断

不是开放式问答，而是可回答“能 / 不能 / 该 / 不该”的业务判断。

### 3. 有解释输出

系统必须能说明：

- 为什么这么判断
- 哪些对象和规则参与了判断

### 4. 有动作出口

至少能做到以下之一：

- 发起审批
- 创建工单
- 触发通知
- 提交受控变更

### 5. 有结果回流

你需要知道：

- 动作有没有执行
- 后果好不好
- 判断对不对

没有回流，就无法真正验证价值。

## 最大价值到底是什么

很多人会先想到：

- 知识更多
- 图谱更漂亮
- Agent 更聪明

但本体最大的价值，其实通常不是这些。

## 本体最大的价值

如果只保留一句，我会保留这句：

> 本体最大的价值，是把“企业里原本隐性的业务语义和决策依据”变成“可共享、可执行、可解释、可治理的运行时资产”。

把它拆开，就是 5 个直接收益：

### 1. 决策更稳

因为 Agent 和应用不再直接面对混乱表结构和口头规则。

### 2. 解释更强

因为结论不再只来自 Prompt，而是来自对象、关系、规则和动作。

### 3. 跨系统协同更顺

因为不同系统围绕同一组业务对象和状态工作。

### 4. 变更成本更低

规则不再散落在：

- Prompt
- SQL
- 前端判断
- 人工经验

### 5. Agent 更容易被治理

因为“能看什么、能做什么、通过什么动作做”可以被显式控制。

## 什么时候说明这条路不值得继续投

试点失败不一定是坏事，但要能识别失败信号。

以下情况通常说明要及时收缩：

- 业务规则其实很简单，单系统单表就能解决
- 业务 owner 无法稳定参与
- 没有动作出口，只能停在分析展示
- 没有可观测指标，无法证明改进
- 团队其实只是想做目录治理，不是真的要做对象与动作层
- 最后实现完全退化成普通中台服务，语义层没有独立价值

## 一个建议的 6 周试点节奏

### 第 1 周

- 确定场景
- 确定业务 owner
- 写试点假设
- 选最小指标

### 第 2 周

- 梳理对象、关系、状态
- 识别跨系统语义冲突
- 确定动作边界

### 第 3 周

- 建最小 ontology
- 建规则和函数
- 接真实数据读取

### 第 4 周

- 接 workflow / 审批
- 做最小 UI 或 Agent 工具面

### 第 5 周

- 跑并行验证
- 记录误判、追问、回退、人工接管

### 第 6 周

- 复盘指标
- 判断是否继续扩场景
- 判断是上更强标准栈、产品栈，还是止损

## 一个足够保守的推荐

如果你现在就要开始，我建议：

1. 先选“订单加急资格”或“异常告警升级”这类场景  
   因为最容易形成闭环。

2. 先做 3 到 5 个对象、1 到 3 个动作、1 到 2 个函数  
   不要追求完整。

3. 先让 Agent 负责查询、解释、发起动作  
   写操作仍走受控 workflow。

4. 用 6 周证明价值，而不是用 6 个月设计大图纸

## 参考资料

1. Protégé / WebProtégé  
   https://protege.stanford.edu/software.php

2. Owlready2 Documentation  
   https://owlready2.readthedocs.io/

3. Owlready2 Reasoning  
   https://owlready2.readthedocs.io/en/latest/reasoning.html

4. Apache Jena Fuseki  
   https://jena.apache.org/documentation/fuseki2/

5. Apache Jena Fuseki Configuration  
   https://jena.apache.org/documentation/fuseki2/fuseki-configuration

6. OpenMetadata Documentation  
   https://docs.open-metadata.org/latest

7. OpenMetadata Getting Started  
   https://docs.open-metadata.org/latest/quick-start/getting-started

8. n8n Docs  
   https://docs.n8n.io/

9. Temporal Docs  
   https://docs.temporal.io/

10. Camunda Platform Overview  
    https://camunda.com/platform/

11. Palantir Ontology Overview  
    https://www.palantir.com/docs/foundry/ontology/overview/

12. Palantir Ontology System  
    https://www.palantir.com/docs/foundry/architecture-center/ontology-system

13. Palantir Architecture Center Overview  
    https://www.palantir.com/docs/foundry/architecture-center/overview
