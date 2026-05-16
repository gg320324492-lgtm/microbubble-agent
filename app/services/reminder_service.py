from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.models.task import Task
from app.models.member import Member
from app.models.reminder import Reminder


class ReminderService:
    """提醒服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_pending_reminders(self) -> List[Reminder]:
        """检查待发送的提醒"""
        now = datetime.utcnow()
        result = await self.db.execute(
            select(Reminder)
            .where(
                Reminder.remind_at <= now,
                Reminder.status == "pending"
            )
        )
        return result.scalars().all()

    async def send_reminder(self, reminder: Reminder) -> bool:
        """发送提醒"""
        # 获取任务信息
        task_result = await self.db.execute(
            select(Task).where(Task.id == reminder.task_id)
        )
        task = task_result.scalar_one_or_none()

        if not task or not task.assignee_id:
            return False

        # 获取成员信息
        member_result = await self.db.execute(
            select(Member).where(Member.id == task.assignee_id)
        )
        member = member_result.scalar_one_or_none()

        if not member:
            return False

        # 格式化提醒消息
        message = self._format_reminder_message(task, member)

        # 这里调用微信推送服务
        # await wechat_service.send_message(member.wechat_id, message)

        # 更新提醒状态
        reminder.status = "sent"
        reminder.sent_at = datetime.utcnow()
        await self.db.commit()

        return True

    def _format_reminder_message(self, task: Task, member: Member) -> str:
        """格式化提醒消息"""
        now = datetime.utcnow()
        days_left = (task.due_date - now).days if task.due_date else 0

        if days_left < 0:
            emoji = "⚠️"
            status = f"已逾期{abs(days_left)}天"
        elif days_left == 0:
            emoji = "🔔"
            status = "今天到期"
        elif days_left <= 2:
            emoji = "⏰"
            status = f"还有{days_left}天到期"
        else:
            emoji = "📋"
            status = f"还有{days_left}天到期"

        return f"""
{emoji} 任务提醒

{member.name}，你好！

你有一个任务即将到期：
📌 任务：{task.title}
📅 截止：{task.due_date.strftime('%Y-%m-%d')}
📊 状态：{status}
📈 进度：{task.progress}%

请及时处理！
"""

    async def process_reminders(self):
        """处理所有待发送提醒"""
        reminders = await self.check_pending_reminders()

        success_count = 0
        fail_count = 0

        for reminder in reminders:
            try:
                success = await self.send_reminder(reminder)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                fail_count += 1
                print(f"发送提醒失败: {e}")

        return {
            "total": len(reminders),
            "success": success_count,
            "fail": fail_count
        }


def process_reminders_task():
    """Celery task: 处理所有待发送提醒"""
    import asyncio
    from app.core.database import async_session

    async def _run():
        async with async_session() as db:
            service = ReminderService(db)
            result = await service.process_reminders()
            print(f"提醒处理完成: {result}")
            return result

    return asyncio.run(_run())
