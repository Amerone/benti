# Protege 5.6.9 制造业试验本体建模指南

本文根据 `manufacturing-trial-ontology-mvp (1).docx` 的制造业试制验证场景编写，目标是教你用 Protege 5.6.9 从零建立一个可演示的 OWL 本体。

场景可以先记成一句话：

> 一次试验有多个批次，每个批次有很多测量记录；每条测量记录按某个规格版本判定 Pass/Fail；规格变更后不能覆盖历史结论，而是生成新的判定结果和变更影响记录。

## 1. 先理解 Palantir Ontology，再落到 Protege

Palantir 官方把 Ontology 定义为组织的 operational layer。它不是单纯的 OWL 文件，而是把真实业务对象、属性、对象关系、动作、函数和安全治理放到同一层里。

在 Protege 里，我们主要能建的是 Palantir Ontology 中的语义部分：

| Palantir 概念 | 通俗解释 | Protege/OWL 中怎么表达 |
|---|---|---|
| Object Type | 一类业务对象，如 Trial、Batch | OWL Class |
| Object | 某个具体对象，如 T001、B03、M007 | Individual |
| Property | 对象自己的字段，如 measurementValue | Data Property |
| Link Type | 对象之间的关系，如 Trial 包含 Batch | Object Property |
| Action Type | 业务动作，如注册参数、重跑推理 | Protege 不能直接执行；可把动作结果建成 Individual，真正执行放到应用代码 |
| Function | 复杂业务逻辑，如判定 Pass/Fail | Protege 可用 SWRL 做轻量演示，生产逻辑建议放 Python/FastAPI |
| Dynamic Security | 谁能看、谁能改 | Protege MVP 中不做，后续由应用或平台权限实现 |

所以，本项目用 Protege 做的不是完整复刻 Palantir Foundry，而是借 Palantir 的对象化思路，把制造试验业务先建成稳定的语义模型。

## 2. 本体最小图谱

MVP 只建 7 个核心类：

```text
Trial
  hasBatch -> Batch
                 hasMeasurement -> Measurement
                                      hasParameter -> Parameter
                                      hasResult -> Result
                                                     evaluatedAgainst -> Specification

Specification
  supersedes -> Specification

SpecChangeImpact
  impactedMeasurement -> Measurement
  previousResult -> Result
  newResult -> Result
```

对应业务含义：

| 类 | 中文名 | 为什么需要 |
|---|---|---|
| `Trial` | 试验 | 表示一次完整试验，如 T001 注塑工艺验证 |
| `Batch` | 试制批次 | 表示温度梯度批次，如 B01、B02、B03 |
| `Parameter` | 测量参数 | 表示注塑温度、振动频率等可扩展参数 |
| `Measurement` | 测量记录 | 表示一条真实测量事实，如 M007 = 193.5 °C |
| `Specification` | 规格版本 | 表示 Spec_v1、Spec_v2，不覆盖旧版本 |
| `Result` | 判定结果 | 表示一次判定事实，保存规则名、偏差、证据 |
| `SpecChangeImpact` | 规格变更影响 | 表示规格变化导致哪些测量结论发生变化 |

建议先不要加入太多类。产品、模具、设备、人员、审批流都可以后续扩展。MVP 的目标是先证明三件事：规格变更可重算、参数可扩展、推理链可解释。

## 3. 从零建立 Protege 工程

### 3.1 新建本体

1. 打开 Protege 5.6.9。
2. 选择 `File -> New`。
3. 本体 IRI 建议填写：

```text
https://example.com/manufacturing-trial/ontology
```

4. 保存文件时建议保存为：

```text
mvp/ontology/manufacturing-trial.ttl
```

5. 保存格式选择 Turtle，便于后续用 Jena Fuseki、RDFLib、SPARQL 工具读取。

### 3.2 先设置命名习惯

建议采用英文技术名 + 中文 label：

| 用途 | 示例 |
|---|---|
| Class IRI | `Measurement` |
| Object property IRI | `hasResult` |
| Data property IRI | `measurementValue` |
| Individual IRI | `M007` 或 `Result_M007_Spec_v1` |
| 中文显示名 | 用 `rdfs:label` 填“测量记录”“判定结果”等 |

