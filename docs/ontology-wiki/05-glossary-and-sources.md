# 05 Glossary And Sources

## 这页怎么用

这一页不是主线正文，更适合作为索引页。

建议这样使用：

1. 第一次读这套 wiki，不要从这页开始，先回到 [00-overview-and-reading-guide.md](./00-overview-and-reading-guide.md)
2. 在正文里遇到不熟悉的词，先查下面的“高频术语”
3. 只有在要继续深挖时，再看“扩展术语”和“相关资料清单”

这页的职责是：

- 术语速查
- 外部资料索引
- 补充阅读入口

## 先看这些高频术语

### Ontology / 本体

业务领域中概念、关系、属性、约束和可推理结构的显式表达。

### TBox

术语层、结构层、规则层。描述“概念是什么、怎样关联、满足什么约束”。

### ABox

事实层、实例层。描述“现实里有哪些具体对象、它们当前是什么状态”。

### RDF

以三元组形式表达信息的基础标准。

### OWL

建立在 RDF 之上的 Web 本体语言，用于更强的语义建模和逻辑表达。

### SHACL

用于校验 RDF 数据是否满足约束和形状的标准。

### SPARQL

查询和操作 RDF 图数据的标准语言。

### Knowledge Graph / 知识图谱

更偏事实和实例连接的数据集合；通常以本体作为语义框架之一。

## 需要时再看这些扩展术语

### Domain-Driven Design / DDD

围绕业务领域、通用语言、限界上下文和领域模型来设计软件的方法论。

### Bounded Context / 限界上下文

DDD 中控制模型边界和语义一致性的核心概念，不同上下文允许对同一业务词汇有不同建模。

### Ubiquitous Language / 通用语言

DDD 中开发者与领域专家共享使用、并进入文档和代码的统一业务语言。

### Metadata Management / 元数据管理

围绕数据资产的描述、发现、血缘、分类、术语、质量和治理的管理实践。

### Business Glossary / 业务术语表

用于统一关键业务术语、定义、同义词和上下文的治理资产，通常属于元数据管理的一部分。

### Data Catalog / 数据目录

用于发现、搜索、浏览和治理数据资产及其元数据的平台能力。

### Lineage / 血缘

描述数据从来源到加工再到消费链路的关系网络，是元数据管理的重要组成部分。

### Object Type

Palantir Ontology 中对现实实体或事件的类型定义。

### Link Type

Palantir Ontology 中对象类型之间关系的定义。

### Interface

Palantir Ontology 中多个对象类型共享的形状与能力定义，用来支持多态复用。

### Action Type

Palantir Ontology 中一组业务变更的定义，包含参数、校验、写入与副作用。

### Functions On Objects

Palantir 中围绕 ontology objects 和 links 读写、计算、编排业务逻辑的函数能力。

### Object View

对象的可复用展示入口，把属性、关系和相关应用组合成用户可消费的对象上下文。

### Object Explorer

面向业务用户的对象搜索、筛选、探索和批量动作入口。

### OSDK

Ontology SDK。由 Developer Console 基于选定 Ontology 资源生成的应用开发 SDK。

## 相关资料清单

如果你只做最小阅读，先看“先看这些”即可。  
下面几个分组更适合在具体问题出现时按需展开。

### 先看这些

1. Stanford Ontology Development 101  
   https://protege.stanford.edu/publications/ontology_development/ontology101-noy-mcguinness.html  
   适合建立“为什么建本体、怎么开始建”的基本方法感。

2. Protégé 官方主页  
   https://protege.stanford.edu/  
   适合了解桌面版和 Web 版工具。

3. Protégé 软件说明  
   https://protege.stanford.edu/software.php  
   适合理解工具能力边界。

### 语义网标准

4. RDF 1.1 Concepts and Abstract Syntax  
   https://www.w3.org/TR/rdf-concepts/  
   适合理解 RDF 图、三元组、IRI、字面量这些基础概念。

5. OWL 2 Web Ontology Language Overview  
   https://www.w3.org/TR/owl-overview/  
   适合理解 OWL 在整个语义建模栈中的位置。

