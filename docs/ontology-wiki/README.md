# Ontology Wiki

## 从这里开始

如果你第一次进入这套 wiki，先看：

1. [00-overview-and-reading-guide.md](./00-overview-and-reading-guide.md)
2. [01-core-ideas.md](./01-core-ideas.md)
3. [10-pilot-blueprint.md](./10-pilot-blueprint.md)

## 这套 wiki 的目标

这套 wiki 解决一个问题：

> 当企业 Agent 已经接入数据库、API、工作流，为什么仍然会“看起来很聪明，实际上很容易做错”？

这套 wiki 的核心回答是：

- 它拿到了数据，但没有拿到稳定、共享、可推理的业务语义。
- 本体不是知识堆积，而是业务概念、关系、约束和事实之间的结构化表达。
- 对企业 Agent 来说，本体更像“业务地图 + 规则底座 + 推理支架”。

## 一张总图

如果把整套 wiki 压缩成 5 个模块，可以这样看：

1. 理解本体的价值：`01`、`11`
2. 学会最小建模：`02`、`03`
3. 看清系统边界：`04`、`08`、`09`
4. 推进试点和生产验证：`10`、`12`、`13`、`14`
5. 理解 Palantir 分支：`06`、`07`

完整导读见：[00-overview-and-reading-guide.md](./00-overview-and-reading-guide.md)

## 导航

- [00-overview-and-reading-guide.md](./00-overview-and-reading-guide.md)  
  先看整套 wiki 的地图、模块划分、页面职责和推荐阅读路线。

- [01-core-ideas.md](./01-core-ideas.md)  
  先搞清楚本体是什么，不是什么，为什么对 Agent 重要。

- [02-modeling-method.md](./02-modeling-method.md)  
  从业务场景出发，走一遍最小可行本体建模流程。

- [03-standards-stack.md](./03-standards-stack.md)  
  RDF、OWL、SHACL、SPARQL、Protégé、推理机、三元组库分别扮演什么角色。

- [04-agent-integration.md](./04-agent-integration.md)  
  本体和 RAG、Skills、Workflow 怎么配合，而不是互相替代。

- [05-glossary-and-sources.md](./05-glossary-and-sources.md)  
  术语表、阅读清单、外部资料。更适合作为参考索引。

- [06-palantir-ontology.md](./06-palantir-ontology.md)  
  从 Palantir 的产品语境理解 Ontology：对象、链接、接口、动作、函数和 operational layer。

- [07-palantir-practice.md](./07-palantir-practice.md)  
  Palantir Ontology 的实战路径、OSDK、Object Views、应用开发和常见坑。

- [08-ontology-vs-ddd-metadata.md](./08-ontology-vs-ddd-metadata.md)  
  企业本体、DDD、元数据管理分别解决什么问题，边界在哪里，如何配合。

- [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)  
  把 DDD、元数据管理、Ontology、Workflow、Agent 放进同一张企业架构分层图里。

- [10-pilot-blueprint.md](./10-pilot-blueprint.md)  
  如果要用真实业务验证本体是否可行，应该怎么选场景、怎么选技术、怎么搭架构、怎么定义闭环。

- [11-before-vs-after.md](./11-before-vs-after.md)  
  不用本体时企业通常怎么做，用了本体后到底改变了什么，本体最真实的价值点是什么。

- [12-llm-rigor-and-correctness.md](./12-llm-rigor-and-correctness.md)  
  在调用 LLM、MCP、Skills 的情况下，如何把正确性尽量放回数据源、规则层、校验层和受控流程里。

- [13-rigorous-agent-reference-architecture.md](./13-rigorous-agent-reference-architecture.md)  
  面向严谨数据场景的 Agent 参考架构：LLM、Gateway、本体、规则、Workflow、审计各放在哪一层。

- [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md)  
  如果要搭企业级验证体系，应该怎么验证本体、怎么搭技术架构、怎么做选型与分层闭环。

- [15-manufacturing-trial-mvp-rollout.md](./15-manufacturing-trial-mvp-rollout.md)  
  结合制造业试验数据管理 MVP 文档，说明这个场景应该如何落地、如何按周推进、如何做演示和验收。

## 适合谁

- 想理解“企业本体”而不是抽象哲学含义的人
- 正在做 Agent / RAG / Workflow，但发现语义错误总是反复出现的人
- 想把业务规则从口口相传和硬编码里抽出来的人

## 推荐阅读路线

### 路线 A：快速入门

1. [00-overview-and-reading-guide.md](./00-overview-and-reading-guide.md)
2. [01-core-ideas.md](./01-core-ideas.md)
3. [11-before-vs-after.md](./11-before-vs-after.md)
4. [10-pilot-blueprint.md](./10-pilot-blueprint.md)

### 路线 B：准备建模和做 PoC

1. [01-core-ideas.md](./01-core-ideas.md)
2. [02-modeling-method.md](./02-modeling-method.md)
3. [03-standards-stack.md](./03-standards-stack.md)
4. [10-pilot-blueprint.md](./10-pilot-blueprint.md)
5. [05-glossary-and-sources.md](./05-glossary-and-sources.md)

### 路线 C：准备做企业架构与生产方案

1. [08-ontology-vs-ddd-metadata.md](./08-ontology-vs-ddd-metadata.md)
2. [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)
3. [12-llm-rigor-and-correctness.md](./12-llm-rigor-and-correctness.md)
4. [13-rigorous-agent-reference-architecture.md](./13-rigorous-agent-reference-architecture.md)
5. [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md)
6. [15-manufacturing-trial-mvp-rollout.md](./15-manufacturing-trial-mvp-rollout.md)

### 路线 D：只看 Palantir 方向

1. [01-core-ideas.md](./01-core-ideas.md)
2. [06-palantir-ontology.md](./06-palantir-ontology.md)
3. [07-palantir-practice.md](./07-palantir-practice.md)
4. [09-enterprise-architecture-view.md](./09-enterprise-architecture-view.md)
5. [14-enterprise-validation-playbook.md](./14-enterprise-validation-playbook.md)

## 最后一个建议

不要把 [05-glossary-and-sources.md](./05-glossary-and-sources.md) 当成主线阅读页。  
它更适合在阅读其它页面时，作为术语和资料索引随时查阅。