不要直接用中文、空格、括号做 IRI。中文放到 `rdfs:label` 和 `rdfs:comment` 里即可。

## 4. 创建 Classes

进入 `Entities -> Classes`，在 `owl:Thing` 下依次新增这些类：

```text
Trial
Batch
Parameter
Measurement
Specification
Result
SpecChangeImpact
```

如果你希望在 Protege 里演示规则分类，可以再加 3 个辅助类，作为 `Result` 的子类：

```text
PassResult
FailHighResult
FailLowResult
```

这三个辅助类不是业务必须项，而是为了让 SWRL 推理后在 Protege 里能直接看到某个 `Result` 被归类为通过、超上限失败、低于下限失败。

## 5. 创建 Object Properties

进入 `Entities -> Object properties`，在 `owl:topObjectProperty` 下新增以下关系。

| 属性 | Domain | Range | 中文含义 |
|---|---|---|---|
| `hasBatch` | `Trial` | `Batch` | 试验包含批次 |
| `hasMeasurement` | `Batch` | `Measurement` | 批次包含测量记录 |
| `hasParameter` | `Measurement` | `Parameter` | 测量记录使用哪个参数 |
| `appliesToTrial` | `Parameter` | `Trial` | 参数适用于哪个试验 |
| `hasSpecification` | `Measurement` | `Specification` | 测量记录原始采用的规格 |
| `hasResult` | `Measurement` | `Result` | 测量记录有哪些判定结果 |
| `evaluatedAgainst` | `Result` | `Specification` | 判定结果按哪个规格版本得出 |
| `supersedes` | `Specification` | `Specification` | 新规格替代旧规格 |
| `impactedMeasurement` | `SpecChangeImpact` | `Measurement` | 规格变更影响哪条测量 |
| `previousResult` | `SpecChangeImpact` | `Result` | 变更前结果 |
| `newResult` | `SpecChangeImpact` | `Result` | 变更后结果 |

操作方式：

1. 选中某个 object property。
2. 在右侧 `Domains` 区域点 `+`，选择 Domain 类。
3. 在右侧 `Ranges` 区域点 `+`，选择 Range 类。
4. 在 `Annotations` 里加 `rdfs:label`，例如 `hasBatch` 的 label 写“包含批次”。

建模时要注意方向。比如 `hasResult` 是 `Measurement -> Result`，意思是“一条测量记录拥有多个判定结果”。不要把它建成 `Result -> Measurement`，否则后续查询会绕。

## 6. 创建 Data Properties

进入 `Entities -> Data properties`，新增下列字段。

### 6.1 Trial 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `trialCode` | `Trial` | `xsd:string` | `T001` |

### 6.2 Batch 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `batchCode` | `Batch` | `xsd:string` | `B03` |
| `batchGradient` | `Batch` | `xsd:string` | `高温梯度 193°C` |

### 6.3 Parameter 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `parameterCode` | `Parameter` | `xsd:string` | `INJECTION_TEMPERATURE` |
| `parameterName` | `Parameter` | `xsd:string` | `注塑温度` |
| `unit` | `Parameter` | `xsd:string` | `°C` |
| `valueType` | `Parameter` | `xsd:string` | `number` |
| `participatesInInference` | `Parameter` | `xsd:boolean` | `true` |
| `limitSource` | `Parameter` | `xsd:string` | `Specification` |

### 6.4 Measurement 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `measurementId` | `Measurement` | `xsd:string` | `M007` |
| `measurementValue` | `Measurement` | `xsd:decimal` | `193.5` |
| `measurementTime` | `Measurement` | `xsd:dateTime` | `2026-04-20T09:30:00+08:00` |

### 6.5 Specification 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `specVersion` | `Specification` | `xsd:string` | `Spec_v1` |
| `lowerLimit` | `Specification` | `xsd:decimal` | `180.0` |
| `upperLimit` | `Specification` | `xsd:decimal` | `195.0` |
| `effectiveFrom` | `Specification` | `xsd:dateTime` | `2026-04-20T09:00:00+08:00` |
| `changeReason` | `Specification` | `xsd:string` | `初始试制规格` |

