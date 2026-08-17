"""RAG 查询结果缓存 (W99-RAG-1) — 继承 BaseSemanticCache (Plan v1 Step 5)

设计目标:
  - 减少 HybridRetriever.retrieve 重复 query 的 embedding + bm25 + graph + rerank 重复计算
  - 多租户隔离 (user_id + tenant_id 在 key 中)
  - best-effort silently 降级 (Redis 不可用不抛错, 沿用 embedding_service:243 模式)
  - 语义相似命中: embedding 余弦 ≥ threshold 视为命中

类 20.121: Redis 不可用 best-effort silently 降级
类 20.122: 缓存键必须含 user_id + tenant_id 隔离

数据契约 (cached value schema, 与 BaseSemanticCache.set() 兼容):
  {
    "results": List[dict],          # 检索结果 (hybrid_retriever.py 传)
    "citations": List[dict],        # 引用 (W99-RAG-2 占位)
    "retrieval_method": str,        # "hybrid" / "vector_only" / ...
    "score": float,                 # top-1 分数
    "top_k": int,                   # 返回条数
    "timestamp": float,             # 写入时间
    "tenant_id": Optional[int],     # 冗余便于审计
    "user_id": Optional[int],
  }

严禁:
  - 修改 hybrid_retriever.py 既有 10 instance + 5 module-level function 签名 (件 4 门控 B)
  - 修改 knowledge_service.py 任何 def (件 4 门控 A)
  - 抛 Redis 异常 (best-effort silently 降级)
"""
from __future__ import annotations

import logging
import os

from app.core.redis import get_redis  # 2026-08-17 #Plan v2 #6: module-level 让 test patch 可用
from app.services.base_semantic_cache import BaseSemanticCache

logger = logging.getLogger("microbubble.rag_query_cache")


# ============================================================
# 配置 (env 兜底, 默认值与派工 brief 对齐)
# ============================================================

RAG_QUERY_CACHE_PREFIX: str = os.getenv("RAG_QUERY_CACHE_PREFIX", "rag:q:")
RAG_QUERY_CACHE_TTL_SECONDS: int = int(os.getenv("RAG_QUERY_CACHE_TTL", "86400"))
RAG_QUERY_CACHE_SIM_THRESHOLD: float = float(
    os.getenv("RAG_QUERY_CACHE_SIM_THRESHOLD", "0.95")
)
RAG_QUERY_CACHE_ENABLED: bool = os.getenv("RAG_QUERY_CACHE_ENABLED", "1") != "0"
# 语义相似扫描深度 (近邻候选数)
RAG_QUERY_CACHE_NN_PROBE: int = int(os.getenv("RAG_QUERY_CACHE_NN_PROBE", "5"))


class RAGQueryCache(BaseSemanticCache):
    """RAG 查询结果缓存 (W99-RAG-1) — 长期 24h 缓存

    关系: 继承 BaseSemanticCache, 配置常量走 env 注入.
    业务字段 (citations/retrieval_method/score/top_k) 由 hybrid_retriever.py 直接传
    在 result dict, 基类 set() 透传全部字段.
    """

    def __init__(self, ttl: int = RAG_QUERY_CACHE_TTL_SECONDS) -> None:
        super().__init__(
            prefix=RAG_QUERY_CACHE_PREFIX,
            ttl_seconds=ttl,
            sim_threshold=RAG_QUERY_CACHE_SIM_THRESHOLD,
            nn_probe=RAG_QUERY_CACHE_NN_PROBE,
            name="RAGQueryCache",
            enabled=RAG_QUERY_CACHE_ENABLED,
        )

    def value_schema_pre_check(self, result: dict) -> bool:
        """写前校验: results 必须非空列表 (业务合同)"""
        if not result.get("results"):
            return False
        return True


# ============================================================
# 单例 + 工厂 (沿用 hybrid_retriever.py 3 处 import 路径)
# ============================================================

_cache_instance: RAGQueryCache | None = None


def get_rag_query_cache() -> RAGQueryCache:
    """获取 RAGQueryCache 单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RAGQueryCache()
    return _cache_instance


def reset_cache() -> None:
    """重置单例 (主要用于测试)"""
    global _cache_instance
    _cache_instance = None


# ============================================================
# 向后兼容 alias (2026-08-17 #Plan v2 #4 e2e 修跑通)
# ============================================================
# Plan v1 Step 5 把 _exact_cache_key / _user_tenant_index_key 移到 BaseSemanticCache
# 作为 instance methods. 但 tests/rag/test_query_cache.py + test_retrieval_cache.py
# 等单测还在用 module-level import (旧 API). 加 module-level 包装保持向后兼容,
# 实现委托给 RAGQueryCache 单例. 0 业务代码改动, 纯 import compatibility shim.

def _exact_cache_key(query: str, user_id, tenant_id) -> str:
    """向后兼容: 委托给 RAGQueryCache._exact_cache_key (BaseSemanticCache 实例方法)"""
    return get_rag_query_cache()._exact_cache_key(query, user_id, tenant_id)


def _user_tenant_index_key(user_id, tenant_id) -> str:
    """向后兼容: 委托给 RAGQueryCache._user_tenant_index_key"""
    return get_rag_query_cache()._user_tenant_index_key(user_id, tenant_id)
