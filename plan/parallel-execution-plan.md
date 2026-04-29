# 多 Agent 并行执行规划

## 目标

按 `tasks.csv` 的任务拆分交付制造业试验数据管理本体 MVP，并确保实现符合 `acceptance-test-plan.md` 的验收用例与 `framework-design.md` 的架构约束。

## 总体约束

- 架构采用 Streamlit UI -> FastAPI API -> Application Core -> Fuseki/LLM 的分层边界。
- Fuseki 使用单 dataset + 每本体四类 named graph：ontology/data/result/spec。
- 所有 API 使用 `/api/v1` 前缀和统一响应信封，成功和失败都必须带 `trace_id` 与 `trace`。
- 业务 Pass/Fail 判定以 Python 确定性推理为准；Pellet/SWRL 只做本体一致性与对照演示。
- LLM 只做解释，不做判定；白名单外问题不得自由生成 SPARQL。
- 前端只能通过 HTTP API 调后端，不得直接 import `mvp.core`。
- 公开类、核心函数、API 路由和复杂流程必须具备中文说明，说明职责和设计原因。

## 第一波：已启动

| Agent | 任务组 | tasks.csv 范围 | 写入边界 |
|---|---|---|---|
| McClintock | 基础设施 + Trace/日志 | T-A1-1~T-A1-5, T-L1-1~T-L1-4 | 根配置、`mvp/core/trace.py`、`mvp/core/logging_setup.py`、trace/logging 测试 |
| Kepler | 本体注册表与示例本体 | T-B1-1~T-B1-5 | `mvp/core/ontology_registry.py`、`mvp/ontology/*`、注册表测试 |
| Turing | Fuseki 客户端 | T-C1-1~T-C1-2 | `mvp/core/sparql_client.py`、Fuseki 客户端测试 |
| Parfit | 图谱、确定性推理、参数 | T-D1-1~T-D1-7, T-E1-1~T-E1-3, T-F1-1~T-F1-3 | `mvp/core/graph.py`、`inference.py`、`parameters.py`、对应测试 |
| Planck | Owlready2/Pellet/SWRL 对照 | T-G1-1~T-G1-5 | `mvp/core/owlready_reasoner.py`、语义推理测试 |
| Lovelace | LLM Provider 与 QA | T-J1-1~T-J1-9 | `mvp/core/llm/*`、`mvp/core/qa.py`、QA/LLM 测试 |

## 第一波集成检查

- registry descriptor 字段必须与 graph/API 契约一致：`ontology_id`、`label`、`version`、`ttl_path`、`swrl_path`、`graph_iri`、`data_graph_iri`、`result_graph_iri`、`spec_graph_iri`。
- graph 层必须兼容 sparql_client 的 `select/ask/update/construct/upload_graph/ping` 接口。
- trace 参数在 core 模块中必须可选，避免单元测试和脱离 API 调用时失败。
- integration 测试在 Fuseki/Java 不可用时应 skip，不阻塞普通单元测试。

## 第二波：第一波接口稳定后启动

| 任务组 | tasks.csv 范围 | 依赖 |
|---|---|---|
| API 层 | T-H1-1~T-H1-14 | Trace、graph、parameters、inference、reasoner、qa |
| 演示数据 | T-K1-1 | graph.create_and_infer、spec/parameter 写入 |
| 前端 | T-I1-1~T-I1-8 | API 契约和统一信封 |
| 观测补全 | T-L4-1~T-L4-2 | API/核心模块基本完成 |
| 收尾与验收 | T-CN-1, T-K2-1, T-E2E-1~T-E2E-3 | 全功能链路 |

## 验收门槛

- 普通单元测试覆盖 ontology_registry、trace/logging、inference、parameters、qa。
- Fuseki 可用时覆盖 GSP PUT、SELECT、ASK、CONSTRUCT、UPDATE 和 graph named graph 隔离。
- Java 可用时覆盖 Pellet 成功；Java 不可用时覆盖降级。
- API 验收覆盖 TC-100~TC-102、TC-160~TC-164 的信封、trace、异常和日志脱敏。
- 前端验收覆盖 TC-110~TC-116，尤其是前端边界 grep。
- E2E 必须记录 TC-120、TC-121、TC-166 的结果到 `plan/test-results.md`。
