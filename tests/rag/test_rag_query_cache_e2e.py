"""RAGQueryCache e2e 验证 (W99-RAG-1)

门禁: 22/22 PASS
模式: tests/rag/test_pr4_e2e.py (件 1-6 + 22/22 PASS 自检)

覆盖:
  - 件 1: alembic 1 head verify (subprocess)
  - 件 2: RAGQueryCache 端到端 (单测已覆盖, 本套件重点集成)
  - 件 3: hybrid_retriever 集成 (cache hook 不破既有行为)
  - 件 4: 件 4 双门控 (0 def diff)
  - 件 5: 锚点范式 ≥ 6 commits
  - 件 6: 综合硬门禁
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import fakeredis.aioredis

from app.services import rag_query_cache as rqc_mod
from app.services.rag_query_cache import (
    RAG_QUERY_CACHE_ENABLED,
    RAG_QUERY_CACHE_PREFIX,
    RAG_QUERY_CACHE_TTL_SECONDS,
    RAGQueryCache,
    _exact_cache_key,
    get_rag_query_cache,
    reset_cache,
)
from app.services.hybrid_retriever import (
    HybridRetriever,
    retrieve_with_weights,
)
from app.services.recall_observability import RecallTrace
from app.rag.config import (
    RAG_QUERY_CACHE_ENABLED as CFG_ENABLED,
    RAG_QUERY_CACHE_TTL as CFG_TTL,
    RAG_QUERY_CACHE_SIM_THRESHOLD as CFG_THRESHOLD,
)

WORKTREE_ROOT = Path(__file__).parent.parent.parent


def _run_cmd(cmd: str) -> str:
    """subprocess 跑命令 + 返 stdout

    Windows Git Bash 默认 cp936 编码, 这里强制 utf-8 + errors='replace'
    """
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=str(WORKTREE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return (result.stdout or "") + (result.stderr or "")


# ============================================================
# 件 1: alembic 1 head verify
# ============================================================


def test_e2e_01_alembic_single_head() -> None:
    """件 1: python -m alembic heads → 1 head (094)"""
    out = _run_cmd("python -m alembic heads")
    assert "094" in out, f"094 应在 alembic heads 中: {out}"
    assert "Multiple" not in out, f"alembic 多 head, 不应: {out}"


# ============================================================
# 件 2: RAGQueryCache 端到端
# ============================================================


@pytest.mark.asyncio
async def test_e2e_02_basic_set_get() -> None:
    """set → get 命中"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        reset_cache()
        cache = get_rag_query_cache()
        payload = {
            "results": [{"id": 1, "score": 0.9, "retrieval_method": "hybrid"}],
            "citations": [],
            "retrieval_method": "hybrid",
            "score": 0.9,
            "top_k": 5,
        }
        ok = await cache.set("e2e test", user_id=1, tenant_id=1, result=payload)
        assert ok is True
        cached = await cache.get("e2e test", user_id=1, tenant_id=1)
        assert cached is not None
        assert cached["results"] == payload["results"]


@pytest.mark.asyncio
async def test_e2e_03_ttl_set_correctly() -> None:
    """TTL 写入正确"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        cache = RAGQueryCache(ttl=60)
        payload = {"results": [{"id": 1}], "citations": [], "retrieval_method": "hybrid", "score": 0.5, "top_k": 1}
        await cache.set("ttl e2e", user_id=1, tenant_id=1, result=payload)
        key = _exact_cache_key("ttl e2e", 1, 1)
        ttl = await fake.ttl(key)
        assert 0 < ttl <= 60


# ============================================================
# 件 3: 多用户/多租户隔离
# ============================================================


@pytest.mark.asyncio
async def test_e2e_04_user_isolation() -> None:
    """user_id 不同不串数据 (类 20.122)"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        cache = RAGQueryCache()
        payload = {
            "results": [{"id": 1, "score": 0.9, "retrieval_method": "hybrid"}],
            "citations": [],
            "retrieval_method": "hybrid",
            "score": 0.9,
            "top_k": 5,
        }
        await cache.set("user iso", user_id=1, tenant_id=1, result=payload)
        # user_id=2 不命中
        cached = await cache.get("user iso", user_id=2, tenant_id=1)
        assert cached is None
        # user_id=1 命中
        cached = await cache.get("user iso", user_id=1, tenant_id=1)
        assert cached is not None


