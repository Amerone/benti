# 制造业试验数据管理本体 MVP 功能验收测试方案

## 1. 测试目标与范围

本文档基于 `plan/framework-design.md` 制定，用于功能完善后的逐项验收。每个功能模块必须通过对应测试，才视为完成。

验收范围：

- 多本体发现、注册和切换。
- 多本体加载到 Apache Jena Fuseki，并按 ontology/data/result/spec 分图隔离。
- Owlready2 从 Fuseki named graph 加载本体主体。
- Pellet 执行 OWL/SWRL 推理或一致性校验，并展示推理状态。
- 测量录入、确定性业务判定、推理链持久化。
- 规格变更后的历史重推理和差异报告。
- 运行时参数注册。
- LLM/fallback 推理链问答。
- FastAPI `/api/v1`、统一响应信封、Trace、日志。
- Streamlit 五个 Tab 的端到端交互。

不在本测试方案内验收：

- 生产级权限体系、多租户、Kafka/异步任务、React 前端、向量数据库/RAG、真实产线设备接入。

## 2. 通用前置条件

- 已安装 Python 运行环境和项目依赖：`fastapi`、`uvicorn`、`requests`、`streamlit`、`rdflib>=7.0`、`owlready2`、`pytest`。
- Java 可用时执行完整 Pellet 验收；Java 不可用时必须执行 Pellet 失败降级验收。
- Fuseki 通过 `docker compose up` 或等效方式启动，默认地址 `http://localhost:3030`。
- 后端 API 启动在 `http://localhost:8000`，正式 API 前缀为 `/api/v1`。
- Streamlit 通过 `mvp/frontend/app.py` 启动，`API_BASE_URL=http://localhost:8000`，`API_PREFIX=/api/v1`。
- `mvp/ontology/` 至少有两个 `.ttl` 本体文件，其中 `manufacturing-trial.ttl` 必须包含文档定义的 Trial/Batch/Parameter/Measurement/Specification/Result 等核心类。
- 每个 `.ttl` 文件顶部包含：

```turtle
# ontology-id: manufacturing-trial
# ontology-label: 制造业试验数据管理本体
# ontology-version: 1.0.0
# ontology-swrl: manufacturing-trial.swrl
```

## 3. 通用测试数据

基础业务数据：

| 对象 | 数据 |
|---|---|
| Trial | `T001`，注塑工艺验证 |
| Batch | `B01` 低温 183°C、`B02` 中温 188°C、`B03` 高温 193°C |
| 主参数 | `temperature` / 注塑温度 / 单位 °C / number |
| 初始规格 | `Spec_v1`，lower=180，upper=195 |
| 变更规格 | `Spec_v2`，lower=180，upper=190 |

测量样例：

| measurement_id | batch | parameter | value | Spec_v1 预期 | Spec_v2 预期 |
|---|---|---|---:|---|---|
| M001 | B01 | temperature | 179.5 | Fail_Low | Fail_Low |
| M002 | B01 | temperature | 180.0 | Pass | Pass |
| M003 | B02 | temperature | 188.0 | Pass | Pass |
| M004 | B02 | temperature | 190.0 | Pass | Pass |
| M005 | B03 | temperature | 192.1 | Pass | Fail_High |
| M006 | B03 | temperature | 195.0 | Pass | Fail_High |
| M007 | B03 | temperature | 197.2 | Fail_High | Fail_High |

补充参数：

| parameter_code | name | unit | value_type | participates_in_inference |
|---|---|---|---|---|
| vibration_frequency | 振动频率 | Hz | number | true |

## 4. 验收准入与通用通过标准

- 所有测试响应必须使用统一信封：

```json
{"ok": true, "data": {}, "error": null, "trace_id": "...", "trace": []}
```

- 失败响应也必须包含 `trace_id` 和 `trace`，且 `error.code`、`error.message` 非空。
- 核心 API 成功响应的 `trace.length >= 3`；`/health` 至少返回探测步骤。
- 日志不得输出任何 API Key 或完整 prompt。
- 所有时间字段使用 UTC ISO 8601。
- 测试可重复执行；重复加载、重复注册、重复推理不得产生不可控脏数据。
- 核心类、方法、函数、API 路由、数据模型和复杂流程必须具备中文注释或中文 docstring，说明职责、输入输出、异常/降级行为和关键设计原因。

---

## 5. 功能模块测试方案

### 5.1 基础设施与健康检查

#### TC-001 健康检查全部可用

测试目标：验证 API 能探测 Fuseki、Owlready2、Java/Pellet、LLM provider 状态。

前置条件：Fuseki 已启动；API 已启动；Java 已安装；可不配置 LLM Key。

测试步骤：

1. 调用 `GET /api/v1/health`。
2. 查看响应信封、`data.fuseki`、`data.owlready`、`data.reasoner`、`data.llm`。
3. 查看 `trace` 是否包含 `probe_fuseki`、`probe_owlready`、`probe_java_or_pellet`、`probe_llm`。

测试数据：无。

预期结果：

- HTTP 200。
- `ok=true`。
- `data.fuseki=true`。
- `data.owlready=true`。
- Java 可用时 `data.reasoner.pellet` 为 `available` 或可执行成功；无 LLM Key 时 `data.llm.available=false` 但不失败。

验收标准：状态准确、信封完整、Trace 完整，LLM Key 缺失不影响健康检查整体返回。

#### TC-002 Fuseki 未启动降级

测试目标：验证 Fuseki 不可用时系统可见失败，而不是崩溃。

前置条件：停止 Fuseki；API 继续运行。

测试步骤：

