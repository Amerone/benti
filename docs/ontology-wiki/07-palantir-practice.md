# 07 Palantir Practice

## 先看落地心法

Palantir Ontology 的实战，不是先把所有对象都建出来。

更好的方式是：

> 从一个高价值运营动作出发，反推对象、关系、接口、动作、函数和应用接入。

也就是说，起点应该是：

- “谁在做决策”
- “决策依赖哪些对象”
- “决策后要触发什么动作”

而不是：

- “我们有哪些表”
- “我们先把所有字段搬进去”

## 一条最小落地路径

### 第一步：挑一个垂直场景

优先选择同时满足以下条件的场景：

- 决策频繁
- 语义经常混乱
- 涉及多个系统
- 结果需要审计

典型例子：

- 订单是否允许加急
- 设备是否允许停机检修
- 告警是否需要升级处置
- 客户是否满足特殊审批资格

### 第二步：先建对象，不先建报表

围绕场景定义最少对象：

- `Order`
- `Shipment`
- `Warehouse`
- `Customer`
- `InventoryPosition`

对象命名要面向业务使用者，不要面向源系统。

### 第三步：补关系，而不是堆字段

比起无止境加属性，更关键的是补齐：

- `Order -> Customer`
- `Order -> Shipment`
- `Shipment -> Warehouse`
- `Order -> InventoryPosition`

因为很多运营判断，本质上来自关系网络而不是单行记录。

### 第四步：把“动作”建成 action types

例如：

- `Expedite Order`
- `Approve Override`
- `Assign Warehouse`

动作应该表达业务意图，不应该只是 CRUD。

好的动作名通常是：

- 面向角色
- 面向业务后果
- 面向流程节点

不好的动作名通常是：

- `UpdateStatus`
- `EditRow`
- `ChangeField`

### 第五步：把复杂判断放进 functions

适合放进 functions 的逻辑包括：

- 是否满足加急条件
- 是否存在冲突库存
- 是否违反 SLA
- 是否命中黑名单/禁运规则

函数的价值在于把复杂判定从前端、Prompt、脚本碎片里抽出来。

### 第六步：把对象暴露给应用和 Agent

在 Palantir 的推荐链路里，常见消费面包括：

- Object Explorer：找对象、筛对象、批量执行动作
- Object Views：把对象上下文组织成一个稳定入口
- Workshop：做面向业务用户的应用界面
- OSDK：在代码里直接读对象、调用动作、调用函数

## 实战时最容易犯的错

### 错误一：按源表一比一建 object types

这会得到一套“好看的数据目录”，但不是业务本体。

后果通常是：

- 对象太碎
- 关系不稳
- 应用代码仍然要理解底层表逻辑

### 错误二：把 action type 退化成字段编辑器

如果 action 只是为了改字段，那业务语义和校验逻辑还是散在各处。

更合理的做法是：

- 把“业务上发生了什么”建成动作
- 把“允许不允许、改哪些对象、触发哪些副作用”固化进去

### 错误三：用一个 God Object 装一切

比如把客户、订单、履约、账单、工单全压进一个超级对象。

这会让：

- 权限很难分
- 应用很难复用
- 状态语义互相污染

### 错误四：让 Agent 直接做关键状态变更

更稳妥的做法是：

- Agent 负责识别意图、收集参数、解释结果
- 真正写操作走 action types
- 关键动作仍保留审批或策略控制

### 错误五：忽略 interface 设计

当多个 object type 共享同类能力时，不建 interface 会让应用层和 Agent 工具面快速碎裂。

## Palantir 官方实战链路

根据官方 Developer Console 和 OSDK 文档，一条典型开发链路是：

1. 在 Developer Console 创建应用
2. 选择要暴露的 Ontology 资源
3. 生成 OSDK
4. 在 TypeScript / Python / Java 中安装 SDK
5. 初始化客户端并访问对象、actions、functions
6. 用 React 或其他应用层框架构建界面
7. 部署到 Foundry 托管或外部环境

