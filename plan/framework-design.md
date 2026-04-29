# 制造业试验数据管理本体 MVP 框架设计

## 0. 评估结论与本次修订

经对照 `manufacturing-trial-ontology-mvp (1).docx`、`mto_extracted.txt` 以及 `docs/ontology-wiki/15-manufacturing-trial-mvp-rollout.md`，本文档的总体框架**符合目标要求**：它覆盖了多本体加载到 Fuseki、Owlready2 从 Fuseki 读取本体、Pellet 推理、LLM 解释闭环、Streamlit 本体切换和主体展示。

本次修订不改变原有意图和主结构，只补齐以下会影响实现的契约点：

- 统一外部 API 前缀为 `/api/v1`，早期章节和后续章节保持一致。
- 统一前端入口为 `mvp/frontend/app.py`，根目录 `mvp/app.py` 仅作为可选兼容启动包装。
- 统一 Fuseki 图划分：本体图、业务数据图、推理链图、规格历史图分离。
- 明确 Owlready2/Pellet 必须真实接入，但 MVP 业务 Pass/Fail 仍由确定性规则产出，并用 `reasoner` 字段显式标注。
- 区分 API 字段名与 RDF 谓词名，避免 `inferenceRule` / `appliedRule` 等混用导致实现歧义。
- 补充边界条件、失败降级、验收标准与可观测性要求。

## 1. 目标

本项目围绕 `manufacturing-trial-ontology-mvp (1).docx` 中的 MVP 方案搭建框架，目标不是做完整生产系统，而是把三个核心命题跑通并可演示：

1. 规格变更后，历史测量数据可以自动重推理并生成差异报告。
2. 运行时可以新增参数，不修改数据库表结构、不重启服务。
3. 每条判定都保留推理链，并可通过 LLM 用自然语言解释。

在技术实现上，框架需要同时满足：

- 支持多个本体文件加载到 Apache Jena Fuseki。
- 使用 Owlready2 从 Fuseki 中加载本体内容。
- 使用 Pellet 执行 OWL / SWRL 推理或一致性校验。
- 对接 LLM，形成“自然语言问题 -> 图谱查询 -> 推理链解释”的闭环。
- Streamlit 页面可展示从 Fuseki 读取并由 Owlready2 加载后的本体主体，并支持本体切换、推理、问答等交互。

设计约束：

- LLM 不直接给出最终业务判定，只解释图谱中已经持久化的结构化证据。
- Python 确定性规则是 MVP 阶段业务 Pass/Fail 的主判定来源；Pellet 是 OWL/SWRL 推理和一致性校验通道，不允许二者来源混淆。
- 任何推理结论必须可回放：输入值、规格版本、规则名、偏差、推理时间和推理器来源都要写入图谱。
- 多本体切换必须是显式请求参数或客户端状态，不依赖服务端 session。

## 2. 总体架构

```text
┌─────────────────────────────────────────────────────────────┐
│                         Streamlit UI                         │
│  本体切换 | Fuseki加载 | Owlready主体展示 | Pellet推理 | LLM问答 │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP
┌──────────────────────────────▼──────────────────────────────┐
│                         FastAPI API                          │
│  ontology endpoints | inference endpoints | QA endpoints      │
└──────────────┬─────────────────────┬────────────────────────┘
               │                     │
┌──────────────▼──────────────┐      │
│       Application Core       │      │
│ graph.py                     │      │
│ inference.py                 │      │
│ parameters.py                │      │
│ qa.py                        │      │
└──────────────┬──────────────┘      │
               │                     │
┌──────────────▼──────────────┐      │
│      Semantic Services       │      │
│ ontology_registry.py         │      │
│ owlready_reasoner.py         │      │
└──────────────┬──────────────┘      │
               │                     │
┌──────────────▼──────────────┐      ┌▼───────────────────────┐
│     Apache Jena Fuseki       │      │        LLM Provider     │
│ named graphs per ontology    │      │ Claude/OpenAI compatible│
└──────────────────────────────┘      └────────────────────────┘
```

Fuseki 采用**单 dataset + 多 named graph**。每个本体至少包含四类图：本体定义图、业务数据图、推理链图、规格历史图。Owlready2/Pellet 默认只读取本体定义图，避免把大量运行期测量数据直接喂给推理机。

## 3. 目录结构

```text
plan/
  framework-design.md          # 本文件
  implementation-plan.md       # 后续实现计划，可由本设计派生

mvp/
  ontology/
    manufacturing-trial.ttl
    process-window.ttl
  core/
    ontology_registry.py
    sparql_client.py
    graph.py
    owlready_reasoner.py
    inference.py
    parameters.py
    qa.py
  api/
    envelope.py
    main.py
    trace_middleware.py
  frontend/
    app.py
    ui_utils.py
    tabs/
      tab_ontology.py
      tab_subjects.py
      tab_pellet.py
      tab_measure.py
      tab_qa.py
  app.py                      # 可选兼容包装：转调 mvp/frontend/app.py
  demo_data.py
  docker-compose.yml

tests/
  test_ontology_registry.py
  test_inference.py
  test_qa.py

requirements.txt
README.md
```

## 4. 关键模块

### 4.0 中文注释与代码说明规范

项目实现必须增加中文注释，用于说明类、方法、函数和关键流程的作用。注释目标是帮助后续开发、测试和业务评审理解代码意图，而不是逐行复述代码。

要求：

- 每个公开类、核心 dataclass、API 路由函数、核心业务函数必须有中文 docstring，说明职责、输入、输出、异常或降级行为。
- 每个模块顶部必须有中文模块说明，说明该文件在整体架构中的位置和边界。
- 复杂流程必须在关键分支前补充简短中文注释，例如 Fuseki named graph 选择、Turtle 转 RDF/XML、Pellet 降级、规格重推理 diff、LLM fallback。
- 注释必须解释“为什么这样做”，尤其是 Python 确定性判定与 Pellet 推理双轨并行、LLM 只做解释、不做最终判定等设计约束。
- 简单赋值、显而易见的语句不需要注释，避免噪声。
- 公开 API 的请求/响应模型应通过中文 docstring 或字段说明描述业务含义。
- TTL / SWRL 文件头和关键类、关键属性也应保留中文注释或 `rdfs:label`，便于页面展示和业务人员审阅。

示例：

```python
class OntologyRegistry:
    """本体注册表。

    负责扫描本地 TTL 文件、解析文件头元信息，并为每个本体生成
    Fuseki 中的 ontology/data/result/spec 四类 named graph IRI。
    该类只处理文件层元数据，不连接 Fuseki，也不执行 Owlready2 加载。
    """

def rerun_after_spec_change(...):
    """规格变更后重推理历史测量。

    创建新的 Specification 版本，遍历目标参数的历史 Measurement，
    使用确定性判定逻辑重新生成 Result，并返回状态发生变化的差异报告。
    """
```

### 4.1 `ontology_registry.py`

职责：

- 扫描 `mvp/ontology/` 下所有 `.ttl` 文件。
- 读取文件头中的 `# ontology-id:`、`# ontology-label:`、`# ontology-swrl:` 元信息。
- 为每个本体生成稳定的 `ontology_id`。
- 为每个本体绑定 Fuseki named graph IRI，包括 ontology/data/result/spec 四类图。
- 支持多本体列表、当前本体切换、TTL / SWRL 路径展示。

输出示例：

```json
{
  "ontology_id": "manufacturing-trial",
  "label": "制造业试验数据管理本体",
  "ttl_paths": ["mvp/ontology/manufacturing-trial.ttl"],
  "swrl_paths": ["mvp/ontology/manufacturing-trial.swrl"],
  "graph_iri": "https://hifar.top/mto/graph/manufacturing-trial",
  "data_graph_iri": "https://hifar.top/mto/graph/manufacturing-trial/data",
  "result_graph_iri": "https://hifar.top/mto/graph/manufacturing-trial/result",
  "spec_graph_iri": "https://hifar.top/mto/graph/manufacturing-trial/spec"
}
```

### 4.2 `sparql_client.py`

职责：

- 封装 Fuseki HTTP 访问。
- 支持 SPARQL `SELECT` / `ASK` / `CONSTRUCT` / `UPDATE`。
- 支持 Graph Store Protocol 上传 Turtle 到 named graph。
- 统一处理 Fuseki 地址、dataset、认证、超时和错误信息。

配置来源：

```text
FUSEKI_BASE_URL=http://localhost:3030
FUSEKI_DATASET=manufacturing-trial
FUSEKI_USER=
FUSEKI_PASSWORD=
```

### 4.3 `graph.py`

职责：

- 作为业务图谱访问层。
- 将多个本体加载到 Fuseki，不同本体使用不同 named graph；同一本体内按 ontology/data/result/spec 分图。
- 写入 Trial / Batch / Parameter / Measurement / Specification / Result。
- 持久化推理链字段。API 字段使用驼峰或蛇形均可，但 RDF 谓词必须按 §12.2 的契约落地：
  - API: `inferenceRule` / RDF: `mto:appliedRule`
  - API: `specVersion` / RDF: `mto:againstSpecVersion`
  - API: `deviation` / RDF: `mto:deviation`
  - API: `evidenceValue` / RDF: `mto:evidenceValue`
  - API: `evidenceLowerLimit` / RDF: `mto:evidenceLowerLimit`
  - API: `evidenceUpperLimit` / RDF: `mto:evidenceUpperLimit`
  - API: `inferredAt` / RDF: `mto:inferredAt`
  - API: `reasoner` / RDF: `mto:reasoner`
- 查询参数、测量、结果、规格版本和规格变更影响。

核心方法：

```text
load_ontologies()
list_ontologies()
construct_ontology_turtle(ontology_id)
list_ontology_subjects(ontology_id)
graph_iri(ontology_id, kind="ontology|data|result|spec")
register_parameter(...)
create_measurement(...)
create_specification(...)
save_inference_result(...)
list_measurements(...)
```

### 4.4 `owlready_reasoner.py`

职责：

- 从 Fuseki named graph 中 `CONSTRUCT` 出当前本体的 Turtle。
- 使用 RDFLib 将 Turtle 转为 Owlready2 更稳定支持的 RDF/XML。
- 使用 Owlready2 加载本体。
- 调用 Pellet 执行推理。
- 返回页面可展示的主体视图。

核心流程：

```text
Fuseki named graph
  -> CONSTRUCT Turtle
  -> RDFLib parse
  -> RDF/XML 临时文件
  -> Owlready2 World.load()
  -> Pellet sync_reasoner_pellet()
  -> classes / individuals / object_properties / data_properties
```

页面展示对象：

```json
{
  "ontology_id": "manufacturing-trial",
  "loaded_by": "owlready2",
  "reasoner": "pellet",
  "classes": [...],
  "individuals": [...],
  "object_properties": [...],
  "data_properties": [...],
  "pellet_status": "not_run | success | failed"
}
```

### 4.5 `inference.py`

职责：

- 执行业务判定。
- 将 Owlready2/Pellet 的本体加载和一致性推理结果纳入执行上下文。
- 保留文档中的 MVP 决策：数值 Pass / Fail 判定仍用确定性 Python 逻辑，以保证可解释、可调试、可审计。

核心函数：

```text
evaluate_single(value, lower_limit, upper_limit, spec_version)
run_inference(measurement_id, ontology_id)
rerun_after_spec_change(parameter_code, new_lower, new_upper, ontology_id)
```

