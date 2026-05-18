"""主动提醒调度器

定时检查：
- 即将到期的任务 → 提醒负责人
- 已逾期的任务 → 提醒负责人 + 老师
- 未确认的任务 → 提醒确认
- 会议前30分钟 → 提醒参会者
"""

import logging
from datetime import datetime, timedelta
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger("microbubble.wechat.scheduler")

from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.models.meeting import Meeting
from app.models.reminder import Reminder
from app.wechat.notifier import notifier
from app.wechat.bot import wechat_bot
from app.core.database import async_session


class ProactiveScheduler:
    """主动提醒调度器"""

    async def run_all_checks(self):
        """执行所有检查（由 Celery 定时调用）"""
        results = {}

        async with async_session() as db:
            results["due_soon"] = await self.check_due_soon(db)
            results["overdue"] = await self.check_overdue(db)
            results["unconfirmed"] = await self.check_unconfirmed(db)
            results["upcoming_meetings"] = await self.check_upcoming_meetings(db)

        return results

    async def check_due_soon(self, db: AsyncSession) -> int:
        """检查即将到期的任务（明天截止），提醒负责人"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow_end = tomorrow.replace(hour=23, minute=59, second=59)

        result = await db.execute(
            select(Task).where(
                and_(
                    Task.due_date <= tomorrow_end,
                    Task.due_date > datetime.utcnow(),
                    Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
                )
            )
        )
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            if not task.assignee_id:
                continue

            member = await db.get(Member, task.assignee_id)
            if not member or not member.wechat_id:
                continue

            try:
                days_left = (task.due_date - datetime.utcnow()).days
                if days_left <= 0:
                    time_text = "今天到期"
                else:
                    time_text = f"还有{days_left}天到期"

                content = f"⏰ 任务提醒\n\n📌 {task.title}\n📅 截止: {task.due_date.strftime('%Y-%m-%d')}\n⏳ {time_text}\n📊 进度: {task.progress}%\n\n请抓紧完成！"
                await wechat_bot.send_message(member.wechat_id, content)
                count += 1
            except Exception as e:
                logger.warning(f"提醒失败 [{member.name}]: {e}")

        return count

    async def check_overdue(self, db: AsyncSession) -> int:
        """检查已逾期的任务，提醒负责人 + 老师"""
        result = await db.execute(
            select(Task).where(
                and_(
                    Task.due_date < datetime.utcnow(),
                    Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
                )
            )
        )
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            if not task.assignee_id:
                continue

            member = await db.get(Member, task.assignee_id)
            if not member or not member.wechat_id:
                continue

            try:
                days_overdue = (datetime.utcnow() - task.due_date).days
                content = f"⚠️ 任务逾期\n\n📌 {task.title}\n📅 已逾期{days_overdue}天\n📊 进度: {task.progress}%\n\n请尽快处理！"
                await wechat_bot.send_message(member.wechat_id, content)

                # 同时通知老师
                if task.created_by:
                    creator = await db.get(Member, task.created_by)
                    if creator and creator.wechat_id:
                        teacher_msg = f"⚠️ 任务逾期通知\n\n📌 {task.title}\n👤 负责人: {member.name}\n📅 已逾期{days_overdue}天\n📊 进度: {task.progress}%"
                        await wechat_bot.send_message(creator.wechat_id, teacher_msg)

                count += 1
            except Exception as e:
                logger.warning(f"逾期提醒失败 [{member.name}]: {e}")

        return count

    async def check_unconfirmed(self, db: AsyncSession) -> int:
        """检查未确认的任务（分配超过24小时未回复）"""
        yesterday = datetime.utcnow() - timedelta(hours=24)

        result = await db.execute(
            select(Task).where(
                and_(
                    Task.created_at <= yesterday,
                    Task.status == TaskStatus.TODO.value,
                    Task.assignee_id.isnot(None)
                )
            )
        )
        tasks = result.scalars().all()

        count = 0
        for task in tasks:
            member = await db.get(Member, task.assignee_id)
            if not member or not member.wechat_id:
                continue

            try:
                content = f"📋 任务确认提醒\n\n📌 {task.title}\n⏰ 分配已超过24小时\n\n请回复「收到」确认，或说明情况。"
                await wechat_bot.send_message(member.wechat_id, content)
                count += 1
            except Exception as e:
                logger.warning(f"确认提醒失败 [{member.name}]: {e}")

        return count

    async def check_upcoming_meetings(self, db: AsyncSession) -> int:
        """检查30分钟内即将开始的会议"""
        now = datetime.utcnow()
        soon = now + timedelta(minutes=30)

        result = await db.execute(
            select(Meeting).where(
                and_(
                    Meeting.start_time <= soon,
                    Meeting.start_time > now,
                    Meeting.status != "cancelled"
                )
            )
        )
        meetings = result.scalars().all()

        count = 0
        for meeting in meetings:
            try:
                content = f"📅 会议提醒\n\n📌 {meeting.title}\n⏰ {meeting.start_time.strftime('%H:%M')}\n📍 {meeting.location or '未定'}\n\n请准时参加！"
                # 通知参与者
                if meeting.participants:
                    for participant in meeting.participants:
                        if participant.member_id:
                            member = await db.get(Member, participant.member_id)
                            if member and member.wechat_id:
                                await wechat_bot.send_message(member.wechat_id, content)
                                count += 1
            except Exception as e:
                logger.warning(f"会议提醒失败: {e}")

        return count


# 全局实例
scheduler = ProactiveScheduler()


# Celery 任务包装
@shared_task(name="app.wechat.scheduler.run_proactive_checks")
def run_proactive_checks():
    """Celery task: 执行主动提醒检查"""
    import asyncio

    async def _run():
        result = await scheduler.run_all_checks()
        logger.info(f"主动提醒完成: {result}")
        return result

    return asyncio.run(_run())
