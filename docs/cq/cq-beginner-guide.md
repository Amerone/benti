# CQ 初学者说明：它在本系统里负责什么

本文面向第一次接触本项目、CQ 和本体的人。读完后，你应该能回答三个问题：

- CQ 在这个系统里是什么。
- CQ 应该承担什么职责。
- 本系统从“业务数据录入”到“判定解释”的流程是怎么走的。

## 1. 先用一句话理解 CQ

CQ 是 competency question，通常翻译成“胜任力问题”。

在本系统里，可以先把 CQ 理解成：

> 用业务人员能看懂的问题，反过来验证本体、数据、推理和问答链路是否真的能支撑业务。

例如：

```text
M007 为什么 Fail？
M009 为什么 Pass？
```

这类问题看起来像普通提问，但在系统里不是随口问一句。每个 CQ 都会绑定：

- 一句业务问题。
- 一个受控意图，例如 `why_fail` 或 `why_judgement`。
- 一段 SPARQL 查询。
- 一组期望结果。
- 一组必须能提供的 evidence 字段。
- 一个 QA 示例问题。

所以 CQ 不是“问答样例”，而是一份可执行的业务验收契约。

## 2. 本系统解决的业务问题

这个项目是“制造业试验数据管理本体 MVP”。它现在聚焦一个很小但完整的闭环：

1. 工艺或质量人员维护试验对象、参数和规格。
2. 系统记录某个批次里的测量值。
3. 系统根据当前规格上下限做确定性判定。
4. 系统把判定结果和证据写回图数据库。
5. 规格变化时，系统可以重算历史测量并给出影响。
6. 用户可以问“为什么这样判”，系统从图里取证据再解释。

第一批 CQ 聚焦“测量判定”这条链路：

| CQ | 业务问题 | 演示数据 | 期望判定 |
| --- | --- | --- | --- |
| `CQ-MJ-001` | `M007 为什么 Fail？` | `cq_temperature=197.2`，规格 `180 ~ 195` | `Fail_High` |
| `CQ-MJ-002` | `M008 为什么 Fail？` | `cq_temperature=179.1`，规格 `180 ~ 195` | `Fail_Low` |
| `CQ-MJ-003` | `M009 为什么 Pass？` | `cq_temperature=188.0`，规格 `180 ~ 195` | `Pass` |

这里的 `cq_temperature` 是 CQ 专用参数，目的是让验收数据不要误伤真实业务里的 `temperature` 参数、规格或测量。

## 3. 本系统的业务流程怎么走

下面按一条测量数据从进入系统到被解释的过程讲。

### 3.1 加载本体

本体定义“业务世界里有什么”。

在本项目里，本体会定义这些核心概念：

| 概念 | 大白话解释 |
| --- | --- |
| `Trial` | 一次试验 |
| `Batch` | 试验中的批次 |
| `Parameter` | 被测参数，例如温度、压力 |
| `Specification` | 参数规格，例如上下限 |
| `Measurement` | 一条实际测量值 |
| `Result` | 对测量值的判定结果 |

对应代码主要在：

- `mvp/ontology/manufacturing-trial.ttl`
- `mvp/core/graph.py`

### 3.2 注册参数

系统先知道有哪些参数可以被记录，例如：

```text
temperature
cq_temperature
vibration_frequency
```

参数不是随便一个字符串，它至少要有编码、名称、单位、值类型、是否参与推理等信息。

对应接口：

```text
POST /api/v1/parameters
GET  /api/v1/parameters
```

### 3.3 创建规格

规格告诉系统“什么范围算合格”。

例如：

```text
cq_temperature
Spec_v1
lower = 180
upper = 195
```

同一个参数可以有多个规格版本。规格发生变化时，系统会创建新版本，例如 `Spec_v2`，而不是直接覆盖旧规格。

对应接口：

```text
POST /api/v1/specifications
POST /api/v1/specifications/change
```

