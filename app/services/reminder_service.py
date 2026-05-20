import logging
from datetime import datetime, timedelta, timezone
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.models.base import utcnow, BEIJING_TZ
from app.models.task import Task
from app.models.member import Member
from app.models.reminder import Reminder
from app.wechat.bot import wechat_bot

logger = logging.getLogger("microbubble.reminder")


class ReminderService:
    """提醒服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_pending_reminders(self) -> List[Reminder]:
        """检查待发送的提醒"""
        now = utcnow()
        result = await self.db.execute(
            select(Reminder)
            .where(
                Reminder.remind_at <= now,
                Reminder.status == "pending"
            )
        )
        return result.scalars().all()

    async def send_reminder(self, reminder: Reminder) -> bool:
        """发送提醒，只在成功时标记为 sent"""
        task_result = await self.db.execute(
            select(Task).where(Task.id == reminder.task_id)
        )
        task = task_result.scalar_one_or_none()

        if not task or not task.assignee_id:
            logger.warning(f"提醒 {reminder.id} 无法发送: task不存在或无负责人")
            return False

        member_result = await self.db.execute(
            select(Member).where(Member.id == task.assignee_id)
        )
        member = member_result.scalar_one_or_none()

        if not member:
            logger.warning(f"提醒 {reminder.id} 无法发送: 成员不存在 id={task.assignee_id}")
            return False

        if not member.wechat_id and not member.external_userid:
            logger.warning(f"提醒 {reminder.id} 无法发送: 成员 {member.name} 无微信标识")
            return False

        message = self._format_reminder_message(task, member)

        try:
            result = await wechat_bot.smart_send(member, message)
            errcode = result.get("errcode", -1) if isinstance(result, dict) else -1
            if errcode != 0:
                logger.warning(f"微信推送返回错误: {result}, member={member.name}")
                return False
            logger.info(f"微信推送成功: member={member.name}")
        except Exception as e:
            logger.warning(f"微信推送失败: {e}")
            return False

        # 只有发送成功才标记
        reminder.status = "sent"
        reminder.sent_at = utcnow()
        await self.db.commit()
        return True

    def _format_reminder_message(self, task: Task, member: Member) -> str:
        """格式化提醒消息"""
        now = utcnow()
        if not task.due_date:
            return f"📋 任务提醒\n\n{member.name}，你好！\n📌 任务：{task.title}\n📊 进度：{task.progress}%"

        due_date_beijing = task.due_date.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
        diff = task.due_date - now
        total_seconds = diff.total_seconds()

        if total_seconds < 0:
            emoji = "⚠️"
            hours_overdue = int(abs(total_seconds) // 3600)
            if hours_overdue < 24:
                status = f"已逾期{hours_overdue}小时"
            else:
                days = hours_overdue // 24
                status = f"已逾期{days}天"
        elif total_seconds < 3600:
            emoji = "🔔"
            minutes_left = int(total_seconds // 60)
            status = f"还有{minutes_left}分钟到期"
        elif total_seconds < 86400:
            emoji = "🔔"
            hours_left = int(total_seconds // 3600)
            status = f"还有{hours_left}小时到期"
        elif total_seconds <= 172800:
            emoji = "⏰"
            status = f"还有1天到期"
        else:
            emoji = "📋"
            days_left = int(total_seconds // 86400)
            status = f"还有{days_left}天到期"

        return f"""
{emoji} 任务提醒

{member.name}，你好！

你有一个任务即将到期：
📌 任务：{task.title}
📅 截止：{due_date_beijing.strftime('%Y-%m-%d %H:%M')}
📊 状态：{status}
📈 进度：{task.progress}%

请及时处理！
"""

    async def process_reminders(self, redis_override=None):
        """处理所有待发送提醒（优先从 Redis 获取，秒级精度）"""
        import time
        from app.services.reminder_scheduler import reminder_scheduler, ZSET_KEY

        # 使用传入的 Redis 客户端（Celery 任务）或全局的（API 调用）
        r = redis_override
        use_override = r is not None

        if use_override:
            # 直接用传入的 Redis 客户端操作 ZSET
            now = time.time()
            due_bytes = await r.zrangebyscore(ZSET_KEY, 0, now)
            due_ids = [int(rid) for rid in due_bytes]
        else:
            due_ids = await reminder_scheduler.get_due_reminders()

        if not due_ids:
            # Redis 为空时从 DB 兜底，并同步到 Redis
            try:
                db_reminders = await self.check_pending_reminders()
                if db_reminders:
                    mapping = {str(r_.id): r_.remind_at.timestamp() for r_ in db_reminders}
                    if use_override:
                        await r.zadd(ZSET_KEY, mapping)
                    else:
                        await reminder_scheduler.sync_from_db([
                            {"id": r_.id, "remind_at_ts": r_.remind_at.timestamp()}
                            for r_ in db_reminders
                        ])
                    # 重新获取
                    if use_override:
                        now = time.time()
                        due_bytes = await r.zrangebyscore(ZSET_KEY, 0, now)
                        due_ids = [int(rid) for rid in due_bytes]
                    else:
                        due_ids = await reminder_scheduler.get_due_reminders()
            except Exception as e:
                logger.warning(f"从DB同步提醒失败: {e}")

        if not due_ids:
            return {"total": 0, "success": 0, "fail": 0}

        # 从数据库获取提醒详情
        try:
            result = await self.db.execute(
                select(Reminder).where(Reminder.id.in_(due_ids))
            )
            reminders = result.scalars().all()
        except Exception as e:
            logger.error(f"查询提醒失败: {e}")
            return {"total": 0, "success": 0, "fail": 0}

        success_count = 0
        fail_count = 0
        sent_ids = []

        for reminder in reminders:
            if reminder.status != "pending":
                sent_ids.append(reminder.id)
                continue
            try:
                success = await self.send_reminder(reminder)
                if success:
                    success_count += 1
                    sent_ids.append(reminder.id)
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                logger.warning(f"发送提醒失败: {e}")

        # 从 Redis 移除已处理的提醒
        if sent_ids:
            if use_override:
                await r.zrem(ZSET_KEY, *[str(sid) for sid in sent_ids])
            else:
                await reminder_scheduler.remove_batch(sent_ids)

        return {
            "total": len(reminders),
            "success": success_count,
            "fail": fail_count
        }


@shared_task(name="app.services.reminder_service.process_reminders_task")
def process_reminders_task():
    """Celery task: 处理所有待发送提醒"""
    import asyncio
    import time as _time
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.config import settings

    async def _run():
        # 创建独立的引擎和 Redis 连接，避免跨事件循环的连接池冲突
        engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            poolclass=NullPool,
        )
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with async_session_factory() as db:
                service = ReminderService(db)
                result = await service.process_reminders(redis_override=redis_client)
                print(f"提醒处理完成: {result}")
                return result
        finally:
            await redis_client.aclose()
            await engine.dispose()

    return asyncio.run(_run())
