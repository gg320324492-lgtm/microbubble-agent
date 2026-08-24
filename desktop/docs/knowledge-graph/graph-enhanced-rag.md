# Graph-Enhanced RAG

## 概述

图增强检索增强生成（RAG）— 在关键词/向量检索基础上，通过知识图谱进行上下文扩展。

## 检索流程

```
用户问题
   ↓
HybridRetriever（关键词 + 向量）
   ↓
初始 SearchResult[]
   ↓
GraphRetriever.expand(query)
   ↓
GraphContext（实体 + 关系 + 引用）
   ↓
合并结果
   ↓
buildContext → RAGContext
```

## 步骤详解

### 1. 关键词检索

HybridRetriever 在文档库中搜索匹配的文档块。

### 2. 图扩展

GraphRetriever 从查询关键词找到匹配的实体，然后通过 BFS 在图上扩展：

```
查询: "TC degradation mechanism"

Step 1: 找到实体 "TC" 和 "degradation"
Step 2: 查找 neighbors (depth=1)
Step 3: 查找 neighbors (depth=2)
Step 4: 返回所有相关实体和关系
```

### 3. 结果合并

- HybridRetriever 返回的 SearchResult 优先
- 图扩展产生的新实体作为补充 SearchResult
- 去重（按 chunkId）
- 限制最大节点数（默认 20）

### 4. 上下文构建

使用现有的 buildContext 函数（不修改 C3 builder）从合并后的 SearchResult[] 构建 RAGContext。

## 图扩展示例

输入：用户问 "为什么微纳米气泡提高臭氧降解？"

图扩展路径：
```
Microbubble (Material)
  ↓ uses
Mass transfer (Mechanism)
  ↓ causes
Dissolved ozone (Material)
  ↓ causes
Hydroxyl radical ·OH (Material)
  ↓ causes
TC degradation (Result)
```

返回：实体、关系、置信度、引用。

## 集成点

```ts
class GraphRAGAdapter {
  constructor(
    private hybridRetriever: HybridRetriever,
    private graphRetriever: GraphRetriever,
    private buildContext: (results: SearchResult[], query: string) => RAGContext
  ) {}

  async retrieve(query: string, topK: number = 5): Promise<RAGContext> {
    const hybridResults = await this.hybridRetriever.retrieve(query, topK)
    const graphContext = this.graphRetriever.expand(query, 2, 20)
    const mergedResults = this.mergeResults(hybridResults, graphContext)
    return this.buildContext(mergedResults, query)
  }
}
```

## 优势

- **更深上下文**：图扩展提供关键词检索无法发现的间接关系
- **引用追溯**：每个图节点带有 sourceDocuments 引用
- **可解释**：推理路径可视化，支持科研论证
- **与现有 RAG 兼容**：不修改 C3 builder，纯适配器模式

## 局限

- 内存存储（重启后丢失）
- 无 LLM 抽取（规则覆盖有限）
- 关系推导基于简单启发式
