# RAG 全面升级调研与方案 (2026-11-04)

> 触发: 主指挥「跑一下完整的测试，看看有能升级的地方就升级一下，再参考社区成熟的 RAG 项目做一下全面的升级」。
> 本文 = 社区对标结论 + 现状盘点 + 分级升级清单。P0 项本次已落地，P1/P2 待拍板。

## 一、现状盘点：我们已经站在社区 2026 的主流配方上

2026 年社区对「生产级 RAG 该长什么样」已经收敛成同一个配方：
**hybrid 稠密+BM25 双路召回 → cross-encoder 重排 → 上下文丰富的切块**，
真正的分水岭已从「架构」转移到 **评测、可观测性、成本控制**。

对照我们（W97 十 PR 大改造 + 后续迭代）：

| 社区主流配方 | 我们的现状 | 结论 |
|---|---|---|
| hybrid 稠密+BM25 | HybridRetriever **5 路召回**（向量/词法 tsvector/meeting_chunks/page_transcripts/实体图）+ pg_trgm | ✅ 已超配 |
| cross-encoder 重排 | bge-reranker-v2-m3 | ✅ 且社区实测支持保留（见下） |
| 上下文切块 | parent-child chunking + `[PAGE:N]` 页级结构 + page_transcripts | ✅ 已有 |
| 查询改写 | query_rewriter（PR9） | ✅ 已有 |
| 迟分块 late chunking | late_chunking_service（W-N-B） | ✅ 已有（社区 2024-2025 才流行） |
| Self-RAG / agentic RAG | self_rag 重引入（W100） | ✅ 已有 |
| 自动评测 | RAGEvaluator（真召回率）+ SearchLog | ⚠️ 有召回率，缺 LLM-judge 三件套（见 P1） |
| 可观测性 | grafana 7 面板 + 按路耗时分解 | ✅ 已有 |
| 知识图谱 | 实体图 + entity_link_recall + 假设引擎 | ✅ 已有，且社区结论支持我们的用法（见下） |

**结论：不建议再引入新框架**（RAGFlow/LightRAG/ Kotaemon 等换架子 = 重写我们已验证的五路召回与全部业务耦合，收益为负）。升级空间在**评测补全、检索质量微调、模型换代**三件事上。

## 二、社区证据要点（2026 实测数据）

1. **重排器：保留 bge-reranker-v2-m3，不换 Qwen3**。
   独立实测（162 题，pgvector 检索 20 候选重排，jacar.es 2026-11）：
   nDCG@10 = BGE 0.847 vs Qwen3-Reranker-0.6B 0.853（差 0.007，置信区间跨 0，逐题 66:65）；
   但延迟 BGE 3.04s vs Qwen3 9.77s（**3.2 倍**），内存 2.99GiB vs 4.96GiB（4GiB 容器直接 OOM）。
   ⇒ 我们的现役选择就是数据上的最优解。
2. **GraphRAG 全量社区摘要：明确不做**。
   两年期实践回顾（zhguichen.github.io）：对简单事实检索是负资产（索引成本 8 倍、+0.12 F1）；
   结构定价论文（arXiv 2609.18099）给出「按查询 relational 程度动态决定是否走图」的框架。
   ⇒ 我们的实体图作为**可选召回臂**（entity_link_recall）恰好是社区推荐的正确形态，不升级成 GraphRAG 主干。
3. **hnsw 静默截断陷阱**（jacar.es）：`LIMIT 50` 时 pgvector 默认 `hnsw.ef_search=40` 会静默只返回 40 行。
   ⇒ 实测我们的库：**向量列完全没有 ANN 索引**（12,082 chunks 精确扫描）——召回率 100%、无截断风险，
   且类 20.163 的结论（真实退化要 10w+ 行）依然成立。HNSW 归入 P2（数据量触发），触发时用现成的
   `scripts/bench_hnsw_params.py` 选参。
4. **框架层风险提示**：Anthropic Python SDK 2.0 两周前发布，已打断 LlamaIndex/Haystack/LightRAG 的集成——
   本次依赖 pass 已将 `anthropic>=1.13,<2`、`llama-index>=0.13.6,<0.14` 帽住，升级窗口由我们主动选。

## 三、分级升级清单