判定规则：

```text
value < lower_limit  -> Fail_Low
value > upper_limit  -> Fail_High
otherwise            -> Pass
```

Pellet 在 MVP 中承担：

- 本体加载验证。
- OWL 一致性检查。
- SWRL / 属性推理预留。
- 页面上展示推理器执行状态。

### 4.6 `parameters.py`

职责：

- 运行时注册新参数。
- 将参数作为图谱个体写入当前本体 named graph。
- 前端查询参数列表时直接从图谱读取，不依赖固定数据库表结构。

核心字段：

```text
parameterCode
parameterName
unit
valueType
limitSource
participatesInInference
applicableTrial
```

### 4.7 `qa.py`

职责：

- 对接 LLM，实现推理链问答。
- 支持无 API Key 的本地 fallback，便于演示和测试。
- 有 API Key 时调用 Claude 或兼容模型。

流程：

```text
用户问题
  -> 识别 measurement_id / parameter / batch / spec
  -> 生成或选择 SPARQL
  -> 查询 Fuseki
  -> 构造包含推理链字段的上下文
  -> LLM 生成中文解释
```

LLM 输入必须包含：

```text
ontology_id
graph_iri / result_graph_iri
measurement value
status
inferenceRule
specVersion
lowerLimit
upperLimit
deviation
inferredAt
```

问答边界：

- 第一阶段只支持白名单模板：`why_measurement_failed`、`spec_change_impact`、`parameter_or_batch_summary`。
- 模板以外的问题必须返回“不支持该类问题”，不得让 LLM 自由编写 SPARQL。
- LLM 输出必须引用 evidence 字段，不得新增图谱中不存在的事实。

## 5. API 设计

所有对外 API 均挂在 `/api/v1` 下。下列路径均省略此前缀；实际调用示例为 `/api/v1/ontologies`。

### 本体管理

```text
GET  /health
GET  /ontologies
POST /ontologies/load
POST /ontologies/{ontology_id}/activate
GET  /ontologies/{ontology_id}/subjects
POST /ontologies/{ontology_id}/reason
```

说明：

- `/ontologies/load` 将所有发现的 TTL 加载到 Fuseki。
- `/subjects` 返回 Owlready2 从 Fuseki 加载后的 classes / individuals / properties。
- `/reason` 调用 Pellet，并返回推理状态。
- `/ontologies/{ontology_id}/activate` 仅用于演示环境保存默认选择；正式业务请求仍必须显式传递 `ontology_id`。

### 参数与测量

```text
GET  /parameters?ontology_id=...
POST /parameters
POST /measurements
GET  /measurements?ontology_id=...
```

### 规格与重推理

```text
POST /specifications
POST /specifications/change
GET  /specifications?ontology_id=...
GET  /impacts/latest?ontology_id=...
```

### LLM 问答

```text
POST /qa
```

请求：

```json
{
  "ontology_id": "manufacturing-trial",
  "question": "M007为什么Fail？"
}
```

响应：

```json
{
  "answer": "M007 判定为 Fail_High，因为测量值 197°C 高于 Spec_v1 上限 195°C，触发 Rule_Fail_High，偏差 +2°C。",
  "source": "llm | local_fallback",
  "sparql": "...",
  "evidence": {...}
}
```

## 6. Streamlit 页面设计

页面采用工作台式布局，不做营销页。

### 6.1 顶部状态区

显示：

- 当前 API 地址。
- 当前本体。
- Fuseki 连接状态。
- 已加载 graph 数量。
- Owlready2 是否可用。
- Pellet 最近一次执行状态。

### 6.2 Tab 一：本体加载与切换

能力：

- 展示本地发现的多个 TTL 本体。
- 一键加载全部本体到 Fuseki。
- 切换当前本体。
- 展示每个本体的 TTL 路径、named graph、三元组数量。

### 6.3 Tab 二：Owlready2 主体浏览

能力：

- 从 Fuseki 当前 named graph 拉取 Turtle。
- 使用 Owlready2 加载。
- 展示的数据必须来自 Fuseki 返回的 named graph 内容，不能直接读取本地 TTL 文件作为页面结果。
- 展示：
  - Classes
  - Individuals
  - Object Properties
  - Data Properties
- 支持按名称过滤。

### 6.4 Tab 三：Pellet 推理

能力：

- 对当前本体执行 Pellet 推理。
- 显示推理成功、耗时、错误信息。
- 显示推理后新增的类型或属性推断。

### 6.5 Tab 四：测量与规格变更

能力：

- 录入测量值。
- 即时执行推理。
- 展示 Pass / Fail、规则名、偏差、规格版本。
- 修改规格上下限并触发历史重推理。
- 展示差异报告。

### 6.6 Tab 五：参数与问答

能力：

- 运行时新增参数。
- 新参数立即进入测量录入选项。
- 输入自然语言问题。
- 展示 LLM 或 fallback 生成的推理链解释。

## 7. 数据流

### 7.1 多本体加载

```text
本地 TTL 文件
  -> ontology_registry.discover_ontologies()
  -> graph.load_ontologies()
  -> Fuseki ontology named graph
  -> UI 显示 graph 状态
```

### 7.2 Owlready2 加载

```text
UI 点击“加载主体”
  -> API /ontologies/{id}/subjects
  -> graph.construct_ontology_turtle(id)
  -> OwlreadyFusekiReasoner.load_from_fuseki(id)
  -> 返回 classes / individuals / properties
```

### 7.3 Pellet 推理

```text
UI 点击“执行 Pellet”
  -> API /ontologies/{id}/reason
  -> Owlready2 load ontology
  -> sync_reasoner_pellet()
  -> 返回 success / failed / error
```

### 7.4 测量推理

```text
录入 Measurement
  -> graph.create_measurement()
  -> inference.run_inference()
  -> 读取当前本体最近一次 Owlready/Pellet 状态，必要时提示先执行本体推理
  -> evaluate_single()
  -> graph.save_inference_result()
  -> UI 展示推理链
```

### 7.5 规格变更重推理

```text
输入新 lower / upper
  -> create_specification()
  -> 查询历史 Measurement
  -> 逐条 run_inference()
  -> 比较 old_status / new_status
  -> 保存 SpecChangeImpact
  -> UI 展示差异报告
```

### 7.6 LLM 问答

```text
用户问题
  -> qa.answer_question()
  -> 查询推理链
  -> 构造 evidence context
  -> 调用 LLM 或本地 fallback
  -> 返回中文解释
```

## 8. 配置

```text
FUSEKI_BASE_URL=http://localhost:3030
FUSEKI_DATASET=manufacturing-trial
FUSEKI_USER=
FUSEKI_PASSWORD=

LLM_PROVIDER=claude
CLAUDE_API_KEY=
CLAUDE_MODEL=

API_BASE_URL=http://localhost:8000
API_PREFIX=/api/v1
```

## 9. 依赖

```text
fastapi
uvicorn
requests
streamlit
rdflib>=7.0
owlready2
pytest
```

说明：

- `rdflib` 用于 Turtle 与 RDF/XML 转换。
- `owlready2` 用于本体加载和 Pellet 调用。
- Pellet 需要 Java 运行环境；如果没有 Java，API 返回明确错误，页面展示失败原因。
- 第一阶段使用 `requests` 直接访问 Fuseki HTTP 端点，不额外引入 `SPARQLWrapper`；如后续查询复杂度上升，可再替换为专门客户端库。

## 10. 风险与处理

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| Fuseki 未启动 | 本体无法加载和查询 | `/health` 和页面状态明确提示 |
| Owlready2 不支持直接加载 Turtle | 加载失败 | 先用 RDFLib 转 RDF/XML 再交给 Owlready2 |
| Pellet 依赖 Java | 推理失败 | API 捕获错误，提示安装 Java |
| LLM API Key 缺失 | 问答无法远端生成 | 使用本地 fallback 解释推理链 |
| MVP 中 SWRL 表达不完善 | 语义推理结果有限 | 业务判定保留确定性 Python，Pellet 先做一致性和扩展预留 |

## 11. 第一阶段交付边界

第一阶段只交付框架和最小闭环：

- 能发现多个本体。
- 能加载多个本体到 Fuseki。
- 能通过 Owlready2 从 Fuseki 加载当前本体。
- 能调用 Pellet 并展示状态。
- 能录入测量并持久化推理链。
- 能执行规格变更重推理。
- 能通过 LLM/fallback 回答“为什么 Fail”。
- 页面支持本体切换和核心交互。

不在第一阶段实现：

- 复杂 RBAC。
- 生产级异步任务队列。
- 向量数据库 / RAG。
- React 前端。
- 完整制造业总本体。

---

## 12. 命名与数据规范（补充）

### 12.1 命名空间

```text
基础 IRI:    https://hifar.top/mto/
本体 IRI:    https://hifar.top/mto/onto/{ontology_id}#
本体图 IRI:  https://hifar.top/mto/graph/{ontology_id}
数据图 IRI:  https://hifar.top/mto/graph/{ontology_id}/data
结果图 IRI:  https://hifar.top/mto/graph/{ontology_id}/result
规格图 IRI:  https://hifar.top/mto/graph/{ontology_id}/spec
实例 IRI:    https://hifar.top/mto/data/{ontology_id}/{class}/{local_id}
推理链 IRI:  https://hifar.top/mto/data/{ontology_id}/result/{measurement_id}
前缀:
  mto:       https://hifar.top/mto/onto/manufacturing-trial#
  mtod:      https://hifar.top/mto/data/manufacturing-trial/
```

### 12.2 推理链谓词（RDF 层契约）

| 谓词 | 定义域 | 值域 | 基数 |
|---|---|---|---|
| `mto:hasLatestResult` | Measurement | Result | 0..1 |
| `mto:forMeasurement` | Result | Measurement | 1 |
| `mto:resultStatus` | Result | {Pass, Fail_Low, Fail_High} | 1 |
| `mto:appliedRule` | Result | xsd:string | 1 |
| `mto:againstSpecVersion` | Result | Specification | 1 |
| `mto:deviation` | Result | xsd:decimal | 0..1 |
| `mto:evidenceValue` | Result | xsd:decimal | 1 |
| `mto:evidenceLowerLimit` / `evidenceUpperLimit` | Result | xsd:decimal | 1 |
| `mto:inferredAt` | Result | xsd:dateTime | 1 |
| `mto:reasoner` | Result | xsd:string (`python-deterministic` / `pellet-swrl`) | 1 |
| `mto:supersedesSpec` | Specification | Specification | 0..1 |

### 12.3 本体 TTL 元信息头

每个 `.ttl` 顶部必须带注释块，供 `ontology_registry` 解析：

```turtle
# ontology-id: manufacturing-trial
# ontology-label: 制造业试验数据管理本体
# ontology-version: 1.0.0
# ontology-swrl: manufacturing-trial.swrl
```

---

## 13. 任务拆分与并行计划

### 13.1 依赖拓扑（可并行通道）

```text
           ┌─ A. 基础设施 ─┐
           │               │
           ▼               ▼
  B. 本体 & 注册表    C. Fuseki 客户端
           │               │
           └──────┬────────┘
                  ▼
         D. 图谱访问层 graph.py
          │        │        │
          ▼        ▼        ▼
  E. 推理   F. 参数   G. Owlready/Pellet  (三者可并行)
          │        │        │
          └────────┼────────┘
                   ▼
              H. API 层
                   │
                   ▼
             I. Streamlit
                   │
                   ▼
              J. 问答 LLM (可与 I 并行，依赖 graph)
                   │
                   ▼
                K. 测试 & 演示数据（贯穿始终，末期集中）
```