### 3.4 创建试验、批次和测量

业务上，一条测量值不会孤立存在。它属于某个批次，批次属于某个试验。

简化后可以这样理解：

```text
Trial T001
  -> Batch B03
     -> Measurement M007
        -> Parameter cq_temperature
        -> Value 197.2
```

对应核心写入逻辑在 `mvp/core/graph.py`：

- `create_trial`
- `create_batch`
- `create_measurement`
- `create_and_infer`

### 3.5 执行确定性判定

当测量值写入后，系统会找这个参数的最新规格，然后执行确定性判定。

判定规则在 `mvp/core/inference.py` 中：

| 条件 | 结果 | 规则名 | 偏差 |
| --- | --- | --- | --- |
| 测量值低于下限 | `Fail_Low` | `Rule_Fail_Low` | `lower - value` |
| 测量值高于上限 | `Fail_High` | `Rule_Fail_High` | `value - upper` |
| 测量值在范围内 | `Pass` | `Rule_Pass` | `0.0` |

例如：

```text
M007 = 197.2
Spec_v1 = 180 ~ 195
197.2 > 195
所以结果是 Fail_High，偏差是 2.2
```

本系统目前把最终业务判定放在 Python 确定性逻辑里，而不是让 LLM 直接判断。LLM 只负责解释 evidence，不负责决定结果。

### 3.6 保存 Result 和 evidence

系统不会只保存一个 `Fail_High` 字符串。它还会保存判定证据：

- `measurement_id`
- `value`
- `status`
- `rule`
- `spec_version`
- `lower_limit`
- `upper_limit`
- `deviation`
- `reasoner`
- `inferred_at`

这些字段让系统以后可以回答：

```text
为什么 M007 是 Fail_High？
它用了哪个规格版本？
上限是多少？
偏差是多少？
这个结果是谁算出来的？
```

### 3.7 用户提问，QA 只做受控解释

用户可以问：

```text
M007 为什么 Fail？
M009 为什么 Pass？
```

QA 模块不会把任意自然语言直接交给 LLM 自由发挥。它会先做白名单意图识别：

| 问题类型 | 意图 |
| --- | --- |
| 某条测量为什么 Fail | `why_fail` |
| 某条测量为什么 Pass 或为什么这样判 | `why_judgement` |
| 规格变更影响 | `spec_change_impact` |
| 参数或批次汇总 | `parameter_or_batch_summary` |

命中白名单后，系统会构造固定 SPARQL 或通过 adapter 读取结构化 evidence，再由 LLM 或本地 fallback 生成解释。

对应代码：

- `mvp/core/qa.py`
- `mvp/api/main.py` 中的 `/api/v1/qa`

## 4. CQ 在这条业务链路里的位置

CQ 位于“业务语言”和“可执行系统”之间。

可以把它画成这样：

```text
业务人员关心的问题
        |
        v
CQ Markdown
  - Business question
  - SPARQL
  - Expected
  - Evidence fields
        |
        v
CQRunner
  - 准备 fixture 数据
  - 执行 SPARQL
  - 校验 Expected
  - 调用 QA
  - 校验 QA evidence
        |
        v
测试通过或失败
```

所以 CQ 不是业务流程之外的测试文档。它是把业务问题变成系统验收的桥。

## 5. CQ 应该起到的作用

### 5.1 作用一：定义本体必须回答的问题

本体不是越大越好。一个好本体应该能回答关键业务问题。

CQ 先问：

```text
这个系统必须能回答什么？
```

然后再倒推：

- 本体里需要哪些类。
- 数据里需要哪些字段。
- 关系要怎么建。
- 结果要怎么保存。

例如，如果 CQ 要回答“M007 为什么 Fail”，那系统至少需要：

- `Measurement`，知道 `M007` 的值。
- `Specification`，知道规格上下限。
- `Result`，知道判定状态。
- evidence 字段，知道规则、偏差和时间。

