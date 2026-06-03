# 知识库大脑 V2 — 全面升级设计规格

> 日期: 2026-06-03
> 状态: 设计完成，待实现
> 方案: C — 混合架构（保留现有系统 + GraphRAG 增强层 + Agent 智能路由）

---

## 1. 背景与目标

### 1.1 当前系统能力

| 模块 | 核心能力 |
|------|----------|
| KnowledgeService | CRUD + pgvector 语义搜索 + 文件解析 + LLM 动态分析 + 对话自动入库 |
| KnowledgeQAService | RAG 问答（检索→阈值分类→LLM 合成→来源引用）+ 多跳推理 |
| KnowledgeGraphService | 自动关联引擎 + BFS 遍历 + 动态分类 + 标签云 + 统计 |
| AutoResearchService | 知识空白检测 + 联网搜索 + 自动入库 + 矛盾/重复/过期检测 |
| EntityService | 实体三元组提取 + 跨文档融合 + ECharts 力导向图 |
| HypothesisService | 从实体三元组 LLM 生成可验证假设 |
| FormulaService | 32 个内置公式 + 分类树 + 安全计算 + LaTeX 渲染 |
| EvolutionTasks | Celery 定时任务：每日进化 / 空白检测 / 健康检查 / 实体融合 |

### 1.2 当前局限

1. **纯向量检索** — 只有 pgvector 语义搜索，没有关键词检索和图谱检索
2. **简单知识图谱** — 只有三元组 `{subject, predicate, object}`，不是属性知识图谱
3. **无重排序** — 检索结果直接送 LLM，没有精排
4. **无自检** — 不检查检索结果是否真的相关
5. **无评估** — 没有 RAG 质量监控
6. **Agent 被动** — 只有 2 个知识工具，不能主动发现和研究
7. **无多模态** — 只处理文本，不处理图片/表格/音频

### 1.3 升级目标

- **检索质量**：引入 GraphRAG、混合检索、重排序，大幅提升回答准确率
- **知识图谱升级**：构建属性知识图谱，支持多跳推理、图谱引导检索
- **Agent 深度集成**：8 个知识工具 + 主动进化循环 + 知识推送
- **RAG 评估**：持续监控回答质量，反馈闭环优化

### 1.4 规模预期

- 当前：约 100 条知识
- 预期 1 年：5000+ 条知识
- 来源：文件上传 + 对话自动入库 + 自动研究入库 + 结构化数据源

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│                    用户 / 小气助手                         │
│              （自然语言提问 / 主动推送 / 研究建议）          │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              Agent 智能路由层（新增）                       │
│  • 查询意图分类（事实查询 / 概念解释 / 多跳推理 / 开放研究）│
│  • 选择检索策略（向量 / 图谱 / 混合 / 直接回答）            │
│  • 决定是否需要联网搜索 / 自主研究                         │
└──────────────────────┬───────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  向量检索层   │ │  图谱检索层   │ │  关键词检索层 │
│  (现有 pgvec) │ │  (新增 Neo4j) │ │  (新增 BM25) │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
              ┌──────────────────┐
              │   重排序层（新增）  │
              │  Cross-encoder   │
              │  + 相关性评分     │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  Self-RAG 自检    │
              │  检索结果相关性   │
              │  + 幻觉检测      │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  上下文压缩（新增）│
              │  去重 + 摘要     │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  LLM 生成回答    │
              │  + 来源引用      │
              └────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  RAG 评估（新增） │
              │  faithfulness    │
              │  relevance       │
              └──────────────────┘
```

### 2.1 设计原则

1. **保留现有系统** — 现有 pgvector + RAG 问答作为基础层，不删除
2. **增量叠加** — GraphRAG、BM25、重排序作为增强层叠加
3. **可降级** — 新模块失败时自动 fallback 到现有系统
4. **渐进迁移** — 每个阶段可独立上线，不影响现有功能

---

## 3. GraphRAG 增强层

### 3.1 知识图谱构建流程

```
文档/对话/研究入库
       │
       ▼
