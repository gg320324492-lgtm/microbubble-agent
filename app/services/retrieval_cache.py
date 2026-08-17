"""检索结果缓存 — qa-bench v3.1 D3 决策项实施 (Plan v1 Step 5 重构)

设计目标:
  - 减少 HybridRetriever.retrieve 重复 query 的 embedding + bm25 + graph + rerank 重复计算
  - 5min TTL (短, 与 RAGQueryCache 24h 长期缓存区分)
  - best-effort silently 降级 (Redis 不可用不抛错, 沿用 embedding_service:243 模式)
  - 多租户隔离 (user_id + tenant_id 在 key 中)

类 20.121: Redis 不可用 best-effort silently 降级
类 20.122: 缓存键必须含 user_id + tenant_id 隔离多租户

数据契约 (cached value schema, 与 BaseSemanticCache.set() 兼容):
  {
    "results": List[dict],          # 检索结果
    "query_embedding": List[float], # query embedding (供 find_similar 复用)
    "retrieval_method": str,        # "hybrid" / "vector_only" / ...
    "score": float,                 # top-1 分数
    "top_k": int,                   # 返回条数
    "timestamp": float,             # 写入时间
    "tenant_id": Optional[int],
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

from app.services.base_semantic_cache import BaseSemanticCache

logger = logging.getLogger("microbubble.retrieval_cache")


# ============================================================
# 配置 (env 兜底, 与派工 brief 对齐)
# ============================================================

# Plan §D3.D3.2: "Redis 缓存 5min TTL" — 5min = 300s
RETRIEVAL_CACHE_PREFIX: str = os.getenv("RETRIEVAL_CACHE_PREFIX", "rb:rc:")
RETRIEVAL_CACHE_TTL_SECONDS: int = int(os.getenv("RETRIEVAL_CACHE_TTL_SECONDS", "300"))
# 语义相似命中阈值 (默认 0.92, 与 W95 BGE m3 cosine 阈值对齐)
RETRIEVAL_CACHE_SIM_THRESHOLD: float = float(
    os.getenv("RETRIEVAL_CACHE_SIM_THRESHOLD", "0.92")
)
# 总开关 (默认开, 与派工 brief "B + C 方案" 一致)
RETRIEVAL_CACHE_ENABLED: bool = os.getenv("RETRIEVAL_CACHE_ENABLED", "1") != "0"


class RetrievalCache(BaseSemanticCache):
    """检索结果缓存 (qa-bench v3.1 D3) — 短期 5min 缓存

    关系: 继承 BaseSemanticCache, 5min TTL 是它与 RAGQueryCache 唯一区别.
    业务字段 (query_embedding/retrieval_method/score/top_k) 由调用方直接传在 result dict.
    """

    def __init__(self, ttl: int = RETRIEVAL_CACHE_TTL_SECONDS) -> None:
        super().__init__(
            prefix=RETRIEVAL_CACHE_PREFIX,
            ttl_seconds=ttl,
            sim_threshold=RETRIEVAL_CACHE_SIM_THRESHOLD,
            nn_probe=5,  # RetrievalCache 沿用 5 (与 RAGQueryCache 一致)
            name="RetrievalCache",
            enabled=RETRIEVAL_CACHE_ENABLED,
        )

    def value_schema_pre_check(self, result: dict) -> bool:
        """写前校验: results 必须非空"""
        if not result.get("results"):
            return False
        return True


# ============================================================
# 单例 + 工厂 (沿用 hybrid_retriever.py 1 处 import 路径)
# ============================================================

_cache_instance: RetrievalCache | None = None


def get_retrieval_cache() -> RetrievalCache:
    """获取 RetrievalCache 单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RetrievalCache()
    return _cache_instance


def reset_cache() -> None:
    """重置单例 (主要用于测试)"""
    global _cache_instance
    _cache_instance = None