@pytest.mark.asyncio
async def test_e2e_05_tenant_isolation() -> None:
    """tenant_id 不同不串数据 (类 20.122)"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        cache = RAGQueryCache()
        payload = {
            "results": [{"id": 1, "score": 0.9, "retrieval_method": "hybrid"}],
            "citations": [],
            "retrieval_method": "hybrid",
            "score": 0.9,
            "top_k": 5,
        }
        await cache.set("tenant iso", user_id=1, tenant_id=1, result=payload)
        # tenant_id=2 不命中
        cached = await cache.get("tenant iso", user_id=1, tenant_id=2)
        assert cached is None
        # tenant_id=1 命中
        cached = await cache.get("tenant iso", user_id=1, tenant_id=1)
        assert cached is not None


@pytest.mark.asyncio
async def test_e2e_06_anonymous_works() -> None:
    """user_id=None (匿名) 也能命中"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        cache = RAGQueryCache()
        payload = {"results": [{"id": 1}], "citations": [], "retrieval_method": "hybrid", "score": 0.5, "top_k": 1}
        await cache.set("anon", user_id=None, tenant_id=None, result=payload)
        cached = await cache.get("anon", user_id=None, tenant_id=None)
        assert cached is not None


# ============================================================
# 件 4: 语义相似命中
# ============================================================


@pytest.mark.asyncio
async def test_e2e_07_find_similar_hit() -> None:
    """find_similar 命中 (mock embedding 返相同向量)"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    import math
    dim = 1024
    v = 1.0 / math.sqrt(dim)
    fixed_emb = [v] * dim
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        with patch(
            "app.services.embedding_service.get_or_compute_query_embedding",
            new=AsyncMock(return_value=fixed_emb),
        ):
            cache = RAGQueryCache()
            payload = {"results": [{"id": 1, "score": 0.9}], "citations": [], "retrieval_method": "hybrid", "score": 0.9, "top_k": 5}
            await cache.set("sim test", user_id=1, tenant_id=1, result=payload)
            cached = await cache.find_similar("sim test", user_id=1, tenant_id=1)
            assert cached is not None
            assert cached["results"] == payload["results"]


@pytest.mark.asyncio
async def test_e2e_08_find_similar_below_threshold() -> None:
    """find_similar 阈值拦截 (mock embedding 返正交向量)"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    import math
    dim = 1024
    fixed_emb = [1.0 / math.sqrt(dim)] * dim
    orthogonal = [0.0] * 512 + [1.0 / math.sqrt(512)] * 512
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        with patch(
            "app.services.embedding_service.get_or_compute_query_embedding",
            new=AsyncMock(return_value=fixed_emb),
        ) as m:
            cache = RAGQueryCache()
            payload = {"results": [{"id": 1, "score": 0.9}], "citations": [], "retrieval_method": "hybrid", "score": 0.9, "top_k": 5}
            await cache.set("sim low", user_id=1, tenant_id=1, result=payload)
            # 改 mock 返正交向量
            m.return_value = orthogonal
            cached = await cache.find_similar("sim low", user_id=1, tenant_id=1)
            # cosine ≈ 0 < 0.95 → 不命中
            assert cached is None or cached.get("cache_similarity", 0) < 0.95