┌─────────────────┐
│  文本分块        │  语义分块（非固定长度）
│  Semantic Chunk │  按段落/主题自然切分，每块 200-500 字
└────────┬────────┘
         ▼
┌─────────────────┐
│  LLM 实体提取    │  提取：人名/机构/概念/方法/材料/设备/指标
│  + 关系提取      │  关系：uses/produces/inhibits/measures/correlates...
└────────┬────────┘
         ▼
┌─────────────────┐
│  实体消歧        │  同一实体不同称呼合并
│  + 去重         │  "微纳米气泡" = "MNB" = "micro-nano bubble"
└────────┬────────┘
         ▼
┌─────────────────┐
│  Neo4j 写入      │  实体节点 + 关系边 + 属性
│  + 社区检测      │  Leiden 算法聚类相关实体
└────────┬────────┘
         ▼
┌─────────────────┐
│  社区摘要生成    │  LLM 为每个社区生成摘要
│  (GraphRAG 特有) │  用于全局主题检索
└─────────────────┘
```

### 3.2 实体类型定义

| 实体类型 | 示例 | 属性 |
|----------|------|------|
| **Concept** | 微纳米气泡、zeta电位、空化效应 | definition, unit, typical_range |
| **Method** | 超声法、电解法、溶气法 | principle, advantages, disadvantages |
| **Material** | 表面活性剂、聚合物、金属离子 | formula, concentration, role |
| **Equipment** | 粒度分析仪、高速相机 | model, measurement_range, accuracy |
| **Metric** | 粒径分布、含气量、稳定性 | unit, measurement_method, typical_values |
| **Person** | 杜同贺、赵航佳 | role, expertise, publications |
| **Organization** | 课题组、合作单位 | type, focus_area |
| **Paper** | 文献标题 | authors, year, journal, doi |

### 3.3 关系类型定义

| 关系类型 | 含义 | 示例 |
|----------|------|------|
| **uses** | 使用 | 超声法 → uses → 表面活性剂 |
| **produces** | 产生 | 电解法 → produces → 微纳米气泡 |
| **inhibits** | 抑制 | 高盐浓度 → inhibits → 气泡稳定性 |
| **measures** | 测量 | 粒度分析仪 → measures → 粒径分布 |
| **correlates** | 相关 | zeta电位 → correlates → 气泡稳定性 |
| **extends** | 扩展 | 研究A → extends → 研究B |
| **contradicts** | 矛盾 | 结论A → contradicts → 结论B |
| **prerequisite** | 前置 | 方法B → prerequisite → 理论A |

### 3.4 图谱引导检索模式

| 检索模式 | 适用场景 | 工作方式 |
|----------|----------|----------|
| **实体引导检索** | "zeta电位怎么测？" | 找到实体 → 遍历相关实体 → 关联知识条目 |
| **多跳推理** | "哪些方法能提高溶解氧？" | 溶解氧 ← 表面活性剂 ← MNB → 空化效应 → 曝气法 |
| **社区摘要** | "课题组研究方向有哪些？" | 遍历图谱社区 → 返回各社区摘要 |
| **对比检索** | "超声法和化学法哪个好？" | 找到两个实体 → 对比属性和关联知识 |

### 3.5 技术选型

- **图数据库**: Neo4j（Docker 服务，社区版）
- **Python 驱动**: `neo4j` 官方 Python driver
- **社区检测**: Neo4j GDS 库内置 Leiden 算法
- **实体提取**: Claude API（与现有 LLM 分析复用）

---

## 4. 混合检索流水线

### 4.1 三路并发检索

```
用户查询: "微纳米气泡如何提高污水处理效率？"
           │
     ┌─────┼─────┐
     ▼     ▼     ▼
  向量    图谱   BM25
  检索    检索   检索
     │     │     │
     ▼     ▼     ▼
  [条目1] [条目3] [条目1]
  [条目2] [条目5] [条目4]
  [条目3] [条目7] [条目6]
     │     │     │
     └─────┼─────┘
           ▼
     合并 + 去重
           │
           ▼
     Cross-encoder 重排序
           │
           ▼
     [条目3, 条目1, 条目5, ...]
