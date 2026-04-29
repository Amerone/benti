# 委托单 CQ 工程文档入口

本目录这组文档用于把 `commission-testing` 演示讲清楚、跑起来、讲出价值。

## 推荐阅读顺序

1. [commission-cq-傻瓜式使用手册.md](commission-cq-傻瓜式使用手册.md)
   - 给现场操作人员。
   - 目标：不理解本体也能把系统启动、页面打开、完整流程跑通。

2. [commission-cq-客户演示讲稿.md](commission-cq-客户演示讲稿.md)
   - 给售前、项目经理、演示人。
   - 目标：知道每一步点哪里、说什么、客户应该看见什么。

3. [commission-cq-开发演示讲稿.md](commission-cq-开发演示讲稿.md)
   - 给技术负责人、开发团队、架构评审。
   - 目标：讲清楚 CQ 如何反推 TBox/RBox，LLM 为什么只生成草案，验证如何闭环。

4. [commission-cq-本体技术与成本价值说明.md](commission-cq-本体技术与成本价值说明.md)
   - 给决策人、预算评审、技术选型会。
   - 目标：从技术、交付、运维、成本角度说明为什么用本体，而不是只用表、规则、报表或 LLM。

## 一句话定位

`commission-testing` 演示的是：从委托单业务出发，用 CQ 把业务问题转成可执行的本体需求、TBox/RBox 草案、规则和 SPARQL 回归测试；系统能够完成试验任务分解、测试结果判定、标准升级后的历史数据重判，并把结论翻转追溯到任务和标准版本。

## 最小演示链路

```text
新建/重置委托单 CO-2024-001
  -> 自动得到试验项目 P-001/P-002
  -> 自动分解任务 T-001/T-002
  -> 写入 RCS_MEAN / BER 实测值
  -> 按 V1 标准判定 Pass
  -> 发布 V2 标准
  -> 自动重判历史数据
  -> RCS_MEAN: Pass -> Fail
  -> T-001: NeedsReview
  -> CQ 草案生成、保存、reviewed
```

## 当前核心文件

- 本体：`mvp/ontology/commission-testing.ttl`
- CQ 注册表：`docs/cq/commission-testing-cqs.md`
- 规则配置：`mvp/rules/commission-testing.yml`
- 演示数据：`mvp/data/commission-testing-demo.json`
- 核心推理：`mvp/core/commission_reasoning.py`
- RDF 持久化：`mvp/core/commission_graph.py`
- CQ 工程：`mvp/core/cq_engine.py`、`mvp/core/ontology_draft.py`
- API：`mvp/api/commission_routes.py`、`mvp/api/cq_engine_routes.py`
- 页面：`mvp/frontend/tabs/tab_commission_customer.py`、`mvp/frontend/tabs/tab_cq_engine.py`