### 6.6 Result 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `resultStatus` | `Result` | `xsd:string` | `Pass` 或 `Fail_High` |
| `inferenceRule` | `Result` | `xsd:string` | `Rule_Fail_High` |
| `deviation` | `Result` | `xsd:decimal` | `3.5` |
| `judgedAt` | `Result` | `xsd:dateTime` | `2026-04-20T10:00:05+08:00` |
| `evidenceValue` | `Result` | `xsd:decimal` | `193.5` |
| `evidenceLowerLimit` | `Result` | `xsd:decimal` | `180.0` |
| `evidenceUpperLimit` | `Result` | `xsd:decimal` | `190.0` |

### 6.7 SpecChangeImpact 字段

| 属性 | Domain | Range | 示例 |
|---|---|---|---|
| `impactReason` | `SpecChangeImpact` | `xsd:string` | `规格上限从 195°C 收紧到 190°C，M007 超上限 3.5°C。` |

## 7. 加一点类约束，但不要过度

Protege 的 `Class Description` 视图可以给类添加逻辑约束。建议 MVP 阶段只加轻量约束，用来表达“应该有什么”，不要试图把所有数据库校验都塞进 OWL。

可添加的约束示例：

```text
Trial SubClassOf hasBatch some Batch
Trial SubClassOf trialCode exactly 1 xsd:string

Batch SubClassOf hasMeasurement only Measurement
Batch SubClassOf batchCode exactly 1 xsd:string

Measurement SubClassOf hasParameter exactly 1 Parameter
Measurement SubClassOf hasResult some Result
Measurement SubClassOf measurementValue exactly 1 xsd:decimal

Specification SubClassOf lowerLimit exactly 1 xsd:decimal
Specification SubClassOf upperLimit exactly 1 xsd:decimal
Specification SubClassOf specVersion exactly 1 xsd:string

Result SubClassOf evaluatedAgainst exactly 1 Specification
```

重要提醒：OWL 是开放世界假设。没有填 `measurementValue` 不等于系统会自动认为它错误。OWL 约束更像“逻辑描述”，不是数据库 NOT NULL。真正的数据质量校验，后续可以交给 SHACL、应用代码或测试脚本。

## 8. 创建最小演示实例

进入 `Entities -> Individuals by class`，按下面顺序创建 Individual。

### 8.1 创建试验和批次

创建 `T001`，类型为 `Trial`：

| Data property | 值 |
|---|---|
| `trialCode` | `T001` |
| `rdfs:label` | `T001 注塑工艺验证` |

创建 `B01`、`B02`、`B03`，类型为 `Batch`：

| Individual | `batchCode` | `batchGradient` |
|---|---|---|
| `B01` | `B01` | `低温梯度 183°C` |
| `B02` | `B02` | `中温梯度 188°C` |
| `B03` | `B03` | `高温梯度 193°C` |

给 `T001` 添加 object property assertions：

```text
hasBatch B01
hasBatch B02
hasBatch B03
```

### 8.2 创建参数

创建 `Parameter_InjectionTemperature`，类型为 `Parameter`：

| 属性 | 值 |
|---|---|
| `parameterCode` | `INJECTION_TEMPERATURE` |
| `parameterName` | `注塑温度` |
| `unit` | `°C` |
| `valueType` | `number` |
| `participatesInInference` | `true` |
| `limitSource` | `Specification` |
| `appliesToTrial` | `T001` |

如果后续要演示“新增参数无需改代码”，就再创建：

```text
Parameter_VibrationFrequency
```

并填：

| 属性 | 值 |
|---|---|
| `parameterCode` | `VIBRATION_FREQUENCY` |
| `parameterName` | `振动频率` |
| `unit` | `Hz` |
| `valueType` | `number` |
| `participatesInInference` | `false` 或 `true` |
| `limitSource` | `Specification` |
| `appliesToTrial` | `T001` |

这就是本体方式的关键：新增参数是新增一个 `Parameter` 个体，不是改数据库表结构。

### 8.3 创建规格版本

创建 `Spec_v1`，类型为 `Specification`：

| 属性 | 值 |
|---|---|
| `specVersion` | `Spec_v1` |
| `lowerLimit` | `180.0` |
| `upperLimit` | `195.0` |
| `effectiveFrom` | `2026-04-20T09:00:00+08:00` |
| `changeReason` | `初始试制规格` |