这条链路的关键价值在于：

- 应用拿到的是业务对象 API，而不是通用低层 API
- 权限范围跟着应用和 Ontology 资源走
- 文档和类型可以按应用范围生成

## OSDK 应该怎么理解

OSDK 不是普通 SDK 包装器。

它更像：

> 从你的 Ontology 自动长出来的一层 typed application API。

Palantir 官方强调：

- 平台 SDK 更通用，适合直接调用 Foundry APIs
- OSDK 更贴近 Ontology，适合围绕对象和动作做应用开发

所以如果你的场景核心是“读写业务对象”，OSDK 通常是更自然的入口。

## 一个务实的应用开发路径

如果你要做一个最小试点，我建议按下面顺序：

1. 选一个单场景
2. 定义 3 到 5 个 object types
3. 定义关键 link types
4. 定义 1 到 3 个 action types
5. 把最关键的资格判定写成 function
6. 先用 Object Explorer 验证对象与动作可用
7. 再做 Object View
8. 最后用 OSDK 做一个最小应用或 Agent 工具封装

这个顺序的好处是：

- 先验证语义与行为模型
- 再投入 UI 和集成开发

## 一个最小试点模板

### 场景

订单是否允许加急发货。

### 对象

- `Order`
- `Customer`
- `Shipment`
- `Warehouse`
- `InventoryPosition`

### 关系

- `Order -> Customer`
- `Order -> Shipment`
- `Shipment -> Warehouse`
- `Order -> InventoryPosition`

### 动作

- `Request Expedite`
- `Approve Expedite`
- `Reject Expedite`

### 函数

- `isEligibleForExpedite(order)`
- `calculateExpediteRisk(order)`

### Object View 重点

- 当前订单状态
- 客户等级
- 库存占用情况
- 承运限制
- 历史加急记录

### Agent 接入方式

- Agent 先查询对象与函数结果
- 再解释是否可加急
- 如需写入，调用 `Request Expedite` 或 `Approve Expedite`

这就是一个典型的“Palantir 风格 operational ontology”最小闭环。

## 可参考的公开资料

### 官方文档

1. Ontology Overview  
   https://www.palantir.com/docs/foundry/ontology/overview/

2. Action Types Overview  
   https://www.palantir.com/docs/foundry/action-types/overview/

3. Functions on Objects  
   https://www.palantir.com/docs/foundry/functions/functions-on-objects/

4. Object Views Overview  
   https://www.palantir.com/docs/foundry/object-views/overview

5. Object Explorer Overview  
   https://www.palantir.com/docs/foundry/object-explorer/overview

6. Developer Console: Create a new OSDK application  
   https://www.palantir.com/docs/foundry/ontology-sdk/create-a-new-osdk/

7. OSDK React Applications Overview  
   https://www.palantir.com/docs/foundry/ontology-sdk-react-applications/overview

8. Dev Toolchain Overview  
   https://www.palantir.com/docs/foundry/dev-toolchain/overview/

### 公开代码与示例

9. palantir/ontology-starter-react-app  
   https://github.com/palantir/ontology-starter-react-app

10. palantir/osdk-ts  
    https://github.com/palantir/osdk-ts

11. palantir/defense-sdk-examples  
    https://github.com/palantir/defense-sdk-examples

12. Build With Palantir's Defense Ontology  
    https://www.palantir.com/docs/defense-ontology/api

## 这一页应该记住什么

只记住 5 句：

1. 从业务动作反推 Ontology，比从源表正推更有效。
2. Action type 应该表达业务动作，不该退化成字段修改。
3. Function 适合承载复杂业务判定。
4. OSDK 让应用围绕业务对象开发，而不是围绕底层 API 开发。
5. 最小试点要先跑通“对象 + 关系 + 动作 + 函数 + 应用入口”的闭环。