1. 调用 `GET /api/v1/health`。
2. 调用 `GET /api/v1/ontologies`。
3. 查看 Streamlit 顶部状态栏。

测试数据：无。

预期结果：

- `/health` 返回 HTTP 200，`ok=true`，`data.fuseki=false`。
- 依赖 Fuseki 的 API 返回统一失败信封或带明确不可用状态。
- UI 显示 Fuseki DOWN，页面不空白、不异常退出。

验收标准：用户和日志都能明确看到 Fuseki 不可用原因。

#### TC-003 API 前缀契约

测试目标：验证正式 API 只以 `/api/v1` 为契约。

前置条件：API 已启动。

测试步骤：

1. 调用 `GET /api/v1/ontologies`。
2. 调用 `GET /ontologies`。

测试数据：无。

预期结果：

- `/api/v1/ontologies` 返回统一信封。
- `/ontologies` 不作为正式契约；可 404、重定向或返回兼容说明，但不得作为测试依赖。

验收标准：开发和前端只使用 `/api/v1/*`。

---

### 5.2 本体注册表 `ontology_registry.py`

#### TC-010 多本体发现

测试目标：验证可以发现多个 TTL 文件并解析元信息。

前置条件：`mvp/ontology/` 下至少有 `manufacturing-trial.ttl` 和 `process-window.ttl`。

测试步骤：

1. 执行注册表单元测试或调用 `GET /api/v1/ontologies`。
2. 检查返回列表。

测试数据：两个带元信息头的 TTL 文件。

预期结果：

- 返回本体数量 `>=2`。
- 每个本体包含 `ontology_id`、`label`、`version`、`ttl_path`、`graph_iri`、`data_graph_iri`、`result_graph_iri`、`spec_graph_iri`。
- `ontology_id` 稳定，来自文件头而不是随机生成。

验收标准：缺任一图 IRI 或路径字段，均不通过。

#### TC-011 TTL 元信息缺失

测试目标：验证缺少必要元信息时有明确处理。

前置条件：准备一个临时 TTL，不包含 `# ontology-id:`。

测试步骤：

1. 将临时 TTL 放入测试目录。
2. 执行 `discover()`。

测试数据：`missing-header.ttl`。

预期结果：

- 该文件被跳过或生成明确错误。
- 行为必须与设计一致并有单测固定。

验收标准：不得静默生成不稳定 ID；不得导致整个发现过程崩溃。

决策（Q1）：缺 `# ontology-id:` 的 TTL 必须被 `discover()` 跳过并记录 WARNING 日志，不接受文件名 fallback。

#### TC-012 SWRL 路径解析

测试目标：验证 `# ontology-swrl:` 能正确绑定规则文件。

前置条件：TTL 头部声明 `# ontology-swrl: manufacturing-trial.swrl`，文件存在。

测试步骤：

1. 执行 `discover()`。
2. 查看 `swrl_path`。
3. 删除 `.swrl` 后重复执行。

测试数据：`manufacturing-trial.swrl`。

预期结果：

- 文件存在时 `swrl_path` 为绝对或可解析路径。
- 文件缺失时返回 `swrl_path=null` 或明确 warning，不影响 TTL 本体发现。

验收标准：SWRL 缺失不能阻断本体加载，但必须可见。

---

### 5.3 Fuseki 客户端与多图加载

#### TC-020 Fuseki 基础读写

测试目标：验证 `sparql_client.py` 支持 SELECT/ASK/CONSTRUCT/UPDATE/GSP。

前置条件：Fuseki 启动，dataset 为 `manufacturing-trial`。

测试步骤：

1. 用 GSP PUT 上传一段最小 Turtle 到测试图。
2. `ASK` 验证三元组存在。
3. `SELECT` 读取一行。
4. `CONSTRUCT` 返回 Turtle。
5. `UPDATE` 插入一条新三元组。

测试数据：

```turtle
@prefix ex: <https://example.test/> .
ex:s ex:p "v" .
```

预期结果：

- 所有操作成功。
- 错误时抛出 `FusekiError` 或 API 统一错误信封。

验收标准：四类 SPARQL/GSP 能力全部通过。

#### TC-021 多本体加载到 named graph

测试目标：验证 `/ontologies/load` 能加载多个本体到 Fuseki。

前置条件：至少两个 TTL 本体存在；Fuseki 可用。

测试步骤：

1. 调用 `POST /api/v1/ontologies/load`，请求 `{ "reload": true }`。
2. 对返回的每个 `graph_iri` 执行 `COUNT(*)`。
3. 执行跨图统计查询。

测试数据：`manufacturing-trial.ttl`、`process-window.ttl`。

预期结果：

- `data.loaded.length >= 2`。
- 每个 ontology 图三元组数 `>0`。
- Trace 包含 `scan_dir`、`upload_graph`、`count_graph`。

验收标准：任一本体加载失败必须在响应中列出，不得伪装整体成功。

#### TC-022 图隔离

测试目标：验证 ontology/data/result/spec 四类图互不污染。

前置条件：已有本体、业务数据、推理结果、规格历史。

测试步骤：

1. 查询四类图三元组数。
2. 执行 `CLEAR GRAPH <.../result>`。
3. 再次查询四类图三元组数。

测试数据：至少一条 M007 推理结果。

预期结果：

- result 图清空后为 0。
- ontology/data/spec 图三元组数不变。
- Owlready2 主体展示不受 result 图清空影响。

验收标准：清理推理结果不得影响本体定义、业务数据或规格历史。

#### TC-023 重复加载策略

测试目标：验证 `reload=true` 与重复加载行为可控。

