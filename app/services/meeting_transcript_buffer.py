"""会议转录滑动窗口（Redis LIST）

职责：每条 transcript 追加到 Redis LIST，限长 200，提供"最近 N 秒"查询。
"""
import json
import logging
import time

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.transcript_buffer")

MAX_TRANSCRIPT_ENTRIES = 200
TRANSCRIPT_TTL_SECONDS = 86400  # 24h


async def append_transcript(meeting_id: int, entry: dict) -> None:
    """追加一条 transcript 到 Redis LIST，限长 200"""
    r = await get_redis()
    key = f"meeting:{meeting_id}:transcript"
    await r.rpush(key, json.dumps(entry, ensure_ascii=False))
    await r.ltrim(key, -MAX_TRANSCRIPT_ENTRIES, -1)
    await r.expire(key, TRANSCRIPT_TTL_SECONDS)


async def get_recent_transcript(meeting_id: int, seconds: int = 30) -> list[dict]:
    """获取最近 N 秒的转录条目（按 ts 过滤）"""
    r = await get_redis()
    key = f"meeting:{meeting_id}:transcript"
    raw_entries = await r.lrange(key, -MAX_TRANSCRIPT_ENTRIES, -1)
    if not raw_entries:
        return []
    now = time.time()
    entries = []
    for raw in raw_entries:
        try:
            entry = json.loads(raw)
            if now - entry.get("ts", 0) <= seconds:
                entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries
