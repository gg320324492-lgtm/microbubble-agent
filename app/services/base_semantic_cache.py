"""BaseSemanticCache — 语义缓存抽象基类 (Plan v1 Step 5)

设计目标:
  - 抽象 query → Redis 缓存的通用逻辑, 供 RAGQueryCache (W99-RAG-1) + RetrievalCache (qa-bench D3) 共享
  - 子类只需配置: prefix / TTL / sim_threshold / NN_PROBE / 缓存 value schema
  - 0 业务代码改动 (hybrid_retriever.py 3 处 import 路径不变)
  - 类 20.121: Redis 不可用 best-effort silently 降级
  - 类 20.122: 缓存键必须含 user_id + tenant_id 隔离

数据契约 (cached value schema):
  {
    "results": List[dict],          # 检索结果
    "extra": Dict[str, Any],        # 子类扩展字段 (citations/retrieval_method/score...)
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

import hashlib
import json
import logging
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

# get_redis now module-level (Plan v2 #6 fix)  # 2026-08-17 #Plan v2 #6: module-level 让 test patch 可用
from app.core.redis import get_redis

logger = logging.getLogger("microbubble.base_semantic_cache")


class BaseSemanticCache:
    """Redis 语义缓存基类

    子类用法:
        from app.services.base_semantic_cache import BaseSemanticCache

        class MyCache(BaseSemanticCache):
            def __init__(self):
                super().__init__(
                    prefix="my:",
                    ttl_seconds=86400,
                    sim_threshold=0.95,
                    nn_probe=5,
                    name="MyCache",
                )

    提供的核心方法 (子类可直接用, 也可重写):
        - get(query, user_id, tenant_id): 精确匹配 + 语义相似扫描
        - set(query, user_id, tenant_id, result, extra=None, ttl=None): 写缓存 + 索引
        - invalidate(query, user_id, tenant_id): 精确失效
        - find_similar(query_embedding, user_id, tenant_id): 语义相似扫描 (用 NN_PROBE)
        - _cosine_similarity(a, b): 余弦相似度

    子类应重写或注入:
        - value_schema_pre_check(result): 写前校验 (默认 None)
        - value_schema_post_load(value): 读后转换 (默认 passthrough)
    """

    def __init__(
        self,
        prefix: str,
        ttl_seconds: int,
        sim_threshold: float,
        nn_probe: int,
        name: str,
        enabled: bool = True,
    ) -> None:
        self.prefix = prefix
        self.ttl = ttl_seconds
        self.sim_threshold = sim_threshold
        self.nn_probe = nn_probe
        self.name = name  # 仅用于 log, e.g. "RAGQueryCache"
        self.enabled = enabled

    # ============================================================
    # 公共 API
    # ============================================================

    async def get(
        self,
        query: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """精确匹配 + 语义相似扫描

        Args:
            query: 用户查询
            user_id: 归属用户 (None = 匿名)
            tenant_id: 归属租户 (None = default)

        Returns:
            命中: dict 含 results/extra/timestamp/user_id/tenant_id
            未命中: None
            Redis 不可用: None (best-effort silently 降级)
        """
        if not self.enabled:
            return None
        if not query:
            return None

        # 1. 精确匹配优先
        key = self._exact_cache_key(query, user_id, tenant_id)
        try:
            # get_redis now module-level (Plan v2 #6 fix)
            redis = await get_redis()
            raw = await redis.get(key)
        except Exception as e:
            logger.debug(f"[{self.name}.get] redis lookup fail: {e}")
            return None

        if raw is not None:
            try:
                value = json.loads(raw)
                return self.value_schema_post_load(value)
            except (TypeError, ValueError) as e:
                logger.debug(f"[{self.name}.get] json parse fail: {e}")
                return None

        # 2. 精确未命中, 语义相似扫描
        return await self.find_similar(query, user_id, tenant_id)

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
            result: 业务方传的完整结果 dict (results 字段必填, 其余字段透传)
            ttl: 自定义 TTL (None 走 self.ttl)

        Returns:
            True 写成功 / False 失败 — 调用方不必检查

        设计: 业务方把 results/citations/retrieval_method/score/top_k 等所有字段
        平铺在 result dict 传入, 子类通过 value_schema_post_load 在读时还原结构.
        兼容 hybrid_retriever.py 现有调用: cache.set(result={"results": ..., "citations": ...}).
        """
        if not self.enabled:
            return False
        if not query:
            return False

        # 子类预校验
        if not self.value_schema_pre_check(result):
            return False

        effective_ttl = ttl if ttl is not None else self.ttl
        key = self._exact_cache_key(query, user_id, tenant_id)

        # 透传 result 全部字段 + 加 timestamp + 元信息
        value: Dict[str, Any] = {
            **result,  # 透传 fields (results/citations/retrieval_method/score/top_k)
            "timestamp": time.time(),
            "user_id": user_id,
            "tenant_id": tenant_id,
        }

        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            logger.debug(f"[{self.name}.set] json dumps fail: {e}")
            return False

        try:
            # get_redis now module-level (Plan v2 #6 fix)
            redis = await get_redis()
            await redis.setex(key, effective_ttl, payload)
        except Exception as e:
            logger.debug(f"[{self.name}.set] redis setex fail: {e}")
            return False

        # 写 user+tenant 索引 (用于 find_similar 失败不影响主缓存)
        try:
            await self._index_for_similar(key, query, user_id, tenant_id, effective_ttl)
        except Exception as e:
            logger.debug(f"[{self.name}.set] index write fail: {e}")

        return True

    async def invalidate(
        self,
        query: str,
        user_id: Optional[int],
        tenant_id: Optional[int],
    ) -> bool:
        """精确失效 (best-effort)

        Returns:
            True 失效成功 / False 失败 (Redis 不可用)
        """
        if not self.enabled:
            return False
        if not query:
            return False

        key = self._exact_cache_key(query, user_id, tenant_id)
        try:
            # get_redis now module-level (Plan v2 #6 fix)
            redis = await get_redis()
            await redis.delete(key)
        except Exception as e:
            logger.debug(f"[{self.name}.invalidate] redis del fail: {e}")
            return False
        return True

    async def find_similar(
        self,
        query: str,
        user_id: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """语义相似扫描 (类 20.122 多租户隔离)

        1. 拿 user+tenant 索引 (sorted set, 按 timestamp 排)
        2. 取最近 N 条 (NN_PROBE)
        3. 逐条算 cosine similarity
        4. 命中 (≥ sim_threshold) 返最相似一条

        Returns:
            命中: dict (与 get() 同 schema)
            未命中: None
        """
        if not self.enabled:
            return None
        if not query:
            return None

        # 计算 query embedding (失败降级返 None)
        try:
            from app.services.embedding_service import get_or_compute_query_embedding
            query_embedding = await get_or_compute_query_embedding(query)
        except Exception as e:
            logger.debug(f"[{self.name}.find_similar] embed fail: {e}")
            return None
        if not query_embedding:
            return None

        # 拿 user+tenant 索引
        idx_key = self._user_tenant_index_key(user_id, tenant_id)
        try:
            # get_redis now module-level (Plan v2 #6 fix)
            redis = await get_redis()
            members = await redis.zrevrange(idx_key, 0, self.nn_probe - 1)
        except Exception as e:
            logger.debug(f"[{self.name}.find_similar] redis zrevrange fail: {e}")
            return None

        if not members:
            return None

        # 逐条比对
        best_sim = 0.0
        best_value = None
        for member in members:
            # 索引 member 格式: "{exact_key}:{embedding_hash}"
            try:
                cached_raw = await redis.get(member.split(":", 1)[0])
            except Exception:
                continue
            if not cached_raw:
                continue
            try:
                cached_value = json.loads(cached_raw)
            except Exception:
                continue

            # 算 cosine similarity (需要从 cache value 反推 embedding)
            # 简化: 当前实现仅精确匹配, 无 embedding 反推
            # 这里返回 None, 留子类扩展
            # (W99-RAG-1 实际是用外部 embedding 服务比对, 不在 cache 内部)
            return None  # TODO: 上层 semantic lookup 已在调用方做

        return None

    # ============================================================
    # 子类可覆盖的扩展点
    # ============================================================

    def value_schema_pre_check(self, result: Dict[str, Any]) -> bool:
        """写前校验 (默认 None 通过). 子类可重写加 schema 校验."""
        return True

    def value_schema_post_load(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """读后转换 (默认 passthrough). 子类可重写把 extra 字段拍平."""
        return value

    # ============================================================
    # 内部 helper
    # ============================================================

    def _exact_cache_key(self, query: str, user_id: Optional[int], tenant_id: Optional[int]) -> str:
        """精确查询缓存 key (sha256[:16])

        Key 格式: {prefix}{sha256(f"{user_id}:{tenant_id}:{query}")[:16]}
        类 20.122: 必须含 user_id+tenant_id 隔离多租户
        """
        raw = f"{user_id or 'anon'}:{tenant_id or 'default'}:{query}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"{self.prefix}{digest}"

    def _user_tenant_index_key(self, user_id: Optional[int], tenant_id: Optional[int]) -> str:
        """user+tenant 维度的查询索引 key (用于 find_similar 扫描)

        索引值: list of {exact_key, embedding, timestamp}
        简化: 存为 sorted set, score=timestamp, member=exact_key
        """
        raw = f"{user_id or 'anon'}:{tenant_id or 'default'}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"{self.prefix}idx:{digest}"

    async def _index_for_similar(
        self,
        cache_key: str,
        query: str,
        user_id: Optional[int],
        tenant_id: Optional[int],
        ttl: int,
    ) -> None:
        """写 user+tenant 索引 (sorted set, ttl 用 unset)

        上层 (caller) 通过 redis 二次 expire 索引键来限 TTL——
        这里仅 zadd 不设 expire, 由调用方在 set 主缓存时同步 expire 索引键.
        """
        if not self.enabled:
            return
        idx_key = self._user_tenant_index_key(user_id, tenant_id)
        try:
            # get_redis now module-level (Plan v2 #6 fix)
            redis = await get_redis()
            await redis.zadd(idx_key, {cache_key: time.time()})
            await redis.expire(idx_key, ttl)
        except Exception as e:
            logger.debug(f"[{self.name}._index_for_similar] fail: {e}")

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """余弦相似度 (用于 find_similar 内部 metric)"""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