### 13.2 任务表（Owner 用 T-编号引用）

| ID | 任务 | 依赖 | 产出 | 验收 | 可并行组 |
|---|---|---|---|---|---|
| T-A1 | `requirements.txt` / `.env.example` / `docker-compose.yml` | — | Fuseki 可 `docker compose up` | curl `:3030/$/ping` 200 | 组 1 |
| T-A2 | 目录骨架 + `README.md` | — | 目录树 | `python -m compileall` 通过 | 组 1 |
| T-B1 | `ontology_registry.py` + 2 个示例 TTL | A2 | `discover()` 返回 ≥2 | 单测列出 2 本体 | 组 2 |
| T-C1 | `sparql_client.py`（SELECT/UPDATE/GSP） | A1 | Fuseki 可读写 | 集成测试写入再读取 | 组 2 |
| T-D1 | `graph.py` 加载/主体/测量/规格 | B1, C1 | `load_ontologies()` 成功 | 命名图三元组数 > 0 | — |
| T-E1 | `inference.py` evaluate+run+rerun | D1 | Pass/Fail/重推理正确 | pytest 参数化 | 组 3 |
| T-F1 | `parameters.py` 运行时注册 | D1 | 参数出现在 SPARQL | API 测试 | 组 3 |
| T-G1 | `owlready_reasoner.py` Pellet 集成 | D1 | 返回 classes/indiv/props + status | 本地测试 | 组 3 |
| T-H1 | `api/main.py` 所有端点 | E1,F1,G1 | OpenAPI 文档可访问 | httpx 集成测试 | — |
| T-I1 | `mvp/frontend/app.py` Streamlit 五 Tab | H1 | 端到端可点 | 手工脚本 | 组 4 |
| T-J1 | `qa.py` 模板 + LLM + fallback | D1 | `/qa` 返回可解释答复 | fallback 单测 | 组 4 |
| T-K1 | `demo_data.py` 生成 3 批次 150 条 | D1 | 可重入导入 | 查询条数一致 | 贯穿 |
| T-K2 | `tests/` 回归套件 | 各模块 | pytest 全绿 | CI 可复用 | 贯穿 |

### 13.3 建议并行编排（按开发者数量）

- **1 人**：顺序 A→B/C→D→E/F/G→H→I/J→K。
- **2 人**：P1 走 A1→C1→D1→E1→H1；P2 走 A2→B1→G1→J1→I1；K 由先完成者接手。
- **3 人**：增开第三路 F1+K1+K2。

---

## 14. API 契约（补全）

本章所有端点均位于 `/api/v1` 前缀下，响应必须使用 §22.3 的统一信封：

```json
{"ok": true, "data": {...}, "error": null, "trace_id": "...", "trace": [...]}
```

以下示例只展示 `data` 部分，避免重复。

### 14.1 `POST /ontologies/load`

```json
// Request
{ "reload": true }
// Response
{ "loaded": [
  {"ontology_id":"manufacturing-trial","graph_iri":"...","triples":842,"ms":135},
  {"ontology_id":"process-window","graph_iri":"...","triples":231,"ms":54}
]}
```

### 14.2 `GET /ontologies/{id}/subjects?limit=200&q=Batch`

该端点必须从 Fuseki named graph `CONSTRUCT` Turtle 后交给 Owlready2 加载；禁止直接读取本地 TTL 文件后返回页面。

```json
{
  "ontology_id": "manufacturing-trial",
  "loaded_by": "owlready2",
  "reasoner": "pellet",
  "pellet_status": "success",
  "classes":[{"iri":"mto:Batch","label":"批次","n_instances":3}],
  "individuals":[{"iri":"mtod:batch/B01","type":"mto:Batch","label":"B01"}],
  "object_properties":[{"iri":"mto:belongsToTrial","domain":"Batch","range":"Trial"}],
  "data_properties":[{"iri":"mto:measuredValue","range":"xsd:decimal"}]
}
```

### 14.3 `POST /measurements`

```json
// Request
{"ontology_id":"manufacturing-trial","batch":"B01","parameter":"temperature","value":197.2,"operator":"Alice"}
// Response
{"measurement_id":"M007","status":"Fail_High","rule":"Rule_Fail_High","deviation":2.2,
 "spec_version":"Spec_v1","inferred_at":"2026-04-23T10:02:11Z","reasoner":"python-deterministic"}
```

### 14.4 `POST /specifications/change`

```json
// Request
{"ontology_id":"manufacturing-trial","parameter":"temperature","lower":180,"upper":190,"reason":"产线收紧"}
// Response
{"spec_version":"Spec_v2","total":150,"changed":[
  {"measurement_id":"M003","old":"Pass","new":"Fail_High","deviation":+1.3}
],"ms":842}
```

### 14.5 `POST /qa`

```json
// Request
{"ontology_id":"manufacturing-trial","question":"M007 为什么 Fail？"}
// Response
{"answer":"M007 判定为 Fail_High：测量值 197.2°C 高于 Spec_v1 上限 195°C，触发 Rule_Fail_High，偏差 +2.2°C。",
 "source":"llm","sparql":"...","evidence":{"measurement_id":"M007","status":"Fail_High","rule":"Rule_Fail_High","spec_version":"Spec_v1","upper":195,"value":197.2,"deviation":2.2}}
```

### 14.6 `/health`

探测：`fuseki.ping` / `owlready_import` / `java_available` / `pellet_probe` / `llm_key_present`。任一 DOWN 返回 200 + 明细，不抛 5xx。

---

## 15. 关键代码原型

> 所有原型仅定义接口骨架与核心流程，具体实现落在对应 T-编号任务。函数签名与返回结构是后续实现的**契约**。

### 15.1 `ontology_registry.py`（T-B1）

**用途**：扫描 `mvp/ontology/`，解析 TTL 头部注释，生成稳定 `ontology_id`。
**输入**：目录路径。**输出**：`OntologyDescriptor` 列表。
**边界**：不连接 Fuseki，不做 Owlready 加载；纯文件层。

```python
from dataclasses import dataclass
from pathlib import Path
import re

NS_GRAPH = "https://hifar.top/mto/graph/"

@dataclass(frozen=True)
class OntologyDescriptor:
    ontology_id: str
    label: str
    version: str
    ttl_path: Path
    swrl_path: Path | None
    graph_iri: str
    data_graph_iri: str
    result_graph_iri: str
    spec_graph_iri: str

_HEADER = re.compile(r"^#\s*ontology-(id|label|version|swrl):\s*(.+)$")

def parse_header(ttl: Path) -> dict[str, str]:
    meta = {}
    for line in ttl.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        m = _HEADER.match(line)
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta

def discover(root: Path) -> list[OntologyDescriptor]:
    out = []
    for ttl in sorted(root.glob("*.ttl")):
        m = parse_header(ttl)
        if "id" not in m:
            continue
        swrl = root / m["swrl"] if m.get("swrl") else None
        out.append(OntologyDescriptor(
            ontology_id=m["id"],
            label=m.get("label", m["id"]),
            version=m.get("version", "0.0.0"),
            ttl_path=ttl,
            swrl_path=swrl if swrl and swrl.exists() else None,
            graph_iri=f"{NS_GRAPH}{m['id']}",
            data_graph_iri=f"{NS_GRAPH}{m['id']}/data",
            result_graph_iri=f"{NS_GRAPH}{m['id']}/result",
            spec_graph_iri=f"{NS_GRAPH}{m['id']}/spec",
        ))
    return out
```

**落地说明**：`graph.load_ontologies` 遍历结果调用 `sparql_client.upload_graph`。

### 15.2 `sparql_client.py`（T-C1）

**用途**：Fuseki 访问单一入口。
**边界**：不含业务语义；失败抛 `FusekiError`，让上层决定提示。
**端点**：不要硬编码 `/sparql`，按 Fuseki 配置派生 `query_url`、`update_url`、`data_url`，默认如下：

```text
query_url  = {base_url}/{dataset}/query
update_url = {base_url}/{dataset}/update
data_url   = {base_url}/{dataset}/data
```

```python
import requests
from dataclasses import dataclass

class FusekiError(RuntimeError): ...

@dataclass
class FusekiClient:
    base_url: str                   # http://localhost:3030
    dataset: str                    # manufacturing-trial
    user: str | None = None
    password: str | None = None
    timeout: float = 20.0

    @property
    def query_url(self): return f"{self.base_url}/{self.dataset}/query"
    @property
    def update_url(self): return f"{self.base_url}/{self.dataset}/update"
    @property
    def data_url(self): return f"{self.base_url}/{self.dataset}/data"

    @property
    def _auth(self):
        return (self.user, self.password) if self.user else None

    def select(self, sparql: str) -> list[dict]:
        r = requests.post(self.query_url,
                          data={"query": sparql},
                          headers={"Accept": "application/sparql-results+json"},
                          auth=self._auth, timeout=self.timeout)
        if r.status_code >= 400:
            raise FusekiError(f"SELECT {r.status_code}: {r.text[:200]}")
        return r.json()["results"]["bindings"]

    def update(self, sparql_update: str) -> None:
        r = requests.post(self.update_url,
                          data={"update": sparql_update},
                          auth=self._auth, timeout=self.timeout)
        if r.status_code >= 400:
            raise FusekiError(f"UPDATE {r.status_code}: {r.text[:200]}")

    def construct(self, sparql: str) -> str:   # 返回 Turtle
        r = requests.post(self.query_url,
                          data={"query": sparql},
                          headers={"Accept": "text/turtle"},
                          auth=self._auth, timeout=self.timeout)
        if r.status_code >= 400:
            raise FusekiError(f"CONSTRUCT {r.status_code}: {r.text[:200]}")
        return r.text

    def upload_graph(self, graph_iri: str, turtle_text: str) -> None:
        # Graph Store Protocol, PUT 覆盖
        r = requests.put(self.data_url,
                         params={"graph": graph_iri},
                         data=turtle_text.encode("utf-8"),
                         headers={"Content-Type": "text/turtle"},
                         auth=self._auth, timeout=self.timeout)
        if r.status_code >= 400:
            raise FusekiError(f"GSP {r.status_code}: {r.text[:200]}")

    def ping(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/$/ping", timeout=3)
            return r.ok
        except requests.RequestException:
            return False
```

### 15.3 `owlready_reasoner.py`（T-G1）

**用途**：Fuseki→Owlready2→Pellet 主流程。
**边界**：Turtle 转 RDF/XML 经 RDFLib；Pellet 失败时仍返回 Owlready2 解析结果，`pellet_status=failed`+错误。**缓存**键为 `(ontology_id, graph_etag)`。

