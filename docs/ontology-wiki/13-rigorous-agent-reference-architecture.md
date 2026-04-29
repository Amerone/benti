# 13 Rigorous Agent Reference Architecture

## 先看一句话

如果你的场景对数据正确性、审计、审批、合规要求高，那么最稳的 Agent 架构不是：

- 一个大模型
- 一堆通用工具
- 一套长 Prompt

而是：

> 一个把语言能力、事实能力、规则能力、动作能力、审计能力明确分层的系统。

## 一张参考架构图

先把整体压成一张文字图：

```text
用户 / 操作员 / 审批人
          │
          ▼
Chat / Copilot / App UI
          │
          ▼
LLM Orchestrator
  ├─ 意图理解
  ├─ 参数收集
  ├─ 工具选择
  └─ 结果解释
          │
          ▼
Capability Gateway
  ├─ MCP tools
  ├─ Skills wrappers
  ├─ schema validation
  ├─ authz / rate limit
  └─ read/write separation
          │
   ┌──────┼───────────────┬───────────────┐
   ▼      ▼               ▼               ▼
Ontology  Rule Engine     Workflow        Audit / Replay
Layer     / Deterministic / Approval      / Observability
          Functions
   │      │               │               │
   └──────┴───────┬───────┴───────────────┘
                  ▼
          Source Systems / Data Services
      ERP / CRM / MES / WMS / DWH / APIs
```

这张图的核心思想只有一个：

- LLM 在最上面做语言编排
- 正确性在下面几层兜底

## 为什么要这么分层

因为在严谨数据场景里，最危险的设计通常是：

- 让模型自己决定查什么、怎么算、怎么改
- 工具过于泛化
- 没有规则层
- 没有审批层
- 没有审计层

这类方案短期看很快，长期很难信任。

## 每一层具体做什么

## 1. Chat / Copilot / App UI

这是用户入口。

它负责：

- 接收问题
- 展示解释
- 展示证据
- 展示待审批动作

它不负责：

- 直接做业务判断
- 直接落高风险写操作

## 2. LLM Orchestrator

这是模型所在层。

它最适合做 4 件事：

- 把自然语言转成任务意图
- 收集缺失参数
- 规划调用顺序
- 把结构化结果翻译成自然语言

它不适合做：

- 最终事实计算
- 最终规则判定
- 直接修改关键业务状态

### 一个实用原则

让这一层只输出三类东西：

1. 查询计划  
2. 动作提案  
3. 解释文本

而不要让它直接输出：

- 最终业务事实
- 最终金额
- 最终状态变更

## 3. Capability Gateway

这一层非常关键，但经常被忽略。

它是 Agent 和工具之间的防火墙。

它负责：

- 工具注册
- 输入输出 schema 校验
- 权限和租户边界
- 限流
- 超时
- 工具分级
- 读写分离
- 工具审计

### 为什么需要它

如果没有这一层，LLM 往往会直接面对一堆松散工具：

- 工具命名不统一
- 返回格式不统一
- 风险等级不统一

最后模型就会在“工具海洋”里漂。

### 这一层最重要的设计原则

#### 原则一：能力命名必须业务化

尽量暴露：

- `get_order_context`
- `evaluate_release_eligibility`
- `request_override`

不要暴露：

- `run_sql`
- `call_api`
- `execute_script`

#### 原则二：所有工具都要有 schema

至少要明确：

- 参数类型
- 必填字段
- 返回结构
- 错误码
- 风险等级

#### 原则三：读写强分离

例如把工具分成：

- `read_only`
- `decision_support`
- `write_proposal`
- `approved_execution`

这样系统可以根据风险等级决定是否允许模型调用。

## 4. Ontology Layer

这一层负责统一业务对象和动作语义。

它通常提供：

- object query
- object relationships
- object-centric context
- action definitions
- function bindings

在这里，模型不再面对：

- 乱七八糟的表
- 模糊的状态码
- 隐性的跨系统关系

而是面对：

- `Order`
- `Shipment`
- `Customer`
- `ReleaseDecision`

### 为什么这层对严谨性有帮助

因为它把“查什么”和“围绕什么判断”稳定下来了。

模型最容易错的，不只是算错，而是语义拿错。

本体层的价值就是降低这种语义错位。

## 5. Rule Engine / Deterministic Functions

这是正确性最硬的一层之一。

所有关键判断最好在这里做。

例如：

- 是否满足加急资格
- 是否允许放行
- 是否命中合规限制
- 风险等级如何计算

### 这一层怎么实现

实现形式可以很多：

- SQL
- Python / Java 服务
- policy engine
- ontology functions
- 规则引擎

形式不是重点，重点是：

> 它必须是确定性的、可测试的、可版本化的。

### 这一层必须输出什么

不只输出结论，还要输出：

- 命中的规则
- 规则版本
- 关键证据
- 失败原因