前置条件：本体已加载一次。

测试步骤：

1. 记录 ontology 图三元组数。
2. 再次调用 `/ontologies/load`，`reload=true`。
3. 再次记录三元组数。

测试数据：同一 TTL。

预期结果：

- 三元组数稳定，不因重复加载线性增长。
- 响应说明采用 PUT 覆盖或等效幂等策略。

验收标准：重复执行三次后图统计仍稳定。

---

### 5.4 Owlready2 主体加载

#### TC-030 从 Fuseki 加载主体

测试目标：验证 Owlready2 的数据来源是 Fuseki，而不是本地 TTL。

前置条件：本体已加载到 Fuseki。

测试步骤：

1. 调用 `GET /api/v1/ontologies/manufacturing-trial/subjects`。
2. 临时修改本地 TTL 文件中的 label，但不重新 load Fuseki。
3. 再次调用 subjects。

测试数据：`manufacturing-trial`。

预期结果：

- 第一次返回 classes 非空。
- 第二次仍显示 Fuseki 中旧内容。
- Trace 包含 `construct_ontology_turtle`、`turtle_to_rdfxml`、`owlready_load`、`collect_subjects`。

验收标准：页面展示必须来自 Fuseki CONSTRUCT 结果。

#### TC-031 主体结构完整

测试目标：验证主体视图结构满足 UI 展示。

前置条件：本体已加载。

测试步骤：

1. 调用 subjects API。
2. 检查 `classes`、`individuals`、`object_properties`、`data_properties` 字段。

测试数据：`manufacturing-trial`。

预期结果：

- `classes` 非空，包含 Trial/Batch/Parameter/Measurement/Specification/Result。
- `individuals` 可为空但必须为数组。
- properties 字段必须为数组。
- 每项至少包含 `iri`，有 label 时返回 label。

验收标准：字段缺失或类型错误不通过。

#### TC-032 非法本体 ID

测试目标：验证不存在的 `ontology_id` 有明确错误。

前置条件：API 已启动。

测试步骤：

1. 调用 `GET /api/v1/ontologies/not-exists/subjects`。

测试数据：`not-exists`。

预期结果：

- HTTP 404 或 400。
- `ok=false`。
- `error.code` 为 `ONTOLOGY_NOT_FOUND` 或等效明确错误。
- Trace 最后一步为 `failed`。

验收标准：不得返回空成功。

---

### 5.5 Pellet 推理

#### TC-040 Pellet 成功推理

测试目标：验证 Pellet 能被实际调用并返回状态。

前置条件：Java 可用；Owlready2 可 import；本体已加载。

测试步骤：

1. 调用 `POST /api/v1/ontologies/manufacturing-trial/reason`。
2. 查看 `pellet_status`、`pellet_ms`、`reasoner`。
3. 查看 Trace。

测试数据：`manufacturing-trial`。

预期结果：

- `pellet_status=success`。
- `pellet_ms >= 0`。
- 返回 classes/properties 仍可展示。
- Trace 包含 `sync_reasoner_pellet`。

验收标准：如果 Java 可用但 Pellet 未被调用，不通过。

#### TC-041 Java 缺失或 Pellet 失败降级

测试目标：验证 Pellet 失败不会阻断主体展示和业务判定。

前置条件：模拟 Java 不可用，或配置错误的 Java 路径。

测试步骤：

1. 调用 reason API。
2. 调用 subjects API。
3. 录入 M007 并执行业务推理。

测试数据：M007 value=197.2。

预期结果：

- reason API 返回 `pellet_status=failed` 或 `missing_java`，错误原因非空。
- subjects 仍返回 Owlready2 解析出的 classes。
- M007 业务推理仍返回 `Fail_High`，`reasoner=python-deterministic`。
- UI 仅 Pellet Tab 标红，测量/问答 Tab 正常。

验收标准：Pellet 失败不能造成核心业务流程不可用。

#### TC-042 Pellet 并发保护

测试目标：验证多个请求同时触发 Pellet 不造成进程崩溃或缓存污染。

前置条件：API 可用；本体已加载。

测试步骤：

1. 并发发起 5 个 reason 请求。
2. 观察响应、日志和耗时。

测试数据：同一 `ontology_id`。

预期结果：

- 所有请求返回统一信封。
- 同一缓存键可复用结果，或由锁串行执行。
- 无 500 崩溃、无临时文件泄漏。

验收标准：并发场景稳定，失败也必须是可解释失败。

---

### 5.6 业务图谱写入与演示数据

#### TC-050 初始化演示数据

测试目标：验证 `demo_data.py` 可重入生成 Trial/Batch/Parameter/Spec/Measurement。

前置条件：Fuseki 可用，本体已加载。

测试步骤：

1. 执行 demo data 导入。
2. 查询 Trial、Batch、Parameter、Specification、Measurement 数量。
3. 再次执行 demo data 导入。

测试数据：通用测试数据。

预期结果：

- Trial=1。
- Batch=3。
- 主参数至少 1 个。
- Spec_v1 存在。
- 测量样例存在且不重复膨胀。

验收标准：重复执行后对象数量稳定或按设计覆盖。

#### TC-051 图谱写入字段完整

测试目标：验证业务对象写入 data/spec/result 图时字段完整。

前置条件：至少录入一条测量并推理。

测试步骤：

1. 对 data 图查询 M007。
2. 对 result 图查询 M007 的 Result。
3. 对 spec 图查询 Spec_v1。

测试数据：M007。

预期结果：

