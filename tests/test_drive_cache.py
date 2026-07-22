"""Agent 7 5th-wave 教训加固测试 — drive_cache

覆盖:
- cache_drive_list 装饰器 cache hit/miss/expired
- invalidate_drive_list_cache prefix 精准失效 / full invalidate
- get_cache_stats admin 调试
- reset_cache_for_testing fixture 隔离
- cross-user 隔离 (不同 user_id 互不污染)
- prefix 区分 (同 user 不同 prefix 互不污染)

跑法 (无 DB 依赖):
    pytest tests/test_drive_cache.py -v
"""
import asyncio
import pytest

from app.services.drive_cache import (  # noqa: E402
    DEFAULT_TTL_SEC,
    _drive_list_cache,
    cache_drive_list,
    get_cache_stats,
    invalidate_drive_list_cache,
    reset_cache_for_testing,
)


# ============================================================================
# Fixtures — 测试隔离
# ============================================================================

@pytest.fixture(autouse=True)
def _reset_cache():
    """每个测试前后清空 cache (隔离)"""
    reset_cache_for_testing()
    yield
    reset_cache_for_testing()


# ============================================================================
# Mock 函数 — 模拟 drive_service.list_files
# ============================================================================

_call_count = 0


async def _mock_list_files_real(prefix: str, user_id: int, recursive: bool = False) -> list[dict]:
    """模拟真实 list_objects (有延迟, 计数调用次数)"""
    global _call_count
    _call_count += 1
    await asyncio.sleep(0.001)  # 模拟 IO
    return [
        {"key": f"{prefix}file_{i}.pdf", "size": 1000, "user_id": user_id}
        for i in range(3)
    ]


def _reset_call_count():
    global _call_count
    _call_count = 0


# ============================================================================
# TestCacheHit — cache hit/miss 语义
# ============================================================================

class TestCacheHit:
    """cache hit 减少真函数调用"""

    @pytest.mark.asyncio
    async def test_first_call_is_cache_miss(self):
        """第一次调用走真函数 (cache miss)"""
        _reset_call_count()
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        result = await decorated("team/", user_id=1, recursive=False)

        assert len(result) == 3
        assert _call_count == 1  # 真函数被调 1 次

    @pytest.mark.asyncio
    async def test_second_call_is_cache_hit(self):
        """第二次调用走 cache (不再调真函数)"""
        _reset_call_count()
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        result = await decorated("team/", user_id=1, recursive=False)

        assert _call_count == 1  # 真函数仍只 1 次 (cache hit)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_default_ttl_is_30_sec(self):
        """默认 TTL = 30s (覆盖性能 vs 一致性)"""
        assert DEFAULT_TTL_SEC == 30


# ============================================================================
# TestCacheKeyIsolation — cache key 隔离
# ============================================================================

class TestCacheKeyIsolation:
    """不同 user_id / prefix / recursive 互不污染"""

    @pytest.mark.asyncio
    async def test_different_user_isolates_cache(self):
        """user_id 不同 → 不同 cache key (防跨用户泄漏)"""
        _reset_call_count()
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        await decorated("team/", user_id=2, recursive=False)  # 不同 user

        assert _call_count == 2  # 真函数各调 1 次 (user1 + user2)
        assert len(_drive_list_cache) == 2

    @pytest.mark.asyncio
    async def test_different_prefix_isolates_cache(self):
        """prefix 不同 → 不同 cache key"""
        _reset_call_count()
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        await decorated("personal/u1/", user_id=1, recursive=False)

        assert _call_count == 2
        assert len(_drive_list_cache) == 2

    @pytest.mark.asyncio
    async def test_different_recursive_isolates_cache(self):
        """recursive 不同 → 不同 cache key"""
        _reset_call_count()
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        await decorated("team/", user_id=1, recursive=True)

        assert _call_count == 2


# ============================================================================
# TestCacheExpiration — TTL 过期
# ============================================================================

class TestCacheExpiration:
    """TTL 过期后重新走真函数"""

    @pytest.mark.asyncio
    async def test_expired_cache_re_invokes(self, monkeypatch):
        """cache 过期 → 重新走真函数

        用 monkeypatch time.monotonic 模拟时间流逝
        """
        _reset_call_count()
        # monkeypatch 在装饰前, 让首次调用也用 fake time
        fake_time = [1000.0]

        def fake_monotonic():
            return fake_time[0]

        monkeypatch.setattr(
            "app.services.drive_cache.time.monotonic",
            fake_monotonic,
        )

        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        # 第 1 次 (fake time = 1000.0)
        await decorated("team/", user_id=1, recursive=False)
        assert _call_count == 1

        # 推进 fake time 到 1031.0 (过期 30s)
        fake_time[0] = 1031.0

        # 第 2 次 (距离第 1 次 31s fake time, 已过期)
        await decorated("team/", user_id=1, recursive=False)
        assert _call_count == 2  # 重新走真函数