### P0（本次已落地，测试门禁中）
- **依赖升级 pass**：requirements.txt 追加「冻结 + 帽子」块——
  ML/声纹栈全钉（torch/transformers/sentence-transformers/modelscope/funasr/faster-whisper/ctranslate2，
  防嵌入数值漂移导致声纹链路静默失效）；危险大版本全部帽住（anthropic<2/openai<2/hf-hub<2/llama-index<0.14/langfuse<3）；
  Web 层放行升级（fastapi<0.164/sqlalchemy<2.1/pydantic<3/uvicorn<1/anyio<5/httpx<1/alembic<1.22/edge-tts<8/pgvector<0.7）。
  `pip install --dry-run` 全树解析通过（类 20.224：禁 --quiet）。镜像重建 + 全量测试门禁中。
- **LLM 栈换代**：小琪助手全链路 + 视觉/OCR 已切 MiniMax-M3.1-Flash（见 .env 注记与当日会话记录）。

### P1（本周可做，中风险，收益直接）
- **R1 · LLM-judge 评测三件套**：给 RAGEvaluator 加 RAGAS 三指标——
  faithfulness（忠实度：答案是否被检索段支撑）、answer_relevancy（答案与问题相关度）、
  context_precision（检索段排位质量）。judge 用本机 M3.1-Flash（零外部成本），
  固定 50 题评测集（从 SearchLog 真实查询采样）。**这是后续一切 RAG 改动的准入门槛**——
  没有它，任何「升级」都说不清变好还是变坏。
- **R2 · 语义缓存**：Redis 语义缓存（查询 embedding 余弦 ≥0.97 直接复用上次检索结果），
  真实查询重复率高（周会术语固定），命中即省整个五路召回+重排（~1.5-3s）。
  风险低：缓存只作用于检索层，答案仍走完整生成。

### P2（数据量/评测触发再做）
- **R3 · HNSW 索引**：触发条件 = knowledge_chunks > 10 万行（当前 1.2 万，精确扫描 ~30ms 可接受且召回 100%）。
  触发时用 `scripts/bench_hnsw_params.py` 实测选参（W-N-A 时代工具还在）。
- **R4 · 嵌入模型换代**（Qwen3-Embedding-0.6B → 4B/8B）：收益存在但代价 = 全量 5 万+ chunk 重嵌 +
  声纹锚池全量重建（同空间约束），必须先有 R1 的评测基线才允许动手。
- **R5 · HyDE 召回臂**：假设文档检索作为可选第六臂，feature flag + RAGEvaluator 门禁。
- **R6 · Contextual retrieval**（Anthropic 式 chunk 上下文增强）：每 chunk 一次 LLM 调用，成本高；
  只对高频检索命中的 top 文档做，等 R1 数据说话。

### 明确不做（社区证据）
- GraphRAG 全量社区摘要（索引成本 8 倍换 +0.12 F1）；
- ColBERT late-interaction（pgvector 不支持，需引入新索引栈）；
- 换 RAG 框架（RAGFlow/LightRAG 等）——我们的五路召回+业务耦合重写为负收益。

## 四、依赖升级台账（本次 pass）

- 冻结（==，防漂移）：torch==2.14.1 / transformers==5.19.0 / sentence-transformers==5.6.0 /
  modelscope==1.40.2 / funasr==1.4.16 / faster-whisper==1.2.1 / ctranslate2==4.8.2 /
  celery==5.3.6 / asyncpg==0.29.0 / redis==5.0.1 / datasets==5.0.1（原有）/
  numpy==1.26.2 / pyarrow==25.0.1（原有，ABI 对）
- 帽住（防 breaking major）：anthropic<2 / openai<2 / huggingface-hub<2 / llama-index<0.14 / langfuse<3
- 放行升级（测试门禁内浮动）：fastapi<0.164 / sqlalchemy<2.1 / pydantic<3 / uvicorn<1 /
  anyio<5 / httpx<1 / alembic<1.22 / edge-tts<8 / pgvector<0.7
- CVE 审计：pip-audit 结果见当日会话记录；image-scan workflow 会随 requirements.txt 的 push 自动复核。

## 来源
- jacar.es《RAG reranking with llama.cpp and pgvector, measured》(2026-11)
- zhguichen.github.io《GraphRAG Two Years Later》
- arXiv 2609.18099《When Is Graph Structure Worth Its Cost?》
- vdf.ai《Best RAG Frameworks (2026)》; Lin-Guanguo/llm-memory-research production-stacks