- Measurement 包含 localId、measuredValue、parameter、batch。
- Result 包含 `mto:forMeasurement`、`mto:resultStatus`、`mto:appliedRule`、`mto:againstSpecVersion`、`mto:deviation`、`mto:reasoner`。
- Specification 包含上下限、版本、生效时间。

验收标准：推理链字段缺任一核心字段不通过。

---

### 5.7 测量录入与确定性推理

#### TC-060 单条 Pass 判定

测试目标：验证正常范围内测量值判定为 Pass。

前置条件：Spec_v1 为 180-195。

测试步骤：

1. 调用 `POST /api/v1/measurements` 录入 M003 value=188.0。
2. 查询返回结果。
3. 查询 result 图。

测试数据：M003。

预期结果：

- `status=Pass`。
- `rule=Rule_Pass`。
- `deviation=0`。
- `spec_version=Spec_v1`。
- `reasoner=python-deterministic`。

验收标准：API 响应和 RDF 结果一致。

#### TC-061 下限边界

测试目标：验证等于下限为 Pass，低于下限为 Fail_Low。

前置条件：Spec_v1 lower=180。

测试步骤：

1. 录入 M002 value=180.0。
2. 录入 M001 value=179.5。

测试数据：M001、M002。

预期结果：

- M002 为 Pass。
- M001 为 Fail_Low。
- M001 deviation=0.5 或按设计保留精度。

验收标准：边界比较符正确，不能把等于下限判为 Fail。

#### TC-062 上限边界

测试目标：验证等于上限为 Pass，高于上限为 Fail_High。

前置条件：Spec_v1 upper=195。

测试步骤：

1. 录入 M006 value=195.0。
2. 录入 M007 value=197.2。

测试数据：M006、M007。

预期结果：

- M006 为 Pass。
- M007 为 Fail_High。
- M007 deviation=2.2。

验收标准：边界比较符正确，不能把等于上限判为 Fail。

#### TC-063 非数值输入

测试目标：验证非法测量值被拒绝。

前置条件：API 可用。

测试步骤：

1. 调用 measurements API，value 传 `"abc"` 或 null。

测试数据：`value="abc"`、`value=null`。

预期结果：

- `ok=false`。
- 错误码为参数校验错误。
- 不写入 Measurement，不写入 Result。

验收标准：非法输入不得污染图谱。

#### TC-064 无规格可用

测试目标：验证参数无规格时不能伪造推理结果。

前置条件：注册一个无规格参数。

测试步骤：

1. 对该参数录入测量。

测试数据：`parameter=no_spec_param`，value=10。

预期结果：

- 返回失败或 `requires_specification=true` 状态。
- 不产生 Pass/Fail Result。

验收标准：无规格时不得默认 Pass。

决策（Q2）：无规格参数允许写入 Measurement，响应 `status="not_inferred"`、`reason="parameter has no specification"`，HTTP 200，不写 Result。

---

### 5.8 规格变更与历史重推理

#### TC-070 规格变更生成新版本

测试目标：验证规格变更不覆盖旧版本。

前置条件：Spec_v1 存在。

测试步骤：

1. 调用 `POST /api/v1/specifications/change`，upper 从 195 改为 190。
2. 查询 spec 图。

测试数据：Spec_v2 lower=180 upper=190 reason=产线收紧。

预期结果：

- 新增 Spec_v2。
- Spec_v1 仍存在。
- Spec_v2 `mto:supersedesSpec` 指向 Spec_v1。
- 变更原因、生效时间被记录。

验收标准：旧规格不能被覆盖删除。

#### TC-071 历史重推理差异报告

测试目标：验证规格变更后历史测量被重推理并生成差异。

前置条件：已有 M001-M007 在 Spec_v1 下的结果。

测试步骤：

1. 执行 Spec_v2 变更 upper=190。
2. 查看响应 `changed`。
3. 查询 result 图中最新结果。

测试数据：M001-M007。

预期结果：

- M005 从 Pass 变 Fail_High。
- M006 从 Pass 变 Fail_High。
- M003、M004 保持 Pass。
- M007 仍 Fail_High，但新结果关联 Spec_v2。
- 差异报告包含 old_status/new_status、old_spec/new_spec、deviation、measurement_id。

验收标准：差异报告准确，且所有历史数据都被重新评估。

#### TC-072 规格边界非法

测试目标：验证 lower > upper 被拒绝。

前置条件：API 可用。

测试步骤：

1. 调用规格变更，lower=200，upper=190。

测试数据：非法上下限。

预期结果：

- `ok=false`。
- 错误码为 `INVALID_SPEC_RANGE` 或等效错误。
- 不创建新 Spec。
- 不触发重推理。

验收标准：非法规格不得改变图谱状态。

#### TC-073 重复规格变更

测试目标：验证相同上下限重复提交行为可控。

前置条件：Spec_v2 已存在。

测试步骤：

1. 再次提交 lower=180 upper=190。

测试数据：与 Spec_v2 相同。

预期结果：

- 返回幂等结果或创建 Spec_v3，二者必须由设计明确。
- 若创建新版本，必须有 supersedes 链。
- 若幂等，必须说明未创建新版本。

验收标准：不得产生无说明的重复规格链。

决策（Q3）：lower、upper、reason、effective_from 全相同 → 幂等，返回 `created=false` + 旧 spec_version；任一字段不同 → 升版并写 `mto:supersedesSpec`。

---

### 5.9 参数运行时注册

#### TC-080 正常注册新参数

测试目标：验证无需改 schema、无需重启即可新增参数。

前置条件：API 和 Fuseki 可用。

测试步骤：

