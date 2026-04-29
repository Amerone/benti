# 02 Modeling Method

## 快速路线

从零开始建一个业务本体，建议只走这 7 步：

1. 选场景
2. 定边界
3. 抽概念
4. 画关系
5. 写规则
6. 填事实
7. 做验证

## 最小示例：订单加急发货

### 先定义目标问题

不要问“大而全”的问题，先问一个能落地的问题：

> 订单 `A1024` 现在能否加急发货？

### 再抽核心概念

- `Order`
- `Customer`
- `VIPCustomer`
- `InventoryAllocation`
- `Shipment`

### 关系

- `Order -> hasCustomer -> Customer`
- `Order -> hasAllocation -> InventoryAllocation`
- `Shipment -> fulfills -> Order`
- `Shipment -> dependsOn -> InventoryAllocation`

### 属性

- `InventoryAllocation.qcPassed`
- `Order.requiredQty`

### 规则

- 可发货：订单存在库存占用，且库存占用已质检通过
- 可加急：订单可发货，且客户是 VIP

## 展开建模

### Step 1. 先定范围，不要贪大

错误做法：

- 一开始建“制造业总本体”
- 想把 ERP / MES / APS / CRM 全部统一

正确做法：

- 只围绕“订单加急发货”建最小语义闭环

### Step 2. 先抽业务概念，不要先看表字段

优先问：

- 业务里稳定存在的对象是什么？
- 哪些对象只是状态，哪些对象是实体？
- 哪些判断是业务规则，不是字段本身？

### Step 3. 先把关系讲清楚

很多错误不是“没字段”，而是“关系没讲清”。

例如：

- `Order` 有库存占用，不等于已经发货
- `ALLOCATED` 在不同系统里可能不是同一个业务语义

### Step 4. 把规则从经验变成显式约束

例如：

- 不是“客服一般这么回答”
- 而是“满足 X、Y、Z 条件时，订单属于可加急订单”

### Step 5. 用少量实例验证

可以先造两张订单：

- `order_A1024`：普通客户，质检未通过
- `order_A1025`：VIP 客户，质检通过

理想结果：

- 前者不应被推理为可加急
- 后者应被推理为可加急

## 深入一点

### 一个很实用的判断标准

如果某个规则满足下面任一条件，就值得进入本体层：

- 跨系统重复出现
- 经常被人解释错
- 影响关键决策
- 以后可能频繁变化
- 需要被 Agent、流程、人共同使用

### 一个常见误区

不要把“本体建模”理解成“把数据库表重新画一遍”。

数据库更关心：

- 怎么存
- 怎么查
- 怎么保证事务一致

本体更关心：

- 这在业务上到底是什么
- 与谁有关
- 在什么条件下成立
- 能推出什么

## 一个最小 Turtle 风格示意

```ttl
:order_A1025 a :Order ;
  :hasCustomer :customer_vip ;
  :hasAllocation :alloc_A1025 .

:customer_vip a :VIPCustomer .

:alloc_A1025 a :InventoryAllocation ;
  :qcPassed true .
```

如果你的规则已经定义为：

- 有库存占用且 `qcPassed = true` 的订单是 `ReadyToShipOrder`
- `ReadyToShipOrder` 且客户为 `VIPCustomer` 的订单是 `ExpediteEligibleOrder`

那么推理后就可以得到：

- `order_A1025 rdf:type ExpediteEligibleOrder`

这就是“规则 + 事实 -> 新结论”。