## 6. Workflow / Approval

这一层是风险控制层。

它负责：

- 审批
- 双阶段提交
- 人工确认
- 超时处理
- 异常回退

一个稳妥的模式通常是：

1. LLM 发起动作提案  
2. 规则层校验  
3. Workflow 判断是否需要人工审批  
4. 通过后执行动作  

### 这一层特别重要的原因

因为很多事故不是“查错了”，而是“改错了”。

Workflow 就是防止模型从建议者直接滑向执行者。

## 7. Audit / Replay / Observability

如果你需要严谨性，这一层不能省。

它至少要记录：

- 用户输入
- 模型响应
- 调用过哪些工具
- 每个工具返回了什么
- 使用了哪个规则版本
- 最终是否执行动作
- 谁审批了动作

### 为什么它不是可选项

没有这一层，你只能知道“出错了”。

有了这一层，你才能知道：

- 哪一步错了
- 是数据错、规则错，还是模型错
- 能不能复现

## 8. Source Systems / Data Services

这一层是事实源头。

它负责：

- 提供权威数据
- 承接最终写回

注意一个关键原则：

> 模型不应直接连接这里做自由查询和自由写入。

它应该经过：

- ontology layer
- gateway
- rule layer
- workflow

之后再接触底层系统。

## 一个推荐的调用流

以“订单是否允许加急”为例，推荐的数据流如下：

```text
用户：订单 O-1024 能不能加急？
  ↓
LLM 识别意图：需要查询订单上下文 + 资格判断
  ↓
Gateway 调用 get_order_context(order_id)
  ↓
Gateway 调用 evaluate_expedite_eligibility(order_id)
  ↓
规则层返回：
  eligible=false
  reasons=[inventory_shortage, customer_tier_not_eligible]
  rule_version=expedite-v3
  snapshot_time=...
  ↓
LLM 生成解释
  ↓
如用户要求申请例外：
  ↓
LLM 只能发起 request_override(order_id, reason)
  ↓
Workflow 审批
  ↓
通过后执行受控 action
  ↓
全链路写入 audit log
```

这个流里，LLM 没有负责：

- 直接算库存
- 直接判断资格
- 直接改订单状态

所以整体会稳很多。

## 能力分级建议

建议把可调用能力分成 4 级。

### Level 1: Read

只读查询。

例如：

- 查对象
- 查上下文
- 查状态

### Level 2: Evaluate

只做确定性判定，不改数据。

例如：

- 资格判断
- 风险评分
- 合规校验

### Level 3: Propose

允许模型发起动作提案，但不直接执行。

例如：

- 发起审批
- 提交申请
- 生成处置建议

### Level 4: Execute

最终执行层。

这一层通常要求：

- 审批完成
- 权限验证
- 幂等控制
- 审计记录

很多场景下，不建议让 LLM 直接拥有 Level 4 权限。

## 最小可落地版本怎么搭

如果你现在就要做一个最小版本，建议按下面搭。

### 最小 1 版

- LLM：做意图理解和解释
- Gateway：做 schema 校验和工具代理
- 规则服务：做最终判断
- Workflow：先用最简单审批流
- Audit：先完整记录 JSON 日志

### 可以先不做太重的东西

- 不一定先上复杂本体平台
- 不一定先上复杂 BPM 套件
- 不一定先做全企业统一对象

但下面这几个不要省：

- 窄工具
- 结构化返回
- 确定性规则
- 审计日志

## 常见反模式

### 反模式一：万能 SQL 工具

模型拿到任意 SQL 后，短期很强，长期很危险。

### 反模式二：规则写在 Prompt 里

Prompt 可以辅助解释，但不适合承载高风险最终规则。

### 反模式三：查和改都走一个工具

这会让权限边界和风险边界非常模糊。

### 反模式四：只记录模型回答，不记录调用链

这样出了问题根本没法追。

### 反模式五：没有版本号

如果规则版本、工具版本、对象定义版本都不留，后面很难复盘。

## 和本体结合时，最好的位置是什么

如果你有本体层，这套架构会更顺，因为本体刚好适合放在：

- LLM 之下
- 规则层之前
- Workflow 之上

也就是这个位置：

```text
LLM
 ↓
Ontology objects / actions / context
 ↓
Deterministic rules
 ↓
Workflow
 ↓
Execution
```

这是一个很实用的组合：

- 本体解决语义稳定
- 规则层解决判断稳定
- workflow 解决执行稳定

## 这一页应该记住什么

只记住 6 句：

1. 严谨 Agent 架构必须分层，不能把所有责任压给 LLM。
2. Gateway 是工具调用面的防火墙，不能省。
3. Ontology 层负责稳定语义，不负责最终正确性裁决。
4. 最终正确性应尽量由确定性规则层承担。
5. 高风险动作必须经过 workflow / approval。
6. 没有 audit / replay，就谈不上真正可控。
