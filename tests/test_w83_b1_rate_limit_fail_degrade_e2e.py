"""W83 B-1 P1-1: rate_limit fail-degraded-allow e2e

验证 Redis 挂时:
1. ``AsyncRedisRateLimiter.check`` 仍允许请求通过 (不阻断业务)
2. 内部 logger.warning 被打 (不再静默吞错)
3. ``AsyncRedisRateLimiter.remaining`` 降级返回 reduced_quota (max_attempts // 2)
4. middleware 响应头 X-RateLimit-Degraded=1
5. ``AsyncRedisRateLimiter.record`` 同样 fail-degrade + warning

类比: W82 B-1 celery fail-safe (fail-soft + 告警 + 不阻断)
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.core.rate_limit import AsyncRedisRateLimiter


class FakeBrokenRedis:
    """模拟 Redis 客户端所有调用都抛 ConnectionError (Redis 挂)."""

    async def zremrangebyscore(self, *args, **kwargs):
        raise ConnectionError("simulated redis down")

    async def zcard(self, *args, **kwargs):
        raise ConnectionError("simulated redis down")

    async def zadd(self, *args, **kwargs):
        raise ConnectionError("simulated redis down")

    async def expire(self, *args, **kwargs):
        raise ConnectionError("simulated redis down")


class FakeWorkingRedis:
    """模拟 Redis 正常工作."""

    def __init__(self):
        self.zset = {}

    async def zremrangebyscore(self, key, min_score, max_score):
        if key not in self.zset:
            return 0
        before = len(self.zset[key])
        self.zset[key] = {s: v for s, v in self.zset[key].items() if float(s) > float(min_score)}
        return before - len(self.zset[key])

    async def zcard(self, key):
        return len(self.zset.get(key, {}))

    async def zadd(self, key, mapping):
        self.zset.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def expire(self, key, seconds):
        return 1


class TestW83B1RateLimitFailDegrade:
    """W83 B-1 P1-1: Redis 挂时 fail-degraded-allow 路径."""

    @pytest.mark.asyncio
    async def test_check_passes_when_redis_down_fail_degrade(self, caplog):
        """P1-1.1: Redis 挂时 check 不抛 (不是 fail-closed), 不阻断业务."""
        limiter = AsyncRedisRateLimiter(max_attempts=5, window_seconds=60)
        with patch("app.core.redis.get_redis", AsyncMock(return_value=FakeBrokenRedis())):
            with caplog.at_level(logging.WARNING, logger="microbubble.rate_limit"):
                # 必须不抛 — fail-degraded-allow 路径
                await limiter.check("test:key")
                assert any("fail-degrade" in r.message for r in caplog.records), \
                    "expected fail-degrade warning logged"

    @pytest.mark.asyncio
    async def test_record_passes_when_redis_down_fail_degrade(self, caplog):
        """P1-1.2: Redis 挂时 record 不抛 + warning."""
        limiter = AsyncRedisRateLimiter(max_attempts=5, window_seconds=60)
        with patch("app.core.redis.get_redis", AsyncMock(return_value=FakeBrokenRedis())):
            with caplog.at_level(logging.WARNING, logger="microbubble.rate_limit"):
                await limiter.record("test:key")
                assert any("fail-degrade" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_remaining_returns_reduced_quota_when_redis_down(self):
        """P1-1.3: Redis 挂时 remaining 返 max_attempts//2 (reduced_quota, 不再是满配额)."""
        limiter = AsyncRedisRateLimiter(max_attempts=10, window_seconds=60)
        with patch("app.core.redis.get_redis", AsyncMock(return_value=FakeBrokenRedis())):
            r = await limiter.remaining("test:key")
            assert r == 5, f"expected reduced_quota 5 (max_attempts//2), got {r}"

    @pytest.mark.asyncio
    async def test_check_still_raises_429_on_real_overflow(self):
        """P1-1.4: Redis 正常 + 真超限 → 429 仍然 raise (regression 守卫)."""
        limiter = AsyncRedisRateLimiter(max_attempts=3, window_seconds=60)
        fake = FakeWorkingRedis()
        # 预填 3 个 timestamp → 触顶
        for i in range(3):
            await fake.zadd("rl:test:key", {str(1000.0 + i): 1000.0 + i})
        with patch("app.core.redis.get_redis", AsyncMock(return_value=fake)):
            with pytest.raises(HTTPException) as exc_info:
                await limiter.check("test:key")
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_check_passes_when_redis_working(self):
        """P1-1.5: Redis 正常工作 → check 不抛 (regression 守卫)."""
        limiter = AsyncRedisRateLimiter(max_attempts=10, window_seconds=60)
        with patch("app.core.redis.get_redis", AsyncMock(return_value=FakeWorkingRedis())):
            await limiter.check("test:key")  # 必须不抛