```python
import tempfile, time, shutil, os
from pathlib import Path
import rdflib
from owlready2 import get_ontology, sync_reasoner_pellet, World

class ReasonResult(dict): ...

_CACHE: dict[str, ReasonResult] = {}

def _turtle_to_rdfxml(turtle_text: str, out_path: Path) -> None:
    g = rdflib.Graph()
    g.parse(data=turtle_text, format="turtle")
    g.serialize(destination=str(out_path), format="xml")

def load_and_reason(ontology_id: str, turtle_text: str,
                    run_pellet: bool = True, cache_key: str | None = None) -> ReasonResult:
    if cache_key and cache_key in _CACHE:
        return _CACHE[cache_key]
    tmp = Path(tempfile.mkdtemp(prefix=f"onto-{ontology_id}-"))
    try:
        rdfxml = tmp / f"{ontology_id}.owl"
        _turtle_to_rdfxml(turtle_text, rdfxml)
        world = World()
        onto = world.get_ontology(rdfxml.as_uri()).load()

        status, err, ms = "not_run", None, 0
        if run_pellet:
            t0 = time.time()
            try:
                with onto:
                    sync_reasoner_pellet([onto], infer_property_values=True,
                                         infer_data_property_values=True)
                status = "success"
            except Exception as e:          # Java 缺失 / 不一致
                status, err = "failed", str(e)[:500]
            ms = int((time.time() - t0) * 1000)

        result = ReasonResult(
            ontology_id=ontology_id,
            loaded_by="owlready2",
            reasoner="pellet",
            pellet_status=status,
            pellet_error=err,
            pellet_ms=ms,
            classes=[{"iri": c.iri, "label": str(c.label.first() or c.name)} for c in onto.classes()],
            individuals=[{"iri": i.iri, "type": (i.is_a[0].iri if i.is_a else None),
                          "label": str(i.label.first() or i.name)} for i in onto.individuals()],
            object_properties=[{"iri": p.iri} for p in onto.object_properties()],
            data_properties=[{"iri": p.iri} for p in onto.data_properties()],
        )
        if cache_key:
            _CACHE[cache_key] = result
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
```

**说明**：Pellet 需 Java；`pellet_status=failed` 时前端仍能展示主体列表，仅提示推理未完成。后续可把 `_CACHE` 换成 `functools.lru_cache` 或 Redis。

### 15.4 `inference.py`（T-E1）

**用途**：确定性判定 + 规格重推理。**边界**：不直接访问 Fuseki，经 `graph` 注入。

```python
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class Judgement:
    status: str           # Pass / Fail_Low / Fail_High
    rule: str
    deviation: float
    spec_version: str
    inferred_at: str
    reasoner: str = "python-deterministic"

def evaluate_single(value: float, lower: float, upper: float, spec_version: str) -> Judgement:
    now = datetime.now(timezone.utc).isoformat()
    if value < lower:
        return Judgement("Fail_Low", "Rule_Fail_Low", round(lower - value, 4), spec_version, now)
    if value > upper:
        return Judgement("Fail_High", "Rule_Fail_High", round(value - upper, 4), spec_version, now)
    return Judgement("Pass", "Rule_Pass", 0.0, spec_version, now)

def rerun_after_spec_change(graph, ontology_id: str, parameter: str,
                            new_lower: float, new_upper: float, reason: str):
    new_spec = graph.create_specification(ontology_id, parameter, new_lower, new_upper, reason)
    changed = []
    for m in graph.list_measurements(ontology_id, parameter):
        j = evaluate_single(m["value"], new_lower, new_upper, new_spec["version"])
        if j.status != m["status"]:
            changed.append({"measurement_id": m["id"], "old": m["status"], "new": j.status,
                            "deviation": j.deviation})
        graph.save_inference_result(ontology_id, m["id"], j)
    return {"spec_version": new_spec["version"], "changed": changed}
```

### 15.5 `qa.py`（T-J1）

**用途**：NL→SPARQL→evidence→LLM。**边界**：SPARQL 走白名单模板，LLM 仅做"解释"，避免幻觉查询。

```python
import os, json, re, requests

TEMPLATES = {
  "why_fail": """
    PREFIX mto: <https://hifar.top/mto/onto/{ontology_id}#>
    SELECT ?value ?status ?rule ?specV ?lo ?up ?dev WHERE {{
      GRAPH <{data_graph_iri}> {{
        ?m a mto:Measurement ; mto:localId "{mid}" ;
           mto:measuredValue ?value .
      }}
      GRAPH <{result_graph_iri}> {{
        ?r mto:forMeasurement ?m ; mto:appliedRule ?rule ;
           mto:resultStatus ?status ;
           mto:againstSpecVersion ?specV ;
           mto:evidenceLowerLimit ?lo ; mto:evidenceUpperLimit ?up ;
           mto:deviation ?dev .
      }} }} LIMIT 1
  """,
}

def extract_intent(q: str) -> tuple[str, dict]:
    m = re.search(r"([MB]\d+).*为什么.*(Fail|失败)", q)
    if m:
        return "why_fail", {"mid": m.group(1)}
    return "unknown", {}

def local_fallback(evidence: dict) -> str:
    if not evidence: return "未在图谱中找到相关推理链。"
    return (f"{evidence['measurement_id']} 判定为 {evidence['status']}："
            f"测量值 {evidence['value']} 与 {evidence['spec_version']} 区间 "
            f"[{evidence['lower']}, {evidence['upper']}] 比较，触发 {evidence['rule']}，"
            f"偏差 {evidence['deviation']}。")

def call_claude(prompt: str) -> str | None:
    key = os.getenv("CLAUDE_API_KEY")
    if not key: return None
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"),
              "max_tokens": 400, "messages": [{"role": "user", "content": prompt}]},
        timeout=30)
    if not r.ok: return None
    return r.json()["content"][0]["text"]

def answer(graph, ontology_id: str, question: str) -> dict:
    intent, args = extract_intent(question)
    if intent == "unknown":
        return {"answer": "暂不支持该类问题，请按『M007 为什么 Fail？』格式提问。",
                "source": "local_fallback", "sparql": None, "evidence": {}}
    tpl = TEMPLATES[intent]
    sparql = tpl.format(
        ontology_id=ontology_id,
        data_graph_iri=graph.graph_iri(ontology_id, kind="data"),
        result_graph_iri=graph.graph_iri(ontology_id, kind="result"),
        **args,
    )
    rows = graph.sparql.select(sparql)
    evidence = graph.normalize_evidence(rows, args)
    prompt = (f"你是制造业质量分析助手。基于以下推理链 JSON，用中文一段话解释判定原因，"
              f"必须包含：测量值、规则、规格版本、上下限、偏差。\nJSON:\n{json.dumps(evidence, ensure_ascii=False)}")
    text = call_claude(prompt)
    return {"answer": text or local_fallback(evidence),
            "source": "llm" if text else "local_fallback",
            "sparql": sparql, "evidence": evidence}
```

### 15.6 FastAPI `main.py`（T-H1，骨架）

下面代码只展示路由形状；实际实现必须：

- 使用 `APIRouter(prefix="/api/v1")`。
- 使用 §22.3 的统一响应信封。
- 给所有路由接入 `auth_stub` 和 `TraceMiddleware`。
- 不在 Streamlit 中绕过这些 API 直接调用 core。

```python
from fastapi import FastAPI, APIRouter, Request, Depends
from pydantic import BaseModel
from mvp.core import graph as G, inference as I, parameters as P, qa as Q, owlready_reasoner as R
from mvp.api import envelope

app = FastAPI(title="Manufacturing Trial Ontology MVP")
v1 = APIRouter(prefix="/api/v1")

def auth_stub(): return None

class MeasurementIn(BaseModel):
    ontology_id: str; batch: str; parameter: str; value: float; operator: str = "demo"

@v1.get("/health")
def health(request: Request, _=Depends(auth_stub)):
    return envelope.ok({"fuseki": G.client.ping(), "owlready": R.available(), "llm": bool(Q.has_key())},
                       trace=request.state.trace)

@v1.post("/ontologies/load")
def load_ontologies(payload: dict, request: Request, _=Depends(auth_stub)):
    return envelope.ok({"loaded": G.load_ontologies(reload=payload.get("reload", False))},
                       trace=request.state.trace)

@v1.get("/ontologies")
def list_ontologies(request: Request, _=Depends(auth_stub)):
    return envelope.ok(G.list_ontologies(), trace=request.state.trace)

@v1.get("/ontologies/{oid}/subjects")
def subjects(oid: str, request: Request, _=Depends(auth_stub)):
    ttl = G.construct_ontology_turtle(oid)
    data = R.load_and_reason(oid, ttl, run_pellet=True, cache_key=f"{oid}:{hash(ttl)}")
    return envelope.ok(data, trace=request.state.trace)

@v1.post("/measurements")
def create_measurement(m: MeasurementIn, request: Request, _=Depends(auth_stub)):
    return envelope.ok(G.create_and_infer(m.ontology_id, m.batch, m.parameter, m.value, m.operator),
                       trace=request.state.trace)

@v1.post("/specifications/change")
def change_spec(payload: dict, request: Request, _=Depends(auth_stub)):
    return envelope.ok(I.rerun_after_spec_change(G, **payload), trace=request.state.trace)

@v1.post("/qa")
def qa(payload: dict, request: Request, _=Depends(auth_stub)):
    return envelope.ok(Q.answer(G, payload["ontology_id"], payload["question"]),
                       trace=request.state.trace)

app.include_router(v1)
```

### 15.7 Streamlit `mvp/frontend/app.py`（T-I1，骨架）

```python
import streamlit as st, requests, os
API = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
PREFIX = os.getenv("API_PREFIX", "/api/v1")
BASE = f"{API}{PREFIX}"

st.set_page_config(page_title="MTO MVP", layout="wide")
st.session_state.setdefault("ontology_id", None)

# —— 顶部状态 ——
h = requests.get(f"{BASE}/health").json()["data"]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Fuseki", "UP" if h["fuseki"] else "DOWN")
c2.metric("Owlready2", "OK" if h["owlready"] else "MISSING")
c3.metric("LLM", "配置" if h["llm"] else "fallback")
c4.metric("API", API)

ontos = requests.get(f"{BASE}/ontologies").json()["data"]
oid = st.selectbox("当前本体", [o["ontology_id"] for o in ontos],
                   key="ontology_id") if ontos else None

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["本体加载", "Owlready 主体", "Pellet 推理", "测量/规格", "参数/问答"])

with tab1:
    if st.button("加载全部本体到 Fuseki"):
        st.json(requests.post(f"{BASE}/ontologies/load", json={"reload": True}).json())

with tab2:
    if oid and st.button("拉取并展示主体"):
        data = requests.get(f"{BASE}/ontologies/{oid}/subjects").json()["data"]
        st.write(f"Pellet: **{data['pellet_status']}**")
        st.dataframe(data["classes"]); st.dataframe(data["individuals"])

with tab5:
    q = st.text_input("问题", "M007 为什么 Fail？")
    if st.button("提问") and oid:
        st.json(requests.post(f"{BASE}/qa", json={"ontology_id": oid, "question": q}).json())
```

---

## 16. 验收标准（细化）