创建 `Spec_v2`，类型为 `Specification`：

| 属性 | 值 |
|---|---|
| `specVersion` | `Spec_v2` |
| `lowerLimit` | `180.0` |
| `upperLimit` | `190.0` |
| `effectiveFrom` | `2026-04-20T10:00:00+08:00` |
| `changeReason` | `收紧高温梯度量产窗口` |
| `supersedes` | `Spec_v1` |

不要把 `Spec_v1` 的 `upperLimit` 从 195 改成 190。正确做法是新增 `Spec_v2`，并用 `supersedes` 连接旧版本。

### 8.4 创建测量记录

创建 `M007`，类型为 `Measurement`：

| 属性 | 值 |
|---|---|
| `measurementId` | `M007` |
| `measurementValue` | `193.5` |
| `measurementTime` | `2026-04-20T09:30:00+08:00` |
| `hasParameter` | `Parameter_InjectionTemperature` |
| `hasSpecification` | `Spec_v1` |

给 `B03` 添加：

```text
hasMeasurement M007
```

### 8.5 创建判定结果

创建 `Result_M007_Spec_v1`，类型为 `Result`：

| 属性 | 值 |
|---|---|
| `resultStatus` | `Pass` |
| `inferenceRule` | `Rule_Pass` |
| `deviation` | `0.0` |
| `judgedAt` | `2026-04-20T09:30:05+08:00` |
| `evidenceValue` | `193.5` |
| `evidenceLowerLimit` | `180.0` |
| `evidenceUpperLimit` | `195.0` |
| `evaluatedAgainst` | `Spec_v1` |

创建 `Result_M007_Spec_v2`，类型为 `Result`：

| 属性 | 值 |
|---|---|
| `resultStatus` | `Fail_High` |
| `inferenceRule` | `Rule_Fail_High` |
| `deviation` | `3.5` |
| `judgedAt` | `2026-04-20T10:00:05+08:00` |
| `evidenceValue` | `193.5` |
| `evidenceLowerLimit` | `180.0` |
| `evidenceUpperLimit` | `190.0` |
| `evaluatedAgainst` | `Spec_v2` |

给 `M007` 添加：

```text
hasResult Result_M007_Spec_v1
hasResult Result_M007_Spec_v2
```

这就是“推理链持久化”的核心。不要只在 `Measurement` 上存一个 `result = Fail` 字段。否则规格变更后，你无法解释“当时为什么 Pass、后来为什么 Fail”。

### 8.6 创建规格变更影响

创建 `Impact_Spec_v2_M007`，类型为 `SpecChangeImpact`：

| 属性 | 值 |
|---|---|
| `impactedMeasurement` | `M007` |
| `previousResult` | `Result_M007_Spec_v1` |
| `newResult` | `Result_M007_Spec_v2` |
| `impactReason` | `规格上限从 195°C 收紧到 190°C，M007 测量值 193.5°C 超上限 3.5°C。` |

有了这个节点，系统就能回答：

```text
规格从 Spec_v1 变成 Spec_v2 后，哪些历史数据受影响？
```

## 9. 在 Protege 里做轻量规则演示

如果 Protege 里有 SWRLTab，可以建立下面 3 条规则。它们的作用是把 `Result` 个体自动分类为 `PassResult`、`FailHighResult`、`FailLowResult`。

### Rule_Pass

```text
Measurement(?m) ^ hasResult(?m, ?r) ^ Result(?r) ^
evaluatedAgainst(?r, ?s) ^
measurementValue(?m, ?v) ^
lowerLimit(?s, ?low) ^
upperLimit(?s, ?up) ^
swrlb:greaterThanOrEqual(?v, ?low) ^
swrlb:lessThanOrEqual(?v, ?up)
-> PassResult(?r)
```

### Rule_Fail_High

```text
Measurement(?m) ^ hasResult(?m, ?r) ^ Result(?r) ^
evaluatedAgainst(?r, ?s) ^
measurementValue(?m, ?v) ^
upperLimit(?s, ?up) ^
swrlb:greaterThan(?v, ?up)
-> FailHighResult(?r)
```

### Rule_Fail_Low

