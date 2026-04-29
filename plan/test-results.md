# 交付验证记录

## 范围
- 项目：制造业试验数据管理本体 MVP
- 执行日期：2026-04-23
- 本轮目标：确认实现与 `plan/framework-design.md` 一致，并满足 `plan/acceptance-test-plan.md` 的自动化交付基线

## 环境
- Python：`.venv\Scripts\python.exe`
- 依赖：`requirements.txt` 已安装，补充验证过 `pytest-asyncio`
- 容器配置：`docker compose config` 可解析

## 已执行验证
| 检查项 | 命令 | 结果 | 说明 |
|---|---|---|---|
| 全量自动化测试 | `.venv\Scripts\python.exe -m pytest -q` | 通过 | `56 passed, 1 skipped` |
| 编译检查 | `.venv\Scripts\python.exe -m compileall mvp tests` | 通过 | 无语法错误 |
| Compose 配置检查 | `docker compose config` | 通过 | Fuseki 服务配置可解析 |
| 本体语法检查 | `rdflib.Graph().parse(..., format="turtle")` | 通过 | `manufacturing-trial.ttl` 可按 Turtle 解析 |

## 本轮重点修复后复查结论
- 本体打包文件已恢复并补齐头部元信息：`ontology-id`、`ontology-label`、`ontology-version`、`ontology-swrl`
- `manufacturing-trial.ttl` 已与运行时代码统一到 `mto` 命名空间，并补齐关键 RDF 谓词：
  `forBatch`、`forParameter`、`forMeasurement`、`hasLatestResult`、`appliedRule`、`againstSpecVersion`、`reasoner`、`inferredAt`、`supersededBy`、`supersedesSpec` 等
- 业务图谱仓储已支持 Fuseki 侧数据图、结果图、规格图的回填与持久化，不再只有 ontology 图落远端
- `/ontologies/{id}/subjects` 已支持 `q` 与 `limit`
- `/measurements` 已支持 `enable_swrl` 对照模式，并保存并行 `pellet-swrl` 结果且不覆盖 Python 最新结果
- 前端 Tab 四已补齐对照模式开关与来源徽标文案：`Python` / `Pellet-SWRL`

## 当前状态
- 是否符合需求：是，当前实现已覆盖本轮审阅定位出的关键需求缺口
- 是否通过测试要求：是，自动化基线通过
- 是否满足交付条件：基本满足，可进入交付；但仍保留真实环境联调类风险

## 尚未完成的人工/环境类验收
- 未实际启动 Streamlit 页面做人工点击验收
- 未在真实 Java + Pellet + Fuseki 运行环境下完成 TC-140 / TC-166 的人工端到端复核
- 未执行真实外部 LLM provider 联调，仅验证了 fallback 路径和接口契约

## 剩余风险
- SWRL 对照模式当前满足“保留开关 + 1 条端到端能力”的 MVP 目标，但仍偏向对照验证，不是完整 SWRL 驱动业务判定
- 默认环境若缺少 Fuseki 或 Java，系统会降级；自动化已覆盖降级路径，但生产部署仍需显式核对环境变量与依赖