| 场景 | 操作 | 期望 |
|---|---|---|
| V1 多本体加载 | `POST /ontologies/load` | 返回 ≥2 条，Fuseki 对应 graph `COUNT(*)` > 0 |
| V2 主体展示 | `GET /ontologies/{id}/subjects` | classes 非空；individuals 可为空但必须返回数组；pellet_status ∈ {success, failed, not_run}，failed 时 error 非空 |
| V3 本体切换 | UI 下拉切换 | Tab 2 刷新为新本体数据，session_state 同步 |
| V4 测量推理 | 录入 197.2 / 上限 195 | status=Fail_High, rule=Rule_Fail_High, deviation=2.2 |
| V5 规格重推理 | 上限 195→190 | `changed` 数组包含预期 M 编号，耗时 < 10s/150 条 |
| V6 新增参数 | 注册「振动频率」 | 下一次 `GET /parameters` 包含它；UI 下拉出现 |
| V7 LLM 问答 | 问 M007 为什么 Fail | 答复含测量值、规则、规格版本、偏差；无 key 时 source=local_fallback |
| V8 健康检查 | 杀掉 Fuseki | `/health.fuseki=false`，UI 显示 DOWN，不崩 |
| V8.1 API 前缀 | 调用 `/api/v1/ontologies` | 返回统一信封；无 `/api/v1` 的同名路径不作为正式契约 |
| V8.2 图隔离 | 清空 result 图 | ontology/data/spec 图三元组不变 |
| V8.3 Owlready 来源 | 临时改动本地 TTL 但不 reload Fuseki | `/subjects` 仍展示 Fuseki 中的旧版本，证明页面不是直接读文件 |

---

## 17. 风险补充与处置

| 风险 | 触发条件 | 处置 |
|---|---|---|
| Owlready2 丢失 SWRL | Turtle→RDF/XML 转换 | 保留原 `.swrl` 文件，Pellet 阶段附加 `onto.imports` |
| Pellet 并发 | 多请求同时触发 | `owlready_reasoner._CACHE` + 进程级锁；推理 API 加 `X-Rate-Limit` |
| Fuseki GSP PUT 覆盖 | 重复 load 丢三元组 | 采用 `PUT` 覆盖策略；增量需改 `POST` 并在 `graph` 层 dedupe |
| LLM 幻觉 | 自由生成 SPARQL | 仅走 `TEMPLATES` 白名单；LLM 不承担查询 |
| 时间一致性 | 多节点时钟差 | 推理时间一律 UTC，由后端生成 |

---

## 18. LLM 多厂商适配（Claude / OpenAI / DeepSeek / Qwen）

### 18.1 设计原则

- 统一 `LLMProvider` 协议，业务代码只依赖抽象。
- DeepSeek 与 Qwen 均提供 OpenAI 兼容端点，因此共用 `OpenAICompatibleProvider`，仅通过 `base_url` + `model` 区分。
- Claude 使用独立 `ClaudeProvider`。
- 任一 provider 不可用（无 key / 超时 / HTTP 非 2xx）→ 自动降级 `local_fallback`，响应 `source` 字段显式标注。
- 前端 Tab 5 与 `/health` 均显示当前 provider 与可用性。

### 18.2 环境变量

```env
LLM_PROVIDER=claude           # claude | openai | deepseek | qwen
LLM_MODEL=                    # 为空则用默认：claude-sonnet-4-5 / gpt-4o-mini / deepseek-chat / qwen-plus
LLM_TIMEOUT=30
CLAUDE_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
QWEN_API_KEY=
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 18.3 代码原型 `mvp/core/llm/`

**`base.py`**

```python
from typing import Protocol

class LLMProvider(Protocol):
    name: str
    default_model: str
    def available(self) -> bool: ...
    def chat(self, prompt: str, *, max_tokens: int = 400, temperature: float = 0.2) -> str | None: ...
```

**`openai_compat.py`**（OpenAI / DeepSeek / Qwen 共用）

```python
import os, requests
from dataclasses import dataclass

@dataclass
class OpenAICompatibleProvider:
    name: str
    api_key_env: str
    base_url_env: str
    default_base_url: str
    default_model: str
    timeout: float = 30.0

    @property
    def _key(self) -> str | None: return os.getenv(self.api_key_env)
    @property
    def _base(self) -> str: return os.getenv(self.base_url_env, self.default_base_url).rstrip("/")

    def available(self) -> bool: return bool(self._key)

    def chat(self, prompt, *, max_tokens=400, temperature=0.2):
        if not self._key: return None
        model = os.getenv("LLM_MODEL") or self.default_model
        try:
            r = requests.post(f"{self._base}/chat/completions",
                headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "temperature": temperature,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=self.timeout)
            if not r.ok: return None
            return r.json()["choices"][0]["message"]["content"]
        except requests.RequestException:
            return None

OPENAI   = OpenAICompatibleProvider("openai",   "OPENAI_API_KEY",   "OPENAI_BASE_URL",
                                    "https://api.openai.com/v1", "gpt-4o-mini")
DEEPSEEK = OpenAICompatibleProvider("deepseek", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL",
                                    "https://api.deepseek.com/v1", "deepseek-chat")
QWEN     = OpenAICompatibleProvider("qwen",     "QWEN_API_KEY",     "QWEN_BASE_URL",
                                    "https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus")
```

**`claude.py`**

```python
import os, requests
from dataclasses import dataclass

@dataclass
class ClaudeProvider:
    name: str = "claude"
    default_model: str = "claude-sonnet-4-5"
    timeout: float = 30.0

    def available(self) -> bool: return bool(os.getenv("CLAUDE_API_KEY"))

    def chat(self, prompt, *, max_tokens=400, temperature=0.2):
        key = os.getenv("CLAUDE_API_KEY")
        if not key: return None
        model = os.getenv("LLM_MODEL") or self.default_model
        try:
            r = requests.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": model, "max_tokens": max_tokens, "temperature": temperature,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=self.timeout)
            if not r.ok: return None
            return r.json()["content"][0]["text"]
        except requests.RequestException:
            return None
```

**`factory.py`**

```python
import os
from .claude import ClaudeProvider
from .openai_compat import OPENAI, DEEPSEEK, QWEN

_REG = {"claude": ClaudeProvider(), "openai": OPENAI, "deepseek": DEEPSEEK, "qwen": QWEN}

def get_provider():
    name = (os.getenv("LLM_PROVIDER") or "claude").lower()
    return _REG.get(name, _REG["claude"])
```

**`qa.py` 改动（片段）**

```python
from mvp.core.llm.factory import get_provider

def answer(graph, ontology_id, question):
    ...
    provider = get_provider()
    text = provider.chat(prompt) if provider.available() else None
    return {"answer": text or local_fallback(evidence),
            "source": provider.name if text else "local_fallback",
            "provider_available": provider.available(),
            "sparql": sparql, "evidence": evidence}
```

### 18.4 验收补充

- **V9**：`LLM_PROVIDER=openai` 且无 `OPENAI_API_KEY` → 响应 `source=local_fallback`，不抛异常。
- **V10**：切换 `LLM_PROVIDER=deepseek` 并配置 key → 相同问题获得非空答复，`source=deepseek`。
- **V11**：`/health.llm` 返回 `{provider: "qwen", available: true|false}`。

---

## 19. Fuseki 部署形态决策

### 19.1 三种形态对比

| 维度 | A. 单 dataset + 多 named graph | B. 一本体一 dataset | C. 单 dataset 单默认图 |
|---|---|---|---|
| URL | `/mto/sparql`，`GRAPH <iri>` | `/mto-core/sparql`、`/mto-spec/sparql` | `/mto/sparql` |
| 跨本体 SPARQL | 原生 `FROM NAMED` | 需 `SERVICE` 联邦 | 天然跨，失去来源标记 |
| 单本体清空 | `CLEAR GRAPH <iri>` | 删 dataset | 不可单独清 |
| 事务 | dataset 内原子 | 跨 dataset 无事务 | 原子 |
| 资源 | 1 个 TDB2 | N 个 TDB2，内存 × N | 1 个 |
| 命名空间冲突 | 图隔离、前缀可复用 | 完全隔离 | **易冲突** |
| 备份 | 一次备份拿全部 | 每 dataset 单独备份 | 一次备份 |
| 推理链隔离 | 独立 `result` 图，清理方便 | 散各处或另建 dataset | 混在一起 |
| 本项目影响 | 切换、重推理、问答均最简 | qa.py 要多端点路由 | 失去"本体切换"能力 |

### 19.2 选择：A 方案

**Graph IRI 约定**：

```text
本体图 :     https://hifar.top/mto/graph/{ontology_id}
业务数据图 : https://hifar.top/mto/graph/{ontology_id}/data
推理链图 :   https://hifar.top/mto/graph/{ontology_id}/result
规格历史图 : https://hifar.top/mto/graph/{ontology_id}/spec
```

**分图价值**：

- `OwlreadyFusekiReasoner` 只 CONSTRUCT 本体图，不把海量测量数据喂给 Pellet。
- 清空推理结果重跑：`CLEAR GRAPH <.../result>`，不影响本体与业务数据。
- 规格变更影响审计：`spec` 图按版本追加，绝不覆盖。

### 19.3 Dataset 配置（Fuseki）

```text
Dataset:  manufacturing-trial   (TDB2, persistent)
Service:  query (SPARQL 1.1)
Service:  update (SPARQL 1.1 Update)
Service:  gsp (Graph Store Protocol, read + write)
Assembler: 默认 TDB2 模板
```

`docker-compose.yml` 关键配置：

```yaml
services:
  fuseki:
    image: stain/jena-fuseki:4.10.0
    environment:
      ADMIN_PASSWORD: admin
      FUSEKI_DATASET_1: manufacturing-trial
      JVM_ARGS: "-Xmx2g"
    ports: ["3030:3030"]
    volumes: ["./.fuseki-data:/fuseki"]
