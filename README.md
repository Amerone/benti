# 制造业试验数据管理本体 MVP

本仓库实现制造业试验数据管理本体 MVP：

- FastAPI 提供 `/api/v1` 接口
- Streamlit 提供演示工作台
- Apache Jena Fuseki 保存本体图、业务数据图、推理结果图和规格历史图
- Owlready2/Pellet 负责 OWL 推理

## 委托单 CQ 工程文档

面向委托单试验、自动任务分解、标准升级重判和 LLM 辅助 CQ 反推 TBox/RBox 的演示说明，建议从这里开始：

```text
docs/commission-cq-文档入口.md
```

文档包括傻瓜式操作手册、客户演示讲稿、开发演示讲稿，以及从技术、交付、运维和成本角度说明本体价值的材料。

## 本地启动

如果是为了现场演示，建议先读：

```text
docs/系统演示操作手册.md
```

1. 准备 Python 3.11+。
   Windows 仓库已内嵌 Pellet 所需 JRE，默认不再依赖系统 Java。

2. 创建环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

3. 复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

4. 启动 Fuseki：

```powershell
docker compose up -d
```

如果 Fuseki 允许匿名 `query` 但限制 Graph Store 写入，需要在 `.env` 中显式设置
`FUSEKI_USER` 和 `FUSEKI_PASSWORD`。否则本体加载、测量写入、规格写入会返回 `401`。

默认 dataset 为 `manufacturing-trial`，端口为 `3030`，TDB2 数据卷为 `fuseki-tdb2`。

5. 启动 API 与前端：

```powershell
uvicorn mvp.api.main:app --reload --host 0.0.0.0 --port 8000
streamlit run mvp/frontend/app.py
```

## 内嵌 JRE

项目已内嵌 Windows x64 JRE：

- 路径：`runtime/jre/temurin-25.0.2+10-win-x64`
- 可执行文件：`runtime/jre/temurin-25.0.2+10-win-x64/bin/java.exe`
- 来源：Eclipse Temurin 25.0.2+10 官方发布

之所以固定到 Java 25，是因为当前 `owlready2` 打包的
`jena-arq-fixed2.10.0.jar` 中存在 `class file version 69` 的类文件，低于 Java 25
会触发 `UnsupportedClassVersionError`，导致 Pellet 无法执行。

运行时解析顺序如下：

1. `PELLET_JAVA_EXE`
2. 项目内 `runtime/jre`
3. `PELLET_JAVA_HOME` / `JAVA_HOME`
4. 系统 `PATH` 中的 `java`

如果需要替换为别的 Java 发行版，优先通过 `PELLET_JAVA_EXE` 或
`PELLET_JAVA_HOME` 覆盖，不要直接修改 Owlready2 依赖包。

## 测试

全量自动化测试：

```powershell
python -m pytest -q
```

编译检查：

```powershell
python -m compileall mvp tests
```

Pellet 冒烟验证：

```powershell
python - <<'PY'
from pathlib import Path
from mvp.core import owlready_reasoner as r

ttl_text = Path("mvp/ontology/manufacturing-trial.ttl").read_text(encoding="utf-8")
result = r.load_and_reason("manufacturing-trial", ttl_text, run_pellet=True, force=True)
print(result["pellet_status"], result["java_source"], result["java_exe"])
PY
```

## CQ 验收

CQ（competency questions，胜任力问题）用于把本体需求、SPARQL 查询、推理 evidence 和 QA 解释绑定成可执行验收资产。

第一批 CQ 位于：

```text
docs/cq/measurement-judgement-cqs.md
```

如果你第一次接触 CQ，建议先读入门说明：

```text
docs/cq/cq-beginner-guide.md
```

新增 CQ 时必须包含：

- `Business question`
- `Intent`
- `Covers`
- `Demo data`
- `Expected`
- 一个 `sparql` 代码块
- `Evidence fields`
- `Linked QA example`
- `Acceptance`

SPARQL 代码块中的 named graph 使用 runner 渲染的占位符，避免把 CQ 固定到某一个 ontology：

- `{{ontology_graph_iri}}`
- `{{data_graph_iri}}`
- `{{result_graph_iri}}`
- `{{spec_graph_iri}}`

测量判定 CQ 的 fixture 使用专用参数 `cq_temperature`，避免清理验收数据时影响业务侧已有的 `temperature` 参数、规格或测量。

离线解析测试：

```powershell
python -m pytest tests/test_cq_parser.py -q
```

真实 Fuseki/SPARQL 集成测试：

```powershell
docker compose up -d
python -m pytest tests/test_cq_integration.py -q
```

如果 Fuseki 未启动，集成测试会跳过并提示先运行 `docker compose up -d`。如果 Fuseki 写入需要认证，请在 `.env` 或环境变量中设置 `FUSEKI_USER` 和 `FUSEKI_PASSWORD`。
慢速本地 Fuseki 可以通过 `FUSEKI_TEST_TIMEOUT` 调大集成测试 HTTP 超时时间，默认 15 秒。
当该测试被跳过时，只代表本地缺少外部依赖，不代表真实 Fuseki/SPARQL 链路已经通过；发布前应在具备写凭据的环境中运行一次。

## 运行时说明

- 本项目的确定性业务判定不依赖 Pellet。Pellet 不可用时，测量判定与问答 fallback 仍可工作。
- 但涉及 `Pellet` / `SWRL` 的验收项，需要 `pellet_status=success` 才算真正通过。
- 需要 Fuseki 或 Java 的集成测试，应在对应服务可用后再运行，并在测试说明中标注外部依赖。
