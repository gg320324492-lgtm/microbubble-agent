"""录音心跳会话化测试（2026-11-16 长会议/上传收尾加固）。

覆盖：
- 新旧 Redis value 格式解析
- touch 写入 ts|session_id|phase 且 TTL=300
- is_recording_alive 在 Redis 异常时保守返回 True
- is_upload_finalizing 的新鲜/过期/phase 错误三态
- clear_recording_heartbeat 删除 key
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import recording_heartbeat as hb


def _run(coro):
    return asyncio.run(coro)


class _FakeRedis:
    def __init__(self, values=None, exists_error=False):
        self.values = dict(values or {})
        self.exists_error = exists_error
        self.set_calls = []
        self.delete_calls = []
        self.aclose = AsyncMock(return_value=None)

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.set_calls.append((key, value, ex))
        await asyncio.sleep(0)

    async def exists(self, key):
        if self.exists_error:
            raise RuntimeError("Redis down")
        await asyncio.sleep(0)
        return 1 if key in self.values else 0

    async def delete(self, key):
        self.delete_calls.append(key)
        self.values.pop(key, None)
        return 1


def test_parse_new_and_legacy_heartbeat_values():
    now = int(time.time())
    parsed = hb._parse_heartbeat_value(f"{now}|sess-1|uploading")
    assert parsed["ts"] == float(now)
    assert parsed["session_id"] == "sess-1"
    assert parsed["phase"] == "uploading"

    legacy = hb._parse_heartbeat_value(str(now))
    assert legacy["ts"] == float(now)
    assert legacy["session_id"] == ""
    assert legacy["phase"] == ""

    assert hb._parse_heartbeat_value(None) is None
    assert hb._parse_heartbeat_value("not-a-timestamp") is None


def test_touch_writes_session_heartbeat_with_ttl_300():
    redis = _FakeRedis()
    with patch.object(hb, "_get_client", AsyncMock(return_value=redis)):
        assert _run(hb.touch_recording_heartbeat(278, "sess-9", "finalizing")) is True

    key, value, ttl = redis.set_calls[0]
    assert key == hb.heartbeat_key(278)
    assert ttl == 300
    ts, session_id, phase = value.split("|")
    assert int(ts) <= int(time.time())
    assert session_id == "sess-9"
    assert phase == "finalizing"
    redis.aclose.assert_awaited_once()


def test_touch_failure_is_best_effort():
    with patch.object(hb, "_get_client", AsyncMock(side_effect=RuntimeError("Redis down"))):
        assert _run(hb.touch_recording_heartbeat(278)) is False


def test_read_recording_heartbeat_parses_old_pure_timestamp():
    key = hb.heartbeat_key(255)
    now = int(time.time())
    redis = _FakeRedis({key: str(now)})
    got = _run(hb.read_recording_heartbeat(255, redis_client=redis))
    assert got["ts"] == float(now)
    assert got["session_id"] == ""


def test_is_recording_alive_stays_true_on_redis_error():
    redis = _FakeRedis(exists_error=True)
    assert _run(hb.is_recording_alive(255, redis_client=redis)) is True


def test_is_upload_finalizing_fresh_and_expired_and_wrong_phase():
    key = hb.heartbeat_key(278)
    now = time.time()
    fresh = _FakeRedis({key: f"{int(now)}|sess-1|finalizing"})
    assert _run(hb.is_upload_finalizing(278, redis_client=fresh)) is True

    uploading = _FakeRedis({key: f"{int(now)}|sess-1|uploading"})
    assert _run(hb.is_upload_finalizing(278, redis_client=uploading)) is True

    expired = _FakeRedis({key: f"{int(now - 601)}|sess-1|finalizing"})
    assert _run(hb.is_upload_finalizing(278, redis_client=expired)) is False

    wrong_phase = _FakeRedis({key: f"{int(now)}|sess-1|recording"})
    assert _run(hb.is_upload_finalizing(278, redis_client=wrong_phase)) is False


def test_clear_recording_heartbeat_deletes_key():
    key = hb.heartbeat_key(278)
    redis = _FakeRedis({key: f"{int(time.time())}|sess-1|finalizing"})
    assert _run(hb.clear_recording_heartbeat(278, redis_client=redis)) is True
    assert redis.delete_calls == [key]
    assert key not in redis.values