1. 调用 `POST /api/v1/parameters` 注册 `vibration_frequency`。
2. 调用 `GET /api/v1/parameters?ontology_id=manufacturing-trial`。
3. 打开 Streamlit 参数/问答 Tab 或测量 Tab。

测试数据：振动频率参数。

预期结果：

- 参数写入 data 图。
- 参数列表包含新参数。
- UI 下拉出现新参数。
- 服务未重启。

验收标准：参数新增全程不涉及数据库表结构变更。

#### TC-081 重复参数编码

测试目标：验证重复注册同一 code 不产生重复个体。

前置条件：`vibration_frequency` 已注册。

测试步骤：

1. 再次注册相同 code。
2. 查询参数数量。

测试数据：相同 code。

预期结果：

- 返回幂等成功或明确 `PARAMETER_ALREADY_EXISTS`。
- 图谱中该 code 只有一个有效参数个体。

验收标准：不得重复膨胀。

#### TC-082 参数字段缺失

测试目标：验证参数元数据最小字段校验。

前置条件：API 可用。

测试步骤：

1. 注册缺少 `unit` 或 `value_type` 的参数。
2. 注册空 `parameter_code`。

测试数据：字段缺失 payload。

预期结果：

- 返回校验失败。
- 不写入图谱。

验收标准：参数注册不能退化为任意字段注入。

---

### 5.10 LLM/fallback 问答

#### TC-090 why_fail fallback

测试目标：验证无 LLM Key 时仍可解释推理链。

前置条件：M007 已推理；不配置任何 LLM API Key。

测试步骤：

1. 调用 `POST /api/v1/qa`，问题为 `M007 为什么 Fail？`。
2. 查看响应。

测试数据：M007。

预期结果：

- `source=local_fallback`。
- 答复包含 M007、Fail_High、197.2、Spec_v1 或当前 spec、Rule_Fail_High、偏差。
- evidence 字段包含结构化证据。
- Trace 包含 `extract_intent`、`build_sparql`、`fuseki_select`、`compose_answer`。

验收标准：无 Key 场景下问答可用，且不编造证据。

#### TC-091 白名单外问题

测试目标：验证不支持自由问答。

前置条件：API 可用。

测试步骤：

1. 提问：`请预测明天产线良率`。

测试数据：非白名单问题。

预期结果：

- 返回“不支持该类问题”。
- 不调用 LLM 或不生成自由 SPARQL。
- `sparql=null`。

验收标准：LLM 不得自由扩展未定义功能。

#### TC-092 LLM Provider 可用

测试目标：验证配置 LLM Key 后可调用 provider，并保留 evidence 约束。

前置条件：配置一个可用 provider，例如 `LLM_PROVIDER=deepseek` 和对应 Key。

测试步骤：

1. 调用 `/qa` 问 M007。
2. 检查 source/provider。
3. 检查答复内容。

测试数据：M007。

预期结果：

- `source=deepseek` 或配置 provider 名。
- 答复包含 evidence 中的测量值、规格、规则、偏差。
- 不出现 evidence 外的额外业务事实。

验收标准：LLM 只做解释，不做判定、不做事实扩写。

#### TC-093 LLM 超时降级

测试目标：验证远端 LLM 超时后 fallback 可用。

前置条件：将 `LLM_TIMEOUT` 设置很小，或配置不可达 base_url。

测试步骤：

1. 调用 `/qa`。
2. 查看响应和 trace。

测试数据：M007。

预期结果：

- `source=local_fallback`。
- Trace 中 `llm_call` 为 `failed` 或 `fallback`，reason 非空。
- UI 显示降级原因。

验收标准：LLM 故障不影响问答基本可解释能力。

---

### 5.11 API 信封、Trace 与日志

#### TC-100 成功响应信封

测试目标：验证所有核心 API 使用统一响应结构。

前置条件：API 可用。

测试步骤：

1. 分别调用 `/health`、`/ontologies`、`/ontologies/load`、`/subjects`、`/measurements`、`/specifications/change`、`/qa`。
2. 检查响应结构。

测试数据：按前述测试数据。

预期结果：

- 每个响应包含 `ok`、`data`、`error`、`trace_id`、`trace`。
- 成功时 `ok=true`、`error=null`。
- 核心 API `trace.length >= 3`。

验收标准：任何核心 API 缺统一字段不通过。

#### TC-101 失败响应信封

测试目标：验证失败也可追踪。

前置条件：API 可用。

测试步骤：

1. 调用不存在本体 subjects。
2. 提交非法规格。
3. 提交非法测量值。

测试数据：非法 payload。

预期结果：

- `ok=false`。
- `error.code`、`error.message` 非空。
- `trace_id` 非空。
- trace 最后一步 `status=failed`，`reason` 非空。

验收标准：不得出现裸 500 或无 trace 的失败。

#### TC-102 日志敏感信息

测试目标：验证日志不泄露密钥和完整 prompt。

前置条件：配置任意 `*_API_KEY` 环境变量。

测试步骤：

1. 执行一次 `/qa`。
2. grep stdout 或日志文件。

测试数据：`CLAUDE_API_KEY=test-secret-value`。

预期结果：

- 日志中不出现 Key 的值。
- 日志中不出现完整 prompt。
- 可出现 provider、model、latency、prompt 摘要。

验收标准：泄露任何 Key 值即不通过。

---

### 5.12 Streamlit 前端

#### TC-110 顶部状态区

测试目标：验证页面状态可见。

前置条件：API 和 Streamlit 已启动。

测试步骤：

1. 打开 Streamlit 页面。
2. 查看顶部状态区。
3. 停止 Fuseki 后刷新。

测试数据：无。

