"""app/rag/config.py — Hybrid RAG Stack 配置入口

8 项框架能力开关，全部 On by default (激进模式)。
每个开关独立可控，关闭时自动回退到手写层。
"""

import os

# ===== 全局开关 =====
# env RAG_FRAMEWORK_ENABLED=1/0, 默认 1 (激进: On by default)
RAG_FRAMEWORK_ENABLED: bool = (
    os.getenv("RAG_FRAMEWORK_ENABLED", "1").lower() in ("1", "true", "yes")
)

# ===== 各项能力独立开关 =====
# Tracing — LangFuse (开源替代 LangSmith)
LC_TRACING_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("LC_TRACING_ENABLED", "1").lower() in ("1", "true", "yes")
)

# Query 翻译/重写/扩展 — LangChain MultiQuery + HyDE
QUERY_TRANSLATION_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("QUERY_TRANSLATION_ENABLED", "1").lower() in ("1", "true", "yes")
)

# Multi-hop — LlamaIndex SubQuestionQueryEngine
MULTI_HOP_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("MULTI_HOP_ENABLED", "1").lower() in ("1", "true", "yes")
)

# Agent Router — LangChain AgentExecutor 动态检索选择
AGENT_ROUTER_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("AGENT_ROUTER_ENABLED", "1").lower() in ("1", "true", "yes")
)

# Dense/Sparse 一层切换 — LlamaIndex VectorStoreIndex + BM25
DENSE_SPARSE_ROUTING_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("DENSE_SPARSE_ROUTING_ENABLED", "1").lower() in ("1", "true", "yes")
)

# Semantic Chunker — LangChain SemanticChunker
SEMANTIC_CHUNKER_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("SEMANTIC_CHUNKER_ENABLED", "1").lower() in ("1", "true", "yes")
)

# 跨模态文档解析 — LlamaIndex Readers
MULTIMODAL_PARSER_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("MULTIMODAL_PARSER_ENABLED", "1").lower() in ("1", "true", "yes")
)

# ===== W99-RAG-1 Query Cache 结果层 =====
# 仅追加, 不改既有 8 项配置
# 1) RAG_QUERY_CACHE_ENABLED — 总开关 (默认 True)
# 2) RAG_QUERY_CACHE_TTL — 缓存 TTL 秒 (默认 86400 = 24h)
# 3) RAG_QUERY_CACHE_SIM_THRESHOLD — 语义相似命中 cosine 阈值 (默认 0.95)
# 4) RAG_QUERY_CACHE_PREFIX — 缓存键前缀 (默认 rag:q:)
# 5) RAG_QUERY_CACHE_NN_PROBE — 语义相似扫描深度 (默认 5)
# 详见 app/services/rag_query_cache.py 类 20.121/122 铁律
RAG_QUERY_CACHE_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("RAG_QUERY_CACHE_ENABLED", "1").lower() in ("1", "true", "yes")
)
RAG_QUERY_CACHE_TTL: int = int(os.getenv("RAG_QUERY_CACHE_TTL", "86400"))
RAG_QUERY_CACHE_SIM_THRESHOLD: float = float(
    os.getenv("RAG_QUERY_CACHE_SIM_THRESHOLD", "0.95")
)
RAG_QUERY_CACHE_PREFIX: str = os.getenv("RAG_QUERY_CACHE_PREFIX", "rag:q:")
RAG_QUERY_CACHE_NN_PROBE: int = int(os.getenv("RAG_QUERY_CACHE_NN_PROBE", "5"))

# ===== W99-RAG-2 Citation 段落级溯源 =====
# 仅追加, 不改既有 13 项配置 (8 框架 + 5 RAG-1 cache)
# 1) CITATION_ENABLED — 总开关 (默认 True)
# 2) CITATION_MAX_PER_RESULT — 每个 result 最多返回 citation 数 (默认 3)
# 详见 app/services/citation_extractor.py 类 20.124 铁律
CITATION_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("CITATION_ENABLED", "1").lower() in ("1", "true", "yes")
)
CITATION_MAX_PER_RESULT: int = int(os.getenv("CITATION_MAX_PER_RESULT", "3"))

