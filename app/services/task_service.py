from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional

from app.models.task import Task, TaskStatus, TaskPriority
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
            for r in reminders:
                self.db.add(Reminder(
                    task_id=task.id,
                    remind_at=r["remind_at"],
                    remind_type=r.get("remind_type", "wechat"),
                    status="pending"
                ))
            await self.db.commit()
        elif due_date and assignee_id:
            await self._create_default_reminders(task)

        return task

    async def _create_default_reminders(self, task: Task):
        """创建默认提醒"""
        if not task.due_date:
            return

        reminders = [
            # 提前2天提醒
            Reminder(
                task_id=task.id,
                remind_at=task.due_date - timedelta(days=2),
                remind_type="wechat",
                status="pending"
            ),
            # 当天提醒
            Reminder(
                task_id=task.id,
                remind_at=task.due_date.replace(hour=9, minute=0),
                remind_type="wechat",
                status="pending"
            )
        ]

        for reminder in reminders:
            self.db.add(reminder)

        await self.db.commit()

    async def get_task(self, task_id: int) -> Optional[Task]:
        """获取任务"""
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def get_tasks(
        self,
        assignee_id: Optional[int] = None,
        status: Optional[str] = None,
        project_id: Optional[int] = None,
        overdue: bool = False
    ) -> List[Task]:
        """查询任务列表"""
        query = select(Task)
        filters = []

        if assignee_id:
            filters.append(Task.assignee_id == assignee_id)
        if status:
            filters.append(Task.status == status)
        if project_id:
            filters.append(Task.project_id == project_id)
        if overdue:
            filters.append(and_(
                Task.due_date < datetime.utcnow(),
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
            task.completed_at = datetime.utcnow()
            task.progress = 100
        elif status == TaskStatus.IN_PROGRESS.value and not task.started_at:
            task.started_at = datetime.utcnow()

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
            "overdue": sum(1 for t in tasks if t.due_date and t.due_date < datetime.utcnow() and t.status != TaskStatus.DONE.value)
        }