```

### 4.2 各路检索特点

| 检索方式 | 擅长 | 不擅长 | 实现 |
|----------|------|--------|------|
| **向量检索** | 语义相似、同义词 | 精确匹配、专有名词 | 现有 pgvector |
| **BM25** | 精确匹配、关键词 | 语义理解 | `rank-bm25` 库 |
| **图谱检索** | 多跳推理、实体关系 | 模糊查询 | Neo4j Cypher |

### 4.3 重排序（Cross-encoder）

三路检索结果合并后，用 Cross-encoder 模型精排：

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

scores = reranker.predict([(query, item.content) for item in candidates])
ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
```

- 模型: `cross-encoder/ms-marco-MiniLM-L-6-v2`（轻量，CPU 可跑）
- 只对候选集精排（top_k * 3），不做全库扫描

### 4.4 Agent 智能路由

```python
async def route_query(query: str) -> RetrievalStrategy:
    """Agent 根据查询意图选择检索策略"""
    intent = await classify_intent(query)

    if intent == "factual":
        # 事实查询："zeta电位的单位是什么？"
        return RetrievalStrategy(vector + bm25, top_k=3)
    elif intent == "conceptual":
        # 概念解释："什么是空化效应？"
        return RetrievalStrategy(vector + graph, top_k=5)
    elif intent == "multi_hop":
        # 多跳推理："哪些方法能提高溶解氧？"
        return RetrievalStrategy(graph + vector, top_k=8)
    elif intent == "comparative":
        # 对比分析："超声法和化学法哪个好？"
        return RetrievalStrategy(graph + vector + bm25, top_k=10)
    elif intent == "exploratory":
        # 开放研究："课题组目前研究方向有哪些？"
        return RetrievalStrategy(graph_community, top_k=15)
```

### 4.5 Self-RAG 自检

生成回答前，LLM 检查检索结果是否足够：

```python
async def self_rag_check(query: str, context: str) -> dict:
    """检查检索结果是否能回答问题"""
    prompt = f"""判断以下上下文是否能回答用户问题。

用户问题: {query}

检索到的上下文:
{context}

返回 JSON:
{{"can_answer": true/false, "reason": "原因", "missing": "缺少什么信息"}}"""

    result = await llm.generate(prompt)
    return json.loads(result)
```

- `can_answer=true` → 生成回答
- `can_answer=false` → 扩大 top_k / 换策略 / 联网搜索

---

## 5. Agent 深度集成

### 5.1 知识工具升级

当前 2 个 → 升级为 8 个：

| 工具 | 功能 | 触发场景 |
|------|------|----------|
| `search_knowledge` | 混合检索（向量+图谱+BM25） | 用户提问时自动调用 |
| `save_knowledge` | 保存知识（增强版） | 对话中提取 / 手动保存 |
| `explore_knowledge_graph` | 图谱探索（实体+关系+社区） | "XX 和 YY 有什么关系？" |
| `find_knowledge_gaps` | 发现知识空白 | 定期自动 / 用户询问 |
| `auto_research` | 自主研究（联网搜索+入库） | 发现空白时自动触发 |
| `compare_knowledge` | 对比分析 | "A 和 B 哪个好？" |
| `summarize_topic` | 主题总结（基于图谱社区） | "课题组研究方向有哪些？" |
| `suggest_research` | 研究建议（基于假设+空白） | "下一步该研究什么？" |

### 5.2 Agent 主动进化循环

