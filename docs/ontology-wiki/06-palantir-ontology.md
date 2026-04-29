# 06 Palantir Ontology

## 先说结论

Palantir 语境里的 Ontology，不等于传统教材里的“一个 OWL 文件”。

它更接近：

> 面向企业运营的语义层 + 行为层 + 安全治理层。

Palantir 官方把它定义为组织的 operational layer，并强调它既包含：

- semantic elements：objects、properties、links
- kinetic elements：actions、functions、dynamic security

所以理解 Palantir Ontology，关键不是只盯着“概念建模”，而是要看到它把：

- 数据
- 业务语义
- 操作行为
- 权限治理
- 应用接入

放进了同一套产品语义里。

## 为什么它和传统语义网讨论不完全一样

在经典语义网视角里，我们通常会讨论：

- RDF
- OWL
- SHACL
- SPARQL
- 推理机

而在 Palantir 视角里，重点更像：

- 业务对象怎么定义
- 对象之间怎么关联
- 哪些动作允许被执行
- 这些动作写回哪些系统
- 不同角色、不同 Agent 能看见什么、能改什么
- 这些对象如何直接进入应用、分析和自动化

所以它不是否定传统本体方法，而是把本体工程产品化、运营化。

## Palantir Ontology 的核心积木

### Object Types

Object type 是“现实世界实体或事件”的类型定义。

例如：

- `Order`
- `Shipment`
- `Facility`
- `Aircraft`
- `Patient`

它不是数据库表名的简单重命名，更像业务世界里的稳定对象。

### Objects

Object 是 object type 的具体实例。

例如：

- 订单 `O-2026-0417-001`
- 航班 `MU5123-2026-04-17`

Palantir 官方会明确区分：

- type definition：类型定义
- object instance：具体对象

### Properties

Property 是对象的属性。

例如 `Order` 的：

- `status`
- `priority`
- `requestedDeliveryDate`
- `customerTier`

Palantir 的 property 不只是字段，还会带显示名称、类型、约束、可见性等元数据。

### Shared Properties

Shared property 是多个 object type 复用的属性定义。

适合放：

- `createdAt`
- `updatedAt`
- `location`
- `riskLevel`

价值在于统一语义，不让多个团队各自发明同义字段。

### Link Types

Link type 是 object type 之间关系的定义。

例如：

- `Order -> Shipment`
- `Employee -> Manager`
- `Flight -> Aircraft`

这让业务关系成为一等公民，而不是隐藏在外键和 join 里。

### Interfaces

Interface 描述多个 object type 共享的形状与能力。

例如你可以有一个 `Facility` interface，被以下 object type 实现：

- `Airport`
- `ManufacturingPlant`
- `Warehouse`

这样应用和工作流就能面向 interface 编写，而不是为每种对象单独写一套逻辑。

这是 Palantir 很重要的一层：它把“多态语义”直接做进了本体系统。

### Action Types

Action type 是一组业务变更的定义。

它不是“改一个字段”，而是“执行一个有业务意义的动作”。

例如：

- `Assign Employee`
- `Approve Shipment`
- `Expedite Order`
- `Escalate Incident`

一个 action type 往往同时包含：

- 用户输入参数
- 校验规则
- 对对象/属性/链接的修改
- 副作用
- 写回路径

这是 Palantir Ontology 和传统“静态知识模型”最大的区别之一。

### Functions

Functions 用来承载业务逻辑。

Palantir 的 functions 可以直接读写 ontology objects 和 links，所以它们不是普通 FaaS 的薄封装，而是和对象层深度绑定的逻辑层。

适合承载：

- 资格判定
- 派生指标
- 推荐结果
- 跨对象聚合逻辑
- 复杂写回前校验

## 一个更准确的理解框架

把 Palantir Ontology 压成一句话：

> 用对象表达世界，用链接表达关系，用动作表达业务操作，用函数表达业务逻辑，用安全策略控制谁能看到和改变什么。

这比“语义层”更完整。

## 和数字孪生的关系

Palantir 官方多次把 Ontology 描述成组织的 digital twin。

这里的重点不只是“有一个镜像”，而是：

- 镜像有业务语义
- 镜像可被搜索、分析、解释
- 镜像允许受控写回
- 镜像能驱动人和 Agent 的协作

因此它更像“可操作的数字孪生”。

## Palantir Ontology 的产品链路

官方文档反复强调，Ontology 不是孤立存在，而是深度连接应用层。

典型链路是：

1. 把数据源映射到 object types / links
2. 用 actions / functions 定义可执行业务能力
3. 用 Object Explorer 搜索和筛选对象
4. 用 Object Views 展示对象上下文
5. 用 Workshop / Quiver / 应用层消费这些对象与动作
6. 用 OSDK 在代码中读对象、执行 actions、调用 functions

这意味着：

- Ontology 是开发对象模型
- 也是操作员工作台背后的领域模型
- 也是 Agent 可调用的业务接口层

## 对 Agent 特别重要的点

如果你关心的是 Agent，不是每个概念都同样重要。

真正关键的是下面四件事：

### 1. Agent 不再只面对原始表结构

它面对的是：

- `Order`
- `Shipment`
- `Supplier`
- `Facility`

而不是：

- `ods_order_hdr`
- `dwd_ship_evt`
- `crm_customer_base`

这会显著降低语义错位。

### 2. Agent 可以调用“业务动作”而不是裸写接口

比如：

- 不让 Agent 直接 `PATCH status=approved`
- 而让它执行 `Approve Shipment`

这样更容易做：

- 参数校验
- 审批控制
- 审计追踪
- 统一副作用

### 3. Agent 可以围绕 interface 工作

如果多个对象都实现了 `Facility` 或 `Asset` interface，Agent 的工具调用面就会更稳定。

### 4. 安全不是外挂

Palantir 明确把安全放进 Ontology 体系，而不是让应用层自己补。

这对企业 Agent 非常关键，因为“能不能看见、能不能改”通常比“能不能回答”更重要。

## 对传统本体工程人员的一个提醒

如果你熟悉 RDF / OWL，进入 Palantir 语境后要切换一个观察角度：

- 不只关心类、公理、推理
- 还要关心动作、写回、权限、应用集成

如果你只把它理解成“另一种 ontology 建模工具”，会低估它的工程重心。

## 对产品和架构的一个提醒

如果你来自应用架构侧，也不要把 Ontology 理解成“更好看的主数据平台”。

它的关键增量不是把字段起了业务名字，而是把：

- 对象
- 关系
- 逻辑
- 动作
- 权限

装进同一个可复用、可接入、可治理的操作模型。

## 这一页应该记住什么

只记住 4 句就够了：

1. Palantir Ontology 是 operational layer，不只是知识描述层。
2. 它同时建模语义元素和 kinetic elements。
3. 它的重点是“对象化业务世界，并允许受控操作”。
4. 它天然面向应用、工作流和 Agent，而不是停留在知识建模文件。

## 参考资料

1. Palantir Ontology Overview  
   https://www.palantir.com/docs/foundry/ontology/overview/

2. Palantir Types Reference  
   https://www.palantir.com/docs/foundry/object-link-types/type-reference

3. Palantir Interfaces Overview  
   https://www.palantir.com/docs/foundry/interfaces/interface-overview

4. Palantir Architecture Center: The Ontology system  
   https://www.palantir.com/docs/foundry/architecture-center/ontology-system