```

### 19.4 验收补充

- **V12**：`CLEAR GRAPH <.../result>` 后 Pellet 状态不变、业务数据图三元组数不变。
- **V13**：跨本体 SPARQL `SELECT ?g (COUNT(*) AS ?n) { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g` 一次返回全部图统计。

---

## 20. 推理位置决策（L3）

### 20.1 推荐方案：双轨并行 + 显式标签

| 推理任务 | 执行位置 | 触发 | 产出 |
|---|---|---|---|
| OWL 一致性 / 类层次 / 属性推断 | **Pellet** (`sync_reasoner_pellet`) | 本体加载后、规格变更后 | `pellet_status / pellet_ms / inferred_triple_count` |
| Pass / Fail_Low / Fail_High 业务判定 | **Python 确定性** | 每条 Measurement 录入、规格变更重推理 | `Result` 节点 + 推理链字段 |
| SWRL 规则（Rule_Pass / Fail_High / Fail_Low） | **Owlready2 + Pellet**（演示通道，可选） | 前端 Tab 3 勾选"对照模式" | `mto:reasoner="pellet-swrl"` 的平行 Result |

### 20.2 理由

1. 规格变更"秒级重推理"与"推理链可 diff"要求确定性、可调试、可回放 → Python 最优。
2. Pellet 的最大价值在 OWL 层：类层次、等价类、不相交、属性推断 → 保留。
3. 满足"用 Pellet 推理"字面要求：每次本体加载与规格变更后必跑一次，UI 显式展示。
4. 可演进：保留 `.swrl` 与 Pellet 通道，未来把 Rule_* 迁入 SWRL 做 A/B 对比。

### 20.3 前端标注规则

- Result 节点持久化 `mto:reasoner ∈ {python-deterministic, pellet-swrl}`。
- Tab 4 每条结论旁显示徽标：🟦 Python / 🟪 Pellet-SWRL。
- Tab 3 展示：`pellet_status / pellet_ms / inferred_triple_count`，与业务判定来源独立。
- `/health.reasoner` 返回：`{deterministic: true, pellet: "available" | "failed" | "missing_java", pellet_error: "..."}`。
- 前端顶部状态栏增加 "推理器：Python✓ · Pellet✓/✗" 标签。

### 20.4 验收补充

- **V14**：关闭 Java（模拟 `missing_java`）→ 业务判定正常、`/ontologies/{id}/reason` 返回 `pellet_status=failed`，前端仅 Tab 3 标红，其他 Tab 正常。
- **V15**：开启"SWRL 对照模式" → Result 图同时出现 `python-deterministic` 与 `pellet-swrl` 两条 Result，`deviation` 一致。

---

## 21. 前端演进策略（L4：先 Streamlit，后续可扩展）

### 21.1 阶段划分

| 阶段 | 前端 | 时机 | 目标 |
|---|---|---|---|
| Phase 1（当前 MVP） | **Streamlit** | 3 周内 | 五 Tab 闭环演示；全部 UI 逻辑走 `API_BASE_URL` 访问 FastAPI |
| Phase 2（可选增强） | Streamlit + 自定义组件 | 演示通过后 | 图谱可视化（pyvis/vis-network 嵌入）、推理链时间线 |
| Phase 3（长期） | **React / Next.js** 独立工程 | 用户量 >1 人 / 生产化需求 | 登录、多租户、细粒度交互、WebSocket 实时推理 |

### 21.2 为 Phase 3 预留的约束（现在就要守住）

为了让未来 React 接入无需重写后端，Phase 1 实施时必须遵守：

1. **前后端分离**：Streamlit 不直接 import `mvp.core.*`；一律通过 FastAPI HTTP 调用。
2. **API 版本化**：所有路由挂在 `/api/v1/*` 前缀下，`main.py` 用 `APIRouter(prefix="/api/v1")`。
3. **CORS 默认开启**：便于 Phase 3 跨域访问。
4. **响应结构固定**：以 §22.3 为最终契约，必须包含 `trace` 字段。
   ```json
   {"ok": true, "data": {...}, "error": null, "trace_id": "...", "trace": [...]}
   ```
   失败时 `ok=false, error={"code":"...","message":"..."}`。
5. **无 Streamlit 专属字段**：响应里不要塞 pandas DataFrame / HTML 片段，前端自行渲染。
6. **会话状态在客户端**：当前本体 `ontology_id` 通过查询参数或请求体传递，不依赖服务端 session。
7. **鉴权钩子预留**：所有路由通过一个空实现的 `Depends(auth_stub)`，Phase 3 只换实现。

### 21.3 Streamlit 组件边界

- `app.py` 仅负责：UI 组件、调用 HTTP、展示结果。
- 所有对 Fuseki/Owlready/LLM 的访问一律经 FastAPI。
- 公共逻辑（格式化、徽标、错误提示）放 `mvp/frontend/ui_utils.py`，不触及业务。
- 避免使用 `st.experimental_*` 接口；使用 `st.session_state` 管理本体切换。

### 21.4 目录增补

```text
mvp/
  frontend/
    app.py              # Streamlit 入口
    ui_utils.py         # 格式化 / 徽标 / 错误提示
    tabs/
      tab_ontology.py
      tab_subjects.py
      tab_pellet.py
      tab_measure.py
      tab_qa.py
```

按 tab 拆文件可并行开发（对应 T-I1 子任务 T-I1a..T-I1e）。

### 21.5 API 响应统一包装（原型，已被 §22.3 扩展）

本节保留原始简版意图；实际实现以 §22.3 为准，必须额外返回 `trace`。

```python
# mvp/api/envelope.py
from fastapi import Request
from fastapi.responses import JSONResponse
from uuid import uuid4

def ok(data, status=200):
    return JSONResponse({"ok": True, "data": data, "error": None,
                         "trace_id": uuid4().hex}, status_code=status)

def fail(code: str, message: str, status=400):
    return JSONResponse({"ok": False, "data": None,
                         "error": {"code": code, "message": message},
                         "trace_id": uuid4().hex}, status_code=status)
```

### 21.6 CORS & 版本前缀（原型）

```python
# mvp/api/main.py（片段）
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="MTO MVP")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

v1 = APIRouter(prefix="/api/v1")
# ... v1.get(...) / v1.post(...)
app.include_router(v1)
```

### 21.7 验收补充

- **V16**：Streamlit 代码全量 grep 不出现 `from mvp.core`，只出现 `requests` 调用。
- **V17**：`curl http://localhost:8000/api/v1/ontologies` 返回统一信封结构。
- **V18**：未来替换为 React：仅需实现同样路径的 HTTP 客户端，无需改动任何 API 代码。

---

## 22. 用户可见的流程透明性（贯穿性设计原则）

### 22.1 原则声明（贯穿全部章节）

在功能的全部流程中，应保持**用户可见原则**：

1. 系统必须让用户清楚知道**当前流程走到哪里**（当前步骤、总步骤数、状态）。
2. 系统必须说明**为什么走到这里**（选择该链路的判据，例如为何走 Pellet 而非 Python、为何命中 `why_fail` 模板、为何降级到 local_fallback）。
3. 系统必须展示**推理或决策走了什么链路**（所用模块、SPARQL、规则、规格版本、LLM provider）。
4. 所有上述关键节点、链路选择、原因说明、执行状态必须**同步写入后台日志**，便于追踪、排查、理解系统行为。

> 该原则**覆盖本文档 §5、§6、§7、§14、§15、§18、§19、§20、§21 所有模块**；下文提出的 trace 结构、日志规范、UI 呈现是这些章节的统一补丁，不再在各章节重复。

### 22.2 执行轨迹模型 `ExecutionTrace`

每个对外 API 调用生成一条 `ExecutionTrace`，由一组 `TraceStep` 组成。结构：

```python
# mvp/core/trace.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

@dataclass
class TraceStep:
    step: str                 # "fetch_ontology" / "turtle_to_rdfxml" / "sync_reasoner_pellet" / ...
    status: str               # started | success | failed | skipped | fallback
    reason: str = ""          # 为什么走到这一步 / 为什么选这条分支
    detail: dict = field(default_factory=dict)  # 关键字段：IRI、耗时、命中模板、provider、行数
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    elapsed_ms: int | None = None

@dataclass
class ExecutionTrace:
    trace_id: str = field(default_factory=lambda: uuid4().hex)
    endpoint: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ontology_id: str | None = None
    steps: list[TraceStep] = field(default_factory=list)

    def log(self, step: str, status: str, reason: str = "", **detail):
        self.steps.append(TraceStep(step=step, status=status, reason=reason, detail=detail))
        return self.steps[-1]
```

### 22.3 统一响应信封（替换 §21.5）

原 §21.5 的信封增加 `trace` 字段：

```json
{
  "ok": true,
  "data": {...},
  "error": null,
  "trace_id": "a1b2c3...",
  "trace": [
    {"step":"resolve_ontology","status":"success","reason":"ontology_id=manufacturing-trial 命中注册表","detail":{"graph_iri":"..."},"elapsed_ms":3},
    {"step":"construct_ontology_turtle","status":"success","reason":"从 Fuseki 拉取本体图","detail":{"triples":842},"elapsed_ms":47},
    {"step":"turtle_to_rdfxml","status":"success","reason":"Owlready2 不直接支持 Turtle","detail":{"bytes":31200},"elapsed_ms":22},
    {"step":"sync_reasoner_pellet","status":"fallback","reason":"Java 未安装，跳过 Pellet","detail":{},"elapsed_ms":0},
    {"step":"collect_subjects","status":"success","reason":"返回 Owlready2 解析结果","detail":{"classes":7,"individuals":12}}
  ]
}
```

**规则**：

- `trace` 必须在成功与失败响应中均返回。
- 每个 step 的 `reason` 用**人类语言**写明链路选择依据，避免空串。
- `detail` 只放可审计的关键字段，不塞大对象。

### 22.4 日志规范

采用结构化日志（JSON 行），字段与 `TraceStep` 对齐，便于 `jq` / ELK / Loki 消费。

```python
# mvp/core/logging_setup.py
import logging, json, sys

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **getattr(record, "extra_fields", {}),
        }
        return json.dumps(payload, ensure_ascii=False)

def setup():
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [h]
    root.setLevel(logging.INFO)
```

**日志使用约束**：

| 场景 | logger | level | 必含字段 |
|---|---|---|---|
| API 入口 | `mto.api` | INFO | `trace_id`、`endpoint`、`ontology_id` |
| 每个 `TraceStep` | `mto.trace` | INFO（failed/fallback 用 WARNING） | `trace_id`、`step`、`status`、`reason`、`elapsed_ms` |
| Fuseki I/O | `mto.fuseki` | DEBUG（错误 ERROR） | `graph_iri`、`sparql_digest`、`rows` |
| Owlready/Pellet | `mto.reasoner` | INFO / WARNING | `pellet_status`、`pellet_ms`、`pellet_error` |
| LLM 调用 | `mto.llm` | INFO（失败 WARNING） | `provider`、`model`、`latency_ms`、`tokens_in/out` |
| 业务判定 | `mto.inference` | INFO | `measurement_id`、`rule`、`old_status`、`new_status`、`spec_version` |

**日志禁用项**：不记录 API Key、完整 prompt、完整 LLM 回复文本（可记录前 120 字摘要）。

### 22.5 FastAPI 中间件与装饰器（原型）

```python
# mvp/api/trace_middleware.py
import time, logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from mvp.core.trace import ExecutionTrace

log = logging.getLogger("mto.api")

class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace = ExecutionTrace(endpoint=f"{request.method} {request.url.path}")
        request.state.trace = trace
        t0 = time.time()
        log.info("request.begin", extra={"extra_fields": {
            "trace_id": trace.trace_id, "endpoint": trace.endpoint}})
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = int((time.time() - t0) * 1000)
            log.info("request.end", extra={"extra_fields": {
                "trace_id": trace.trace_id, "endpoint": trace.endpoint,
                "elapsed_ms": elapsed, "steps": len(trace.steps)}})

def step(trace, name: str, reason: str = "", **detail):
    """Context manager 记录一个 step 的耗时与结果；异常自动标 failed 并抛出。"""
    import contextlib, time as _t, logging as _l
    lg = _l.getLogger("mto.trace")
    @contextlib.contextmanager
    def _cm():
        t0 = _t.time()
        s = trace.log(name, "started", reason, **detail)
        try:
            yield s
            s.status = "success"; s.elapsed_ms = int((_t.time()-t0)*1000)
            lg.info(name, extra={"extra_fields": {
                "trace_id": trace.trace_id, "step": name, "status": s.status,
                "reason": reason, "elapsed_ms": s.elapsed_ms, **detail}})
        except Exception as e:
            s.status = "failed"; s.elapsed_ms = int((_t.time()-t0)*1000)
            s.detail["error"] = str(e)[:300]
            lg.warning(name, extra={"extra_fields": {
                "trace_id": trace.trace_id, "step": name, "status": "failed",
                "reason": reason, "error": str(e)[:300]}})
            raise
    return _cm()
```

**使用示例**：

```python
# mvp/api/routes_ontology.py
@v1.get("/ontologies/{oid}/subjects")
def subjects(oid: str, request: Request):
    trace = request.state.trace
    trace.ontology_id = oid
    with step(trace, "resolve_ontology", f"oid={oid} 命中注册表"):
        desc = G.get_descriptor(oid)
    with step(trace, "construct_ontology_turtle", "拉取本体图 Turtle", graph_iri=desc.graph_iri):
        ttl = G.construct_ontology_turtle(oid)
    with step(trace, "load_and_reason", "Owlready2 加载 + Pellet 推理"):
        result = R.load_and_reason(oid, ttl, run_pellet=True,
                                   cache_key=f"{oid}:{hash(ttl)}", trace=trace)
    return envelope.ok(result, trace=trace)
```

`load_and_reason` 内部也用 `step(trace, ...)` 记录 `turtle_to_rdfxml` / `owlready_load` / `sync_reasoner_pellet` / `collect_subjects`。

### 22.6 前端呈现规范（Streamlit）

每个 Tab 必须包含以下 UI 元素：

| 元素 | 样式 | 内容 |
|---|---|---|
| **进度条 / Stepper** | `st.progress` 或自定义列 | 当前步骤 / 总步骤，如 `3/5 正在执行 Pellet` |
| **链路面板**（可折叠） | `st.expander("🔍 本次执行链路")` | 渲染 `trace` 列表，每行：状态图标 + step + reason + 耗时 |
| **选择理由气泡** | `st.caption` | 例如 LLM 问答下方："provider=deepseek（配置生效） · 模板=why_fail · 证据来自 graph/manufacturing-trial/result" |
| **徽标** | 文本或 emoji | 🟢 success / 🟡 fallback / 🔴 failed / ⚪ skipped |
| **下载 trace** | `st.download_button` | 导出 JSON 便于反馈问题 |

**示例：Tab 5 问答**

```text
问题：M007 为什么 Fail？

[进度] ●●●●○  4/5 LLM 生成中

🔍 本次执行链路
 🟢 extract_intent     命中模板 why_fail              3 ms   why: 正则匹配 "M007" + "为什么" + "Fail"
 🟢 build_sparql       填充 graph_iri / mid          1 ms
 🟢 fuseki.select      返回 1 行 evidence           47 ms
 🟡 llm.call           deepseek 超时，降级 local   30020 ms  why: LLM_TIMEOUT=30s
 🟢 compose_answer     使用 local_fallback           2 ms

答复：M007 判定为 Fail_High …
来源：local_fallback（provider=deepseek 不可用）
```

### 22.7 可观测性数据流

```text
用户 UI 操作
  → FastAPI TraceMiddleware 生成 trace_id
  → 每个核心步骤用 step(trace, ...) 包裹
      ├─ 写入 ExecutionTrace.steps
      └─ 同步 JSON 行 stdout / logs/*.log
  → 统一信封把 trace 返回给前端
  → Streamlit 渲染 Stepper + 链路面板
  → 需要排查时：按 trace_id grep 日志
```

### 22.8 任务表增补

在 §13.2 任务表追加：

| ID | 任务 | 依赖 | 产出 | 验收 | 可并行组 |
|---|---|---|---|---|---|
| T-L1 | `mvp/core/trace.py` + `logging_setup.py` | A2 | Trace 与 JSON 日志基础设施 | 单测覆盖 step 成功/失败路径 | 组 1 |
| T-L2 | `TraceMiddleware` 与 `step()` 注入所有路由 | H1, L1 | 所有 API 响应含 `trace` 字段 | curl 任一端点可见 ≥3 个 step | 组 1 |
| T-L3 | Streamlit 链路面板 + 徽标组件 | I1, L2 | `ui_utils.render_trace()` | 五 Tab 均出现折叠面板 | 组 4 |
| T-L4 | 全模块埋点（graph/reasoner/qa/inference） | L2 | 每个模块关键节点可见 | 链路覆盖率 ≥90% | 贯穿 |

### 22.9 验收补充

- **V19**：核心 API（`/ontologies/load`、`/ontologies/{id}/subjects`、`/ontologies/{id}/reason`、`/measurements`、`/specifications/change`、`/qa`）成功响应包含 `trace_id` 且 `trace.length ≥ 3`；`/health` 至少包含探测步骤。
- **V20**：核心 API 失败响应也包含 `trace`，最后一个 step 状态为 `failed` 且 `reason` 非空。
- **V21**：按 `trace_id` 在 stdout 日志中 grep，能获得与响应 `trace` 一一对应的 JSON 行。
- **V22**：Streamlit 五个 Tab 均包含"🔍 本次执行链路"折叠面板与 stepper。
- **V23**：LLM 降级、Pellet 缺 Java、Fuseki 超时三种场景下，UI 均显示链路原因而非静默失败。
- **V24**：日志中不出现 `CLAUDE_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY / QWEN_API_KEY` 值。

### 22.10 与既有模块的映射（埋点清单）

| 模块 | 必埋 Step | `reason` 举例 |
|---|---|---|
| `graph.load_ontologies` | `scan_dir` / `upload_graph` | "发现 2 个 TTL" / "GSP PUT 覆盖" |
| `graph.construct_ontology_turtle` | `construct` | "只取本体图，避免把测量数据喂 Pellet" |
| `owlready_reasoner.load_and_reason` | `turtle_to_rdfxml` / `owlready_load` / `sync_reasoner_pellet` / `collect_subjects` | "Owlready2 不直接支持 Turtle" / "Java 未安装" |
| `inference.evaluate_single` | `evaluate` | "value > upper → Rule_Fail_High" |
| `inference.rerun_after_spec_change` | `create_specification` / `iterate_history` / `diff` | "新建 Spec_v2" / "遍历 150 条" |
| `parameters.register_parameter` | `insert_parameter` | "写入 data 图，不改 schema" |
| `qa.answer` | `extract_intent` / `build_sparql` / `fuseki_select` / `llm_call` / `compose_answer` | "命中 why_fail 模板" / "LLM 超时降级" |
| `llm.*.chat` | `http_post` | "provider=deepseek, model=deepseek-chat" |

### 22.11 风险补充

| 风险 | 触发 | 处置 |
|---|---|---|
| 日志泄漏密钥 | 打印 headers 全量 | 日志层统一 `sanitize()` 过滤 `*KEY*` 字段 |
| Trace 过大 | 长流程 step 数爆炸 | `trace` 仅保留关键节点（≤30），详情放 detail；日志不截断 |
| 前端面板拖慢 | 每次点击重拉 | `st.session_state` 缓存最近 5 条 trace，按 trace_id 查看 |
| 链路 reason 空洞 | 开发者偷懒传空串 | Lint 规则：`step(trace, name, reason="")` 禁用，CI grep 检查 |

---

## 23. 审阅补丁（P1–P14）

本章为 2026-04-23 审阅后对前序章节的收口补丁。规则：前文已写的保持不动；本章与前文冲突处，以本章为准。

### 23.1 P1 全局异常与信封一致性

FastAPI 默认对 404/422/未捕获异常返回 `{"detail": ...}`，不带 `trace`。必须添加全局异常处理器，确保统一信封：

```python
# mvp/api/exceptions.py
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from mvp.api import envelope

class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code, self.message, self.status = code, message, status

def install(app):
    @app.exception_handler(DomainError)
    async def _domain(request: Request, exc: DomainError):
        trace = getattr(request.state, "trace", None)
        if trace is not None:
            trace.log("domain_error", "failed", reason=exc.message, code=exc.code)
        return envelope.fail(exc.code, exc.message, status=exc.status, trace=trace)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        trace = getattr(request.state, "trace", None)
        return envelope.fail(f"HTTP_{exc.status_code}", str(exc.detail),
                             status=exc.status_code, trace=trace)

    @app.exception_handler(RequestValidationError)
    async def _validate(request: Request, exc: RequestValidationError):
        trace = getattr(request.state, "trace", None)
        if trace is not None:
            trace.log("request_validation", "failed",
                      reason="Pydantic 参数校验失败", errors=exc.errors()[:10])
        return envelope.fail("REQUEST_VALIDATION", "请求参数不合法", status=422, trace=trace)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        trace = getattr(request.state, "trace", None)
        if trace is not None:
            trace.log("unhandled", "failed", reason=str(exc)[:200])
        return envelope.fail("INTERNAL_ERROR", "服务内部错误", status=500, trace=trace)
```

`main.py` 启动时调用 `exceptions.install(app)`，置于 `TraceMiddleware` 之后。

### 23.2 P1+P13 `envelope.ok/fail` 扩展

```python
# mvp/api/envelope.py（修订版）
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

def _dump_trace(trace):
    if trace is None:
        return {"trace_id": None, "trace": [], "started_at": None, "elapsed_ms": None}
    started = trace.started_at
    now = datetime.now(timezone.utc).isoformat()
    return {
        "trace_id": trace.trace_id,
        "trace": [s.__dict__ for s in trace.steps],
        "started_at": started,
        "elapsed_ms": None,   # 由 TraceMiddleware 在结束时回填
    }

def ok(data, trace=None, status=200):
    return JSONResponse({"ok": True, "data": data, "error": None, **_dump_trace(trace)},
                        status_code=status)

def fail(code, message, trace=None, status=400):
    return JSONResponse({"ok": False, "data": None,
                         "error": {"code": code, "message": message}, **_dump_trace(trace)},
                        status_code=status)
```

### 23.3 P2 `load_and_reason` 接受可选 `trace`

修订 §15.3 的函数签名：

```python
def load_and_reason(ontology_id, turtle_text, *, run_pellet=True,
                    cache_key=None, trace=None):
    # 内部使用 step(trace, "...") 记录子步骤；trace=None 时用 _NoopStep 占位
    ...
```

`_NoopStep` 提供同样 API 但不写 trace/日志，避免 `if trace` 满地。

### 23.4 P3+P5 补齐 API 原型

补全端点（请求/响应均为 `data` 字段内容）。

**POST `/ontologies/{id}/reason`**
```json
// Request (可选)
{"force": false}
// Response data
{"ontology_id":"manufacturing-trial","pellet_status":"success","pellet_ms":312,
 "inferred_triple_count":18,"pellet_error":null}
```

**POST `/ontologies/{id}/activate`**（仅演示；正式请求仍需显式传 `ontology_id`）
```json
{"active_ontology_id":"manufacturing-trial","note":"仅用于演示；客户端必须在后续请求中显式携带 ontology_id"}
```

**GET `/parameters?ontology_id=...`**
```json
{"items":[{"code":"temperature","name":"注塑温度","unit":"°C","value_type":"number",
           "participates_in_inference":true,"created_at":"..."}]}
```

**POST `/parameters`**
```json
// Request
{"ontology_id":"manufacturing-trial","code":"vibration_frequency","name":"振动频率",
 "unit":"Hz","value_type":"number","participates_in_inference":true}
// Response
{"code":"vibration_frequency","created":true}   // 重复注册时 created=false
```

**GET `/measurements?ontology_id=...&parameter=...&limit=200`**
```json
{"items":[{"measurement_id":"M007","batch":"B03","parameter":"temperature","value":197.2,
           "status":"Fail_High","rule":"Rule_Fail_High","deviation":2.2,
           "spec_version":"Spec_v2","reasoner":"python-deterministic",
           "inferred_at":"..."}], "total":150}
```

**POST `/specifications`**（首次创建规格）
```json
// Request
{"ontology_id":"manufacturing-trial","parameter":"temperature","lower":180,"upper":195,"reason":"初始规格"}
// Response
{"spec_version":"Spec_v1","created":true}
```

**GET `/impacts/latest?ontology_id=...&parameter=...`**
```json
{"old_spec":"Spec_v1","new_spec":"Spec_v2","changed":[...],"generated_at":"..."}
```

### 23.5 P4 QA 模板补齐

`TEMPLATES` 白名单扩展到三类：

```python
TEMPLATES = {
    "why_fail": "...(§15.5 已有)...",
    "spec_change_impact": """
      PREFIX mto: <{onto_ns}>
      SELECT ?mid ?oldStatus ?newStatus ?oldSpec ?newSpec ?dev WHERE {{
        GRAPH <{result_graph_iri}> {{
          ?impact mto:forMeasurement ?m ;
                  mto:oldStatus ?oldStatus ; mto:newStatus ?newStatus ;
                  mto:oldSpecVersion ?oldSpec ; mto:newSpecVersion ?newSpec ;
                  mto:deviation ?dev .
          ?m mto:localId ?mid .
        }} FILTER (?oldSpec = "{old_spec}" && ?newSpec = "{new_spec}")
      }}
    """,
    "parameter_or_batch_summary": """
      PREFIX mto: <{onto_ns}>
      SELECT (COUNT(?r) AS ?n) ?status WHERE {{
        GRAPH <{data_graph_iri}> {{ ?m a mto:Measurement ; mto:forParameter ?p . ?p mto:parameterCode "{code}" . }}
        GRAPH <{result_graph_iri}> {{ ?r mto:forMeasurement ?m ; mto:resultStatus ?status . }}
      }} GROUP BY ?status
    """,
}
```

### 23.6 P6 "最新 Result" 语义

规则：

- 每条 Measurement 仅有一个当前 `mto:hasLatestResult`，指向最近一次 Result。
- 旧 Result 不删除，通过 `mto:supersededBy` 形成链。
- 重推理 SPARQL 模式：

```sparql
DELETE { GRAPH <.../result> { ?m mto:hasLatestResult ?old . ?old mto:supersededBy ?old2 . } }
INSERT { GRAPH <.../result> {
    ?m mto:hasLatestResult <NEW_IRI> .
    ?old mto:supersededBy <NEW_IRI> .
    <NEW_IRI> a mto:Result ; ... } }
WHERE  { GRAPH <.../result> { ?m mto:hasLatestResult ?old . OPTIONAL { ?old mto:supersededBy ?old2 } } }
```

补充谓词到 §12.2：`mto:supersededBy (Result→Result, 0..1)`。

### 23.7 P7 缓存键与并发

- 缓存键使用**Fuseki 图的稳定指纹**：`SELECT (sha256(GROUP_CONCAT(?s?p?o))) ...`，或对 CONSTRUCT 出的 Turtle 做 `hashlib.sha1`，不使用 Python 内置 `hash()`。
- `owlready_reasoner` 模块级 `threading.Lock()`，同一 key 的 Pellet 调用串行。
- Lock 超时 60s，超时返回 `pellet_status="busy"`，前端提示重试。

### 23.8 P8 `graph.py` 方法补齐

核心方法清单补充：

```text
create_trial(ontology_id, trial_id, ...)
create_batch(ontology_id, trial_id, batch_id, ...)
list_trials(ontology_id)
list_batches(ontology_id, trial_id=None)
```

### 23.9 P9 `/health` 字段统一

```json
{
  "fuseki": {"available": true, "base_url": "http://localhost:3030", "latency_ms": 4},
  "owlready": {"available": true, "version": "0.46"},
  "reasoner": {"deterministic": true, "pellet": "available", "pellet_error": null},
  "llm": {"provider": "deepseek", "available": true, "model": "deepseek-chat"}
}
```

所有其他章节的 `/health` 引用一律以此为准。

### 23.10 P10 `list_ontologies` 序列化契约

```json
[
  {"ontology_id":"...","label":"...","version":"1.0.0",
   "ttl_path":"mvp/ontology/manufacturing-trial.ttl",
   "swrl_path":"mvp/ontology/manufacturing-trial.swrl",
   "graph_iri":"...","data_graph_iri":"...","result_graph_iri":"...","spec_graph_iri":"...",
   "loaded":true,"triples":842}
]
```

### 23.11 P11 依赖与镜像修订

```text
fastapi>=0.111
uvicorn[standard]>=0.30
requests>=2.32
httpx>=0.27           # 测试集成
streamlit>=1.36
rdflib>=7.0
owlready2>=0.46
pydantic>=2.6
python-dotenv>=1.0
pytest>=8.2
pytest-asyncio>=0.23
```

Fuseki 镜像改用 `secoresearch/fuseki:5.x` 或 `apache/jena-fuseki:5.x`（官方最新）。Java 要求：`OpenJDK >= 11`（Pellet 基于 Java 8+，实测 11/17 均可）。

### 23.12 P12 `/ontologies/load` 语义

- `reload=true` 仅覆盖 `ontology` 图（GSP PUT）；**不触碰** `data/result/spec` 图。
- 响应体增加字段：`{"ontology_id":"...","ontology_graph_written":842,"data_graph_preserved":true}`。

### 23.13 P14 LLM prompt 约束

- Evidence JSON 最大 4 KB；超限时剪裁并在 prompt 中标注 `<truncated>`。
- Prompt 组装层统一 `sanitize()`，去除 `Authorization`、`x-api-key`、任何 `*_API_KEY` 模式。
- 日志记录 prompt 前 120 字 + SHA1 摘要，便于排查不泄密。

### 23.14 验收补丁

- **V25**：未注册路径（如 `/api/v1/nonexistent`）返回 `ok=false`、`error.code=HTTP_404`、含 `trace`。
- **V26**：Pydantic 校验失败返回 `ok=false`、`error.code=REQUEST_VALIDATION`、含 `trace`。
- **V27**：未捕获异常返回 `ok=false`、`error.code=INTERNAL_ERROR`，日志含堆栈摘要。
- **V28**：同一 `ontology_id` 并发 10 个 `/reason`，仅触发 ≤1 次真实 Pellet 调用；其余共享缓存或等待锁。
- **V29**：`GET /api/v1/ontologies` 返回的每项包含 §23.10 中全部字段。
- **V30**：`/specifications` 首次创建与 `/specifications/change` 的写图分工清晰：前者只写 `spec` 图，后者写 `spec` + `result` 图。

---

## 24. 已决策规则（Q1–Q10）

本章对前序所有"待确认/建议"条目给出最终决策。实现与测试一律以本章为准。

### 24.1 决策表

| 编号 | 决策 |
|---|---|
| **Q1 TTL 元信息** | 强制要求 `# ontology-id:`。缺失时 `discover()` 跳过并发 WARNING；不接受文件名 fallback |
| **Q2 无规格参数录入** | 允许写入 Measurement，响应 `status="not_inferred"`、`reason="parameter has no specification"`，HTTP 200，不写 Result |
| **Q3 规格变更幂等** | lower/upper/reason/effective_from 全相同 → 幂等（`created=false`）；任一不同 → 升版并写 `mto:supersedesSpec` |
| **Q4 SWRL 对照模式** | 第一阶段可选。Pellet 必做 OWL 一致性与主体推理；SWRL 对照保留开关 + 1 条端到端验证 |
| **Q5 `/ontologies/{id}/activate`** | 仅演示用，服务端不持久化。正式请求必须显式携带 `ontology_id`，缺失返回 `error.code=ONTOLOGY_ID_REQUIRED` |
| **Q6 `not_inferred` 状态码** | HTTP 200 + `status` 字段 |
| **Q7 Pellet 锁超时** | HTTP 200 + `pellet_status="busy"` + `retry_after_ms` |
| **Q8 SWRL 规则落地业务结果** | 不落。业务判定仍走 Python 确定性；SWRL 仅对照演示 |
| **Q9 LLM 多 provider 失败转移** | 不自动切。当前 provider 失败 → 直接 `local_fallback`，`source` 如实标注 |
| **Q10 `/ontologies/load` 部分失败** | 不回滚。响应 `{"loaded":[...], "failed":[{ontology_id,error}]}`，HTTP 200，`ok=true` |

### 24.2 对前序章节的约束

**§4.1 `ontology_registry`**：`discover()` 遇到无 `# ontology-id:` 的 TTL，`logger.warning("ontology.skip", extra={...path, reason:'missing header'})` 后跳过。

**§4.6 `parameters.py`**：Parameter 实例写入时若无匹配 Specification，`/measurements` 路径下 `graph.create_and_infer` 走短路分支，直接返回 `not_inferred`，不调用 `inference.evaluate_single`。

**§14.3 `POST /measurements` 响应扩展**：
```json
// 有规格
{"measurement_id":"M007","status":"Fail_High", ...}
// 无规格（Q2）
{"measurement_id":"M101","status":"not_inferred","reason":"parameter has no specification",
 "parameter":"ambient_humidity","value":55.2}
```

**§14.4 `POST /specifications/change` 响应扩展（Q3）**：
```json
// 升版
{"spec_version":"Spec_v2","created":true,"changed":[...]}
// 幂等
{"spec_version":"Spec_v1","created":false,"changed":[],"reason":"identical to existing spec"}
```

**§14.1 `POST /ontologies/load` 响应（Q10）**：
```json
{"loaded":[{"ontology_id":"manufacturing-trial","graph_iri":"...","triples":842,"ms":135}],
 "failed":[{"ontology_id":"broken-onto","error":"TTL parse error at line 42"}]}
```
顶层 `ok=true`，即使 `failed` 非空。

**§15.3 `owlready_reasoner.load_and_reason` 扩展（Q7）**：
```python
LOCK_TIMEOUT_SEC = 30
def load_and_reason(...):
    lock = _LOCKS.setdefault(ontology_id, threading.Lock())
    if not lock.acquire(timeout=LOCK_TIMEOUT_SEC):
        return ReasonResult(ontology_id=ontology_id, pellet_status="busy",
                            retry_after_ms=2000, reason="lock timeout")
    try:
        ...
    finally:
        lock.release()
```

**§15.5 `qa.answer` 扩展（Q9）**：provider 调用失败后**不**尝试其他 provider，直接进 `local_fallback`：
```python
provider = get_provider()
text = provider.chat(prompt) if provider.available() else None
if text is None:
    trace.log("llm_call", "fallback", reason=f"provider {provider.name} unavailable")
```

**§18.4 验收**：V9/V10/V11 已覆盖；新增：
- **V31**：`LLM_PROVIDER=deepseek` 但 key 无效 → `source=local_fallback`，不自动切 openai/qwen/claude。

**§4.7 `qa.py`**：`/ontologies/{id}/activate` 在 `qa.answer` 中**不读**，只读请求体的 `ontology_id`；缺失直接 `DomainError("ONTOLOGY_ID_REQUIRED", ...)`。

### 24.3 新增错误码

| code | HTTP | 含义 |
|---|---|---|
| `ONTOLOGY_ID_REQUIRED` | 400 | 正式请求未携带 `ontology_id`（Q5） |
| `PARAMETER_NO_SPEC` | 200 | 非错误，作为 `status` 值返回，非 `error.code`（Q2） |
| `INVALID_SPEC_RANGE` | 400 | lower > upper |
| `ONTOLOGY_NOT_FOUND` | 404 | 未在注册表找到 |
| `FUSEKI_UNAVAILABLE` | 503 | Fuseki ping 失败 |
| `PELLET_BUSY` | 200 | 非错误，作为 `pellet_status` 值（Q7） |
| `REQUEST_VALIDATION` | 422 | Pydantic 校验失败 |
| `HTTP_404` / `HTTP_405` | 4xx | 路由/方法未命中 |
| `INTERNAL_ERROR` | 500 | 未捕获异常 |