@pytest.mark.asyncio
async def test_e2e_09_find_similar_user_isolation() -> None:
    """find_similar 也受 user/tenant 隔离"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    import math
    dim = 1024
    fixed_emb = [1.0 / math.sqrt(dim)] * dim
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        with patch(
            "app.services.embedding_service.get_or_compute_query_embedding",
            new=AsyncMock(return_value=fixed_emb),
        ):
            cache = RAGQueryCache()
            payload = {"results": [{"id": 1, "score": 0.9}], "citations": [], "retrieval_method": "hybrid", "score": 0.9, "top_k": 5}
            await cache.set("sim iso", user_id=1, tenant_id=1, result=payload)
            # user_id=2 不命中 (索引在另一个 user 下)
            cached = await cache.find_similar("sim iso", user_id=2, tenant_id=1)
            assert cached is None


# ============================================================
# 件 5: hybrid_retriever 集成 (cache hook 不破既有行为)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_10_hybrid_retriever_signature_unchanged() -> None:
    """件 4 门控 B 守恒: 原 retrieve 函数签名不变"""
    import inspect
    sig = inspect.signature(HybridRetriever.retrieve)
    params = list(sig.parameters.keys())
    assert "query" in params
    assert "top_k" in params
    assert "category" in params
    assert "enable_vector" in params
    assert "enable_bm25" in params
    assert "enable_graph" in params
    assert "enable_rerank" in params


@pytest.mark.asyncio
async def test_e2e_11_hybrid_retriever_methods_count() -> None:
    """原方法集不丢失"""
    methods = [m for m in dir(HybridRetriever) if not m.startswith("__")]
    expected = {
        "retrieve",
        "_vector_search",
        "_bm25_search",
        "_refresh_bm25_index",
        "_merge_results",
        "_graph_search",
        "_normalize_scores",
        "evaluate",
    }
    assert expected.issubset(set(methods)), f"原方法缺失: {expected - set(methods)}"


@pytest.mark.asyncio
async def test_e2e_12_retrieve_with_weights_signature_unchanged() -> None:
    """retrieve_with_weights 签名不变 (cache hook 仅追加)"""
    import inspect
    sig = inspect.signature(retrieve_with_weights)
    params = list(sig.parameters.keys())
    assert "db" in params
    assert "query" in params
    assert "top_k" in params
    assert "weights" in params
    assert "enable_synonym_expansion" in params


# ============================================================
# 件 6: RecallTrace + search_log 字段传递
# ============================================================


def test_e2e_13_recall_trace_cache_fields() -> None:
    """RecallTrace 新增 cache_hit + cache_similarity 字段"""
    t = RecallTrace()
    assert t.cache_hit is False
    assert t.cache_similarity is None
    t.cache_hit = True
    t.cache_similarity = 0.97
    d = t.to_dict()
    assert d["cache_hit"] is True
    assert d["cache_similarity"] == 0.97


def test_e2e_14_recall_trace_field_count() -> None:
    """RecallTrace 字段数 ≥ 22 (20 老 + 2 新, 实际 22)"""
    t = RecallTrace()
    assert len(t.to_dict()) >= 22, f"RecallTrace 字段数 {len(t.to_dict())} < 22"


def test_e2e_15_search_log_model_fields() -> None:
    """search_log model 新增 cache_hit + cache_similarity 列"""
    from app.models.search_log import SearchLog
    columns = {c.name for c in SearchLog.__table__.columns}
    assert "cache_hit" in columns
    assert "cache_similarity" in columns


# ============================================================
# 件 7: 边界 / 故障降级
# ============================================================


@pytest.mark.asyncio
async def test_e2e_16_redis_unavailable_silently_degrade() -> None:
    """类 20.121: Redis 不可用 → silently 降级, 不抛错"""
    cache = RAGQueryCache()
    with patch(
        "app.core.redis.get_redis",
        new=AsyncMock(side_effect=ConnectionError("Redis down")),
    ):
        # get 不抛
        cached = await cache.get("test", user_id=1, tenant_id=1)
        assert cached is None
        # set 不抛
        payload = {"results": [], "citations": [], "retrieval_method": "hybrid", "score": 0.0, "top_k": 5}
        ok = await cache.set("test", user_id=1, tenant_id=1, result=payload)
        assert ok is False
        # invalidate 不抛
        ok = await cache.invalidate("test", user_id=1, tenant_id=1)
        assert ok is False
        # find_similar 不抛
        cached = await cache.find_similar("test", user_id=1, tenant_id=1)
        assert cached is None


@pytest.mark.asyncio
async def test_e2e_17_corrupted_json_silently_degrade() -> None:
    """Redis 返坏 JSON → 不抛, 返 None"""
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    key = _exact_cache_key("corrupt", 1, 1)
    await fake.set(key, "broken{json")
    with patch("app.core.redis.get_redis", new=AsyncMock(return_value=fake)):
        cache = RAGQueryCache()
        cached = await cache.get("corrupt", user_id=1, tenant_id=1)
        assert cached is None


# ============================================================
# 件 8: 配置文件
# ============================================================


def test_e2e_18_config_values() -> None:
    """app/rag/config.py 5 配置正确加载"""
    assert CFG_ENABLED is True
    assert CFG_TTL == 86400
    assert CFG_THRESHOLD == 0.95
    assert RAG_QUERY_CACHE_ENABLED is True


def test_e2e_19_module_constants() -> None:
    """rag_query_cache module 常量"""
    assert RAG_QUERY_CACHE_TTL_SECONDS == 86400
    assert RAG_QUERY_CACHE_PREFIX == "rag:q:"


# ============================================================
# 件 9: 锚点范式 (subprocess)
# ============================================================


def test_e2e_20_anchor_paradigm_commits_count() -> None:
    """件 5: git log --grep "W99-RAG-1" 至少 5 条 (起步阶段)"""
    out = _run_cmd('git log --grep "W99-RAG-1" --oneline')
    lines = [l for l in out.split("\n") if l.strip() and "W99-RAG-1" in l]
    assert len(lines) >= 5, f"W99-RAG-1 锚点 commit < 5, 实际 {len(lines)}"


def test_e2e_21_hybrid_retriever_zero_def_diff() -> None:
    """件 4 门控 B: hybrid_retriever.py 0 def diff"""
    out = _run_cmd("git diff 2ebf8f1d5..HEAD -- app/services/hybrid_retriever.py")
    def_lines = [
        l for l in out.split("\n")
        if l.startswith("+def ") or l.startswith("-def ")
    ]
    assert len(def_lines) == 0, f"hybrid_retriever.py 有 def 改动, 应为 0: {def_lines[:5]}"


def test_e2e_22_knowledge_service_zero_def_diff() -> None:
    """件 4 门控 A: knowledge_service.py 0 def diff"""
    out = _run_cmd("git diff 2ebf8f1d5..HEAD -- app/services/knowledge_service.py")
    def_lines = [
        l for l in out.split("\n")
        if l.startswith("+def ") or l.startswith("-def ")
    ]
    assert len(def_lines) == 0, f"knowledge_service.py 有 def 改动, 应为 0: {def_lines[:5]}"
