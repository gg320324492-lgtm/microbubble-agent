from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional
from datetime import timezone, timedelta
from app.models.base import utcnow, BEIJING_TZ
from app.config import settings

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundException, ValidationException
from app.schemas.pagination import PaginatedResponse
from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.models.project import Project
from app.models.reminder import Reminder
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskList, TaskStats
)
from app.services.task_service import TaskService

router = APIRouter()

@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建任务"""
    # 2026-09-05 角色扁平化：任何成员可创建任务并分配给他人

    task_svc = TaskService(db)

    # 准备自定义提醒数据
    reminders_data = None
    if task_data.reminders:
        reminders_data = [r.model_dump() for r in task_data.reminders]

    task = await task_svc.create_task(
        title=task_data.title,
        assignee_id=task_data.assignee_id,
        project_id=task_data.project_id,
        priority=task_data.priority,
        due_date=task_data.due_date,
        description=task_data.description,
        tags=task_data.tags,
        source="manual",
        created_by=current_user.id,
        reminders=reminders_data,
    )

    # 如果分配给了其他成员，立即通知负责人 + 通知创建人确认
    # 2026-09 企业微信下线: 原 wechat notifier 改站内推送 (notify_user)
    if task.assignee_id and task.assignee_id != current_user.id:
        try:
            import logging
            from app.services.notification_service import notify_user
            _notify_logger = logging.getLogger("microbubble.notify")
            assignee = await db.get(Member, task.assignee_id)

            due_date_str = ""
            if task.due_date:
                due_date_beijing = task.due_date.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
                due_date_str = due_date_beijing.strftime("%Y-%m-%d %H:%M")

            body_lines = [
                f"{current_user.name} 给你派了一个任务",
                f"📌 任务：{task.title}",
                f"⏱ 优先级：{task.priority}",
            ]
            if due_date_str:
                body_lines.append(f"📅 截止：{due_date_str}")
            if task.description:
                body_lines.append(f"📝 {task.description}")

            # 通知负责人
            if assignee:
                await notify_user(
                    assignee.id,
                    title=f"📌 新任务：{task.title}",
                    body="\n".join(body_lines),
                    context="reminder",
                    db=db,
                )
                _notify_logger.info(f"任务分配通知成功: {assignee.name} <- {task.title}")

            # 通知创建人：任务已派发
            await notify_user(
                current_user.id,
                title=f"✅ 任务已派发：{task.title}",
                body=(
                    f"任务「{task.title}」已派发给 "
                    f"{assignee.name if assignee else '未知成员'}"
                    + (f"，截止 {due_date_str}。" if due_date_str else "。")
                ),
                context="reminder",
                db=db,
            )
            _notify_logger.info(f"派发确认通知成功: {current_user.name} <- {task.title}")
        except Exception as notify_err:
            logging.getLogger("microbubble.notify").warning(f"任务分配通知异常: {notify_err}")

    return task


@router.get("/tasks", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    overdue: bool = False,
    include_deleted: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询任务列表（默认排除已删除任务）"""
    query = select(Task)
    filters = []

    # 垃圾桶/活跃 过滤
    if include_deleted:
        filters.append(Task.deleted_at.isnot(None))
    else:
        filters.append(Task.deleted_at.is_(None))

    if assignee_id:
        filters.append(Task.assignee_id == assignee_id)
    if status:
        filters.append(Task.status == status)
    if project_id:
        filters.append(Task.project_id == project_id)
    if overdue:
        filters.append(and_(
            Task.due_date < utcnow(),
            Task.status.notin_(["done", "cancelled"])
        ))

    if filters:
        query = query.where(and_(*filters))

    # 排序：最新创建在前
    query = query.order_by(Task.created_at.desc())

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    tasks = result.scalars().all()

    # 2026-06-03：为软删除任务附加 auto_delete_at = deleted_at + retention_days
    # 用 setattr 而非持久化字段，避免与 Celery auto_purge 任务的 retention 逻辑漂移
    retention = timedelta(days=settings.TRASH_RETENTION_DAYS)
    for t in tasks:
        if t.deleted_at is not None:
            t.auto_delete_at = t.deleted_at + retention

    # 获取总数
    count_query = select(func.count(Task.id))
    if filters:
        count_query = count_query.where(and_(*filters))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return PaginatedResponse.create(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total, page=page, page_size=page_size,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取任务详情"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise NotFoundException("任务")

    # 已删除的任务不返回（垃圾桶视图通过 include_deleted 查询）
    if task.deleted_at is not None:
        # 计算自动删除时间
        task.auto_delete_at = task.deleted_at + timedelta(days=settings.TRASH_RETENTION_DAYS)

    return task


@router.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise NotFoundException("任务")

    # 不能编辑已删除的任务
    if task.deleted_at is not None:
        raise ValidationException("任务已删除，无法编辑")

    # 2026-09-05 角色扁平化：任何成员可编辑任意任务、可改分配人

    # 更新字段
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    # 如果标记为完成，设置完成时间
    if task_data.status == TaskStatus.DONE.value:
        task.completed_at = utcnow()
        task.progress = 100

    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除任务（软删除，进入垃圾桶）"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise NotFoundException("任务")

    # 已删除的任务不能再删除
    if task.deleted_at is not None:
        raise ValidationException("任务已在垃圾桶中")

    # 2026-09-05 角色扁平化：任何成员可删除任意任务

    # 软删除：设置 deleted_at
    task.deleted_at = utcnow()
    await db.commit()


@router.post("/tasks/{task_id}/restore", response_model=TaskResponse)
async def restore_task(
    task_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """恢复任务（从垃圾桶）"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise NotFoundException("任务")

    if task.deleted_at is None:
        raise ValidationException("任务未删除，无需恢复")

    # 2026-09-05 角色扁平化：任何成员可恢复任意任务

    task.deleted_at = None
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/tasks/{task_id}/permanent", status_code=204)
async def permanent_delete_task(
    task_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """永久删除任务（从垃圾桶彻底删除）"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise NotFoundException("任务")

    if task.deleted_at is None:
        raise ValidationException("请先删除任务再永久删除")

    # 2026-09-05 角色扁平化：任何成员可永久删除任意任务

    await db.delete(task)
    await db.commit()


@router.post("/tasks/batch-permanent-delete")
async def batch_permanent_delete(
    body: dict,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """批量永久删除任务"""
    ids = body.get("ids", [])
    if not ids:
        raise ValidationException("ids 不能为空")

    result = await db.execute(select(Task).where(Task.id.in_(ids)))
    tasks = result.scalars().all()

    # 2026-09-05 角色扁平化：任何成员可批量永久删除任意任务
    deleted = 0
    for task in tasks:
        if task.deleted_at is None:
            continue
        await db.delete(task)
        deleted += 1

    await db.commit()
    return {"deleted": deleted}


@router.get("/tasks/stats/overview", response_model=TaskStats)
async def get_task_stats(
    project_id: Optional[int] = None,
    member_id: Optional[int] = None,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取任务统计"""

    query = select(Task)

    # 排除已删除的任务
    query = query.where(Task.deleted_at.is_(None))

    if project_id:
        query = query.where(Task.project_id == project_id)

    if member_id:
        query = query.where(Task.assignee_id == member_id)

    result = await db.execute(query)
    tasks = result.scalars().all()

    now = utcnow()
    todo_count = sum(1 for t in tasks if t.status == TaskStatus.TODO.value)
    in_progress_count = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS.value)
    stats = TaskStats(
        total=len(tasks),
        todo=todo_count,
        in_progress=in_progress_count + todo_count,
        blocked=sum(1 for t in tasks if t.status == TaskStatus.BLOCKED.value),
        review=sum(1 for t in tasks if t.status == TaskStatus.REVIEW.value),
        done=sum(1 for t in tasks if t.status == TaskStatus.DONE.value),
        cancelled=sum(1 for t in tasks if t.status == TaskStatus.CANCELLED.value),
        overdue=sum(1 for t in tasks if t.due_date and t.due_date < now and t.status not in [TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
    )

    return stats


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取仪表盘统计数据"""
    now = utcnow()

    # 所有成员可查看全部任务，仅排除已删除
    task_filter = Task.deleted_at.is_(None)

    # 任务状态统计
    status_query = select(Task.status, func.count(Task.id))
    status_query = status_query.where(task_filter)
    task_status_result = await db.execute(status_query.group_by(Task.status))
    task_status_stats = {row[0]: row[1] for row in task_status_result.all()}

    # 任务优先级统计
    priority_query = select(Task.priority, func.count(Task.id))
    priority_query = priority_query.where(task_filter)
    task_priority_result = await db.execute(priority_query.group_by(Task.priority))
    task_priority_stats = {row[0]: row[1] for row in task_priority_result.all()}

    # 项目进度统计
    project_query = select(
        Project.name,
        func.count(Task.id).label("total_tasks"),
        func.count(Task.id).filter(Task.status == TaskStatus.DONE.value).label("done_tasks")
    ).outerjoin(Task, Task.project_id == Project.id)
    project_query = project_query.where(task_filter)
    project_stats_result = await db.execute(
        project_query.group_by(Project.id, Project.name)
    )
    project_stats = []
    for row in project_stats_result.all():
        total = row.total_tasks or 0
        done = row.done_tasks or 0
        project_stats.append({
            "name": row.name,
            "total_tasks": total,
            "done_tasks": done,
            "progress": round(done / total * 100) if total > 0 else 0
        })

    # 成员任务统计
    member_query = select(
        Member.name,
        func.count(Task.id).label("total"),
        func.count(Task.id).filter(Task.status == TaskStatus.IN_PROGRESS.value).label("in_progress"),
        func.count(Task.id).filter(Task.status == TaskStatus.DONE.value).label("done")
    ).outerjoin(Task, Task.assignee_id == Member.id).where(Member.is_active == True)
    member_query = member_query.where(task_filter)
    member_stats_result = await db.execute(
        member_query.group_by(Member.id, Member.name).limit(10)
    )
    member_stats = [
        {"name": row.name, "total": row.total or 0, "in_progress": row.in_progress or 0, "done": row.done or 0}
        for row in member_stats_result.all()
    ]

    # 总体统计
    total_tasks = sum(s["total_tasks"] for s in project_stats)

    # 逾期任务数
    overdue_query = select(func.count(Task.id)).where(
        and_(
            Task.due_date < now,
            Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value]),
            Task.deleted_at.is_(None)
        )
    )
    overdue_result = await db.execute(overdue_query)
    overdue_count = overdue_result.scalar() or 0

    return {
        "task_status": task_status_stats,
        "task_priority": task_priority_stats,
        "project_stats": project_stats,
        "member_stats": member_stats,
        "summary": {
            "total_tasks": total_tasks,
            "todo_tasks": 0,
            "in_progress_tasks": task_status_stats.get("in_progress", 0) + task_status_stats.get("todo", 0),
            "done_tasks": task_status_stats.get("done", 0),
            "overdue_tasks": overdue_count
        }
    }


@router.get("/reminders/pending-count")
async def get_pending_reminder_count(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的待处理提醒数量"""
    result = await db.execute(
        select(func.count(func.distinct(Reminder.task_id)))
        .join(Task, Task.id == Reminder.task_id)
        .where(
            and_(
                Task.assignee_id == current_user.id,
                Reminder.status == "pending",
                Task.deleted_at.is_(None)
            )
        )
    )
    count = result.scalar() or 0
    return {"count": count}


@router.post("/reminders/mark-read")
async def mark_reminders_read(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """v2: 标记当前用户所有待处理提醒为"已确认收到"

    2026-06-15 优化：语义对齐 ack 状态机
    - 旧版: status="sent"（语义模糊，"系统已发"还是"用户已读"？）
    - 新版: status="acknowledged"（明确"用户已确认收到"）+ 记 acknowledged_at/by/channel
    """
    from app.services.reminder_service import ReminderService
    svc = ReminderService(db)
    count = await svc.acknowledge_all_user_reminders(
        current_user.id, channel="web"
    )
    return {"status": "success", "acknowledged_count": count}


@router.get("/reminders")
async def get_pending_reminders(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的待处理提醒列表（含任务标题）"""
    result = await db.execute(
        select(Reminder, Task.title)
        .join(Task, Task.id == Reminder.task_id)
        .where(
            and_(
                Task.assignee_id == current_user.id,
                Reminder.status == "pending",
                Task.deleted_at.is_(None)
            )
        )
        .distinct(Reminder.task_id)
        .order_by(Reminder.task_id, Reminder.remind_at.asc())
        .limit(50)
    )
    rows = result.all()
    return {
        "reminders": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "task_title": title,
                "remind_at": r.remind_at.isoformat() if r.remind_at else None,
                "remind_type": r.remind_type,
                "status": r.status
            }
            for r, title in rows
        ]
    }