6. SHACL Recommendation  
   https://www.w3.org/TR/shacl/  
   适合理解如何对 RDF 数据做结构化校验。

7. SPARQL 1.1 Overview  
   https://www.w3.org/TR/sparql11-overview/  
   适合理解本体/图数据如何查询与操作。

### 企业语义层实践

8. Palantir Ontology Overview  
   https://www.palantir.com/docs/foundry/ontology/overview/  
   适合理解“企业本体作为 operational layer / digital twin”的产品化表达。

9. Palantir Action Types Overview  
   https://www.palantir.com/docs/foundry/action-types/overview/  
   适合理解语义层如何连接到实际业务动作。

10. Palantir Functions on Objects  
    https://www.palantir.com/docs/foundry/functions/functions-on-objects/  
    适合理解对象、链接、函数如何进入实际执行层。

11. Palantir Types Reference  
    https://www.palantir.com/docs/foundry/object-link-types/type-reference  
    适合理解 object type、link type、shared property、interface 等核心资源。

12. Palantir Interfaces Overview  
    https://www.palantir.com/docs/foundry/interfaces/interface-overview  
    适合理解跨对象类型复用和多态建模。

13. Palantir Object Views Overview  
    https://www.palantir.com/docs/foundry/object-views/overview  
    适合理解对象如何进入实际应用视图。

14. Palantir Object Explorer Overview  
    https://www.palantir.com/docs/foundry/object-explorer/overview  
    适合理解对象搜索、筛选和批量动作入口。

15. Palantir Developer Console: Create a new OSDK application  
    https://www.palantir.com/docs/foundry/ontology-sdk/create-a-new-osdk/  
    适合理解如何围绕 Ontology 生成应用 SDK。

16. Palantir OSDK React Applications Overview  
    https://www.palantir.com/docs/foundry/ontology-sdk-react-applications/overview  
    适合理解前端应用如何直接建立在 Ontology 之上。

17. Palantir Dev Toolchain Overview  
    https://www.palantir.com/docs/foundry/dev-toolchain/overview/  
    适合理解 OSDK 在整体开发工具链中的位置。

18. Palantir Architecture Center: The Ontology system  
    https://www.palantir.com/docs/foundry/architecture-center/ontology-system  
    适合理解 Palantir 如何把 Ontology 解释为企业决策系统的核心。

19. palantir/ontology-starter-react-app  
    https://github.com/palantir/ontology-starter-react-app  
    适合理解一个最小 React + OSDK 应用骨架。

20. palantir/osdk-ts  
    https://github.com/palantir/osdk-ts  
    适合理解 TypeScript OSDK 相关库的结构和基本用法。

21. palantir/defense-sdk-examples  
    https://github.com/palantir/defense-sdk-examples  
    适合理解面向复杂业务域的公开示例。

22. Build With Palantir's Defense Ontology  
    https://www.palantir.com/docs/defense-ontology/api  
    适合理解 Ontology SDK 如何面向特定行业领域开放能力。

### DDD 与软件领域建模

23. Martin Fowler: Bounded Context  
    https://martinfowler.com/bliki/BoundedContext.html  
    适合理解 DDD 为什么反对在大型系统里强行追求单一统一模型。

24. Microsoft Learn: Use Domain Analysis to Model Microservices  
    https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis  
    适合理解 DDD 的战略设计、业务能力边界和通用语言。

25. Microsoft Learn: Use Tactical DDD to Design Microservices  
    https://learn.microsoft.com/en-us/azure/architecture/microservices/model/tactical-domain-driven-design  
    适合理解实体、聚合和上下文内部模型如何落地。

26. Microsoft Learn: Design a Microservice Domain Model  
    https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/microservice-domain-model  
    适合理解领域模型、实体和限界上下文在工程中的落点。

27. Microsoft Learn: Domain Model Layer Validations  
    https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-model-layer-validations  
    适合理解 DDD 中聚合和不变量的职责。

### 元数据管理与数据治理