```text
Measurement(?m) ^ hasResult(?m, ?r) ^ Result(?r) ^
evaluatedAgainst(?r, ?s) ^
measurementValue(?m, ?v) ^
lowerLimit(?s, ?low) ^
swrlb:lessThan(?v, ?low)
-> FailLowResult(?r)
```

注意边界：

- SWRL 可以帮你分类，但通常不适合在 Protege 里自动创建新的 `Result` 个体。
- SWRL 也不擅长把 `deviation = 193.5 - 190.0` 这类计算结果稳定写回数据属性。
- MVP 里建议：Protege 表达语义结构；Python/FastAPI 执行确定性判定并把 `Result` 写回图谱。

## 10. 运行 Reasoner 检查

在 Protege 顶部菜单中：

1. 选择 `Reasoner`。
2. 选择可用的 reasoner，例如 HermiT 或 Pellet。
3. 点击 `Start reasoner`。
4. 点击 `Classify ontology`。
5. 点击 `Check consistency`。

如果你使用 SWRL 内置比较函数，例如 `swrlb:greaterThan`，不同 reasoner 支持情况可能不同。若 SWRL 规则跑不起来，不代表本体建错了；可以把规则演示放到 SWRLTab 或 Python 里执行。

## 11. 查询时应该能回答的问题

建完后，图谱应该能回答这些问题：

### 11.1 M007 为什么 Fail？

查询路径：

```text
M007
  hasResult -> Result_M007_Spec_v2
    resultStatus -> Fail_High
    inferenceRule -> Rule_Fail_High
    evidenceValue -> 193.5
    evidenceUpperLimit -> 190.0
    deviation -> 3.5
    evaluatedAgainst -> Spec_v2
```

自然语言解释：

```text
M007 的测量值是 193.5°C，按 Spec_v2 的上限 190.0°C 判定。
因为 193.5°C 超过上限 3.5°C，所以触发 Rule_Fail_High，结论为 Fail_High。
```

### 11.2 规格变更影响了哪些数据？

查询路径：

```text
Spec_v2
  supersedes -> Spec_v1

Impact_Spec_v2_M007
  impactedMeasurement -> M007
  previousResult -> Result_M007_Spec_v1
  newResult -> Result_M007_Spec_v2
```

自然语言解释：

```text
Spec_v2 替代 Spec_v1 后，M007 从原来的 Pass 变成 Fail_High。
原因是上限从 195°C 收紧到 190°C。
```

### 11.3 如何新增一个参数？

新增参数不是改 schema，而是新增 `Parameter` 个体：

```text
Parameter_VibrationFrequency
  parameterCode = VIBRATION_FREQUENCY
  parameterName = 振动频率
  unit = Hz
  valueType = number
  appliesToTrial = T001
```

后续测量记录只要 `hasParameter` 指向这个新参数即可。

## 12. 推荐的建模原则

### 12.1 类不要按数据库表照搬

`Trial`、`Batch`、`Measurement` 是业务对象，不是表名翻译。建模时先问：

```text
业务人员会不会这样说话？
这个对象是否有稳定身份？
它是否会被查询、判定、审计或关联？
```

答案是“是”，才适合建成类。

### 12.2 规格版本一定要新增，不要覆盖

错误做法：

```text
把 Spec_v1.upperLimit 从 195 改成 190
```

正确做法：

```text
新增 Spec_v2
Spec_v2 supersedes Spec_v1
重新生成 Result_Mxxx_Spec_v2
必要时生成 SpecChangeImpact
```

### 12.3 判定结果要建成对象

不要只存：

```text
M007 resultStatus Fail
```

要存：

```text
M007 hasResult Result_M007_Spec_v2
Result_M007_Spec_v2 evaluatedAgainst Spec_v2
Result_M007_Spec_v2 inferenceRule Rule_Fail_High
Result_M007_Spec_v2 deviation 3.5
```

因为审计要看的不是“结果是什么”，而是“依据什么规则、哪个规格版本、什么证据得出结果”。

### 12.4 参数扩展用 Individual，不先改 Class

`Parameter` 是类，`注塑温度`、`振动频率` 是参数个体。这样新增参数时，只新增数据，不改本体结构。

只有当某类参数拥有完全不同的行为和约束时，才考虑建子类，例如：

```text
NumericParameter
CategoricalParameter
```

