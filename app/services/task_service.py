from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional

from app.models.base import utcnow
from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.models.reminder import Reminder


class TaskService:
    """任务服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        title: str,
        assignee_id: Optional[int] = None,
        project_id: Optional[int] = None,
        priority: str = "medium",
        due_date: Optional[datetime] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: str = "manual",
        created_by: Optional[int] = None,
        reminders: Optional[List[dict]] = None,
    ) -> Task:
        """创建任务"""
        task = Task(
            title=title,
            assignee_id=assignee_id,
            project_id=project_id,
            priority=priority,
            due_date=due_date,
            description=description,
            tags=tags,
            status=TaskStatus.TODO.value,
            source=source,
            created_by=created_by,
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # 创建提醒
        if reminders:
            created_reminders = []
            for r in reminders:
                rem = Reminder(
                    task_id=task.id,
                    remind_at=r["remind_at"],
                    remind_type=r.get("remind_type", "wechat"),
                    status="pending"
                )
                self.db.add(rem)
                created_reminders.append(rem)
            await self.db.commit()
            # 刷新获取 ID 后同步到 Redis
            for rem in created_reminders:
                await self.db.refresh(rem)
            await self._sync_reminders_to_redis(created_reminders)
        elif due_date and assignee_id:
            await self._create_default_reminders(task)

        return task

    async def _create_default_reminders(self, task: Task):
        """创建默认提醒（根据距截止时间的远近自动调整）"""
        if not task.due_date:
            return

        now = utcnow()
        time_until_due = task.due_date - now
        total_seconds = time_until_due.total_seconds()

        reminders = []

        if total_seconds <= 3600:
            # 1小时内到期：1分钟后提醒（即时提醒场景）
            reminders.append(Reminder(
                task_id=task.id,
                remind_at=now + timedelta(minutes=1),
                remind_type="wechat",
                status="pending"
            ))
        elif total_seconds <= 86400:
            # 24小时内到期：提前30分钟提醒
            remind_at = task.due_date - timedelta(minutes=30)
            if remind_at > now:
                reminders.append(Reminder(
                    task_id=task.id,
                    remind_at=remind_at,
                    remind_type="wechat",
                    status="pending"
                ))
        else:
            # 超过24小时：提前2天 + 提前2小时
            reminders.append(Reminder(
                task_id=task.id,
                remind_at=task.due_date - timedelta(days=2),
                remind_type="wechat",
                status="pending"
            ))
            reminders.append(Reminder(
                task_id=task.id,
                remind_at=task.due_date - timedelta(hours=2),
                remind_type="wechat",
                status="pending"
            ))

        for reminder in reminders:
            self.db.add(reminder)

        await self.db.commit()

        # 刷新获取 ID 后同步到 Redis
        for reminder in reminders:
            await self.db.refresh(reminder)
        await self._sync_reminders_to_redis(reminders)

    async def _sync_reminders_to_redis(self, reminders: list):
        """将提醒同步到 Redis 有序集合，实现秒级精确调度"""
        try:
            from app.services.reminder_scheduler import reminder_scheduler
            for rem in reminders:
                if rem.status == "pending" and rem.remind_at:
                    ts = rem.remind_at.timestamp()
                    await reminder_scheduler.add_reminder(rem.id, ts)
        except Exception as e:
            import logging
            logging.getLogger("microbubble.task").warning(f"提醒同步到Redis失败: {e}")

    async def get_task(self, task_id: int) -> Optional[Task]:
        """获取任务（排除已删除）"""
        result = await self.db.execute(
            select(Task).where(Task.id == task_id, Task.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_tasks(
        self,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        project_id: Optional[int] = None,
        overdue: bool = False
    ) -> List[Task]:
        """查询任务列表（排除已删除）"""
        query = select(Task)
        filters = [Task.deleted_at.is_(None)]

        if assignee_id:
            filters.append(Task.assignee_id == assignee_id)
        if status:
            filters.append(Task.status == status)
        if project_id:
            filters.append(Task.project_id == project_id)
        if overdue:
            filters.append(and_(
                Task.due_date < utcnow(),
                Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
            ))

        if filters:
            query = query.where(and_(*filters))

        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_task_status(
        self,
        task_id: int,
        status: str,
        progress: Optional[int] = None
    ) -> Optional[Task]:
        """更新任务状态"""
        task = await self.get_task(task_id)
        if not task:
            return None

        task.status = status

        if progress is not None:
            task.progress = progress

        if status == TaskStatus.DONE.value:
            task.completed_at = utcnow()
            task.progress = 100
        elif status == TaskStatus.IN_PROGRESS.value and not task.started_at:
            task.started_at = utcnow()

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_overdue_tasks(self) -> List[Task]:
        """获取逾期任务"""
        return await self.get_tasks(overdue=True)

    async def get_member_workload(self, member_id: int) -> dict:
        """获取成员工作量统计"""
        tasks = await self.get_tasks(assignee_id=member_id)

        return {
            "total": len(tasks),
            "todo": sum(1 for t in tasks if t.status == TaskStatus.TODO.value),
            "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS.value),
            "done": sum(1 for t in tasks if t.status == TaskStatus.DONE.value),
            "overdue": sum(1 for t in tasks if t.due_date and t.due_date < utcnow() and t.status != TaskStatus.DONE.value)
        }

    async def get_all_members_workload(self) -> List[dict]:
        """获取所有成员的任務统计（按成员分组，供管理员使用）"""
        # 获取所有活跃成员
        result = await self.db.execute(
            select(Member).where(Member.is_active == True)
        )
        members = result.scalars().all()

        # 获取所有任务
        all_tasks = await self.get_tasks()

        # 按成员分组
        member_stats = []
        for member in members:
            member_tasks = [t for t in all_tasks if t.assignee_id == member.id]
            member_stats.append({
                "member_id": member.id,
                "member_name": member.name,
                "role": member.role,
                "tasks": member_tasks,
                "total": len(member_tasks),
                "todo": sum(1 for t in member_tasks if t.status == TaskStatus.TODO.value),
                "in_progress": sum(1 for t in member_tasks if t.status == TaskStatus.IN_PROGRESS.value),
                "done": sum(1 for t in member_tasks if t.status == TaskStatus.DONE.value),
            })

        return member_stats
