"""会议多设备广播服务（Redis pub/sub）

频道命名：
- transcript:{meeting_id} - 转录增量广播
- ai_reply:{meeting_id} - AI 回复广播
- speaker_mapping:{meeting_id} - speaker_mapping 更新广播
"""
import json
import logging

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.broadcast")


async def publish_transcript(meeting_id: int, entry: dict) -> None:
    """广播 transcript 增量（同会议其他设备）"""
    r = await get_redis()
    await r.publish(f"transcript:{meeting_id}", json.dumps(entry, ensure_ascii=False))


async def publish_ai_reply(meeting_id: int, reply: dict) -> None:
    """广播 AI 回复（同会议其他设备）"""
    r = await get_redis()
    await r.publish(f"ai_reply:{meeting_id}", json.dumps(reply, ensure_ascii=False))


async def publish_speaker_mapping(meeting_id: int, mapping: dict) -> None:
    """广播 speaker_mapping 更新"""
    r = await get_redis()
    await r.publish(f"speaker_mapping:{meeting_id}", json.dumps(mapping, ensure_ascii=False))
