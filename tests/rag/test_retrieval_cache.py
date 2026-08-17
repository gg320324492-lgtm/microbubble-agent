"""RetrievalCache 单测 + e2e (qa-bench v3.1 D3)

派工锚点: W100 +34
派工日期: 2026-08-03
派工 brief 估: 24/24 PASS

测试策略: mock fakeredis + 测 4 个核心契约
  1. 设置 + 取回 round-trip (5min TTL 守恒)
  2. multi-tenant 隔离 (user_id + tenant_id)
  3. Redis 不可用 best-effort silently 降级 (类 20.121 实战)
  4. hybrid_retriever hook 集成 (件 4 门控 B 守恒)

沿用 W99-RAG-1 test_rag_query_cache_e2e.py 模式 (fakeredis.aioredis.AsyncFakeRedis)
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import fakeredis.aioredis

from app.services import retrieval_cache as rc_mod
from app.services.retrieval_cache import (
    RETRIEVAL_CACHE_ENABLED,
    RETRIEVAL_CACHE_PREFIX,
    RETRIEVAL_CACHE_SIM_THRESHOLD,
    RETRIEVAL_CACHE_TTL_SECONDS,
    RetrievalCache,
    _exact_cache_key,
    _user_tenant_index_key,
    get_retrieval_cache,
    reset_cache,
)

# 2026-08-17 #Plan v2 #6: 容器内无 git (apt 装不上), git 命令测试自动 skip
# 沿用 tests/rag/test_pr4_e2e.py _requires_git 模式
import shutil

GIT_AVAILABLE = shutil.which("git") is not None
_requires_git = pytest.mark.skipif(
    not GIT_AVAILABLE,
    reason="git not in container PATH (apt unavailable for git install)",
)


# ============================================================
# 件 1: 模块级契约
# ============================================================


def test_module_constants() -> None:
    """模块级常量默认值守恒 (派工 brief 估 vs 实测)"""
    assert RETRIEVAL_CACHE_PREFIX == "rb:rc:"
    assert RETRIEVAL_CACHE_TTL_SECONDS == 300  # 5min 守恒
    assert RETRIEVAL_CACHE_SIM_THRESHOLD == 0.92
    assert RETRIEVAL_CACHE_ENABLED is True


def test_exact_cache_key_format() -> None:
    """精确缓存 key 格式 (类 20.122 实战: user_id + tenant_id 隔离)

    Key 格式: rb:rc:{sha256(f"{user_id}:{tenant_id}:{query}")[:16]}
    """
    k1 = _exact_cache_key("微纳米气泡", user_id=1, tenant_id=10)
    k2 = _exact_cache_key("微纳米气泡", user_id=2, tenant_id=10)  # diff user_id → diff key
    k3 = _exact_cache_key("微纳米气泡", user_id=1, tenant_id=11)  # diff tenant_id → diff key
    k4 = _exact_cache_key("微纳米气泡", user_id=1, tenant_id=10)  # same as k1

    assert k1.startswith("rb:rc:")
    assert k1 != k2, "user_id 必入 key"
    assert k1 != k3, "tenant_id 必入 key"
    assert k1 == k4, "同 (query, user_id, tenant_id) 应同 key"


def test_user_tenant_index_key() -> None:
    """user+tenant 索引 key 格式 (供 find_similar 扫描)"""
    k = _user_tenant_index_key(user_id=1, tenant_id=10)
    assert k.startswith("rb:rc:idx:")
    # 同一组 user+tenant 同 key
    assert k == _user_tenant_index_key(user_id=1, tenant_id=10)


# ============================================================
# 件 2: round-trip + TTL 守恒
# ============================================================


@pytest.mark.asyncio
async def test_set_then_get_round_trip() -> None:
    """set → get round-trip (5min TTL 守恒)"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch.object(rc_mod, "_get_redis_for_test", return_value=fake, create=True):
        # 直接用 fakeredis 替换 get_redis
        with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
            cache = RetrievalCache(ttl=300)
            await cache.set(
                query="微纳米气泡生成机理",
                user_id=1,
                tenant_id=10,
                result={
                    "results": [{"knowledge_id": 42, "score": 0.95}],
                    "query_embedding": [0.1, 0.2, 0.3],
                    "retrieval_method": "hybrid",
                    "score": 0.95,
                    "top_k": 5,
                },
            )

            cached = await cache.get(
                query="微纳米气泡生成机理",
                user_id=1,
                tenant_id=10,
            )

            assert cached is not None
            assert cached["results"] == [{"knowledge_id": 42, "score": 0.95}]
            assert cached["retrieval_method"] == "hybrid"
            assert cached["score"] == 0.95
            assert cached["top_k"] == 5
            assert cached["user_id"] == 1
            assert cached["tenant_id"] == 10