```
┌─────────────────────────────────────────────────┐
│              Agent 主动进化循环                   │
│                                                  │
│  1. 监听：对话/文件/会议 → 自动提取知识           │
│  2. 分析：新知识 → 图谱关联 → 发现空白            │
│  3. 研究：空白 → 联网搜索 → 自动入库              │
│  4. 推送：新发现 → 主动通知用户                    │
│  5. 评估：知识质量 → 标记过期/矛盾                 │
│                                                  │
│  触发方式：                                       │
│  • 实时：每次对话后自动分析                        │
│  • 定时：Celery 每日进化任务                       │
│  • 事件：新知识入库时触发关联分析                   │
└─────────────────────────────────────────────────┘
```

### 5.3 小气助手的"知识意识"

Agent 系统提示词中注入知识库上下文：

```python
system_prompt = f"""
你是小气助手，课题组的 AI 助手。

当前知识库状态：
- 共 {knowledge_count} 条知识
- {gap_count} 个知识空白待填补
- {stale_count} 条知识可能过期
- 最近新增：{recent_topics}

你的知识能力：
- 可以搜索知识库回答问题
- 可以发现知识空白并主动研究
- 可以对比不同知识条目
- 可以探索知识图谱发现关联

当用户提问时，优先从知识库检索。如果知识库没有答案，
主动提出"要不要我帮你研究一下？"
"""
```

### 5.4 知识推送机制

| 触发条件 | 推送对象 | 推送方式 |
|----------|----------|----------|
| 新知识入库 | 相关成员 | 企业微信 / 通知面板 |
| 知识过期 | 创建者 | 企业微信 / 通知面板 |
| 矛盾检测 | 相关成员 | 企业微信 / 通知面板 |
| 空白填补 | 提问者 | 企业微信 / 通知面板 |
| 假设验证 | 研究者 | 企业微信 / 通知面板 |
| 每日知识摘要 | 全体成员 | 企业微信群消息 |

---

## 6. RAG 评估框架

### 6.1 核心指标（RAGAS 框架）

| 指标 | 含义 | 计算方式 |
|------|------|----------|
| **Faithfulness** | 回答是否基于检索结果 | LLM 分解回答为声明，逐一验证 |
| **Answer Relevancy** | 回答是否切题 | LLM 从回答反向生成问题，与原问题比较 |
| **Context Precision** | 检索结果排序是否合理 | 相关条目是否排在前面 |
| **Context Recall** | 是否检索到了所有相关信息 | 与标准答案对比覆盖率 |

### 6.2 评估流程

```
用户提问 → 检索 → 生成回答
                    │
                    ▼
            ┌───────────────┐
            │  自动评估      │
            │  (异步，不阻塞) │
            └───────┬───────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    faithfulness  relevancy   precision
        │           │           │
        └───────────┼───────────┘
                    ▼
            评估结果写入 DB
            (用于持续监控)
```

### 6.3 反馈闭环

```
评估结果 → 识别低质量回答
    │
    ├── 检索问题 → 调整检索策略 / 优化 embedding
    ├── 生成问题 → 优化 prompt / 换模型
    └── 知识问题 → 标记需补充的知识领域
```

---

## 7. 数据模型变更

### 7.1 新增表