# ============================================================================
# TestInvalidateCache — invalidate_drive_list_cache
# ============================================================================

class TestInvalidateCache:
    """invalidate_drive_list_cache prefix / full 失效"""

    @pytest.mark.asyncio
    async def test_partial_invalidate_by_prefix(self):
        """prefix 匹配 → 失效该 prefix 全部 cache"""
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        await decorated("team/", user_id=2, recursive=False)
        await decorated("personal/u3/", user_id=3, recursive=False)
        assert len(_drive_list_cache) == 3

        invalidate_drive_list_cache(prefix="team/")

        # team/ 两个失效, personal/u3/ 保留
        assert len(_drive_list_cache) == 1
        remaining_key = next(iter(_drive_list_cache.keys()))
        assert "personal/u3/" in remaining_key

    def test_full_invalidate_clears_all(self):
        """空 prefix → 失效全部"""
        _drive_list_cache["fake_key"] = (0.0, [])
        _drive_list_cache["another_key"] = (0.0, [])

        invalidate_drive_list_cache(prefix="")

        assert len(_drive_list_cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_then_recall_reruns_real_function(self):
        """invalidate 后再调 → 走真函数"""
        _reset_call_count()
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        assert _call_count == 1

        invalidate_drive_list_cache(prefix="team/")

        await decorated("team/", user_id=1, recursive=False)
        assert _call_count == 2  # 重新走真函数


# ============================================================================
# TestCacheStats — admin 调试接口
# ============================================================================

class TestCacheStats:
    """get_cache_stats() 返回 size/keys/oldest_age_sec"""

    @pytest.mark.asyncio
    async def test_empty_cache_stats(self):
        """空 cache → size=0"""
        stats = get_cache_stats()

        assert stats["size"] == 0
        assert stats["keys"] == []
        assert stats["oldest_age_sec"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_caching(self):
        """缓存后 → size/keys 正确"""
        decorated = cache_drive_list(ttl_sec=30)(_mock_list_files_real)

        await decorated("team/", user_id=1, recursive=False)
        await decorated("personal/u2/", user_id=2, recursive=False)

        stats = get_cache_stats()

        assert stats["size"] == 2
        assert len(stats["keys"]) == 2
        assert stats["oldest_age_sec"] >= 0.0
        # key 格式: "user:N|prefix:X|recursive:Y"
        assert any("user:1" in k for k in stats["keys"])
        assert any("user:2" in k for k in stats["keys"])

    def test_reset_cache_for_testing_clears_all(self):
        """reset_cache_for_testing 清空"""
        _drive_list_cache["fake"] = (0.0, [])

        reset_cache_for_testing()

        assert len(_drive_list_cache) == 0


# ============================================================================
# TestDriveCacheIntegrationPattern — 集成模式示例
# ============================================================================

class TestDriveCacheIntegrationPattern:
    """drive_service.list_files() 集成模式"""

    @pytest.mark.asyncio
    async def test_5th_wave_real_list_pattern(self):
        """5th-wave 教训: list_files 真没 cache, 加装饰器修复

        集成代码示例:
            @cache_drive_list(ttl_sec=30)
            async def list_files(prefix, user_id, recursive=False):
                # MinIO list_objects
                ...
        """
        _reset_call_count()

        # 模拟 drive_service.list_files (加装饰器)
        @cache_drive_list(ttl_sec=30)
        async def list_files(prefix: str, user_id: int, recursive: bool = False) -> list[dict]:
            return await _mock_list_files_real(prefix, user_id, recursive)

        # 第 1 次
        result1 = await list_files("team/", user_id=1)
        assert len(result1) == 3
        assert _call_count == 1

        # 第 2 次 (cache hit)
        result2 = await list_files("team/", user_id=1)
        assert result2 == result1
        assert _call_count == 1  # 没新增调用

        # delete 后 invalidate
        from app.services.drive_cache import invalidate_drive_list_cache
        invalidate_drive_list_cache(prefix="team/")

        # 第 3 次 (cache miss, 重新走真函数)
        result3 = await list_files("team/", user_id=1)
        assert len(result3) == 3
        assert _call_count == 2


# ============================================================================
# TestDecoratorMetadataPreservation — functools.wraps
# ============================================================================

class TestDecoratorMetadataPreservation:
    """functools.wraps 保留函数元数据"""

    @pytest.mark.asyncio
    async def test_function_name_preserved(self):
        """__name__ 保留"""
        @cache_drive_list(ttl_sec=30)
        async def my_special_list_func(prefix, user_id, recursive=False):
            return []

        assert my_special_list_func.__name__ == "my_special_list_func"

    @pytest.mark.asyncio
    async def test_docstring_preserved(self):
        """__doc__ 保留"""
        @cache_drive_list(ttl_sec=30)
        async def documented_func(prefix, user_id, recursive=False):
            """My special documentation."""
            return []

        assert documented_func.__doc__ == "My special documentation."