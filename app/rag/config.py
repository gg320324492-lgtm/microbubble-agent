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
