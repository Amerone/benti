# 00 Overview And Reading Guide

## 这套 wiki 在讲什么

这套 wiki 不是在讲抽象哲学意义上的“本体论”，而是在回答一个更工程化的问题：

> 当企业已经有数据库、API、工作流和 Agent，为什么系统还是容易出现语义错位、规则散落、结果难解释、动作难治理的问题？

这套 wiki 的核心判断是：

- 企业 Agent 的难点，很多时候不是“拿不到数据”，而是“拿不到稳定的业务语义”
- 本体的真正价值，不是知识更多，而是让对象、关系、规则、动作和解释都更稳定
- 真正能落地的方案，一定不是只有本体，还要把 DDD、元数据治理、规则、流程和 Agent 放到同一张图里

## 先看地图

可以把整套 wiki 理解成 5 个模块：

### 模块 1：先理解本体到底解决什么问题

- [01-core-ideas.md](./01-core-ideas.md)
- [11-before-vs-after.md](./11-before-vs-after.md)

这一组回答：

- 本体是什么，不是什么
- 不做本体时，企业到底卡在哪里
- 做了本体之后，真实价值体现在哪

### 模块 2：再理解怎么建模、用什么标准

- [02-modeling-method.md](./02-modeling-method.md)
- [03-standards-stack.md](./03-standards-stack.md)
- [05-glossary-and-sources.md](./05-glossary-and-sources.md)

这一组回答：

- 怎么从业务问题出发做最小建模
- RDF、OWL、SHACL、SPARQL 分别干什么
- 常用术语和进一步阅读资料是什么

### 模块 3：再理解怎么和系统架构结合

- [04-agent-integration.md](./04-agent-integration.md)
- [08-ontology-vs-ddd-metadata.md](./08-ontology-vs-ddd-metadata.md)
- [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)

这一组回答：

- 本体和 RAG、Skills、Workflow 怎么分工
- 本体和 DDD、元数据管理的边界是什么
- 企业里这些层应该怎么放在一起

### 模块 4：再理解如何做试点、严谨性和企业级验证

- [10-pilot-blueprint.md](./10-pilot-blueprint.md)
- [12-llm-rigor-and-correctness.md](./12-llm-rigor-and-correctness.md)
- [13-rigorous-agent-reference-architecture.md](./13-rigorous-agent-reference-architecture.md)
- [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md)
- [15-manufacturing-trial-mvp-rollout.md](./15-manufacturing-trial-mvp-rollout.md)

这一组回答：

- 试点到底该怎么选场景、定指标、搭闭环
- 高严谨场景下，LLM 应该做什么，不该做什么
- 面向生产环境，参考架构和验证体系应该怎么搭

### 模块 5：Palantir 路线的专门分支

- [06-palantir-ontology.md](./06-palantir-ontology.md)
- [07-palantir-practice.md](./07-palantir-practice.md)

这一组回答：

- Palantir 语境里的 Ontology 到底是什么
- 如果沿着 Foundry / OSDK / Actions 的路线走，落地该怎么做

## 每一页各自负责什么

| 页面 | 作用 |
|---|---|
| [01-core-ideas.md](./01-core-ideas.md) | 建立共同语言，先搞清楚“本体是什么” |
| [02-modeling-method.md](./02-modeling-method.md) | 给出最小建模方法，避免一开始就做大而全 |
| [03-standards-stack.md](./03-standards-stack.md) | 解释标准栈与工具栈 |
| [04-agent-integration.md](./04-agent-integration.md) | 说明本体如何和 Agent、RAG、Workflow 配合 |
| [05-glossary-and-sources.md](./05-glossary-and-sources.md) | 术语速查与资料索引 |
| [06-palantir-ontology.md](./06-palantir-ontology.md) | Palantir Ontology 的概念页 |
| [07-palantir-practice.md](./07-palantir-practice.md) | Palantir 路线的实践页 |
| [08-ontology-vs-ddd-metadata.md](./08-ontology-vs-ddd-metadata.md) | 澄清本体、DDD、元数据管理的边界 |
| [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md) | 把这些概念放进一张企业架构图 |
| [10-pilot-blueprint.md](./10-pilot-blueprint.md) | 试点方法、选型与闭环 |
| [11-before-vs-after.md](./11-before-vs-after.md) | 做与不做本体的前后对比 |
| [12-llm-rigor-and-correctness.md](./12-llm-rigor-and-correctness.md) | 高严谨场景下的正确性控制 |
| [13-rigorous-agent-reference-architecture.md](./13-rigorous-agent-reference-architecture.md) | 严谨 Agent 参考架构 |
| [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md) | 企业级验证体系、架构和选型建议 |
| [15-manufacturing-trial-mvp-rollout.md](./15-manufacturing-trial-mvp-rollout.md) | 制造业试验数据管理场景的落地推进页 |

## 推荐阅读路线

### 路线 A：第一次接触，想先搞懂值不值得做

1. [01-core-ideas.md](./01-core-ideas.md)
2. [11-before-vs-after.md](./11-before-vs-after.md)
3. [04-agent-integration.md](./04-agent-integration.md)
4. [10-pilot-blueprint.md](./10-pilot-blueprint.md)

### 路线 B：要开始建模和做 PoC

1. [01-core-ideas.md](./01-core-ideas.md)
2. [02-modeling-method.md](./02-modeling-method.md)
3. [03-standards-stack.md](./03-standards-stack.md)
4. [10-pilot-blueprint.md](./10-pilot-blueprint.md)
5. [05-glossary-and-sources.md](./05-glossary-and-sources.md)

### 路线 C：要做架构对齐和生产设计

1. [08-ontology-vs-ddd-metadata.md](./08-ontology-vs-ddd-metadata.md)
2. [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)
3. [12-llm-rigor-and-correctness.md](./12-llm-rigor-and-correctness.md)
4. [13-rigorous-agent-reference-architecture.md](./13-rigorous-agent-reference-architecture.md)
5. [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md)
6. [15-manufacturing-trial-mvp-rollout.md](./15-manufacturing-trial-mvp-rollout.md)

### 路线 D：你在看 Palantir 路线

1. [01-core-ideas.md](./01-core-ideas.md)
2. [06-palantir-ontology.md](./06-palantir-ontology.md)
3. [07-palantir-practice.md](./07-palantir-practice.md)
4. [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)
5. [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md)

## 如果你只想先看 3 页

我会推荐：

1. [01-core-ideas.md](./01-core-ideas.md)
2. [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)
3. [10-pilot-blueprint.md](./10-pilot-blueprint.md)

这 3 页基本能回答：

- 为什么需要本体
- 本体在企业架构里放哪
- 怎么从真实业务试点开始

## 这一页应该记住什么

只记住 4 句话：

1. 这套 wiki 不是单讲本体，而是在讲“本体如何进入企业 Agent 架构”。
2. 阅读顺序最好按“价值理解 -> 建模 -> 架构 -> 试点 -> 生产验证”推进。
3. Palantir 是一条专门分支，不是整套 wiki 的默认前提。
4. [05-glossary-and-sources.md](./05-glossary-and-sources.md) 更适合作为参考索引，而不是线性主线的一部分。