```sql
-- 知识条目的语义分块
CREATE TABLE knowledge_chunks (
    id SERIAL PRIMARY KEY,
    knowledge_id INTEGER REFERENCES knowledge(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_chunks_knowledge ON knowledge_chunks(knowledge_id);
CREATE INDEX idx_chunks_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

-- 知识图谱实体（同步到 Neo4j）
CREATE TABLE kg_entities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,  -- Concept/Method/Material/Equipment/Metric/Person/Organization/Paper
    description TEXT,
    aliases TEXT[],                     -- 别名列表
    properties JSONB,                   -- 类型特有属性
    neo4j_id VARCHAR(50),              -- Neo4j 节点 ID
    knowledge_ids INTEGER[],           -- 关联的知识条目 ID
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_entities_name ON kg_entities(name);
CREATE INDEX idx_entities_type ON kg_entities(entity_type);

-- 知识图谱关系（同步到 Neo4j）
CREATE TABLE kg_relations (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES kg_entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(50) NOT NULL,  -- uses/produces/inhibits/measures/correlates/extends/contradicts/prerequisite
    properties JSONB,
    score FLOAT DEFAULT 0.5,
    neo4j_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 图谱社区
CREATE TABLE kg_communities (
    id SERIAL PRIMARY KEY,
    community_id INTEGER NOT NULL,
    summary TEXT,
    entity_ids INTEGER[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- RAG 评估记录
CREATE TABLE rag_evaluations (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    answer TEXT,
    context TEXT,
    faithfulness FLOAT,
    answer_relevancy FLOAT,
    context_precision FLOAT,
    context_recall FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 知识推送订阅
CREATE TABLE knowledge_subscriptions (
    id SERIAL PRIMARY KEY,
    member_id INTEGER REFERENCES members(id),
    topic VARCHAR(200),
    notify_on TEXT[],  -- ['new_knowledge', 'stale', 'contradiction', 'gap_filled']
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 7.2 修改表

```sql
-- knowledge 表新增字段
ALTER TABLE knowledge ADD COLUMN chunk_count INTEGER DEFAULT 0;
ALTER TABLE knowledge ADD COLUMN graph_synced_at TIMESTAMP;
ALTER TABLE knowledge ADD COLUMN quality_metrics JSONB;

