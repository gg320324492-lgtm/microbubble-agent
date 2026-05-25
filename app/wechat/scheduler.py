"""主动提醒调度器

定时检查：
- 即将到期的任务 → 提醒负责人
- 已逾期的任务 → 提醒负责人 + 老师
- 未确认的任务 → 提醒确认

去重机制：Redis SET 记录已提醒的任务，24 小时过期，避免重复发送。
"""

import logging
from datetime import timedelta, timezone
from app.models.base import utcnow, BEIJING_TZ
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger("microbubble.wechat.scheduler")

from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.wechat.notifier import notifier
from app.wechat.bot import wechat_bot


class ProactiveScheduler:
    """主动提醒调度器"""

    async def _already_notified(self, redis_client, check_type: str, task_id: int) -> bool:
        """检查该任务在此检查类型下是否已提醒过"""
        if not redis_client:
            return False
        return await redis_client.sismember(f"scheduler:{check_type}:notified", str(task_id))

    async def _mark_notified(self, redis_client, check_type: str, task_id: int):
        """标记任务已提醒，SET 整体 24 小时过期"""
        if not redis_client:
            return
        key = f"scheduler:{check_type}:notified"
        await redis_client.sadd(key, str(task_id))
        await redis_client.expire(key, 86400)

    async def run_all_checks(self, db: AsyncSession, redis_client=None):
        """执行所有检查（由 Celery 定时调用）"""
        results = {}
        results["due_soon"] = await self.check_due_soon(db, redis_client)
        results["overdue"] = await self.check_overdue(db, redis_client)
        results["unconfirmed"] = await self.check_unconfirmed(db, redis_client)
        return results

    async def check_due_soon(self, db: AsyncSession, redis_client=None) -> int:
        """检查即将到期的任务（明天截止），提醒负责人 + 通知创建人"""
        tomorrow = utcnow() + timedelta(days=1)
        tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)

        result = await db.execute(
            select(Task).where(
                and_(
                    Task.due_date <= tomorrow_end,
                    Task.due_date > utcnow(),
                    Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
                )
            )
        )
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            if not task.assignee_id:
                continue

            if await self._already_notified(redis_client, "due_soon", task.id):
                continue

            member = await db.get(Member, task.assignee_id)
            if not member or (not member.wechat_id and not member.external_userid):
                continue

            try:
                total_seconds = (task.due_date - utcnow()).total_seconds()
                if total_seconds <= 0:
                    time_text = "已到期"
                elif total_seconds < 3600:
                    time_text = f"还有{int(total_seconds // 60)}分钟到期"
                elif total_seconds < 86400:
                    time_text = f"还有{int(total_seconds // 3600)}小时到期"
                else:
                    time_text = f"还有{int(total_seconds // 86400)}天到期"

                beijing_tz = BEIJING_TZ
                due_date_beijing = task.due_date.replace(tzinfo=timezone.utc).astimezone(beijing_tz)
                due_date_str = due_date_beijing.strftime('%Y-%m-%d %H:%M')

                # 通知负责人
                content = f"⏰ 任务提醒\n\n📌 {task.title}\n📅 截止: {due_date_str}\n⏳ {time_text}\n📊 进度: {task.progress}%\n\n请抓紧完成！"
                await wechat_bot.smart_send(member, content)

                # 通知创建人
                if task.created_by and task.created_by != task.assignee_id:
                    creator = await db.get(Member, task.created_by)
                    if creator and (creator.wechat_id or creator.external_userid):
                        try:
                            await notifier.notify_due_soon_to_creator(
                                creator=creator,
                                task_title=task.title,
                                assignee_name=member.name,
                                due_date=due_date_str,
                                time_left=time_text,
                                progress=task.progress,
                            )
                        except Exception as e:
                            logger.warning(f"创建人到期提醒失败 [{creator.name}]: {e}")

                await self._mark_notified(redis_client, "due_soon", task.id)
                count += 1
            except Exception as e:
                logger.warning(f"提醒失败 [{member.name}]: {e}")

        return count

    async def check_overdue(self, db: AsyncSession, redis_client=None) -> int:
        """检查已逾期的任务，提醒负责人 + 通知创建人"""
        result = await db.execute(
            select(Task).where(
                and_(
                    Task.due_date < utcnow(),
                    Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
                )
            )
        )
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            if not task.assignee_id:
                continue

            if await self._already_notified(redis_client, "overdue", task.id):
                continue

            member = await db.get(Member, task.assignee_id)

            try:
                total_seconds = (utcnow() - task.due_date).total_seconds()
                hours_overdue = int(total_seconds // 3600)
                if hours_overdue < 24:
                    overdue_text = f"已逾期{hours_overdue}小时"
                else:
                    overdue_text = f"已逾期{hours_overdue // 24}天"

                # 给负责人发通知
                if member and (member.wechat_id or member.external_userid):
                    content = f"⚠️ 任务逾期\n\n📌 {task.title}\n📅 {overdue_text}\n📊 进度: {task.progress}%\n\n请尽快处理！"
                    await wechat_bot.smart_send(member, content)

                # 通知创建人（无论负责人是否收到都通知）
                if task.created_by:
                    creator = await db.get(Member, task.created_by)
                    if creator and (creator.wechat_id or creator.external_userid):
                        assignee_name = member.name if member else "未知"
                        teacher_msg = f"⚠️ 任务逾期通知\n\n📌 {task.title}\n👤 负责人: {assignee_name}\n📅 {overdue_text}\n📊 进度: {task.progress}%"
                        await wechat_bot.smart_send(creator, teacher_msg)

                await self._mark_notified(redis_client, "overdue", task.id)
                count += 1
            except Exception as e:
                logger.warning(f"逾期提醒失败 [{task.title}]: {e}")

        return count

    async def check_unconfirmed(self, db: AsyncSession, redis_client=None) -> int:
        """检查未确认的任务（分配超过24小时未回复）"""
        yesterday = utcnow() - timedelta(hours=24)

        result = await db.execute(
            select(Task).where(
                and_(
                    Task.created_at <= yesterday,
                    Task.status.in_([TaskStatus.TODO.value, TaskStatus.IN_PROGRESS.value, TaskStatus.BLOCKED.value]),
                    Task.assignee_id.isnot(None)
                )
            )
        )
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            if await self._already_notified(redis_client, "unconfirmed", task.id):
                continue

            member = await db.get(Member, task.assignee_id)
            if not member or (not member.wechat_id and not member.external_userid):
                continue

            try:
                content = f"📋 任务确认提醒\n\n📌 {task.title}\n⏰ 分配已超过24小时\n\n请回复「收到」确认，或说明情况。"
                await wechat_bot.smart_send(member, content)
                await self._mark_notified(redis_client, "unconfirmed", task.id)
                count += 1
            except Exception as e:
                logger.warning(f"确认提醒失败 [{member.name}]: {e}")

        return count


# 全局实例
scheduler = ProactiveScheduler()


# Celery 任务包装
@shared_task(name="app.wechat.scheduler.run_proactive_checks")
def run_proactive_checks():
    """Celery task: 执行主动提醒检查"""
    import asyncio
    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.config import settings

    async def _run():
        engine = create_async_engine(
            settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
            poolclass=NullPool,
        )
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with async_session_factory() as db:
                result = await scheduler.run_all_checks(db, redis_client=redis_client)
                logger.info(f"主动提醒完成: {result}")
                return result
        finally:
            await redis_client.aclose()
            await engine.dispose()

    return asyncio.run(_run())