# ===== W100-RAG-3 Query Intent 分类 =====
# 仅追加, 不改既有 15 项配置 (8 框架 + 5 RAG-1 + 2 RAG-2)
# 1) INTENT_CLASSIFIER_ENABLED — 总开关 (默认 True)
# 2) INTENT_FALLBACK — LLM 失败回退 intent (默认 factual)
# 详见 app/rag/intent_classifier.py 类 20.125 铁律
# + app/rag/intent_router.py 类 20.126 铁律 (weights 配置化)
INTENT_CLASSIFIER_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("INTENT_CLASSIFIER_ENABLED", "1").lower() in ("1", "true", "yes")
)
INTENT_FALLBACK: str = os.getenv("INTENT_FALLBACK", "factual")

# ===== W100-RAG-4 Reranker 多 backend =====
# 仅追加, 不改既有 17 项配置 (8 框架 + 5 RAG-1 + 2 RAG-2 + 2 RAG-3)
# 1) RERANKER_BACKEND — backend 选择 (cross_encoder / bge_v2 / cohere)
# 2) RERANKER_MODEL — 模型名, 默认沿用 W75 BGE m3
# 3) RERANKER_API_KEY — Cohere API key (cross_encoder / bge_v2 不需要)
# 4) RERANKER_ACCEPTANCE_GATE — 92% acceptance gate (类 20.127 失败必 raise)
# 详见 app/services/reranker_v2.py 类 20.127/128 铁律
# + app/services/reranker_service.py 既有 W75 接口 (cross_encoder 默认 backend)
RERANKER_BACKEND: str = os.getenv("RERANKER_BACKEND", "cross_encoder")
RERANKER_MODEL: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_API_KEY: str = os.getenv("RERANKER_API_KEY", "")
RERANKER_ACCEPTANCE_GATE: float = float(
    os.getenv("RERANKER_ACCEPTANCE_GATE", "0.92")
)

# ===== W100-RAG-5 Multimodal Retriever 第 5 路 =====
# OCR 已完成的图片通过 ocr_text 双塔召回；candidate 向量不持久化。
MULTIMODAL_RETRIEVER_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("MULTIMODAL_RETRIEVER_ENABLED", "1").lower()
    in ("1", "true", "yes")
)
MULTIMODAL_RETRIEVER_WEIGHT: float = float(
    os.getenv("MULTIMODAL_RETRIEVER_WEIGHT", "0.15")
)

# ===== W100-RAG-6 Temporal Retriever 时间衰减 =====
# 仅追加, 不改既有 19 项配置 (8 框架 + 5 RAG-1 + 2 RAG-2 + 2 RAG-3 + 4 RAG-4 + 2 RAG-5)
# 1) TEMPORAL_DECAY_ENABLED — 总开关 (默认 True)
# 2) TEMPORAL_BOOST_YEARS — 近 N 年内加权 (默认 2)
# 3) TEMPORAL_BOOST_FACTOR — 近 N 年加权幅度 (默认 +0.2)
# 4) TEMPORAL_DECAY_YEARS — 超过 N 年减权 (默认 5)
# 5) TEMPORAL_DECAY_FACTOR — 老资料减权幅度 (默认 0.3)
# 详见 app/services/temporal_retriever.py 类 20.131/132 铁律
TEMPORAL_DECAY_ENABLED: bool = (
    RAG_FRAMEWORK_ENABLED
    and os.getenv("TEMPORAL_DECAY_ENABLED", "1").lower() in ("1", "true", "yes")
)
TEMPORAL_BOOST_YEARS: int = int(os.getenv("TEMPORAL_BOOST_YEARS", "2"))
TEMPORAL_BOOST_FACTOR: float = float(os.getenv("TEMPORAL_BOOST_FACTOR", "0.2"))
TEMPORAL_DECAY_YEARS: int = int(os.getenv("TEMPORAL_DECAY_YEARS", "5"))
TEMPORAL_DECAY_FACTOR: float = float(os.getenv("TEMPORAL_DECAY_FACTOR", "0.3"))

# ===== 框架配置 =====
# LangFuse 自托管服务地址
LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_TRACE_ENABLED: bool = (
    LC_TRACING_ENABLED
    and bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)
)

# LlamaIndex PGVector 配置 (复用现有表, 不建新表)
LLAMAINDEX_PGVECTOR_SCHEMA: str = os.getenv("LLAMAINDEX_PGVECTOR_SCHEMA", "public")
LLAMAINDEX_EMBEDDING_DIM: int = int(os.getenv("LLAMAINDEX_EMBEDDING_DIM", "1024"))

# Agent Router 限制
AGENT_ROUTER_MAX_CALLS_PER_REQUEST: int = int(os.getenv("AGENT_ROUTER_MAX_CALLS_PER_REQUEST", "1"))