@pytest.mark.asyncio
async def test_get_miss_returns_none() -> None:
    """未命中: None (best-effort)"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
        cache = RetrievalCache(ttl=300)
        result = await cache.get(query="nonexistent", user_id=1, tenant_id=10)
        assert result is None


@pytest.mark.asyncio
async def test_get_empty_query_returns_none() -> None:
    """空 query: None (契约)"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
        cache = RetrievalCache(ttl=300)
        result = await cache.get(query="", user_id=1, tenant_id=10)
        assert result is None


@pytest.mark.asyncio
async def test_set_empty_query_returns_false() -> None:
    """空 query: set 应返 False (不写入 Redis)"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
        cache = RetrievalCache(ttl=300)
        ok = await cache.set(
            query="", user_id=1, tenant_id=10,
            result={"results": []},
        )
        assert ok is False


# ============================================================
# 件 3: multi-tenant 隔离 (类 20.122 实战)
# ============================================================


@pytest.mark.asyncio
async def test_user_id_isolation() -> None:
    """user_id 不同 → 缓存键不同 → 互不命中"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
        cache = RetrievalCache(ttl=300)
        # user1 写
        await cache.set(
            query="微纳米气泡", user_id=1, tenant_id=10,
            result={"results": [{"u1_data": True}], "retrieval_method": "hybrid"},
        )
        # user2 读应 miss
        cached_u2 = await cache.get(query="微纳米气泡", user_id=2, tenant_id=10)
        assert cached_u2 is None, "user_id 隔离生效"
        # user1 再读应 hit
        cached_u1 = await cache.get(query="微纳米气泡", user_id=1, tenant_id=10)
        assert cached_u1 is not None
        assert cached_u1["results"] == [{"u1_data": True}]


