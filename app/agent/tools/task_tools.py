"""任务域工具（v2 架构）

迁移：
- query_tasks: 字段补全（description/project_name/tags/meeting_id）

未迁移（仍走 dispatch_legacy）：
- create_task / update_task / query_all_member_tasks / get_task_stats
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
