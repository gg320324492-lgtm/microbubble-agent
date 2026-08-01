"""RAG 查询结果缓存 (W99-RAG-1)

设计目标:
  - 减少 HybridRetriever.retrieve 重复 query 的 embedding + bm25 + graph + rerank 重复计算
  - 多租户隔离 (user_id + tenant_id 在 key 中)
  - best-effort silently 降级 (Redis 不可用不抛错, 沿用 embedding_service:243 模式)
  - 语义相似命中: embedding 余弦 ≥ threshold 视为命中

类 20.121: Redis 不可用 best-effort silently 降级
类 20.122: 缓存键必须含 user_id + tenant_id 隔离

数据契约 (cached value schema):
  {
    "results": List[dict],          # 检索结果
    "citations": List[dict],        # 引用 (备查)
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


def _exact_cache_key(query: str, user_id: Optional[int], tenant_id: Optional[int]) -> str:
    """精确查询缓存 key (sha256[:16])

    Key 格式: rag:q:{sha256(f"{user_id}:{tenant_id}:{query}")[:16]}
    类 20.122: 必须含 user_id+tenant_id 隔离多租户
    """
    raw = f"{user_id or 'anon'}:{tenant_id or 'default'}:{query}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{RAG_QUERY_CACHE_PREFIX}{digest}"


def _user_tenant_index_key(user_id: Optional[int], tenant_id: Optional[int]) -> str:
    """user+tenant 维度的查询索引 key (用于 find_similar 扫描)

    索引值: list of {exact_key, embedding, timestamp}
    简化: 存为 sorted set, score=timestamp, member=exact_key
    """
    raw = f"{user_id or 'anon'}:{tenant_id or 'default'}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{RAG_QUERY_CACHE_PREFIX}idx:{digest}"


class RAGQueryCache:
    """RAG 查询结果缓存

    用法:
        cache = RAGQueryCache()
        cached = await cache.get(query, user_id, tenant_id)
        if cached is None:
            # 实际检索
            result = await retriever.retrieve(query, ...)
            await cache.set(query, user_id, tenant_id, result)
        else:
            # 命中 - 用 cached["results"]
            result = cached["results"]
    """

    def __init__(self, ttl: int = RAG_QUERY_CACHE_TTL_SECONDS) -> None:
        self.ttl = ttl

    # ============================================================
    # 核心: 精确查询缓存 (最常用)
    # ============================================================

    async def get(
        self,
        query: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """精确查询缓存命中检查

        Args:
            query: 用户查询
            user_id: 归属用户 (None = 匿名)
            tenant_id: 归属租户 (None = default)

        Returns:
            命中: dict 含 results/citations/retrieval_method/score/timestamp 等
            未命中: None
            Redis 不可用: None (best-effort silently 降级)
        """
        if not RAG_QUERY_CACHE_ENABLED:
            return None
        if not query:
            return None

        key = _exact_cache_key(query, user_id, tenant_id)
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            raw = await redis.get(key)
        except Exception as e:
            logger.debug(f"[RAGQueryCache.get] redis lookup fail: {e}")
            return None

        if raw is None:
            return None

        try:
            value = json.loads(raw)
        except (TypeError, ValueError) as e:
            logger.debug(f"[RAGQueryCache.get] json parse fail: {e}")
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
        """写缓存 (best-effort)

        Args:
            query: 用户查询
            user_id: 归属用户
            tenant_id: 归属租户
            result: 实际检索结果 (dict 含 results/citations/retrieval_method/score/top_k)
            ttl: 自定义 TTL (None 走 self.ttl 默认值)

        Returns:
            True 写成功 / False 失败 (Redis 不可用 / 序列化失败) — 调用方不必检查
        """
        if not RAG_QUERY_CACHE_ENABLED:
            return False
        if not query:
            return False

        effective_ttl = ttl if ttl is not None else self.ttl
        key = _exact_cache_key(query, user_id, tenant_id)

        # 组装 value
        value: Dict[str, Any] = {
            "results": result.get("results", []),
            "citations": result.get("citations", []),
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
            logger.debug(f"[RAGQueryCache.set] json dumps fail: {e}")
            return False

        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            await redis.setex(key, effective_ttl, payload)
        except Exception as e:
            logger.debug(f"[RAGQueryCache.set] redis setex fail: {e}")
            return False

        # 写 user+tenant 索引 (用于语义相似扫描, 失败不影响主缓存)
        try:
            await self._index_for_similar(key, query, user_id, tenant_id, effective_ttl)
        except Exception as e:
            logger.debug(f"[RAGQueryCache.set] index write fail: {e}")

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
            logger.debug(f"[RAGQueryCache.invalidate] fail: {e}")
            return False

    # ============================================================
    # 扩展: 语义相似命中 (复用 query embedding 缓存)
    # ============================================================

    async def find_similar(
        self,
        query: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
        sim_threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """语义相似命中: 复用 query embedding 找近邻

        简化实现: 不存 query embedding 到缓存键 (避免双写), 而是:
        1. 复用 embedding_service.get_or_compute_query_embedding 算 query 向量
        2. 扫描 user+tenant 索引 (RAG_QUERY_CACHE_NN_PROBE 条)
        3. 算余弦相似度, ≥ threshold 视为命中

        性能: 索引扫描 ≤ 5 条候选, 算 5 次 cosine = 1ms 以内

        Args:
            query: 用户查询
            user_id: 归属用户
            tenant_id: 归属租户
            sim_threshold: 余弦相似度阈值 (None 走配置默认 0.95)

        Returns:
            命中: 与 get() 同样 dict
            未命中: None
        """
        if not RAG_QUERY_CACHE_ENABLED:
            return None
        if not query:
            return None

        threshold = sim_threshold if sim_threshold is not None else RAG_QUERY_CACHE_SIM_THRESHOLD
        idx_key = _user_tenant_index_key(user_id, tenant_id)

        # 1) 拿 query embedding
        try:
            from app.services.embedding_service import get_or_compute_query_embedding
            q_emb = await get_or_compute_query_embedding(query, has_query_prompt=True)
        except Exception as e:
            logger.debug(f"[RAGQueryCache.find_similar] embedding fail: {e}")
            return None
        if not q_emb:
            return None

        # 2) 拉索引候选
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            # zrevrange 0 N-1 (取最近 N 条)
            members = await redis.zrevrange(idx_key, 0, RAG_QUERY_CACHE_NN_PROBE - 1)
        except Exception as e:
            logger.debug(f"[RAGQueryCache.find_similar] zrevrange fail: {e}")
            return None

        if not members:
            return None

        # 3) 对每个候选算余弦, ≥ threshold 命中
        best_sim = -1.0
        best_value: Optional[Dict[str, Any]] = None
        for exact_key in members:
            try:
                raw = await redis.get(exact_key)
            except Exception as e:
                logger.debug(f"[RAGQueryCache.find_similar] get candidate fail: {e}")
                continue
            if not raw:
                continue
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                continue

            # value 应存了 query embedding (写 set 时一并写入)
            cand_emb = value.get("query_embedding")
            if not cand_emb:
                continue
            sim = self._cosine_similarity(q_emb, cand_emb)
            if sim >= threshold and sim > best_sim:
                best_sim = sim
                best_value = value

        if best_value is not None:
            # 标记语义命中
            best_value["cache_similarity"] = round(best_sim, 4)
        return best_value

    # ============================================================
    # 内部 helpers
    # ============================================================

    async def _index_for_similar(
        self,
        exact_key: str,
        query: str,
        user_id: Optional[int],
        tenant_id: Optional[int],
        ttl: int,
    ) -> None:
        """写 user+tenant 索引 + 同步存 query embedding (供 find_similar 算余弦)

        - zadd idx_key score=timestamp member=exact_key
        - 单独存 exact_key → query_embedding JSON (短 TTL)
        """
        from app.services.embedding_service import get_or_compute_query_embedding
        q_emb = await get_or_compute_query_embedding(query, has_query_prompt=True)
        if not q_emb:
            return
        idx_key = _user_tenant_index_key(user_id, tenant_id)
        emb_key = f"{exact_key}:emb"
        now = time.time()
        from app.core.redis import get_redis
        redis = await get_redis()
        # 写索引 (zadd)
        await redis.zadd(idx_key, {exact_key: now})
        # 写 query embedding (短 TTL, 与 value TTL 对齐)
        await redis.setex(emb_key, ttl, json.dumps(q_emb, ensure_ascii=False))
        # 顺便在主 value 里塞 query_embedding (供 find_similar 读)
        try:
            raw = await redis.get(exact_key)
            if raw:
                value = json.loads(raw)
                value["query_embedding"] = q_emb
                await redis.setex(exact_key, ttl, json.dumps(value, ensure_ascii=False, default=str))
        except Exception as e:
            logger.debug(f"[RAGQueryCache._index_for_similar] update value fail: {e}")

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """余弦相似度 (a, b 已 L2 normalize 的话, dot = cosine)"""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        return float(dot)


# ============================================================
# 全局工厂 (与 recall_observability 风格一致)
# ============================================================

_cache_instance: Optional[RAGQueryCache] = None


def get_rag_query_cache() -> RAGQueryCache:
    """获取 RAGQueryCache 单例"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RAGQueryCache()
    return _cache_instance


def reset_cache() -> None:
    """测试用: 重置单例"""
    global _cache_instance
    _cache_instance = None


__all__ = [
    "RAGQueryCache",
    "get_rag_query_cache",
    "reset_cache",
    "RAG_QUERY_CACHE_PREFIX",
    "RAG_QUERY_CACHE_TTL_SECONDS",
    "RAG_QUERY_CACHE_SIM_THRESHOLD",
    "RAG_QUERY_CACHE_ENABLED",
]
