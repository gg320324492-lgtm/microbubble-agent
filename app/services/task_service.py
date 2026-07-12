from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app
from app.config import settings
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
            status=TaskStatus.IN_PROGRESS.value,
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
        """v2 策略：1 task = 1 reminder，统一在下次 11AM 北京时间窗口发送

        2026-06-15 任务提醒体系全面优化：
        - 不再根据 due_date 距离远近创建多条 reminder
        - 1 个任务只创建 1 条 reminder，remind_at 落点 = next_digest_slot(task.due_date)
        - 详见 C:\\Users\\admin\\.claude\\plans\\snappy-coalescing-quiche.md
        """
        if not task.due_date:
            return

        from app.services.reminder_policy import (
            next_digest_slot,
            batch_date_for,
        )

        remind_at = next_digest_slot(task.due_date)
        batch_date = batch_date_for(task.due_date)

        reminder = Reminder(
            task_id=task.id,
            remind_at=remind_at,
            remind_type="wechat",
            status="pending",
            reminder_batch_date=batch_date,
            policy_version=2,
        )
        self.db.add(reminder)
        await self.db.commit()
        await self.db.refresh(reminder)
        await self._sync_reminders_to_redis([reminder])

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

        todo_count = sum(1 for t in tasks if t.status == TaskStatus.TODO.value)
        return {
            "total": len(tasks),
            "todo": todo_count,
            "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS.value) + todo_count,
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
            m_todo = sum(1 for t in member_tasks if t.status == TaskStatus.TODO.value)
            member_stats.append({
                "member_id": member.id,
                "member_name": member.name,
                "role": member.role,
                "tasks": member_tasks,
                "total": len(member_tasks),
                "todo": m_todo,
                "in_progress": sum(1 for t in member_tasks if t.status == TaskStatus.IN_PROGRESS.value) + m_todo,
                "done": sum(1 for t in member_tasks if t.status == TaskStatus.DONE.value),
            })

        return member_stats

    @staticmethod
    async def auto_purge_trash(db: AsyncSession, retention_days: int = 3) -> dict:
        """自动永久删除垃圾桶中超过 retention_days 天的任务

        Returns: {"deleted_count": int, "deleted_ids": list[int], "cutoff": datetime}

        关联清理由 DB 层自动处理：
            - reminders: ORM relationship `cascade="all, delete-orphan"` 自动级联
            - task_dependencies: FK 配 `ondelete="CASCADE"`，DB 自动级联
        避免在 async session 中访问 lazy relationship（2026-06-02 教训：
        async session 触发同步 IO → MissingGreenlet / asyncpg cross-loop 错误）
        """
        cutoff = utcnow() - timedelta(days=retention_days)
        result = await db.execute(
            select(Task).where(Task.deleted_at < cutoff)
        )
        expired = result.scalars().all()
        deleted_ids: list[int] = [task.id for task in expired]
        # 一次 delete 一个 task 让 SQLAlchemy 收集所有依赖，
        # 单次 commit 提交，asyncpg 连接在 commit 后由 session 关闭时释放
        for task in expired:
            await db.delete(task)
        if expired:
            await db.commit()
        return {
            "deleted_count": len(expired),
            "deleted_ids": deleted_ids,
            "cutoff": cutoff,
        }


@celery_app.task(name="app.services.task_service.auto_purge_trash_task")
def auto_purge_trash_task(retention_days: Optional[int] = None):
    """Celery 定时任务：自动清理过期垃圾桶任务

    Args:
        retention_days: 保留天数（None 时使用 settings.TRASH_RETENTION_DAYS，默认 3）

    实现要点（与 reminder_service.process_reminders_task 一致）：
        - 独立 create_async_engine(NullPool) + async_sessionmaker：避免全局
          async_session 绑定主进程事件循环，与 asyncio.run() 新循环冲突
        - NullPool：禁用连接池，每任务创建新连接避免跨 loop 复用
        - engine.dispose() finally：清理连接
    """
    import asyncio
    import logging
    logger = logging.getLogger("microbubble.trash")
    days = retention_days if retention_days is not None else settings.TRASH_RETENTION_DAYS
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                async with session_factory() as db:
                    result = await TaskService.auto_purge_trash(db, retention_days=days)
                    # 始终输出日志（即使删除 0 个）便于健康监控 + 审计追溯
                    if result["deleted_count"] > 0:
                        logger.warning(
                            f"🗑️ 自动清理垃圾桶: 永久删除 {result['deleted_count']} 个超过 {days} 天的任务 "
                            f"cutoff={result['cutoff'].isoformat()} ids={result['deleted_ids'][:20]}"
                            f"{'...' if len(result['deleted_ids']) > 20 else ''}"
                        )
                    else:
                        logger.info(
                            f"✅ 垃圾桶健康: 当前无超过 {days} 天的过期任务 "
                            f"(cutoff={result['cutoff'].isoformat()})"
                        )
                    return result
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return {"status": "ok", "deleted_count": result["deleted_count"]}
    except Exception as e:
        logger.error(f"❌ 自动清理垃圾桶失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
