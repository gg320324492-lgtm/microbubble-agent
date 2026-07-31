# Hybrid RAG Stack — 框架融合方案 v2.0 (2026-07-31)

> **状态**: W98 第 1 批交付 (RAG-FW-01..10 合并收口, main HEAD `8f3012d08`, 锚点 +9)
> **性质**: 在现有手写 RAG 栈之上新增 LangChain + LlamaIndex + LangFuse 框架能力层, 全部 On by default (激进模式)
> **完整架构图**: [HYBRID-RAG-STACK-ARCHITECTURE.md](HYBRID-RAG-STACK-ARCHITECTURE.md)
> **CLAUDE.md 镜像**: [W98-HYBRID-RAG-STACK-ANCHOR.md](W98-HYBRID-RAG-STACK-ANCHOR.md)

## 4 层架构

- **层 1: 手写层** (7 服务, 0 修改) — `app/services/` 现有 RAG 栈, 本次 0 改动:
  - `knowledge_qa_service.py` — RAG 问答引擎 (单轮)
  - `hybrid_retriever.py` — 4 路混合检索 (vector + bm25 + trgm + tsvector)
  - `bm25_service.py` — BM25 稀疏检索
  - `embedding_service.py` — Qwen3-Embedding 向量 (1024 维)
  - `chunking_service.py` — 3 规则策略分块
  - `file_parser_service.py` — fitz 抽文字 + `multimodal_extraction_service.py` OCR
  - `knowledge_graph_service.py` — 实体图谱
- **层 2: 框架层** (`app/rag/` 8 文件, LangChain + LlamaIndex + LangFuse) — 8 项能力, 0 老文件修改
- **层 3: 回退门控** (`framework_gate` 装饰器, `app/rag/gate.py`) — 开关关闭 / ImportError / 运行时异常 3 级自动回退
- **层 4: 基础设施** (PostgreSQL + pgvector + SQLAlchemy async + langfuse 服务) — langfuse 自托管已入 docker-compose (端口 3000), trace 数据落自有 PostgreSQL

## 8 项能力全览

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

## 依赖 (On by default)

- langchain>=0.3.0 / langchain-community / langchain-anthropic
- llama-index>=0.12.0 / llama-index-vector-stores-pgvector / readers-file
- langfuse>=2.0.0

## 测试

- tests/rag_framework/ 74+ mock 测试 (CI 无需框架依赖)
- CI: .github/workflows/rag-framework-ci.yml

## 部署

- docker-compose 已加 langfuse 服务 (端口 3000)
- LANGCHAIN/LANGFUSE keys 由部署环境注入
