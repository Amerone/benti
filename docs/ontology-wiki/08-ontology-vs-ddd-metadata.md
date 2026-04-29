# 08 Ontology vs DDD vs Metadata Management

## 先给结论

这三者不是一回事，而且通常不在同一层解决问题。

可以先记成：

- DDD 主要解决：软件系统如何围绕业务语义来设计
- 元数据管理主要解决：数据资产有什么、从哪来、怎么被治理
- 企业本体 / Palantir Ontology 主要解决：业务对象、关系、动作、规则，如何成为可共享、可执行、可治理的运行时语义层

如果把它们混成一个词，后面就很容易出现两类误判：

- 以为做了数据目录就等于做了本体
- 以为做了领域建模就等于解决了跨系统共享语义

## 一张总表

| 维度 | DDD | 元数据管理 | 企业本体 / Palantir Ontology |
|---|---|---|---|
| 核心目标 | 让软件模型贴近业务 | 管理数据资产与治理上下文 | 统一业务对象、关系、动作、规则 |
| 主要对象 | 实体、值对象、聚合、领域服务、限界上下文 | 资产、字段、血缘、分类、术语、目录 | Object、Link、Interface、Action、Function |
| 主要服务谁 | 开发团队、架构团队 | 数据治理团队、数据平台团队、分析用户 | 业务、应用、分析、Agent、开发团队 |
| 主要落点 | 代码结构与服务边界 | 目录、血缘、质量、权限、发现 | 运营语义层、应用对象层、动作层 |
| 是否直接面向动作 | 有，但多数在代码里 | 通常较弱 | 很强，动作是核心一等公民 |
| 是否适合直接给 Agent 用 | 间接 | 通常不够直接 | 非常适合 |
| 典型产物 | 限界上下文图、领域模型、聚合规则 | 数据目录、血缘图、业务术语表、数据质量规则 | 对象模型、关系模型、动作模型、对象视图、应用 SDK |

## 它和 DDD 的区别

### DDD 的重点是“软件该怎么设计”

DDD 最关心的是：

- 业务能力怎么切分
- 限界上下文怎么划分
- 通用语言如何进入代码
- 聚合边界怎么控制一致性
- 领域规则应该由谁维护

也就是说，DDD 的主要战场在：

- 代码模型
- 服务边界
- 团队协作语义

### Ontology 的重点是“业务世界如何被共享表达和操作”

企业本体更强调：

- 什么是稳定的业务对象
- 对象之间怎么关联
- 哪些规则和状态应该被显式化
- 哪些动作可以被统一执行
- 人、应用、Agent 如何共享这套语义

所以两者最大的差异不是“都在讲业务”，而是：

- DDD 偏系统内部设计
- Ontology 偏跨系统共享语义和运行时操作模型

### 一个关键差异：DDD 不追求全局统一模型

Martin Fowler 对 Bounded Context 的解释很明确：DDD 通过限界上下文把大模型拆开，避免全系统强行共用一个统一模型。

这和很多企业做 Ontology 时的天然冲动不一样。

做本体的人常常会倾向于：

- 统一客户
- 统一订单
- 统一资产
- 统一事件

这件事有价值，但也有风险：

- 过度统一会抹平不同上下文的真实差异
- 把多个局部真相硬压成一个“企业大真相”，反而会失真

所以更稳妥的做法通常是：

> 用 DDD 保住各业务上下文内部模型的正确性，再用 Ontology 为跨系统决策、搜索、分析、Agent 协作抽取共享语义层。

### 什么时候该优先用 DDD

如果你的主要问题是：

- 服务边界混乱
- 代码模型贫血
- 业务规则散落在控制器和 SQL 里
- 团队说不清“订单”和“发运单”是不是同一个东西

那优先级通常是 DDD。

因为这时问题首先出在：

- 应用设计
- 领域边界
- 代码表达

而不是本体平台本身。

## 它和元数据管理的区别

### 元数据管理的重点是“把数据管明白”

元数据管理常见关注点是：

- 资产目录
- 字段定义
- 血缘关系
- 分类分级
- 业务术语
- 权限与治理
- 数据质量

这套能力非常重要，但它主要回答的是：

> 数据资产是什么、在哪里、由谁负责、能不能信。

### Ontology 还要继续回答“业务对象能做什么”

企业本体不只要知道：

- 哪张表里有订单
- 订单字段是什么意思

还要继续定义：

- 什么是 `Order`
- 什么是 `Shipment`
- `Order -> Shipment` 关系怎么表达
- 哪些状态迁移是合法的
- 什么动作算“批准”“加急”“升级”
- 这些动作如何被应用、工作流、Agent 复用

所以两者的区别可以压成一句话：

> 元数据管理更像“知道数据是什么”；Ontology 更像“知道业务对象是什么、处于什么关系、能执行什么动作”。

### 元数据管理通常停在“描述与治理”

典型元数据平台很擅长：

- 发现资产
- 展示血缘
- 维护 glossary
- 管理标签、分类、质量

