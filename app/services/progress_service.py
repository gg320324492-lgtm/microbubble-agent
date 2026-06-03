"""会议挂断后处理进度服务

职责：
- 写入进度状态到 Redis HASH
- 通过 Redis pub/sub 推送给订阅者
- 提供 REST 查询接口

Redis Key 规范：
- progress:{meeting_id} HASH
  - 字段: stage / detail / percent / status / started_at / updated_at
  - TTL: 1 小时
- progress:{meeting_id} channel (pub/sub)
"""
import json
import logging
import time
from enum import Enum

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.progress")

PROGRESS_TTL_SECONDS = 3600  # 1h
TOTAL_STAGES = 6  # 不含 done


class ProgressStage(str, Enum):
    EXTRACTING_TRANSCRIPT = "extracting_transcript"  # 0
    POLISHING_TRANSCRIPT = "polishing_transcript"    # 1  (2026-06-02 新增：L3 全文精润色)
    IDENTIFYING_SPEAKERS = "identifying_speakers"    # 2
    GENERATING_TITLE = "generating_title"            # 3
    GENERATING_MINUTES = "generating_minutes"        # 4
    CREATING_TASKS = "creating_tasks"                # 5
    LINKING_HISTORY = "linking_history"              # 6
    DONE = "done"                                    # 7


STAGE_ORDER = [s.value for s in ProgressStage]


def _key(meeting_id: int) -> str:
    return f"progress:{meeting_id}"


def _channel(meeting_id: int) -> str:
    return f"progress:{meeting_id}"


async def init_progress(meeting_id: int) -> None:
    """初始化进度：HSET progress:{id} 所有字段"""
    r = await get_redis()
    now = int(time.time())
    key = _key(meeting_id)
    await r.hset(key, mapping={
        "stage": ProgressStage.EXTRACTING_TRANSCRIPT.value,
        "detail": "准备开始处理",
        "percent": 0.0,
        "status": "running",
        "started_at": now,
        "updated_at": now,
    })
    await r.expire(key, PROGRESS_TTL_SECONDS)
    logger.info(f"进度初始化: meeting_id={meeting_id}")


async def update_progress(
    meeting_id: int,
    stage: ProgressStage,
    detail: str | None = None,
    percent: float | None = None,
    status: str = "running",
    redis_override=None,
) -> None:
    """
    更新进度：HSET + PUBLISH
    1. 计算 stage_index
    2. HSET progress:{id}
    3. PUBLISH progress:{id} channel
    4. DONE 状态保留 TTL
    """
    r = redis_override if redis_override is not None else await get_redis()
    now = int(time.time())
    key = _key(meeting_id)
    channel = _channel(meeting_id)

    # 默认 percent 按阶段计算
    if percent is None:
        try:
            stage_index = STAGE_ORDER.index(stage.value)
            percent = round(stage_index / TOTAL_STAGES * 100, 1)
        except ValueError:
            percent = 0.0

    update_data = {
        "stage": stage.value,
        "detail": detail or "",
        "percent": percent,
        "status": status,
        "updated_at": now,
    }
    if stage == ProgressStage.DONE:
        update_data["percent"] = 100.0
        update_data["status"] = "done"

    await r.hset(key, mapping=update_data)
    if stage == ProgressStage.DONE:
        await r.expire(key, PROGRESS_TTL_SECONDS)

    # pub/sub 推送
    message = json.dumps({
        "type": "progress_update",
        "data": update_data,
    }, ensure_ascii=False)
    await r.publish(channel, message)
    logger.debug(f"进度更新: meeting_id={meeting_id}, stage={stage.value}, percent={percent}%")


async def get_progress(meeting_id: int) -> dict | None:
    """REST 端点用，HGETALL progress:{id}"""
    r = await get_redis()
    data = await r.hgetall(_key(meeting_id))
    if not data:
        return None
    # 类型转换
    if "percent" in data:
        data["percent"] = float(data["percent"])
    if "started_at" in data:
        data["started_at"] = int(data["started_at"])
    if "updated_at" in data:
        data["updated_at"] = int(data["updated_at"])
    return data


async def cleanup_progress(meeting_id: int) -> None:
    """清理进度（HGETALL 返回空时无操作）"""
    r = await get_redis()
    await r.delete(_key(meeting_id))
