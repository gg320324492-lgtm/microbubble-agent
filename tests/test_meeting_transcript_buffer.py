"""Tests for meeting_transcript_buffer — Redis LIST sliding window.

Uses real Redis (configured via REDIS_URL) since the module's contract
is precisely about Redis LIST semantics (RPUSH / LTRIM / EXPIRE / LRANGE).
SKIP_DB_SETUP=1 is fine — only the DB fixtures are gated, Redis is open.
"""

import time

import pytest

from app.services.meeting_transcript_buffer import (
    append_transcript,
    get_recent_transcript,
)


@pytest.mark.asyncio
async def test_append_and_get_recent():
    """append + get_recent_transcript 时间过滤"""
    meeting_id = 99001
    now = time.time()

    # 清空
    from app.core.redis import get_redis
    r = await get_redis()
    await r.delete(f"meeting:{meeting_id}:transcript")

    # 追加 3 条
    await append_transcript(meeting_id, {"speaker": "A", "text": "1秒前", "ts": now - 1})
    await append_transcript(meeting_id, {"speaker": "A", "text": "10秒前", "ts": now - 10})
    await append_transcript(meeting_id, {"speaker": "A", "text": "40秒前", "ts": now - 40})

    try:
        # 获取最近 30 秒：应返回 2 条（1秒 + 10秒前）
        recent = await get_recent_transcript(meeting_id, seconds=30)
        assert len(recent) == 2
        texts = [e["text"] for e in recent]
        assert "1秒前" in texts
        assert "10秒前" in texts
        assert "40秒前" not in texts
    finally:
        await r.delete(f"meeting:{meeting_id}:transcript")


@pytest.mark.asyncio
async def test_maxlen_200():
    """超过 200 自动 trim"""
    meeting_id = 99002
    from app.core.redis import get_redis
    r = await get_redis()
    await r.delete(f"meeting:{meeting_id}:transcript")

    # 追加 250 条
    for i in range(250):
        await append_transcript(meeting_id, {"speaker": "A", "text": f"msg-{i}", "ts": time.time()})

    try:
        # LTRIM 应保留最后 200
        length = await r.llen(f"meeting:{meeting_id}:transcript")
        assert length == 200
    finally:
        await r.delete(f"meeting:{meeting_id}:transcript")