-- knowledge_relations 表新增字段
ALTER TABLE knowledge_relations ADD COLUMN neo4j_id VARCHAR(50);
```

---

## 8. 实施阶段

### Phase 1: 混合检索（1 周）

**目标**：在现有向量检索基础上添加 BM25 关键词检索 + 简单重排序

**任务**：
- [ ] 安装 `rank-bm25` 依赖
- [ ] 实现 `BM25Service`（中文分词 + BM25 索引）
- [ ] 实现 `HybridRetriever`（向量 + BM25 并发 + 合并去重）
- [ ] 实现简单重排序（Cross-encoder）
- [ ] 修改 `KnowledgeQAService` 使用混合检索
- [ ] 单元测试

**验收标准**：
- 混合检索返回结果比纯向量检索更准确
- 检索延迟 < 2s（含重排序）

### Phase 2: 知识图谱（2 周）

**目标**：部署 Neo4j，构建属性知识图谱

**任务**：
- [ ] Docker 部署 Neo4j 社区版
- [ ] 实现 `KnowledgeGraphBuilder`（LLM 实体提取 + 关系提取）
- [ ] 实现 `Neo4jService`（CRUD + Cypher 查询）
- [ ] 实现知识入库时自动提取实体和关系
- [ ] 实现 `EntityResolver`（实体消歧 + 去重）
- [ ] 数据迁移：现有知识条目批量提取实体
- [ ] 单元测试

**验收标准**：
- 新知识入库时自动提取实体和关系
- Neo4j 中有完整的知识图谱
- 实体消歧正确率 > 80%

### Phase 3: GraphRAG 检索（1 周）

**目标**：基于知识图谱的引导检索

**任务**：
- [ ] 实现 `GraphRetriever`（实体引导检索 + 多跳推理）
- [ ] 实现社区检测（Leiden 算法）
- [ ] 实现社区摘要生成（LLM）
- [ ] 实现 `HybridRetriever` 集成图谱检索（三路并发）
- [ ] Agent 路由层：根据查询意图选择检索策略
- [ ] 单元测试

**验收标准**：
- 多跳推理查询能正确遍历图谱
- 社区摘要能概括课题组研究方向
- 三路并发检索延迟 < 3s

### Phase 4: Agent 集成（2 周）

**目标**：8 个知识工具 + 主动进化循环

**任务**：
- [ ] 实现 8 个 Agent 工具（search/save/explore/gaps/research/compare/summarize/suggest）
- [ ] Agent 系统提示词注入知识库上下文
- [ ] 实现主动进化循环（监听→分析→研究→推送→评估）
- [ ] 实现知识推送机制（企业微信 / 通知面板）
- [ ] 实现每日知识摘要（Celery 任务）
- [ ] 单元测试

**验收标准**：
- Agent 能通过 8 个工具与知识库深度交互
- 新知识入库后自动触发关联分析
- 知识推送正确送达

### Phase 5: Self-RAG（1 周）

**目标**：检索自检 + 上下文压缩

**任务**：
- [ ] 实现 `SelfRAGChecker`（LLM 检查检索结果相关性）
- [ ] 实现 `ContextCompressor`（去重 + 摘要压缩）
- [ ] 集成到 RAG 问答流程
- [ ] 单元测试

**验收标准**：
- 检索结果不相关时能自动重新检索
- 上下文压缩后 token 数减少 50%+

### Phase 6: RAG 评估（1 周）

**目标**：持续监控 RAG 质量

**任务**：
- [ ] 安装 `ragas` 依赖
- [ ] 实现 `RAGEvaluator`（faithfulness / relevancy / precision / recall）
- [ ] 实现异步评估（不阻塞用户请求）
- [ ] 实现评估结果 Dashboard（前端）
- [ ] 实现反馈闭环（低质量回答自动标记）
- [ ] 单元测试

**验收标准**：
- 每次 RAG 问答后自动评估
- Dashboard 能展示质量趋势
- 低质量回答被正确标记

### Phase 7: 多模态（2 周，可选）

**目标**：图片/表格/音频纳入知识图谱

**任务**：
- [ ] 图片 OCR + 描述提取
- [ ] 表格结构化提取
- [ ] 音频转文字 + 知识提取
- [ ] 多模态 embedding
- [ ] 单元测试

**验收标准**：
- 图片/表格/音频能被正确提取和检索

---

## 9. 技术依赖

| 组件 | 用途 | 新增/已有 |
|------|------|-----------|
| **Neo4j** | 知识图谱存储 | 新增 Docker 服务 |
| **neo4j** (Python) | Neo4j 官方驱动 | 新增 pip 包 |
| **rank-bm25** | BM25 关键词检索 | 新增 pip 包 |
| **sentence-transformers** | Cross-encoder 重排序 | 已有 |
| **ragas** | RAG 评估框架 | 新增 pip 包 |
| **jieba** | 中文分词（BM25 用） | 新增 pip 包 |

### 9.1 Docker Compose 新增服务

```yaml
# Neo4j 图数据库
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"  # Web UI
    - "7687:7687"  # Bolt 协议
  volumes:
    - ./data/neo4j:/data
  environment:
    - NEO4J_AUTH=neo4j/password
    - NEO4J_PLUGINS=["graph-data-science"]
```

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| Neo4j 内存占用大 | 云服务器 2G 内存不够 | 限制 Neo4j 内存（`-Xmx512m`），或只在本地部署 |
| Cross-encoder 推理慢 | 检索延迟增加 | 使用轻量模型（MiniLM），CPU 可跑 |
| LLM 实体提取不准 | 图谱质量差 | 多轮提取 + 人工校验 + 置信度阈值 |
| 三路并发复杂度高 | 维护困难 | 每路独立实现，通过接口组合 |
| 评估框架开销大 | 影响响应速度 | 异步评估，不阻塞用户请求 |

---

## 11. 成功标准

| 指标 | 当前基线 | 目标 |
|------|----------|------|
| RAG 回答准确率 | ~60%（主观估计） | >85% |
| 检索相关性 | ~70% | >90% |
| 多跳推理能力 | 不支持 | 支持 2-3 跳 |
| 知识空白发现 | 手动 | 自动 + 主动推送 |
| Agent 知识工具 | 2 个 | 8 个 |
| RAG 质量监控 | 无 | 实时 Dashboard |
