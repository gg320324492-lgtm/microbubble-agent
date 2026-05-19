from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.models.project import Project
from app.models.reminder import Reminder
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskList, TaskStats
)

router = APIRouter()


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建任务"""
    # 查找负责人
    assignee_id = None
    if task_data.assignee_id:
        assignee_id = task_data.assignee_id

    task = Task(
        title=task_data.title,
        description=task_data.description,
        assignee_id=assignee_id,
        project_id=task_data.project_id,
        priority=task_data.priority,
        due_date=task_data.due_date,
        tags=task_data.tags,
        status=TaskStatus.TODO.value,
        source="manual"
    )

    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.get("/tasks", response_model=TaskList)
async def list_tasks(
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    project_id: Optional[int] = None,
    overdue: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询任务列表"""
    query = select(Task)

    # 筛选条件
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
            Task.status.notin_(["done", "cancelled"])
        ))

    if filters:
        query = query.where(and_(*filters))

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    tasks = result.scalars().all()

    # 获取总数（用 COUNT 聚合，避免加载全部数据）
    count_query = select(func.count(Task.id))
    if filters:
        count_query = count_query.where(and_(*filters))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return TaskList(items=tasks, total=total)


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
        raise HTTPException(status_code=404, detail="任务不存在")

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
        raise HTTPException(status_code=404, detail="任务不存在")

    # 更新字段
    update_data = task_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    # 如果标记为完成，设置完成时间
    if task_data.status == TaskStatus.DONE.value:
        task.completed_at = datetime.utcnow()
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
    """删除任务"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    await db.delete(task)
    await db.commit()


@router.get("/tasks/stats/overview", response_model=TaskStats)
async def get_task_stats(
    project_id: Optional[int] = None,
    member_id: Optional[int] = None,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取任务统计"""
    query = select(Task)

    if project_id:
        query = query.where(Task.project_id == project_id)
    if member_id:
        query = query.where(Task.assignee_id == member_id)

    result = await db.execute(query)
    tasks = result.scalars().all()

    now = datetime.utcnow()
    stats = TaskStats(
        total=len(tasks),
        todo=sum(1 for t in tasks if t.status == TaskStatus.TODO.value),
        in_progress=sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS.value),
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
    now = datetime.utcnow()

    # 任务状态统计
    task_status_result = await db.execute(
        select(Task.status, func.count(Task.id)).group_by(Task.status)
    )
    task_status_stats = {row[0]: row[1] for row in task_status_result.all()}

    # 任务优先级统计
    task_priority_result = await db.execute(
        select(Task.priority, func.count(Task.id)).group_by(Task.priority)
    )
    task_priority_stats = {row[0]: row[1] for row in task_priority_result.all()}

    # 项目进度统计（单条 SQL 聚合，避免 N+1）
    project_stats_result = await db.execute(
        select(
            Project.name,
            func.count(Task.id).label("total_tasks"),
            func.count(Task.id).filter(Task.status == TaskStatus.DONE.value).label("done_tasks")
        ).outerjoin(Task, Task.project_id == Project.id)
         .group_by(Project.id, Project.name)
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

    # 成员任务统计（单条 SQL 聚合，避免 N+1）
    member_stats_result = await db.execute(
        select(
            Member.name,
            func.count(Task.id).label("total"),
            func.count(Task.id).filter(Task.status == TaskStatus.IN_PROGRESS.value).label("in_progress"),
            func.count(Task.id).filter(Task.status == TaskStatus.DONE.value).label("done")
        ).outerjoin(Task, Task.assignee_id == Member.id)
         .where(Member.is_active == True)
         .group_by(Member.id, Member.name)
         .limit(10)
    )
    member_stats = [
        {"name": row.name, "total": row.total or 0, "in_progress": row.in_progress or 0, "done": row.done or 0}
        for row in member_stats_result.all()
    ]

    # 总体统计（复用上面的聚合结果）
    total_tasks = sum(s["total_tasks"] for s in project_stats)

    # 逾期任务数（单独聚合）
    overdue_result = await db.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.due_date < now,
                Task.status.notin_([TaskStatus.DONE.value, TaskStatus.CANCELLED.value])
            )
        )
    )
    overdue_count = overdue_result.scalar() or 0

    return {
        "task_status": task_status_stats,
        "task_priority": task_priority_stats,
        "project_stats": project_stats,
        "member_stats": member_stats,
        "summary": {
            "total_tasks": total_tasks,
            "todo_tasks": task_status_stats.get("todo", 0),
            "in_progress_tasks": task_status_stats.get("in_progress", 0),
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
        select(func.count(Reminder.id))
        .join(Task, Task.id == Reminder.task_id)
        .where(
            and_(
                Task.assignee_id == current_user.id,
                Reminder.status == "pending"
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
    """标记当前用户所有待处理提醒为已读"""
    from sqlalchemy import update
    await db.execute(
        update(Reminder)
        .where(
            Reminder.id.in_(
                select(Reminder.id)
                .join(Task, Task.id == Reminder.task_id)
                .where(
                    and_(
                        Task.assignee_id == current_user.id,
                        Reminder.status == "pending"
                    )
                )
            )
        )
        .values(status="sent")
    )
    await db.commit()
    return {"status": "success"}