### 12.5 Protege 负责“表达”，应用负责“执行”

Protege 很适合表达：

- 有哪些业务对象
- 对象之间是什么关系
- 每个对象有哪些属性
- 哪些规则可被解释

应用代码更适合执行：

- 批量重推理
- 偏差计算
- 写回 Result
- 生成差异报告
- 权限控制
- 用户操作动作

这也对应 Palantir 的思路：Ontology 不只是静态模型，还要连接 actions/functions/applications。Protege MVP 先把语义层建稳，动作和函数后续用 Python/FastAPI/Streamlit 承接。

## 13. 可选二期扩展

当 MVP 跑通后，可以再加这些类。

| 类 | 用途 |
|---|---|
| `Product` | 表示注塑成型精密外壳的新型号 |
| `Mold` | 表示新模具 |
| `Person` | 表示操作员、工艺工程师、质量主管 |
| `Operator` | `Person` 子类，录入或采集数据 |
| `ProcessEngineer` | `Person` 子类，创建试验方案和规格 |
| `QualitySupervisor` | `Person` 子类，审核异常和放行 |
| `Decision` | 表示人工放行、驳回、覆盖判定 |
| `ProcessInsight` | 表示跨 Trial 形成的工艺洞察 |

可选关系：

| 属性 | Domain | Range | 用途 |
|---|---|---|---|
| `recordedBy` | `Measurement` | `Person` | 谁录入测量 |
| `createdBy` | `Specification` | `Person` | 谁创建规格 |
| `approvedBy` | `Decision` | `QualitySupervisor` | 谁批准决策 |
| `overridesResult` | `Decision` | `Result` | 人工决策覆盖哪个结果 |
| `basedOnImpact` | `Decision` | `SpecChangeImpact` | 决策依据哪次影响分析 |

不要一开始就加这些扩展。先让 `Trial -> Batch -> Measurement -> Result -> Specification` 的主链路能跑通。

## 14. 最终检查清单

建模完成后，逐项检查：

- 已有 7 个核心类：`Trial`、`Batch`、`Parameter`、`Measurement`、`Specification`、`Result`、`SpecChangeImpact`
- `Trial` 能通过 `hasBatch` 找到 `B01/B02/B03`
- `B03` 能通过 `hasMeasurement` 找到 `M007`
- `M007` 能通过 `hasParameter` 找到 `Parameter_InjectionTemperature`
- `M007` 能通过 `hasResult` 找到 `Result_M007_Spec_v1` 和 `Result_M007_Spec_v2`
- `Result_M007_Spec_v1` 指向 `Spec_v1`，结论是 `Pass`
- `Result_M007_Spec_v2` 指向 `Spec_v2`，结论是 `Fail_High`
- `Spec_v2 supersedes Spec_v1`
- `Impact_Spec_v2_M007` 同时连接旧结果、新结果和受影响测量
- `Result` 中保存了 `inferenceRule`、`deviation`、`evidenceValue`、`evidenceLowerLimit`、`evidenceUpperLimit`
- 新增参数时只新增 `Parameter` 个体，不修改表结构

如果这些都成立，你的本体已经能支撑 docx 中 MVP 的三个核心命题。

## 15. 参考资料

- Palantir Ontology Overview: https://www.palantir.com/docs/foundry/ontology/overview
- Palantir Object Types Overview: https://www.palantir.com/docs/foundry/object-link-types/object-types-overview
- Palantir Properties Overview: https://www.palantir.com/docs/foundry/object-link-types/properties-overview
- Palantir Link Types Overview: https://www.palantir.com/docs/foundry/object-link-types/link-types-overview
- Palantir Action Types Overview: https://www.palantir.com/docs/foundry/action-types/overview
- Palantir Action Rules: https://www.palantir.com/docs/foundry/action-types/rules
- Protege 5.6.9 Documentation: https://protegeproject.github.io/protege/
- Protege Getting Started: https://protegeproject.github.io/protege/getting-started/
- Protege Class Description View: https://protegeproject.github.io/protege/views/class-description/
- Protege Wiki - Using Reasoners: https://protegewiki.stanford.edu/wiki/Using_Reasoners
- Protege Wiki - SWRLTab: https://protegewiki.stanford.edu/wiki/SWRLTab