### 5.2 作用二：把业务语言变成可执行验收

普通需求可能写成：

```text
系统应能解释测量失败原因。
```

这句话太宽，容易各自理解。

CQ 会把它收敛成：

```text
业务问题：M007 为什么 Fail？
SPARQL：查 M007 的测量值和最新 Result。
Expected：只返回 1 行，status=Fail_High，rule=Rule_Fail_High。
Evidence fields：必须包含 value、spec_version、lower_limit、upper_limit、deviation 等字段。
```

这样需求就从“听起来合理”变成“可以自动检查”。

### 5.3 作用三：保护推理链和解释链不漂移

如果以后有人改了：

- 本体字段名。
- Result 保存结构。
- 推理规则。
- QA 模板。
- SPARQL graph IRI。

CQ 测试会发现：

- SPARQL 查不到数据。
- 期望状态不对。
- QA evidence 缺字段。
- 解释链和实际推理链不一致。

这就是 CQ 的回归保护作用。

### 5.4 作用四：约束 LLM 只能解释证据

本项目不希望 LLM 自己判断 `Pass` 或 `Fail`。

正确链路是：

```text
确定性推理先算出 Result
      |
图数据库保存 evidence
      |
QA 读取 evidence
      |
LLM 或 fallback 只解释 evidence
```

CQ 会检查 QA evidence 是否和 SPARQL 查到的 Result 一致，从而避免 LLM 解释出图谱里不存在的事实。

### 5.5 作用五：作为业务、 ontology、工程三方的共同语言

同一条 CQ 对不同角色都有意义：

| 角色 | 通过 CQ 关心什么 |
| --- | --- |
| 业务人员 | 这个问题是不是我们真正要问的 |
| 本体建模人员 | 模型是否足够表达这个问题 |
| 后端工程师 | 数据、推理和接口是否能跑通 |
| 测试人员 | 期望结果是否稳定可验证 |
| AI/Agent | 应该读取哪些 evidence，不该自由发挥什么 |

## 6. CQ 不应该承担什么

为了避免误用，需要明确 CQ 不是这些东西：

| 不是 | 原因 |
| --- | --- |
| 不是随手写的问答样例 | 它必须有可执行查询和期望结果 |
| 不是单纯测试数据 | 它代表一个业务验收问题 |
| 不是自由 SPARQL 入口 | SPARQL 应该受控、可审阅、可回归 |
| 不是 LLM prompt 集合 | LLM 只解释 evidence，CQ 约束 evidence |
| 不是越多越好 | 应优先覆盖关键业务判断和风险点 |

## 7. 当前 CQ 文件怎么读

当前 CQ 文件在：

```text
docs/cq/measurement-judgement-cqs.md
```

每个 CQ 大致长这样：

````text
## CQ-MJ-001 Why is M007 Fail_High?

- Business question: M007 为什么 Fail？
- Intent: why_fail
- Covers: Measurement, Specification, Result
- Demo data: M007, cq_temperature=197.2, Spec_v1 lower=180 upper=195
- Expected: row_count=1, status=Fail_High, rule=Rule_Fail_High, spec_version=Spec_v1, deviation=2.2

```sparql
...
```

- Evidence fields: measurement_id, value, status, rule, spec_version, lower_limit, upper_limit, deviation, reasoner, inferred_at
- Linked QA example: M007 为什么 Fail？
- Acceptance: SPARQL returns exactly one row and QA evidence contains the same fields.
````

字段含义：

| 字段 | 说明 |
| --- | --- |
| `Business question` | 给业务人员看的自然语言问题 |
| `Intent` | QA 白名单意图 |
| `Covers` | 这个 CQ 覆盖哪些模型概念 |
| `Demo data` | 验收用的演示数据 |
| `Expected` | SPARQL 结果必须满足的断言 |
| `sparql` | 验证查询 |
| `Evidence fields` | QA 解释必须拿到的证据字段 |
| `Linked QA example` | 实际问答模块会收到的问题 |
| `Acceptance` | 通过条件 |

