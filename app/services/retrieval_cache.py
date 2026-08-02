"""检索结果缓存 — qa-bench v3.1 D3 决策项实施 (2026-08-03)

设计目标 (plan §D3 B + C 方案):
  - 减少 HybridRetriever.retrieve 重复 query 的 embedding + bm25 + graph + rerank 重复计算
  - 5min TTL (短, 与 RAG_QUERY_CACHE_TTL_SECONDS=86400 区分; RAG-1 长期缓存 vs 测评短期缓存)
  - best-effort silently 降级 (Redis 不可用不抛错, 沿用 embedding_service:243 模式)
  - 多租户隔离 (user_id + tenant_id 在 key 中)

类 20.121: Redis 不可用 best-effort silently 降级
类 20.122: 缓存键必须含 user_id + tenant_id 隔离多租户
类 20.131: 派工起点必 fetch origin + merge-base 拦截漂移 (本任务实测守恒)

数据契约 (cached value schema):
  {
    "results": List[dict],          # 检索结果 (List[dict] w/ knowledge_id/score/chunk_id)
    "query_embedding": List[float], # query embedding (供 find_similar 复用)
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

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

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


def _exact_cache_key(query: str, user_id: Optional[int], tenant_id: Optional[int]) -> str:
    """精确查询缓存 key (sha256[:16])

    Key 格式: rb:rc:{sha256(f"{user_id}:{tenant_id}:{query}")[:16]}
    类 20.122: 必须含 user_id+tenant_id 隔离多租户
    """
    raw = f"{user_id or 'anon'}:{tenant_id or 'default'}:{query}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{RETRIEVAL_CACHE_PREFIX}{digest}"


def _user_tenant_index_key(user_id: Optional[int], tenant_id: Optional[int]) -> str:
    """user+tenant 维度的查询索引 key (用于 find_similar 扫描)"""
    raw = f"{user_id or 'anon'}:{tenant_id or 'default'}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{RETRIEVAL_CACHE_PREFIX}idx:{digest}"


class RetrievalCache:
    """检索结果缓存 (qa-bench v3.1 D3 实施)

    Plan §D3.D3.2 用法:
        cache = RetrievalCache()
        cached = await cache.get(query, user_id, tenant_id)
        if cached is None:
            # 实际检索
            result = await retriever.retrieve(query, ...)
            await cache.set(query, user_id, tenant_id, result)
        else:
            result = cached["results"]

    与 RAGQueryCache (W99-RAG-1) 区别:
        - TTL 5min (qa-bench/perf 短期) vs 86400s (RAG-1 长期)
        - 默认阈值 0.92 vs 0.95
        - 命名 rb:rc: vs rag:q:
        - 性能优化定位: 同一题 3 轮跑测复用, RAG-1 是跨天复用
    """

    def __init__(self, ttl: int = RETRIEVAL_CACHE_TTL_SECONDS) -> None:
        self.ttl = ttl

    # ============================================================
    # 异步路径 (主流程 / hybrid_retriever hook)
    # ============================================================

    async def get(
        self,
        query: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """精确查询缓存命中检查 (异步)

        Args:
            query: 用户查询
            user_id: 归属用户 (None = 匿名)
            tenant_id: 归属租户 (None = default)

        Returns:
            命中: dict 含 results/query_embedding/retrieval_method/score/timestamp 等
            未命中: None
            Redis 不可用: None (best-effort silently 降级)
        """
        if not RETRIEVAL_CACHE_ENABLED:
            return None
        if not query:
            return None

        key = _exact_cache_key(query, user_id, tenant_id)
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            raw = await redis.get(key)
        except Exception as e:
            logger.debug(f"[RetrievalCache.get] redis lookup fail: {e}")
            return None

        if raw is None:
            return None

        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            value = json.loads(raw)
        except (TypeError, ValueError) as e:
            logger.debug(f"[RetrievalCache.get] json parse fail: {e}")
            return None

        return value

    async def set(
        self,
        query: str,
        user_id: Optional[int],
        tenant_id: Optional[int],
        result: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """写缓存 (best-effort, 异步)

        Args:
            query: 用户查询
            user_id: 归属用户
            tenant_id: 归属租户
            result: 实际检索结果 (dict 含 results/query_embedding/retrieval_method/score/top_k)
            ttl: 自定义 TTL (None 走 self.ttl 默认值)

        Returns:
            True 写成功 / False 失败 (Redis 不可用 / 序列化失败) — 调用方不必检查
        """
        if not RETRIEVAL_CACHE_ENABLED:
            return False
        if not query:
            return False

        effective_ttl = ttl if ttl is not None else self.ttl
        key = _exact_cache_key(query, user_id, tenant_id)

        # 组装 value
        value: Dict[str, Any] = {
            "results": result.get("results", []),
            "query_embedding": result.get("query_embedding", []),
            "retrieval_method": result.get("retrieval_method", "hybrid"),
            "score": result.get("score", 0.0),
            "top_k": result.get("top_k", 0),
            "timestamp": time.time(),
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            logger.debug(f"[RetrievalCache.set] json dumps fail: {e}")
            return False

        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            await redis.setex(key, effective_ttl, payload)
        except Exception as e:
            logger.debug(f"[RetrievalCache.set] redis setex fail: {e}")
            return False

        # 写 user+tenant 索引 (用于语义相似扫描, 失败不影响主缓存)
        try:
            await self._index_for_similar(key, value.get("query_embedding", []), user_id, tenant_id, effective_ttl)
        except Exception as e:
            logger.debug(f"[RetrievalCache.set] index write fail: {e}")

        return True

    async def invalidate(
        self,
        query: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> bool:
        """精确失效某个 query 的缓存

        Returns:
            True 删成功 / False 失败
        """
        if not query:
            return False
        key = _exact_cache_key(query, user_id, tenant_id)
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            await redis.delete(key)
            return True
        except Exception as e:
            logger.debug(f"[RetrievalCache.invalidate] fail: {e}")
            return False

    # ============================================================
    # 内部 helpers
    # ============================================================

    async def _index_for_similar(
        self,
        exact_key: str,
        query_embedding: List[float],
        user_id: Optional[int],
        tenant_id: Optional[int],
        ttl: int,
    ) -> None:
        """写 user+tenant 索引 (用于 find_similar)

        - zadd idx_key score=timestamp member=exact_key
        - query_embedding 已存在主 value, 无需重写
        """
        if not query_embedding:
            return
        idx_key = _user_tenant_index_key(user_id, tenant_id)
        now = time.time()
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            await redis.zadd(idx_key, {exact_key: now})
        except Exception as e:
            logger.debug(f"[RetrievalCache._index_for_similar] zadd fail: {e}")


# ============================================================
# 全局工厂
# ============================================================

_cache_instance: Optional[RetrievalCache] = None


def get_retrieval_cache() -> RetrievalCache:
    """获取 RetrievalCache 单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RetrievalCache()
    return _cache_instance


def reset_cache() -> None:
    """测试用: 重置单例"""
    global _cache_instance
    _cache_instance = None


__all__ = [
    "RetrievalCache",
    "get_retrieval_cache",
    "reset_cache",
    "RETRIEVAL_CACHE_PREFIX",
    "RETRIEVAL_CACHE_TTL_SECONDS",
    "RETRIEVAL_CACHE_SIM_THRESHOLD",
    "RETRIEVAL_CACHE_ENABLED",
]