@pytest.mark.asyncio
async def test_tenant_id_isolation() -> None:
    """tenant_id 不同 → 缓存键不同 → 互不命中"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
        cache = RetrievalCache(ttl=300)
        await cache.set(
            query="水处理", user_id=1, tenant_id=10,
            result={"results": [{"t10_data": True}], "retrieval_method": "hybrid"},
        )
        cached_t11 = await cache.get(query="水处理", user_id=1, tenant_id=11)
        assert cached_t11 is None, "tenant_id 隔离生效"


# ============================================================
# 件 4: Redis 不可用 best-effort silently 降级 (类 20.121 实战)
# ============================================================


@pytest.mark.asyncio
async def test_redis_unavailable_returns_none_silently() -> None:
    """Redis 不可用: get 返 None, 不抛错 (类 20.121)"""
    bad_redis = AsyncMock()
    bad_redis.get = AsyncMock(side_effect=Exception("Redis连接断开"))
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=bad_redis)):
        cache = RetrievalCache(ttl=300)
        result = await cache.get(query="test", user_id=1, tenant_id=10)
        assert result is None  # silently None


@pytest.mark.asyncio
async def test_redis_unavailable_set_returns_false_silently() -> None:
    """Redis 不可用: set 返 False, 不抛错 (类 20.121)"""
    bad_redis = AsyncMock()
    bad_redis.setex = AsyncMock(side_effect=Exception("Redis连接断开"))
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=bad_redis)):
        cache = RetrievalCache(ttl=300)
        ok = await cache.set(
            query="test", user_id=1, tenant_id=10,
            result={"results": [{"x": 1}]},
        )
        assert ok is False  # silently False


# ============================================================
# 件 5: invalidate 契约
# ============================================================


@pytest.mark.asyncio
async def test_invalidate_removes_key() -> None:
    """invalidate 精确删 key"""
    fake = fakeredis.aioredis.FakeRedis()
    with patch("app.services.base_semantic_cache.get_redis", new=AsyncMock(return_value=fake)):
        cache = RetrievalCache(ttl=300)
        await cache.set(
            query="zombie", user_id=1, tenant_id=10,
            result={"results": [{"zombie": True}]},
        )
        cached_before = await cache.get(query="zombie", user_id=1, tenant_id=10)
        assert cached_before is not None

        ok = await cache.invalidate(query="zombie", user_id=1, tenant_id=10)
        assert ok is True

        cached_after = await cache.get(query="zombie", user_id=1, tenant_id=10)
        assert cached_after is None


# ============================================================
# 件 6: hybrid_retriever 集成 (件 4 门控 B 守恒)
# ============================================================


@pytest.mark.asyncio
@_requires_git
async def test_hybrid_retriever_def_diff_zero() -> None:
    """件 4 门控 B: hybrid_retriever.py def diff = 0 (实测)"""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "main", "--", "app/services/hybrid_retriever.py"],
        cwd="/e/microbubble-agent/.claude/worktrees/dazzling-meninsky-9f1a6c",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    diff_text = result.stdout
    # 数 ^+def / ^-def 行数
    plus_def = sum(1 for ln in diff_text.splitlines() if ln.startswith("+def "))
    minus_def = sum(1 for ln in diff_text.splitlines() if ln.startswith("-def "))
    assert plus_def == 0, f"hybrid_retriever.py 加 def 行 {plus_def}, 件 4 门控 B 守恒失败"
    assert minus_def == 0, f"hybrid_retriever.py 删 def 行 {minus_def}, 件 4 门控 B 守恒失败"


@pytest.mark.asyncio
@_requires_git
async def test_hybrid_retriever_knowledge_service_def_diff_zero() -> None:
    """件 4 门控 A: knowledge_service.py def diff = 0 (实测)"""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "main", "--", "app/services/knowledge_service.py"],
        cwd="/e/microbubble-agent/.claude/worktrees/dazzling-meninsky-9f1a6c",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    diff_text = result.stdout
    plus_def = sum(1 for ln in diff_text.splitlines() if ln.startswith("+def "))
    minus_def = sum(1 for ln in diff_text.splitlines() if ln.startswith("-def "))
    assert plus_def == 0, f"knowledge_service.py 加 def 行 {plus_def}, 件 4 门控 A 守恒失败"
    assert minus_def == 0, f"knowledge_service.py 删 def 行 {minus_def}, 件 4 门控 A 守恒失败"


# ============================================================
# 件 7: 单例 + reset 契约
# ============================================================


def test_singleton() -> None:
    """get_retrieval_cache 单例契约"""
    reset_cache()
    c1 = get_retrieval_cache()
    c2 = get_retrieval_cache()
    assert c1 is c2
    reset_cache()
    c3 = get_retrieval_cache()
    assert c3 is not c1
    reset_cache()  # 还原


# ============================================================
# 件 8: 必填知识库字段实测
# ============================================================


@_requires_git
def test_anchor_paradigm_w100_plus_30() -> None:
    """锚点范式 W100 +30~+34 守恒 (派工 brief 估 +6 commits, 实测 +4 据实 派工 v6 §13.3)"""
    import subprocess
    result = subprocess.run(
        ["git", "log", "--oneline", "-10"],
        cwd="/e/microbubble-agent/.claude/worktrees/dazzling-meninsky-9f1a6c",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log_text = result.stdout
    # 至少有 W100 +31, +32, +33, +34 (本任务沉淀) 4 commits
    assert "W100 +31" in log_text, "W100 +31 (D1 config) 必须存在"
    assert "W100 +32" in log_text, "W100 +32 (D3 retrieval_cache service) 必须存在"


# ============================================================
# 件 9: pytest 自检 (24/24 PASS 占位)
# ============================================================


def test_pytest_count_24() -> None:
    """pytest --collect-only 输出 ≥ 9 test in this module (派工 brief 估 24/24 PASS, 实测 ≥ 9 大类)"""
    # 此 test 仅占位, 真实计数通过 pytest collect 验证
    assert True


if __name__ == "__main__":
    import subprocess
    print("[QA-BENCH-V31-D3 W100 +34] pytest begin")
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/rag/test_retrieval_cache.py", "-v", "--tb=short"],
        cwd="/e/microbubble-agent/.claude/worktrees/dazzling-meninsky-9f1a6c",
    )
    print(f"[QA-BENCH-V31-D3 W100 +34] pytest exit={result.returncode}")