## 8. CQRunner 做了什么

`CQRunner` 在 `mvp/core/cq.py` 中。

它的工作可以拆成四步：

1. `prepare_measurement_judgement_fixture()`
   准备 CQ 专用试验数据、参数、规格和测量值。

2. `render_sparql()`
   把 CQ 文件里的 graph 占位符渲染成当前 ontology 对应的 named graph。

3. `run_question()`
   执行 CQ 的 SPARQL，校验 `Expected`。

4. 调用 `qa.answer()`
   用 `Linked QA example` 走一遍 QA 链路，再校验 QA evidence 和 SPARQL 结果一致。

这意味着一个 CQ 通过，不只是说明 SPARQL 能跑，也说明：

- fixture 数据能写入。
- 推理能产生 Result。
- Result 能被 SPARQL 查出。
- QA 能拿到同一份 evidence。
- 自然语言解释没有脱离证据。

## 9. 新增 CQ 的建议流程

新增 CQ 时，不要先写 SPARQL。建议按这个顺序：

1. 先写业务问题。

   ```text
   M010 为什么从 Pass 变成 Fail_High？
   ```

2. 判断它属于哪个业务场景。

   ```text
   测量判定？
   规格变更影响？
   参数/批次汇总？
   ```

3. 确定系统需要哪些 evidence。

   ```text
   measurement_id, old_spec, new_spec, old_status, new_status, deviation
   ```

4. 检查本体和数据图是否已经能表达这些字段。

5. 再写 SPARQL 和 `Expected`。

6. 最后补测试。

   ```powershell
   python -m pytest tests/test_cq_parser.py -q
   python -m pytest tests/test_cq_integration.py -q
   ```

如果第 4 步发现表达不了，不应该硬写 SPARQL 绕过去，而应该回到模型或数据保存结构，补齐真正缺失的概念和关系。

## 10. 一个简单判断标准

判断 CQ 写得好不好，可以问这几个问题：

- 业务人员能不能看懂这个问题？
- 这个问题是不是系统必须回答的关键问题？
- SPARQL 是否只读取受控 named graph？
- `Expected` 是否足够具体？
- QA evidence 是否能解释结论，而不是只给状态？
- 如果代码被改坏，这个 CQ 是否会失败？
- 如果 LLM 胡说，这个 CQ 是否能把它拉回 evidence？

如果这些问题大多回答“是”，这个 CQ 就是有价值的。

## 11. 当前系统的关键文件地图

| 文件 | 职责 |
| --- | --- |
| `docs/cq/measurement-judgement-cqs.md` | CQ 定义，业务可读、机器可执行 |
| `mvp/core/cq.py` | CQ 解析、fixture 准备、SPARQL 渲染、结果校验 |
| `mvp/core/graph.py` | 业务图谱读写、参数、规格、测量、Result 持久化 |
| `mvp/core/inference.py` | 确定性测量判定逻辑 |
| `mvp/core/qa.py` | 受控自然语言问答、SPARQL 模板、evidence 解释 |
| `mvp/api/main.py` | FastAPI 路由，把 core 能力暴露为 `/api/v1` |
| `tests/test_cq_parser.py` | CQ Markdown 结构和渲染测试 |
| `tests/test_cq_integration.py` | 真实 Fuseki/SPARQL/CQRunner 集成测试 |

## 12. 最后再浓缩一次

在这个系统里：

- 本体回答“业务世界里有什么”。
- 图数据库保存“发生了什么”和“推理得出了什么”。
- 确定性推理回答“这条测量应该怎么判”。
- QA 回答“为什么这么判”。
- CQ 负责证明“上面这些环节合起来，真的能回答关键业务问题”。

因此，CQ 最重要的作用不是增加几条测试，而是把业务问题变成系统可持续演进的验收资产。