预期结果：

- 显示 API、当前本体、Fuseki、Owlready2、Pellet、LLM/fallback 状态。
- Fuseki 停止后显示 DOWN，不白屏。

验收标准：状态区必须反映后端真实状态。

#### TC-111 Tab 一：本体加载与切换

测试目标：验证 UI 可加载和切换多个本体。

前置条件：至少两个本体文件存在。

测试步骤：

1. 点击“加载全部本体到 Fuseki”。
2. 查看返回 loaded 列表。
3. 切换当前本体。

测试数据：两个 TTL。

预期结果：

- loaded 显示两个本体。
- 本体下拉可切换。
- 切换后后续 Tab 请求携带新的 `ontology_id`。
- 页面出现 Trace 面板。

验收标准：切换状态只在客户端维护，请求必须显式传 `ontology_id`。

#### TC-112 Tab 二：Owlready 主体

测试目标：验证 UI 展示 Owlready2 从 Fuseki 加载的主体。

前置条件：本体已加载到 Fuseki。

测试步骤：

1. 选择 `manufacturing-trial`。
2. 点击加载主体。
3. 使用过滤关键字 `Batch`。

测试数据：`Batch`。

预期结果：

- Classes 表格包含 Batch。
- Individuals 表格为空也正常展示空数组。
- 显示 Pellet 状态。
- Trace 面板显示 `construct_ontology_turtle` 和 `owlready_load`。

验收标准：UI 不直接读取本地 TTL。

#### TC-113 Tab 三：Pellet 推理

测试目标：验证 Pellet 推理操作和失败可见。

前置条件：Java 可用或可模拟不可用。

测试步骤：

1. 点击执行 Pellet。
2. 查看状态、耗时、错误。
3. 模拟 Java 不可用后重复。

测试数据：当前本体。

预期结果：

- 成功时绿色状态。
- 失败时红色状态，显示错误原因。
- 其他 Tab 不受失败影响。

验收标准：推理状态与后端 reason API 一致。

#### TC-114 Tab 四：测量与规格

测试目标：验证测量录入、即时推理、规格变更和差异报告。

前置条件：demo 数据可用。

测试步骤：

1. 录入 M007 value=197.2。
2. 查看结果。
3. 将上限改为 190 并执行重推理。
4. 查看差异报告。

测试数据：M001-M007。

预期结果：

- M007 显示 Fail_High、Rule_Fail_High、偏差 2.2。
- 差异报告包含 M005、M006。
- 每条结果旁显示 `Python` 或 `Pellet-SWRL` 来源徽标。
- Trace 面板可见。

验收标准：UI、API、图谱结果一致。

#### TC-115 Tab 五：参数与问答

测试目标：验证新增参数和问答闭环。

前置条件：API 可用，M007 已推理。

测试步骤：

1. 注册 `vibration_frequency`。
2. 确认测量选项出现该参数。
3. 提问 `M007 为什么 Fail？`。

测试数据：振动频率、M007。

预期结果：

- 新参数立即出现。
- 问答返回推理链解释。
- 无 LLM Key 时显示 fallback 来源。
- Trace 面板显示 intent、SPARQL、LLM/fallback 路径。

验收标准：参数与问答功能均通过 UI 完成，无需重启。

#### TC-116 前端边界

测试目标：验证 Streamlit 不直接调用 core。

前置条件：代码完成。

测试步骤：

1. 执行 grep：`rg "from mvp\\.core|import mvp\\.core" mvp/frontend mvp/app.py`。
2. 执行 grep：`rg "requests\\." mvp/frontend`。

测试数据：源代码。

预期结果：

- 不出现 `from mvp.core` 或 `import mvp.core`。
- 前端通过 `requests` 调用 HTTP API。

验收标准：前后端边界符合设计。

#### TC-117 中文注释与代码说明

测试目标：验证代码实现具备足够的中文注释，便于后续维护和业务评审。

前置条件：代码完成。

测试步骤：

1. 检查 `mvp/core/`、`mvp/api/`、`mvp/frontend/` 中每个模块顶部是否有中文模块说明。
2. 检查公开类、核心 dataclass、API 路由函数、核心业务函数是否有中文 docstring。
3. 检查复杂流程是否有中文注释说明设计原因，包括 Fuseki 分图、Turtle 转 RDF/XML、Pellet 降级、规格重推理 diff、LLM fallback。
4. 抽查注释质量，确认注释解释“作用和原因”，而不是简单复述代码。
5. 检查 TTL / SWRL 文件是否保留中文注释或 `rdfs:label`，可支撑页面展示和业务审阅。

测试数据：源代码和本体文件。

预期结果：

- 每个核心模块都有中文模块说明。
- 每个公开类、核心函数和 API 路由都有中文 docstring。
- 关键流程前有中文注释说明设计意图。
- 注释不泄露密钥、prompt 或环境敏感信息。

验收标准：缺少核心中文说明、注释与代码意图明显不符，或注释无法说明类/方法/函数作用时，不通过。

---

### 5.13 端到端业务流程

#### TC-120 MVP 主流程演示

测试目标：验证三个核心命题完整闭环。

前置条件：Fuseki、API、Streamlit 启动；本体已加载；demo 数据可导入。

测试步骤：

1. 加载多个本体到 Fuseki。
2. 切换到 `manufacturing-trial`。
3. 执行 Owlready 主体加载。
4. 执行 Pellet 推理。
5. 导入或录入 M001-M007。
6. 验证 M007 为什么 Fail。
7. 将规格上限从 195 改为 190，执行历史重推理。
8. 注册振动频率参数。
9. 再次提问 M007 为什么 Fail。

