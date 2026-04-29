# 委托单 CQ 工程傻瓜式使用手册

这份文档按“照着做就能跑”的方式写。第一次演示前，建议先完整走一遍。

## 你要准备什么

- Windows 或 Linux 开发机。
- Python 3.11+。
- Docker Desktop，用来启动 Fuseki。
- 当前项目代码。
- 浏览器，推荐 Chrome 或 Edge。

## 第 1 步：进入项目目录

```powershell
cd E:\company\temp\benti
```

如果你的目录不同，把命令里的路径换成自己的项目路径。

## 第 2 步：安装依赖

第一次运行需要执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

以后每次新开终端，只需要：

```powershell
cd E:\company\temp\benti
.\.venv\Scripts\Activate.ps1
```

## 第 3 步：启动 Fuseki

```powershell
docker compose up -d
```

检查是否启动：

```powershell
docker compose ps
```

看到 `fuseki` 处于 running 状态即可。

## 第 4 步：启动 API

推荐用 8000 端口：

```powershell
python -m uvicorn mvp.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

如果 8000 被占用，换成 8010：

```powershell
python -m uvicorn mvp.api.main:create_app --factory --host 127.0.0.1 --port 8010
```

浏览器打开：

```text
http://127.0.0.1:8000/api/v1/health
```

如果用的是 8010，就打开：

```text
http://127.0.0.1:8010/api/v1/health
```

成功标志：页面里 `ok` 是 `true`。

## 第 5 步：启动页面

如果 API 在 8000：

```powershell
streamlit run mvp/frontend/app.py --server.port 8501
```

如果 API 在 8010：

```powershell
$env:API_BASE_URL="http://127.0.0.1:8010"
streamlit run mvp/frontend/app.py --server.port 8502
```

浏览器打开：

```text
http://127.0.0.1:8501
```

或：

```text
http://127.0.0.1:8502
```

## 第 6 步：客户演示流程

打开页面后，顶部会看到几个页签：

```text
客户讲 | 委托单试验 | 技术讲 | 设备健康
```

点击 `委托单试验`。

### 6.1 初始化演示数据

点击：

```text
初始化 / 重置 CO-2024-001
```

应该看到：

- 委托单号：`CO-2024-001`
- 委托人：李工
- 产品：相控阵雷达导引头
- 型号：`X-01`
- 两个试验任务：`T-001`、`T-002`

### 6.2 讲清楚当前状态

此时可以说：

> 系统不是只存了一张表，而是把“委托单、产品、试验项目、任务、测试项、数据记录、判定结果、标准版本”都变成了图谱中的对象和关系。

客户应该看到：

- `高低温振动试验` 对应任务 `T-001`
- `电磁兼容试验` 对应任务 `T-002`
- `RCS_MEAN` 实测值 `0.042`
- `BER` 实测值 `0.00021`
- 两项在 V1 标准下都是 `Pass`

### 6.3 触发标准升级

点击：

```text
触发标准升级 V2
```

系统会自动做三件事：

1. 发布新标准 `GJB-7821-2024 V2`。
2. 找出用 V1 标准判过的数据。
3. 用 V2 标准重新计算，并标记结论是否翻转。

成功后重点看：

```text
RCS_MEAN: Pass -> Fail
T-001: NeedsReview
BER: Pass -> Pass
T-002: Completed
```

### 6.4 这一页要讲的价值

可以直接这样讲：

> 传统系统通常只保存最终结果，标准升级后要靠人工查历史数据。本体系统把“结果为什么产生、依赖哪个标准、哪个任务受影响”都建成可查询关系，所以标准变化后可以自动重判、自动追溯、自动生成复核清单。

## 第 7 步：开发演示流程

点击顶部 `技术讲`。

在技术页内部点击：

```text
CQ 工程台
```

### 7.1 选择生成模式

页面有一个生成模式下拉框：

```text
llm_with_template_fallback
template_only
llm_only
```

建议现场演示优先选择：

```text
template_only
```

原因：不依赖外部 LLM，也不会因为网络或 Key 影响演示。

### 7.2 生成并保存草案

点击：

```text
生成并保存草案
```

应该看到草案内容，包括：

- `CQ-CT-001` 到 `CQ-CT-005`
- 候选类：`CommissionOrder`、`TestTask`、`StandardVersion` 等
- 候选关系：`hasProduct`、`decomposesToTask`、`supersedesStandard`
- 候选规则：任务分解、阈值判定、结论翻转后标记复核
- 草案 Turtle
- SPARQL 测试清单

### 7.3 标记 reviewed

选择草案后，点击：

```text
标记为 reviewed
```

草案状态会从：

```text
draft
```

变为：

```text
reviewed
```

### 7.4 这一页要讲的价值

可以直接这样讲：

> LLM 只负责生成候选草案，不直接改正式本体。正式进入本体前，需要人审、需要 CQ 验证、需要 SPARQL 回归测试。这避免了“AI 说得像真的，但模型不可控”的风险。

## 第 8 步：验证系统没有坏

常用测试：

```powershell
python -m pytest -q
```

成功标志：

```text
150 passed
```

编译检查：

```powershell
python -m compileall mvp tests
```

CQ/Fuseki 集成检查：

```powershell
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

如果 Fuseki 可用，应该看到：

```text
1 passed
```

## 常见问题

### 页面打不开

先确认 Streamlit 是否启动。默认地址：

```text
http://127.0.0.1:8501
```

如果使用 8502：

```text
http://127.0.0.1:8502
```

### 页面能打开，但按钮报错

检查 API 是否启动：

```text
http://127.0.0.1:8000/api/v1/health
```

如果 API 在 8010，启动 Streamlit 前要设置：

```powershell
$env:API_BASE_URL="http://127.0.0.1:8010"
```

### Fuseki 不可用

执行：

```powershell
docker compose up -d
```

然后再跑：

```powershell
python -m pytest tests/test_commission_cq_integration.py -q -rs
```

### 不想用真实 LLM

开发演示时选择：

```text
template_only
```

这样不会调用外部 LLM。
