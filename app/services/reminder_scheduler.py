"""基于 Redis 的精确提醒调度器

使用 Redis 有序集合（ZSET）存储待触发的提醒，
分数为 remind_at 的 Unix 时间戳。
Celery 每10秒扫描一次到期提醒，精度可达秒级。
"""

import json
import logging
import time
from typing import List, Dict, Optional

from app.core.redis import get_redis

logger = logging.getLogger("microbubble.reminder_scheduler")

ZSET_KEY = "reminders:pending"


class RedisReminderScheduler:
    """Redis 精确提醒调度器"""

    async def add_reminder(self, reminder_id: int, remind_at_timestamp: float):
        """添加提醒到 Redis 有序集合"""
        r = await get_redis()
        await r.zadd(ZSET_KEY, {str(reminder_id): remind_at_timestamp})
        logger.debug(f"提醒 {reminder_id} 已加入调度，触发时间: {remind_at_timestamp}")

    async def remove_reminder(self, reminder_id: int):
        """从 Redis 中移除提醒"""
        r = await get_redis()
        await r.zrem(ZSET_KEY, str(reminder_id))

    async def get_due_reminders(self) -> List[int]:
        """获取所有到期的提醒 ID（分数 <= 当前时间戳）"""
        r = await get_redis()
        now = time.time()
        # ZRANGEBYSCORE: 获取分数在 [0, now] 范围内的成员
        due = await r.zrangebyscore(ZSET_KEY, 0, now)
        return [int(rid) for rid in due]

    async def remove_batch(self, reminder_ids: List[int]):
        """批量移除已处理的提醒"""
        if not reminder_ids:
            return
        r = await get_redis()
        await r.zrem(ZSET_KEY, *[str(rid) for rid in reminder_ids])

    async def get_pending_count(self) -> int:
        """获取待触发提醒总数"""
        r = await get_redis()
        return await r.zcard(ZSET_KEY)

    async def sync_from_db(self, db_reminders: List[Dict]):
        """从数据库同步待发送提醒到 Redis（启动时或恢复时使用）"""
        r = await get_redis()
        mapping = {}
        for rem in db_reminders:
            mapping[str(rem["id"])] = rem["remind_at_ts"]
        if mapping:
            await r.zadd(ZSET_KEY, mapping)
            logger.info(f"从数据库同步 {len(mapping)} 条提醒到 Redis")


# 全局实例
reminder_scheduler = RedisReminderScheduler()
