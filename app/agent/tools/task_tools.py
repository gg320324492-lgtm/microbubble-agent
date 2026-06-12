"""任务域工具（v2 架构）

迁移：
- query_tasks: 字段补全（description/project_name/tags/meeting_id）
- create_task: 任务创建（含微信通知 + 权限检查）
- update_task: 任务状态/进度更新

未迁移（仍走 dispatch_legacy）：
- query_all_member_tasks / get_task_stats（admin only，使用频率低）
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.task")


class QueryTasksInput(BaseModel):
    assignee_name: Optional[str] = Field(None, description="按负责人姓名筛选")
    status: Optional[str] = Field(None, description="按状态筛选（in_progress/blocked/review/done/cancelled）")
    project_name: Optional[str] = Field(None, description="按项目名称筛选")
    overdue: bool = Field(False, description="是否只查询逾期任务")


class TaskListItem(BaseModel):
    id: int
    title: str
    status: str
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None
    progress: Optional[int] = None
    # === 字段补全（2026-06-12 优化）===
    description: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    meeting_id: Optional[int] = None
    rich_block_type: str = "task_list"


class QueryTasksOutput(BaseModel):
    status: str
    count: int
    tasks: list[TaskListItem]


@tool(
    name="query_tasks",
    description="查询任务列表。当用户询问某人的任务、某项目的任务、逾期任务等时使用。",
    input_model=QueryTasksInput,
    output_model=QueryTasksOutput,
)
async def query_tasks(input: QueryTasksInput, ctx: ToolContext) -> dict:
    """查询任务列表（含字段补全）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService
    from app.services.project_service import ProjectService
    from app.models.member import Member
    from app.models.project import Project

    # 权限检查：研究生/特殊成员可见组内，普通成员只看自己
    is_admin = False
    is_graduate = False
    if ctx.user_id:
        member_svc = MemberService(ctx.db)
        current = await member_svc.get_member(ctx.user_id)
        is_admin = current and current.role in ("admin", "leader")
        if current:
            graduate_grades = ("研一", "研二", "研三", "博一", "博二")
            special_names = ("贾琦", "周之超")
            is_graduate = current.grade in graduate_grades or current.name in special_names

    # 解析 assignee_name → assignee_id
    assignee_id = None
    if input.assignee_name:
        member_svc = MemberService(ctx.db)
        m = await member_svc.get_member_by_name(input.assignee_name)
        if m:
            assignee_id = m.id

    # 解析 project_name → project_id
    project_id = None
    if input.project_name:
        proj_svc = ProjectService(ctx.db)
        projects = await proj_svc.get_projects()
        for p in projects:
            if p.name == input.project_name:
                project_id = p.id
                break

    # 权限：非管理员不指定 assignee 时只查自己
    if not is_admin and not assignee_id and not is_graduate and ctx.user_id:
        assignee_id = ctx.user_id

    # 查询
    task_svc = TaskService(ctx.db)
    tasks = await task_svc.get_tasks(
        assignee_id=assignee_id,
        status=input.status,
        project_id=project_id,
        overdue=input.overdue,
    )

    # 批量获取 assignee 姓名 + project 名称
    assignee_ids = {t.assignee_id for t in tasks if t.assignee_id}
    assignee_map = {}
    if assignee_ids:
        result = await ctx.db.execute(select(Member).where(Member.id.in_(assignee_ids)))
        assignee_map = {m.id: m.name for m in result.scalars().all()}

    project_ids = {t.project_id for t in tasks if t.project_id}
    project_map = {}
    if project_ids:
        result = await ctx.db.execute(select(Project).where(Project.id.in_(project_ids)))
        project_map = {p.id: p.name for p in result.scalars().all()}

    items = []
    for t in tasks:
        items.append({
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "assignee_id": t.assignee_id,
            "assignee_name": assignee_map.get(t.assignee_id, "未分配") if t.assignee_id else "未分配",
            "due_date": t.due_date.strftime("%Y-%m-%d %H:%M") if t.due_date else None,
            "progress": t.progress,
            "description": (t.description or "")[:200] if t.description else None,
            "project_id": t.project_id,
            "project_name": project_map.get(t.project_id) if t.project_id else None,
            "tags": list(t.tags or []),
            "meeting_id": getattr(t, "meeting_id", None),
            "rich_block_type": "task_list",
        })

    return {"status": "success", "count": len(items), "tasks": items}


# ============================================================================
# 2. create_task（迁移 — 含权限检查 + 微信通知）
# ============================================================================


class ReminderItem(BaseModel):
    remind_at: str = Field(..., description="提醒时间 YYYY-MM-DD HH:MM")
    remind_type: str = Field("wechat", description="提醒方式：wechat / email")


class CreateTaskInput(BaseModel):
    title: str = Field(..., min_length=1, description="任务标题")
    assignee_name: Optional[str] = Field(None, description="负责人姓名（不填则默认为当前用户）")
    project_name: Optional[str] = Field(None, description="所属项目名称（可选）")
    priority: str = Field("medium", description="优先级：high/medium/low")
    due_date: Optional[str] = Field(None, description="截止日期 YYYY-MM-DD HH:MM")
    description: Optional[str] = Field(None, description="任务详细描述")
    reminders: Optional[list[ReminderItem]] = Field(None, description="自定义提醒列表")


