# W98 Hybrid RAG Stack 收口 (CLAUDE.md 镜像, 2026-07-31)

> **来源**: RAG-FW-01..13 交付 + MERGE-RAG-FW-BASE/ALL 合并 + RAG-FW-13 grand closure
> **位置**: 此文件镜像 CLAUDE.md 锚点段 (E43/E44 铁律: **严禁**改 CLAUDE.md 主体, 用 mirror 文件)
> **生效范围**: 锚点范式守卫、0 production code 改动铁律、框架融合方案 v2.0
> **主仓路径**: `E:\microbubble-agent`; 镜像同步来源: `docs/rag/HYBRID-RAG-STACK.md`

---

## §1 Hybrid RAG Stack 收口 (W98 第 1 批, 2026-07-31)

**Hybrid RAG Stack — 框架融合方案 v2.0**: 8 项框架能力 (LangChain + LlamaIndex + LangFuse) 全线交付, 全部 On by default (激进模式). 当前 main HEAD = `8f3012d08` (MERGE-RAG-FW-ALL +9 收口). **0 production code 改动铁律**: 层 1 手写层 7 服务 0 修改 (`git diff main~7..main -- app/services/ | grep -cE "^[+-]def"` = 0), 层 2 框架层全部为 `app/rag/` 新增文件. alembic 1 head `['091_add_kg_entity']` 守恒 (10 分支 0 新迁移, PGVectorStore perform_setup=False 只读复用). pytest baseline 3272 collected ≥ 3230 守恒 (rag_framework 74 mock 测试, CI 无需框架依赖). 派工前提类 20 实战 21 (RAG-FW-13 据实上报: RAG-FW-11/12 分支 0 commit — e2e-gate 并入 RAG-FW-02 5 场景, rag-framework-ci.yml 未落地, 不擅自扩也不擅自缩). 详见 `memory/w98-rag-fw-grand-closure-2026-07-31.md` (本批沉淀) + `docs/rag/HYBRID-RAG-STACK.md`.

## §2 4 层架构

- **层 1: 手写层** (7 服务, 0 修改) — knowledge_qa_service / hybrid_retriever / bm25_service / embedding_service / chunking_service / file_parser_service / knowledge_graph_service
- **层 2: 框架层** (`app/rag/` 8 文件, LangChain + LlamaIndex + LangFuse) — 8 项能力
- **层 3: 回退门控** (`framework_gate` 装饰器) — 开关关闭 / ImportError / 运行时异常 3 级自动回退; fallback_fn=None 时不擅自降级
- **层 4: 基础设施** — PostgreSQL + pgvector HNSW + SQLAlchemy async + langfuse 服务 (docker-compose 端口 3000, trace 落自有 PostgreSQL)

## §3 8 项能力全览

| # | 能力 | 文件 | 框架 | 开关 | 回退到 |
|---|------|------|------|------|--------|
| 1 | LangFuse Tracing | lc_tracing.py | LangFuse | LC_TRACING_ENABLED | recall_observability 日志 |
| 2 | Query 翻译 | query_translator.py | LangChain | QUERY_TRANSLATION_ENABLED | 原 query 直传 |
| 3 | Multi-hop | multi_hop_engine.py | LlamaIndex | MULTI_HOP_ENABLED | knowledge_qa_service 单轮 |
| 4 | Agent Router | agent_retriever.py | LangChain | AGENT_ROUTER_ENABLED | hybrid_retriever 4 路 |
| 5 | Dense/Sparse | dense_sparse_routing.py | LlamaIndex | DENSE_SPARSE_ROUTING_ENABLED | hybrid_retriever 4 路 |
| 6 | Semantic Chunker | semantic_chunker.py | LangChain | SEMANTIC_CHUNKER_ENABLED | chunking_service 规则 |
| 7 | 跨模态解析 | multimodal_parser.py | LlamaIndex | MULTIMODAL_PARSER_ENABLED | file_parser_service |
| 8 | 回退门控 | gate.py | 自研 | RAG_FRAMEWORK_ENABLED | 各能力回退路径 |

## §4 铁律 (RAG-FW 系列沉淀)

1. **只读复用 pgvector** — PGVectorStore perform_setup=False, 不建表/不建索引/不 UPSERT, 复用 knowledge.embedding HNSW, 0 新 alembic
2. **0 改老文件** — 层 1 手写层 7 服务 0 修改, 框架层仅 `app/rag/` 新增
3. **中文句读显式注入** — LangChain SemanticChunker 默认只覆盖英文标点, 必须注入 `(?<=[。！？!?；;])\s*` 否则中文语义分块失效
4. **fallback_fn=None 不擅自降级** — 调用方自行决定, 不静默返回坏结果
5. **依赖 On by default** — langchain>=0.3.0 / llama-index>=0.12.0 / langfuse>=2.0.0 已入 requirements.txt (pydantic-settings>=2.4.0 + httpx>=0.15.4 连带放宽)
6. **收口文档必真验证分支 commit** — 类 20 实战 21: RAG-FW-11/12 分支 0 commit 据实上报, 不照 brief 假设填时间线
7. **测试全 mock 可 CI 跑** — conftest patch.dict('sys.modules') 集中 mock, rag_integration mark 预留可选集成通道

## §5 锚点守恒

- W97 477 → W98 +9: MERGE-RAG-FW-BASE `f4a833f67`(+0) `67317eabc`(+1) `2c1df3de4`(+2) + MERGE-RAG-FW-ALL `e8a02c9e8`(+3) `30941990c`(+4) `b132a83ff`(+5) `55ff32404`(+6) `2ed8dae9f`(+7) `b017a6c8c`(+8) `8f3012d08`(+9)
- RAG-FW-13 本任务: docs/memory 范畴, `[RAG-FW-13 W98 +0]` 锚点守恒 0 增量
- alembic 1 head `091_add_kg_entity` 守恒 (10 分支 0 新迁移)