测试数据：通用测试数据。

预期结果：

- 命题一：规格变更后生成差异报告，M005/M006 从 Pass 变 Fail_High。
- 命题二：新参数无需重启即出现在 UI。
- 命题三：M007 问答包含测量值、规格版本、规则、偏差。
- 所有步骤都有 Trace。

验收标准：任一核心命题失败，MVP 不通过。

#### TC-121 端到端异常恢复

测试目标：验证关键依赖异常下系统能解释并降级。

前置条件：API 和 UI 可用。

测试步骤：

1. 停止 Fuseki，打开 UI。
2. 恢复 Fuseki，重新加载本体。
3. 模拟 Pellet 缺 Java，执行 reason。
4. 移除 LLM Key，执行问答。

测试数据：M007。

预期结果：

- Fuseki DOWN 可见。
- Fuseki 恢复后可继续加载。
- Pellet 失败不影响业务判定。
- LLM 缺失时 fallback 可用。

验收标准：异常场景均有用户可见原因和日志 trace。

---

## 6. 已决策项（原"待确认项"）

下表项已固化为实现规则，TC 用例按此执行。如需调整必须先改本表与 framework-design §24。

| 编号 | 问题 | 决策 |
|---|---|---|
| Q1 | TTL 缺少 `# ontology-id:` 时是否允许文件名 fallback | **强制要求文件头**。缺失 `# ontology-id:` 的 TTL 在 `discover()` 阶段跳过并产生 WARNING 日志，不进入注册表 |
| Q2 | 无规格参数是否允许记录 Measurement 但不推理 | **允许记录，不推理**。响应 `status="not_inferred"`、`reason="parameter has no specification"`，HTTP 200 |
| Q3 | 相同上下限重复规格变更是幂等还是升版 | **幂等**。若 lower、upper、reason、effective_from 全部相同，返回旧版本 `created=false`；任一字段不同则升版 |
| Q4 | SWRL 对照模式是否进入第一阶段必做 | **第一阶段可选**。Pellet 必做 OWL 一致性 + 主体推理；SWRL 对照模式仅保留开关 + 1 条端到端验证（TC-140） |
| Q5 | `/ontologies/{id}/activate` 是否持久化默认本体 | **仅演示用**。服务端不持久化；所有正式请求必须显式携带 `ontology_id`，否则 `error.code=ONTOLOGY_ID_REQUIRED` |
| Q6 | `not_inferred` 走 HTTP 200 还是 202 | **HTTP 200 + `status` 字段**。便于前端统一处理 |
| Q7 | Pellet 锁等待超时返回 503 还是 200+`pellet_status=busy` | **HTTP 200 + `pellet_status="busy"` + `retry_after_ms`**。避免 UI 重试风暴 |
| Q8 | SWRL 对照模式纳入 MVP 必做或仅技术预研 | **仅保留开关与端到端 1 例验证**；规则迁移到 SWRL 延后到 Phase 2 |
| Q9 | LLM 失败时是否自动尝试备用 provider | **不自动切换**。当前 provider 失败 → 直接 `local_fallback`，trace 与 `source` 字段如实标注 |
| Q10 | `/ontologies/load` 部分失败是否回滚已成功的 | **不回滚**。响应 `loaded=[...]` 与 `failed=[{ontology_id,error}]` 两个数组并列；HTTP 200，`ok=true` |

## 7. 验收出口标准


项目功能完善后，必须满足：

- 本文档所有非“待确认”的测试用例通过。
- `pytest` 覆盖注册表、确定性推理、参数校验、QA fallback、Trace 信封。
- 至少一次完整端到端手工演示通过 TC-120。
- 至少一次异常恢复演示通过 TC-121。
- 所有失败响应可追踪，日志不泄露密钥。
- 测试结果记录到 `plan/test-results.md` 或等效验收记录文件。

---

## 8. 审阅补充测试用例（A1–A17）

本章用例由 2026-04-23 文档审阅追加，对应 framework-design §23 的补丁。

### 8.1 加载与图隔离补强

#### TC-130 reload 不破坏 data/result/spec

测试目标：验证 §23.12，`reload=true` 仅覆盖 ontology 图。

步骤：
1. 写入若干业务测量、规格、推理结果（让 data/result/spec 图各自有三元组）。
2. 记录 data/result/spec 图三元组数。
3. 调用 `/ontologies/load` `reload=true`。
4. 再次记录 data/result/spec 图三元组数。

预期：三者三元组数严格不变；ontology 图被覆盖且与本地 TTL 解析后一致。

#### TC-131 多本体并存数据互不串

测试目标：补 A12。

步骤：
1. 加载 `manufacturing-trial` 与 `process-window` 两个本体。
2. 调用 `GET /api/v1/ontologies/process-window/subjects`。
3. 调用 `GET /api/v1/ontologies/manufacturing-trial/subjects`。

预期：两次响应的 `classes.iri` 集合无交集（除非两本体显式 import）。Trace 中 `construct_ontology_turtle` 的 `graph_iri` 与请求的 `ontology_id` 一致。

#### TC-132 Fuseki dataset 名错误

测试目标：补 A14。

步骤：将 `FUSEKI_DATASET=does-not-exist` 启动 API；调用 `/ontologies/load`。

预期：`ok=false`，`error.code=FUSEKI_DATASET_NOT_FOUND` 或 `FUSEKI_HTTP_404`，trace 末步 `failed`，日志含 base_url（不含密码）。

#### TC-133 跨图统计

测试目标：补 A16，对应 framework V13。

