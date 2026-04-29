# 委托单 CQ 工程开发演示讲稿

这份文档面向技术团队。重点讲清楚：CQ 如何驱动建模，LLM 如何辅助但不越权，TBox/RBox/ABox 如何分层，系统如何验证。

## 技术演示目标

让开发团队理解四件事：

1. CQ 是建模输入，不是普通问答样例。
2. CQ 可以反推类、关系、属性、规则和 SPARQL 回归测试。
3. LLM 只生成候选草案，正式本体由人审和测试把关。
4. 本体、数据、规则、API、页面之间有清晰边界。

## 技术对象映射

| 英文类名 | 中文含义 | 演示对象 |
| --- | --- | --- |
| `CommissionOrder` | 委托单 | `CO-2024-001` |
| `Product` | 产品 | 相控阵雷达导引头 `X-01` |
| `TestProject` | 试验项目 | 高低温振动试验、电磁兼容试验 |
| `TestTask` | 试验任务 | `T-001`、`T-002` |
| `TestItem` | 测试项 | `RCS_MEAN`、`BER` |
| `TestDataRecord` | 测试数据记录 | `0.042`、`0.00021` |
| `PassCriterion` | 通过条件 | `<= 0.05`、`<= 0.035` |
| `StandardVersion` | 标准版本 | `V1`、`V2` |
| `JudgementResult` | 判定结果 | `Pass`、`Fail` |
| `ReevaluationImpact` | 重判影响 | `Pass -> Fail` |
| `CQDraft` | CQ 工程草案 | 生成后保存、reviewed |

## TBox / RBox / ABox 怎么讲

### TBox

TBox 是“有哪些概念”。

本系统里的例子：

```text
CommissionOrder
Product
TestProject
TestTask
TestItem
StandardVersion
JudgementResult
ReevaluationImpact
```

讲解词：

> TBox 解决“业务世界里有哪些对象”的问题。没有 TBox，系统只有表和字段；有了 TBox，系统知道委托单、任务、标准版本是不同类型的业务对象。

### RBox

RBox 是“对象之间是什么关系”。

本系统里的例子：

```text
CommissionOrder hasProduct Product
CommissionOrder hasTestProject TestProject
TestProject decomposesToTask TestTask
TestTask hasTestItem TestItem
TestItem recordsData TestDataRecord
TestDataRecord hasJudgementResult JudgementResult
PassCriterion criterionInStandard StandardVersion
StandardVersion supersedesStandard StandardVersion
ReevaluationImpact impactsTask TestTask
```

讲解词：

> RBox 解决“对象如何连起来”的问题。标准升级影响分析之所以能做，是因为系统知道结果、标准、任务、影响之间的关系。

### ABox

ABox 是“具体事实”。

本系统里的例子：

```text
CO-2024-001 是一个 CommissionOrder
T-001 是一个 TestTask
RCS_MEAN 实测值是 0.042
V1 阈值是 <= 0.05
V2 阈值是 <= 0.035
T-001 状态是 NeedsReview
```

讲解词：

> ABox 是真实业务数据。TBox 和 RBox 提供语义框架，ABox 填入事实，SPARQL 和规则在这个图上执行。

## CQ 如何反推 TBox/RBox

开发演示时打开：

```text
技术讲 -> CQ 工程台
```

选择：

```text
template_only
```

点击：

```text
生成并保存草案
```

你会看到：

- `candidate_cqs`
- `candidate_classes`
- `candidate_relations`
- `candidate_properties`
- `candidate_rules`
- `draft_turtle`
- `draft_sparql_tests`
- `source_trace`

讲解顺序：

1. 先看 `candidate_cqs`
   - 说明业务问题被登记为 CQ。
   - 例如：标准升级后哪些历史结果翻转？

2. 再看 `candidate_classes`
   - 说明 CQ 中反复出现的名词会成为候选类。
   - 例如：委托单、任务、测试项、标准版本。

3. 再看 `candidate_relations`
   - 说明 CQ 中的动词和业务连接会成为候选关系。
   - 例如：项目分解成任务、标准版本互相替代。