但它通常不会天然提供：

- 运营动作模型
- 对象级业务函数
- Agent 可直接消费的统一业务动作面

这正是 Palantir Ontology 这类路线和数据目录产品最不一样的地方。

### 什么时候该优先做元数据管理

如果你的主要问题是：

- 大家找不到数据
- 口径不清
- 血缘不透明
- 列级解释混乱
- 数据质量和归属不清

那优先级通常是元数据管理。

因为这时最缺的是：

- 可发现性
- 可追溯性
- 可治理性

而不是动作建模。

## 三者的重叠点

虽然它们不同，但不是完全无交集。

### DDD 和 Ontology 的重叠

共同点：

- 都重视业务语义
- 都反对只按数据库结构思考
- 都强调命名和概念边界

不同点：

- DDD 更偏每个上下文内部的一致模型
- Ontology 更偏跨上下文共享与外部消费

### 元数据管理和 Ontology 的重叠

共同点：

- 都会涉及术语、分类、关系、上下文
- 都会讨论标准化和治理

不同点：

- 元数据管理偏资产视角
- Ontology 偏业务对象与动作视角

### DDD 和元数据管理的重叠

共同点：

- 都可能讨论通用语言
- 都要求概念一致

不同点：

- DDD 关心代码与服务设计
- 元数据管理关心数据资产与治理

## 一个更实用的架构分工

如果你在做企业 AI / Agent / 数据平台，比较稳妥的分工通常是：

1. 用 DDD 设计业务系统  
   保证每个服务或上下文内的模型、规则、聚合、边界清楚。

2. 用元数据管理治理数据资产  
   管好数据目录、血缘、质量、分类、术语、责任人。

3. 用 Ontology 提供跨系统语义与操作层  
   把对象、关系、规则、动作暴露给分析、应用、人和 Agent。

这个分工有一个好处：

- DDD 不被迫承担全企业知识地图的任务
- 元数据平台不被迫承担运营动作编排的任务
- Ontology 不被迫回头替代软件边界设计

## 放到 Palantir 语境里怎么理解

在 Palantir 里，Ontology 的独特点主要体现在：

- object types：不是数据表，而是业务对象
- link types：不是 join，而是业务关系
- interfaces：不是代码接口，而是跨对象语义能力面
- action types：不是裸写 API，而是业务动作
- functions：不是零散脚本，而是围绕对象的业务逻辑

所以如果你拿它去和：

- DDD 的聚合
- 元数据平台的 glossary / lineage / catalog

做一比一映射，通常都会映射歪。

更准确的理解应该是：

> Palantir Ontology 同时吃到了部分领域建模价值，也吃到了部分元数据治理价值，但它真正的定位仍然是 operational ontology，而不是 DDD 工具，也不是纯 metadata catalog。

## 一个判断优先级的简单方法

### 优先做 DDD

当你最痛的是：

- 软件设计失控
- 领域规则散落
- 服务边界混乱

### 优先做元数据管理

当你最痛的是：

- 找不到数据
- 不知道能不能信
- 不知道是谁负责
- 血缘和口径不清

### 优先做 Ontology

当你最痛的是：

- 多系统对同一个业务对象定义不一致
- 决策依赖跨系统关系和规则
- Agent 需要围绕业务对象和动作稳定工作
- 你需要可解释、可治理的对象级操作语义

## 这一页应该记住什么

只记住 5 句：

1. DDD 主要解决软件设计边界，不直接等于企业本体。
2. 元数据管理主要解决数据资产治理，不直接等于业务对象操作层。
3. 企业本体 / Palantir Ontology 更像跨系统共享的业务对象与动作语义层。
4. 三者可以互补，最稳的方式是分层协作，而不是互相替代。
5. 如果你的目标是让 Agent 稳定操作业务对象，Ontology 的直接价值通常高于单纯 glossary 或代码模型。

## 参考资料

1. Martin Fowler: Bounded Context  
   https://martinfowler.com/bliki/BoundedContext.html

2. Microsoft Learn: Use Domain Analysis to Model Microservices  
   https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis

3. Microsoft Learn: Use Tactical DDD to Design Microservices  
   https://learn.microsoft.com/en-us/azure/architecture/microservices/model/tactical-domain-driven-design

4. Microsoft Learn: Design a Microservice Domain Model  
   https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/microservice-domain-model

5. DAMA International: DAMA-DMBOK  
   https://dama.org/learning-resources/dama-data-management-body-of-knowledge-dmbok/

6. DAMA International: What is Data Management?  
   https://dama.org/about-dama/what-is-data-management/

7. Microsoft Purview Unified Catalog  
   https://learn.microsoft.com/en-us/purview/what-is-data-catalog

8. Microsoft Purview Data Governance Glossary  
   https://learn.microsoft.com/en-us/purview/purview-glossary

9. OpenMetadata Documentation  
   https://docs.open-metadata.org/latest

10. OpenMetadata Getting Started  
    https://docs.open-metadata.org/latest/quick-start/getting-started
