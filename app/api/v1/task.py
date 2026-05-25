from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional
from datetime import timezone
from app.models.base import utcnow, BEIJING_TZ

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.models.project import Project
from app.models.reminder import Reminder
from app.schemas.task import (
    TaskCreate, TaskUpdate, TaskResponse, TaskList, TaskStats
)
from app.services.task_service import TaskService

router = APIRouter()

GRADUATE_GRADES = ("研一", "研二", "研三", "博一", "博二")
SPECIAL_NAMES = ("贾琦", "周之超")


async def _get_visible_member_ids(db: AsyncSession, user: Member) -> list[int]:
    """研究生 + 贾琦 + 周之超 互相对方任务可见"""
    if user.grade in GRADUATE_GRADES or user.name in SPECIAL_NAMES:
        result = await db.execute(
            select(Member.id).where(
                or_(
                    Member.grade.in_(GRADUATE_GRADES),
                    Member.name.in_(SPECIAL_NAMES)
                )
            )
        )
        return [row[0] for row in result.all()]
    return [user.id]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    task_data: TaskCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建任务"""
    is_admin = current_user.role in ("admin", "leader")

    # 权限：普通成员只能给自己创建任务
    if not is_admin:
        if task_data.assignee_id and task_data.assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="普通成员只能给自己创建任务")

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
    if task.assignee_id and task.assignee_id != current_user.id:
        try:
            from app.wechat.notifier import notifier
            import logging
            _notify_logger = logging.getLogger("microbubble.notify")
            assignee = await db.get(Member, task.assignee_id)

            due_date_str = ""
            if task.due_date:
                due_date_beijing = task.due_date.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
                due_date_str = due_date_beijing.strftime("%Y-%m-%d %H:%M")

            # 通知负责人
            if assignee and (assignee.wechat_id or assignee.external_userid):
                result = await notifier.notify_task_assigned(
                    member=assignee,
                    task_title=task.title,
                    due_date=due_date_str,
                    priority=task.priority,
                    description=task.description or "",
                    assigner=current_user.name
                )
                errcode = result.get("errcode", -1) if isinstance(result, dict) else -1
                if errcode == 0:
                    _notify_logger.info(f"任务分配通知成功: {assignee.name} <- {task.title}")
                else:
                    _notify_logger.warning(f"任务分配通知失败: errcode={errcode}, result={result}, assignee={assignee.name}")
            else:
                _notify_logger.warning(f"跳过负责人通知: {assignee.name if assignee else task.assignee_id} 无微信标识")

            # 通知创建人：任务已派发
            if current_user.wechat_id or current_user.external_userid:
                result2 = await notifier.notify_task_assigned_to_creator(
                    creator=current_user,
                    task_title=task.title,
                    assignee_name=assignee.name if assignee else "未知",
                    due_date=due_date_str,
                    priority=task.priority,
                )
                errcode2 = result2.get("errcode", -1) if isinstance(result2, dict) else -1
                if errcode2 == 0:
                    _notify_logger.info(f"派发确认通知成功: {current_user.name} <- {task.title}")
                else:
                    _notify_logger.warning(f"派发确认通知失败: errcode={errcode2}, result={result2}")
        except Exception as notify_err:
            logging.getLogger("microbubble.notify").warning(f"任务分配通知异常: {notify_err}")

    return task


@router.get("/debug/wechat-notify/{member_name}")
async def debug_wechat_notify(
    member_name: str,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """调试接口：测试给指定成员发送企业微信通知"""
    results = {"steps": []}

    # Step 1: 查找成员
    result = await db.execute(select(Member).where(Member.name == member_name))
    member = result.scalar_one_or_none()
    if not member:
        results["steps"].append({"step": "查找成员", "status": "FAIL", "detail": f"未找到成员: {member_name}"})
        return results
    results["steps"].append({"step": "查找成员", "status": "OK", "detail": f"id={member.id}, name={member.name}"})

    # Step 2: 检查微信标识
    results["steps"].append({
        "step": "检查微信标识",
        "status": "OK" if (member.wechat_id or member.external_userid) else "FAIL",
        "detail": f"wechat_id={member.wechat_id}, external_userid={member.external_userid}"
    })

    if not member.wechat_id and not member.external_userid:
        return results

    # Step 3: 测试发送
    try:
        from app.wechat.bot import wechat_bot
        test_msg = f"🔧 测试通知\n\n这是一条调试测试消息，发送给 {member.name}。\n如果你能看到这条消息，说明企业微信通知正常工作。"
        send_result = await wechat_bot.smart_send(member, test_msg)
        errcode = send_result.get("errcode", -1) if isinstance(send_result, dict) else -1
        results["steps"].append({
            "step": "发送测试消息",
            "status": "OK" if errcode == 0 else "FAIL",
            "detail": f"errcode={errcode}, result={send_result}"
        })
    except Exception as e:
        results["steps"].append({"step": "发送测试消息", "status": "ERROR", "detail": str(e)})

    return results


@router.post("/debug/sync-wechat-ids")
async def sync_wechat_ids(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """从企业微信API同步成员userid（仅管理员）"""
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(status_code=403, detail="仅管理员可操作")

    from app.wechat.bot import wechat_bot
    import logging
    logger = logging.getLogger("microbubble.sync")

    # 从企业微信获取所有成员
    wechat_members = await wechat_bot.list_department_members(department_id=1)
    if not wechat_members:
        return {"status": "error", "message": "获取企业微信成员列表失败，请检查 WECHAT_CORP_ID 和 WECHAT_SECRET 配置"}

    # 构建 name -> userid 映射
    wechat_map = {}
    for wm in wechat_members:
        name = wm.get("name", "")
        userid = wm.get("userid", "")
        if name and userid:
            wechat_map[name] = userid

    # 匹配并更新
    result = await db.execute(select(Member).where(Member.is_active == True))
    members = result.scalars().all()

    updated = []
    skipped = []
    not_found = []

    for member in members:
        if member.wechat_id:
            skipped.append(member.name)
            continue
        if member.name in wechat_map:
            member.wechat_id = wechat_map[member.name]
            updated.append(f"{member.name} -> {wechat_map[member.name]}")
        else:
            not_found.append(member.name)

    await db.commit()

    logger.info(f"同步完成: 更新{len(updated)}人, 跳过{len(skipped)}人, 未匹配{len(not_found)}人")
    return {
        "status": "success",
        "updated": updated,
        "skipped": skipped,
        "not_found": not_found,
        "wechat_total": len(wechat_members)
    }


@router.get("/tasks", response_model=TaskList)
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
    is_admin = current_user.role in ("admin", "leader")

    query = select(Task)
    filters = []

    # 默认排除已删除任务
    if not include_deleted:
        filters.append(Task.deleted_at.is_(None))

    # 权限：普通成员只看自己创建/负责的；研究生+贾琦+周之超互相对方任务可见
    if not is_admin:
        visible_ids = await _get_visible_member_ids(db, current_user)
        filters.append(or_(
            Task.created_by == current_user.id,
            Task.assignee_id.in_(visible_ids)
        ))

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

    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    tasks = result.scalars().all()

    # 获取总数
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

    # 已删除的任务不返回（除非是管理员查看垃圾桶）
    if task.deleted_at is not None:
        is_admin = current_user.role in ("admin", "leader")
        if not is_admin:
            raise HTTPException(status_code=404, detail="任务不存在")

    # 权限：普通成员只能查看自己的任务
    is_admin = current_user.role in ("admin", "leader")
    if not is_admin:
        if task.created_by != current_user.id and task.assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权查看此任务")

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

    # 不能编辑已删除的任务
    if task.deleted_at is not None:
        raise HTTPException(status_code=400, detail="任务已删除，无法编辑")

    # 权限：管理员可编辑任意任务，普通成员只能编辑自己或组内可见成员的任务
    is_admin = current_user.role in ("admin", "leader")
    if not is_admin:
        visible_ids = await _get_visible_member_ids(db, current_user)
        if task.created_by != current_user.id and task.assignee_id not in visible_ids:
            raise HTTPException(status_code=403, detail="只能编辑自己创建或被分配的任务")
        # 不能把任务分配给其他人
        if task_data.assignee_id is not None and task_data.assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="普通成员不能将任务分配给其他人")

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
        raise HTTPException(status_code=404, detail="任务不存在")

    # 已删除的任务不能再删除
    if task.deleted_at is not None:
        raise HTTPException(status_code=400, detail="任务已在垃圾桶中")

    # 权限：普通成员只能删除自己或组内可见成员的任务
    is_admin = current_user.role in ("admin", "leader")
    if not is_admin:
        visible_ids = await _get_visible_member_ids(db, current_user)
        if task.created_by != current_user.id and task.assignee_id not in visible_ids:
            raise HTTPException(status_code=403, detail="只能删除自己创建或被分配的任务")

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
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.deleted_at is None:
        raise HTTPException(status_code=400, detail="任务未删除，无需恢复")

    # 权限：管理员可恢复任意任务，普通成员只能恢复自己或组内可见成员的任务
    is_admin = current_user.role in ("admin", "leader")
    if not is_admin:
        visible_ids = await _get_visible_member_ids(db, current_user)
        if task.created_by != current_user.id and task.assignee_id not in visible_ids:
            raise HTTPException(status_code=403, detail="只能恢复自己创建或被分配的任务")

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
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.deleted_at is None:
        raise HTTPException(status_code=400, detail="请先删除任务再永久删除")

    # 权限：管理员可永久删除任意任务，普通成员只能永久删除自己或组内可见成员的任务
    is_admin = current_user.role in ("admin", "leader")
    if not is_admin:
        visible_ids = await _get_visible_member_ids(db, current_user)
        if task.created_by != current_user.id and task.assignee_id not in visible_ids:
            raise HTTPException(status_code=403, detail="只能永久删除自己创建或被分配的任务")

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
    is_admin = current_user.role in ("admin", "leader")

    query = select(Task)

    # 排除已删除的任务
    query = query.where(Task.deleted_at.is_(None))

    if project_id:
        query = query.where(Task.project_id == project_id)

    if is_admin:
        if member_id:
            query = query.where(Task.assignee_id == member_id)
    else:
        visible_ids = await _get_visible_member_ids(db, current_user)
        query = query.where(or_(
            Task.created_by == current_user.id,
            Task.assignee_id.in_(visible_ids)
        ))

    result = await db.execute(query)
    tasks = result.scalars().all()

    now = utcnow()
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
    now = utcnow()
    is_admin = current_user.role in ("admin", "leader")

    # 权限：普通成员只看自己的数据（研究生可见组内成员任务），且排除已删除
    if not is_admin:
        visible_ids = await _get_visible_member_ids(db, current_user)
        task_filter = and_(
            Task.deleted_at.is_(None),
            or_(
                Task.created_by == current_user.id,
                Task.assignee_id.in_(visible_ids)
            )
        )
    else:
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