4. 再看 `candidate_rules`
   - 说明 CQ 里隐含的判断逻辑会成为规则候选。
   - 例如：小于等于阈值为通过，结论翻转则任务需复核。

5. 最后看 `draft_sparql_tests`
   - 说明 CQ 不停留在文档，而是变成可执行验收测试。

## 为什么 LLM 只生成草案

页面有三个模式：

| 模式 | 含义 | 适合场景 |
| --- | --- | --- |
| `template_only` | 只用内置模板 | 稳定演示、无网络、无 API Key |
| `llm_with_template_fallback` | 优先 LLM，失败回退模板 | 日常开发 |
| `llm_only` | 必须 LLM 成功 | 验证 LLM 接入质量 |

关键讲法：

> LLM 的输出只进入 `CQDraft`，状态默认是 `draft`。它不会直接覆盖正式 OWL/Turtle，也不会直接改生产规则。只有 reviewed 后，才进入后续人工发布流程。

## 技术边界怎么讲

| 层 | 文件 | 职责 |
| --- | --- | --- |
| 本体 | `mvp/ontology/commission-testing.ttl` | 定义类、关系、属性 |
| CQ | `docs/cq/commission-testing-cqs.md` | 定义能力问题和 SPARQL 验收 |
| 规则 | `mvp/rules/commission-testing.yml` | 定义任务分解和判定规则 |
| 纯推理 | `mvp/core/commission_reasoning.py` | 不依赖 RDF 的确定性计算 |
| RDF 持久化 | `mvp/core/commission_graph.py` | 把业务事实写入数据图 |
| CQ 工程 | `mvp/core/cq_engine.py` | 解析 CQ、保存草案、运行 CQ |
| 草案生成 | `mvp/core/ontology_draft.py` | LLM/模板生成候选模型 |
| API | `mvp/api/*.py` | 对页面提供 HTTP 接口 |
| 页面 | `mvp/frontend/tabs/*.py` | 只通过 API 使用系统 |

讲解词：

> 页面不直接 import core，API 不写业务规则，业务规则不依赖页面。这样后续换页面、换存储、换 LLM，都不会把整个系统推倒重来。

## 技术演示命令

### 全量测试

```powershell
python -m pytest -q
```

当前验收结果：

```text
150 passed
```

### CQ/Fuseki 集成

```powershell
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

当前验收结果：

```text
1 passed
```

### 前端边界

```powershell
python -m pytest tests/test_frontend_boundaries.py -q
```

这个测试保证：

- 新页面只走 API。
- 新页面不直接 import `mvp.core`。
- `委托单试验` 和 `CQ 工程台` 页签没有接错。

## 开发演示推荐话术

> 我们不是让 LLM 直接写本体，而是让 CQ 先把业务问题结构化，再让 LLM 或模板生成候选 TBox/RBox/规则/SPARQL。候选物进入草案区，由人审和测试约束。这样既利用 LLM 提速，又保留工程可控性。

> 本体开发最怕的是“模型看起来对，但无法证明”。这里每个 CQ 都有 Expected 和 Evidence fields，能跑成 SPARQL 集成测试，所以模型不是靠口头判断，而是靠可执行验收闭环。

## 开发团队最该关注的扩展点

### 新增试验项目

改：

```text
mvp/data/commission-testing-demo.json
```

然后补：

```text
docs/cq/commission-testing-cqs.md
```

### 新增类或关系

改：

```text
mvp/ontology/commission-testing.ttl
```

同时补：

```text
tests/test_ontology_registry.py
tests/test_commission_cq_engine.py
tests/test_commission_cq_integration.py
```

### 新增判定规则

改：

```text
mvp/rules/commission-testing.yml
mvp/core/commission_reasoning.py
```

同时补：

```text
tests/test_commission_reasoning.py
```

## 技术演示结束总结

可以照读：

> 这套实现的重点不是单个页面，而是一个可持续演进的本体工程流程：CQ 登记需求，TBox/RBox 表达模型，ABox 承载事实，规则产生结果，SPARQL 做回归验收，LLM 只辅助生成草案。它把业务建模从“靠人记、靠文档传”变成“可执行、可追溯、可测试”的工程资产。
