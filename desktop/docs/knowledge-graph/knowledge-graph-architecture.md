# Knowledge Graph Architecture

## Overview

科研知识图谱系统 — 从文档/实验中自动抽取实体和关系，为 RAG 提供图扩展能力。

## 数据模型

### ScientificEntity（实体）

```ts
interface ScientificEntity {
  id: string
  name: string
  type: EntityType  // Paper | Author | Method | Material | Parameter | Mechanism | Experiment | Result | Claim | Equation | Dataset | Model
  description: string
  sourceDocuments: string[]
  confidence: number  // 0..1
  metadata: Record<string, unknown>
}
```

### KnowledgeRelation（关系）

```ts
interface KnowledgeRelation {
  id: string
  sourceEntityId: string
  targetEntityId: string
  relationType: RelationType  // supports | contradicts | improves | causes | depends_on | measured_by | uses | compared_with | derived_from
  confidence: number  // 0..1
  evidence: string
}
```

## 实体类型 (12)

- Paper — 论文
- Author — 作者
- Method — 方法
- Material — 材料/物质
- Parameter — 参数
- Mechanism — 机理
- Experiment — 实验
- Result — 结果
- Claim — 主张
- Equation — 方程
- Dataset — 数据集
- Model — 模型

## 关系类型 (9)

- supports 支持
- contradicts 矛盾
- improves 改进
- causes 导致
- depends_on 依赖
- measured_by 测量
- uses 使用
- compared_with 比较
- derived_from 派生

## 系统组件

### 本地实体抽取器 (local-entity-extractor)

- 基于确定性规则（无 LLM）
- 支持中英文双语关键词
- 5 类规则集：Material/Parameter/Mechanism/Result/Method
- 自动推导关系链

### 知识图谱存储 (knowledge-graph-store)

- 内存 Map 存储
- 防御性拷贝（getter 返回克隆）
- 确定性排序（按 id 排序）
- 去重管理
- 快照支持

### 图检索器 (graph-retriever)

- BFS 扩展查询
- 最大深度 2
- 最大节点 20
- 收集路径上的实体和关系
- 计算平均置信度

### 图增强 RAG 适配器 (graph-rag-adapter)

- 集成 HybridRetriever
- 合并关键词检索 + 图扩展结果
- 使用现有 RAGContext builder（不修改）

### 知识推理服务 (knowledge-reasoning-service)

- 机理路径查找 (findMechanismPath)
- 证据链查找 (findEvidenceChain)
- 相关方法推荐 (findRelatedMethods)

## 安全边界

- 所有值使用秘密防护检查（findForbidden）
- 无 API key/secret/token/cipher 泄漏
- 验证器在导入时检查违规

## 数据流

```
文档/Chunk
  ↓
LocalEntityExtractor
  ↓
ScientificEntity + KnowledgeRelation
  ↓
KnowledgeGraphStore
  ↓
GraphRetriever / KnowledgeReasoningService
  ↓
RAGContext / 推理结果
```