class CreateTaskOutput(BaseModel):
    status: str
    task_id: Optional[int] = None
    title: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="create_task",
    description="创建新任务。当用户要求创建任务、分配任务给某人时使用。",
    input_model=CreateTaskInput,
    output_model=CreateTaskOutput,
)
async def create_task(input: CreateTaskInput, ctx: ToolContext) -> dict:
    """创建任务（含权限检查 + 微信通知）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService
    from app.services.project_service import ProjectService
    from app.models.base import BEIJING_TZ
    from datetime import datetime, timezone

    member_svc = MemberService(ctx.db)

    # 权限检查
    is_admin = False
    if ctx.user_id:
        current = await member_svc.get_member(ctx.user_id)
        is_admin = current and current.role in ("admin", "leader")

    # 解析 assignee
    assignee_id = None
    if input.assignee_name:
        m = await member_svc.get_member_by_name(input.assignee_name)
        if not m:
            return {"status": "error", "message": f"未找到成员: {input.assignee_name!r}"}
        assignee_id = m.id
    elif ctx.user_id:
        assignee_id = ctx.user_id  # 默认分配给自己

    # 权限：普通成员只能给自己创建
    if not is_admin and assignee_id and ctx.user_id and assignee_id != ctx.user_id:
        return {"status": "error", "message": "普通成员只能给自己创建任务"}

    # 解析 project
    project_id = None
    if input.project_name:
        proj_svc = ProjectService(ctx.db)
        projects = await proj_svc.get_projects()
        for p in projects:
            if p.name == input.project_name:
                project_id = p.id
                break

    # 解析 due_date（北京时间 → UTC）
    due_date = None
    if input.due_date:
        try:
            beijing_dt = datetime.strptime(input.due_date, "%Y-%m-%d %H:%M")
        except ValueError:
            beijing_dt = datetime.strptime(input.due_date, "%Y-%m-%d").replace(hour=18, minute=0)
        due_date = beijing_dt.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)

    # 解析 reminders
    reminders_data = None
    if input.reminders:
        reminders_data = []
        for r in input.reminders:
            rem_beijing = datetime.strptime(r.remind_at, "%Y-%m-%d %H:%M")
            rem_utc = rem_beijing.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)
            reminders_data.append({"remind_at": rem_utc, "remind_type": r.remind_type})

    task_svc = TaskService(ctx.db)
    task = await task_svc.create_task(
        title=input.title,
        assignee_id=assignee_id,
        project_id=project_id,
        priority=input.priority,
        due_date=due_date,
        description=input.description,
        source="ai",
        created_by=ctx.user_id,
        reminders=reminders_data,
    )

    # 微信通知（best-effort，失败不阻塞）
    if assignee_id and ctx.user_id and assignee_id != ctx.user_id:
        try:
            from app.wechat.notifier import notifier
            assignee = await member_svc.get_member(assignee_id)
            creator = await member_svc.get_member(ctx.user_id)
            due_date_str = ""
            if due_date:
                due_date_beijing = due_date.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
                due_date_str = due_date_beijing.strftime("%Y-%m-%d %H:%M")
            if assignee and (assignee.wechat_id or assignee.external_userid):
                await notifier.notify_task_assigned(
                    member=assignee,
                    task_title=input.title,
                    due_date=due_date_str,
                    priority=input.priority,
                    description=input.description or "",
                    assigner=creator.name if creator else "管理员",
                )
        except Exception as e:
            logger.warning(f"微信通知失败（任务已创建）: {e}")

    return {
        "status": "success",
        "task_id": task.id,
        "title": task.title,
        "rich_block_type": None,
    }


# ============================================================================
# 3. update_task（迁移 — 含权限检查）
# ============================================================================


class UpdateTaskInput(BaseModel):
    task_id: int = Field(..., description="任务ID")
    status: Optional[str] = Field(None, description="新状态：in_progress/blocked/review/done/cancelled")
    progress: Optional[int] = Field(None, ge=0, le=100, description="进度百分比 0-100")
    due_date: Optional[str] = Field(None, description="新截止日期 YYYY-MM-DD HH:MM")


class UpdateTaskOutput(BaseModel):
    status: str
    task_id: Optional[int] = None
    new_status: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="update_task",
    description="更新任务状态。当用户要求标记任务完成、修改进度、延期等时使用。",
    input_model=UpdateTaskInput,
    output_model=UpdateTaskOutput,
)
async def update_task(input: UpdateTaskInput, ctx: ToolContext) -> dict:
    """更新任务（状态/进度/截止日期 + 权限检查）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService
    from app.models.base import BEIJING_TZ
    from datetime import datetime, timezone

    task_svc = TaskService(ctx.db)
    task = await task_svc.get_task(input.task_id)
    if not task:
        return {"status": "error", "message": f"任务 {input.task_id} 不存在"}

    # 权限：仅创建者/被分配者/admin
    if ctx.user_id:
        member_svc = MemberService(ctx.db)
        current = await member_svc.get_member(ctx.user_id)
        is_admin = current and current.role in ("admin", "leader")
        if not is_admin and task.created_by != ctx.user_id and task.assignee_id != ctx.user_id:
            return {"status": "error", "message": "只能编辑自己创建或被分配的任务"}

    updated = await task_svc.update_task_status(
        task_id=input.task_id,
        status=input.status or "in_progress",
        progress=input.progress,
    )
    if not updated:
        return {"status": "error", "message": f"任务 {input.task_id} 更新失败"}

    # 更新截止日期
    if input.due_date and updated:
        try:
            new_due_beijing = datetime.strptime(input.due_date, "%Y-%m-%d %H:%M")
        except ValueError:
            new_due_beijing = datetime.strptime(input.due_date, "%Y-%m-%d").replace(hour=18, minute=0)
        updated.due_date = new_due_beijing.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)
        await ctx.db.commit()

    return {
        "status": "success",
        "task_id": updated.id,
        "new_status": updated.status,
        "rich_block_type": None,
    }