步骤：调用任意 SPARQL 端点执行：
```sparql
SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g
```

预期：返回每个 `*/data`、`*/result`、`*/spec` 与本体图，至少 4 个 graph。

### 8.2 推理与 SWRL 对照

#### TC-140 SWRL 对照模式

测试目标：补 A15，对应 framework V15。

前置：Java 可用；TTL 含 SWRL 规则；前端启用"对照模式"。

步骤：
1. 录入 M007。
2. 启用对照模式重跑 `/measurements`。
3. 查询 result 图同一 measurement 的 Result 节点。

预期：result 图存在两条 Result，`mto:reasoner` 分别为 `python-deterministic` 与 `pellet-swrl`，`status` 与 `deviation` 一致。

#### TC-141 Pellet 缓存与并发

测试目标：补 A2，对应 framework V28。

步骤：并发 10 个 `/api/v1/ontologies/manufacturing-trial/reason` 请求。

预期：实际 Pellet 调用次数 ≤ 1（通过日志 `mto.reasoner` 行计数）；所有请求收到一致 `pellet_status` 与近似 `pellet_ms`；无 500。

### 8.3 业务校验补强

#### TC-150 非数值与缺字段拆分

测试目标：补 A4。

步骤分两步：
1. `value="abc"` → 预期 `error.code=REQUEST_VALIDATION`，HTTP 422。
2. `value=null` 或字段缺失 → 预期 `error.code=REQUEST_VALIDATION`，HTTP 422。

不允许任一情况写入 Measurement。

#### TC-151 Specification 字段完整

测试目标：补 A5。

步骤：创建 Spec_v1 与 Spec_v2；查询 spec 图。

预期：每个 Specification 含 `mto:lowerLimit`、`mto:upperLimit`、`mto:specVersion`、`mto:effectiveFrom`、`mto:reason`，Spec_v2 含 `mto:supersedesSpec` 指向 Spec_v1。

#### TC-152 不参与推理的参数

测试目标：补 A6。

步骤：注册 `participates_in_inference=false` 的参数 `ambient_humidity`；录入测量。

预期：Measurement 写入成功；不产生 Result；响应 `status=not_inferred`，`reason=参数不参与推理`。

#### TC-153 提取到 mid 但意图不属于 why_fail

测试目标：补 A7。

步骤：提问 `M007 是什么型号？`。

预期：`extract_intent` 不命中 `why_fail`，返回"不支持该类问题"；`sparql=null`；trace 含 `extract_intent.status=skipped`，reason 写明"未匹配任何模板"。

#### TC-154 重推理硬性能门

测试目标：补 A11，对应 framework V5。

前置：data 图至少 150 条 Measurement。

步骤：执行规格变更。

预期：响应 `ms < 10000`；trace `iterate_history.detail.count >= 150`。

### 8.4 端到端与异常

#### TC-160 路由 404 走信封

测试目标：对应 V25。

步骤：`curl /api/v1/nonexistent`。

预期：HTTP 404，`ok=false`，`error.code=HTTP_404`，含 `trace_id` 与 `trace`（至少有 `request.begin` 与 `http_404` 步骤）。

#### TC-161 Pydantic 校验信封

测试目标：对应 V26。

步骤：向 `/measurements` POST `{"foo":"bar"}`。

预期：HTTP 422，`error.code=REQUEST_VALIDATION`，trace 含 `request_validation.status=failed`，`detail.errors` 非空。

#### TC-162 未捕获异常

测试目标：对应 V27。

步骤：人为在 `graph.create_and_infer` 内 `raise RuntimeError("boom")`（测试构件，非生产代码）；调用 `/measurements`。

预期：HTTP 500，`error.code=INTERNAL_ERROR`，响应不暴露堆栈；日志含 `unhandled` 一行带堆栈摘要。

#### TC-163 LLM 多 provider 切换

测试目标：补 A8。

步骤：依次设置 `LLM_PROVIDER` 为 `claude` / `openai` / `deepseek` / `qwen`，相同问题访问 `/qa`，无 key 时观察。

预期：每次响应 `source` 等于当前 provider 或 `local_fallback`；`/health.llm.provider` 与之一致。

#### TC-164 日志 sanitize

测试目标：补 A9 + A13，对应 V24/V21 加强。

步骤：设置 `OPENAI_API_KEY=sk-test-leak`、`OPENAI_BASE_URL` 含查询串 `?token=secret`；执行一次 `/qa`；grep 日志。

预期：日志中无 `sk-test-leak`；无 `secret`；`Authorization`、`x-api-key`、`Cookie` 字段被遮蔽为 `***`。

#### TC-165 grep 边界严格

测试目标：补 A10，加强 TC-116。

步骤：增加规则：
```
rg "from\\s+mvp\\.core" mvp/frontend mvp/app.py
rg "import\\s+mvp(\\.|\\s)" mvp/frontend mvp/app.py
rg "importlib" mvp/frontend mvp/app.py
```

预期：三条均无命中。

#### TC-166 端到端含 LLM 与对照模式

测试目标：补 A17。

步骤：在 TC-120 步骤 7 之前增加：
- 7a. 启用 SWRL 对照模式重跑 M007。
- 7b. 设置 `LLM_PROVIDER=deepseek`（如可用）后再次问答。

预期：result 图同时含两类 reasoner Result；问答 `source=deepseek` 且包含 evidence 字段。

---

## 9. 变更记录

- 2026-04-23 初稿。
- 2026-04-23 审阅补丁：追加 §8（TC-130~TC-166），将 §6 从"待确认"改为"已决策"，并入 Q6–Q10。