28. DAMA-DMBOK  
    https://dama.org/learning-resources/dama-data-management-body-of-knowledge-dmbok/  
    适合理解数据管理与元数据管理的学科边界。

29. DAMA: What is Data Management?  
    https://dama.org/about-dama/what-is-data-management/  
    适合理解元数据管理在整体数据管理中的位置。

30. Microsoft Purview Unified Catalog  
    https://learn.microsoft.com/en-us/purview/what-is-data-catalog  
    适合理解企业数据目录、治理域、数据产品和业务术语。

31. Microsoft Purview Data Governance Glossary  
    https://learn.microsoft.com/en-us/purview/purview-glossary  
    适合理解 metadata、glossary、asset、data map 等常用治理概念。

32. Microsoft Purview Scans and Ingestion in Data Map  
    https://learn.microsoft.com/en-us/purview/concept-scans-and-ingestion  
    适合理解元数据平台如何从源系统采集技术元数据与血缘。

33. OpenMetadata Documentation  
    https://docs.open-metadata.org/latest  
    适合理解开源元数据平台的整体能力面。

34. OpenMetadata Getting Started  
    https://docs.open-metadata.org/latest/quick-start/getting-started  
    适合理解统一元数据图、连接器、发现、治理和质量能力。

35. OpenMetadata Features  
    https://docs.open-metadata.org/features  
    适合理解数据发现、质量、可观测性和协作在元数据平台中的位置。

36. OpenMetadata Standards  
    https://docs.open-metadata.org/v1.11.x/api-reference/sdk/openmetadata-standards  
    适合理解元数据标准与 RDF/OWL/SHACL 的交叉点。

### 试点落地与技术选型

37. Protégé / WebProtégé  
    https://protege.stanford.edu/software.php  
    适合理解协作式 OWL 本体建模工具能力。

38. Owlready2 Documentation  
    https://owlready2.readthedocs.io/  
    适合理解如何在 Python 中读取、修改和推理 OWL 本体。

39. Owlready2 Reasoning  
    https://owlready2.readthedocs.io/en/latest/reasoning.html  
    适合理解 HermiT / Pellet 推理与一致性校验的最小用法。

40. Apache Jena Fuseki  
    https://jena.apache.org/documentation/fuseki2/  
    适合理解如何提供 SPARQL 查询与更新服务。

41. Apache Jena Fuseki Configuration  
    https://jena.apache.org/documentation/fuseki2/fuseki-configuration  
    适合理解试点环境下的服务配置与数据访问控制。

42. n8n Docs  
    https://docs.n8n.io/  
    适合理解轻量工作流自动化与 API 编排。

43. Temporal Docs  
    https://docs.temporal.io/  
    适合理解高可靠工作流编排路线。

44. Camunda Platform Overview  
    https://camunda.com/platform/  
    适合理解流程治理、审批和编排平台路线。

## 两篇已读文章

如果你只想先抓住这套 wiki 的问题意识和基本判断，这两篇文章可以当作背景材料。

1. 企业级 AI Agent 的终极王牌：带你理解 “本体论” 与 6 块核心“积木”  
   https://www.toutiao.com/article/7610789275896267314/

2. 手把手带你构建第一个业务本体（Ontology）  
   https://www.toutiao.com/article/7612456070761447986/

## 推荐阅读顺序

### 只想快速入门

1. 已读文章综合总结
2. Stanford Ontology 101
3. Protégé 官网

### 想做工程落地

1. 已读文章综合总结
2. Palantir Ontology Overview
3. RDF / OWL / SHACL / SPARQL 四篇 W3C 文档
4. 再回看本 wiki 的建模方法页

### 想做试点项目

建议直接挑一个最小场景：

- 发货资格
- 授信审批
- 合同履约
- 质检放行

然后用本 wiki 的第二、三、四页反推方案，而不是继续抽象讨论。

## 这一页应该记住什么

1. 这页是索引页，不是主线正文页。
2. 高效用法是“先查高频术语，再按需看扩展术语和资料”。
3. 真正的线性阅读入口应该是 [00-overview-and-reading-guide.md](./00-overview-and-reading-guide.md)。
