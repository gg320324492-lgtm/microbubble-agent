"""任务域扩展工具（v3 迁移）

迁移自 core.py._execute_tool：
- query_all_member_tasks (line 692) — admin/leader 专用
- get_task_stats (line 789)
"""

import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.extra_task")


# ============================================================================
# 1. query_all_member_tasks（admin/leader 专用）
# ============================================================================


class QueryAllMemberTasksInput(BaseModel):
    pass  # 无参数


class AllMemberTaskItem(BaseModel):
    member: str
    title: str
    progress: Optional[int] = None
    due_date: Optional[str] = None


class QueryAllMemberTasksOutput(BaseModel):
    status: str
    formatted_text: str
    in_progress_count: int
    done_count: int
    total_count: int
    rich_block_type: Optional[str] = None


@tool(
    name="query_all_member_tasks",
    description="查询所有成员的任务状况，按状态分组显示（进行中/待办/已完成）。仅管理员或组长可用。当管理员或组长询问所有人的任务进度、团队任务分布时使用。",
    input_model=QueryAllMemberTasksInput,
    output_model=QueryAllMemberTasksOutput,
)
async def query_all_member_tasks(input: QueryAllMemberTasksInput, ctx: ToolContext) -> dict:
    """查询所有成员任务（admin/leader 权限）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService

    # 权限检查
    is_admin = False
    if ctx.user_id:
        member_svc = MemberService(ctx.db)
        current = await member_svc.get_member(ctx.user_id)
        is_admin = current and current.role in ("admin", "leader")

    if not is_admin:
        return {
            "status": "error",
            "message": "仅管理员或组长可以查看所有成员的任务状况",
            "formatted_text": "",
            "in_progress_count": 0,
            "done_count": 0,
            "total_count": 0,
        }

    task_svc = TaskService(ctx.db)
    all_member_stats = await task_svc.get_all_members_workload()

    in_progress_list = []
    done_list = []

    for member_data in all_member_stats:
        member_name = member_data["member_name"]
        for task in member_data["tasks"]:
            task_info = {
                "member": member_name,
                "title": task.title,
                "progress": task.progress,
                "due_date": task.due_date.strftime("%Y-%m-%d") if task.due_date else None,
            }
            if task.status in ("in_progress", "todo"):
                in_progress_list.append(task_info)
            elif task.status == "done":
                done_list.append(task_info)

    # 格式化文本
    def fmt(items):
        lines = []
        for item in items:
            parts = [f"- {item['member']}：{item['title']}"]
            if item["progress"] is not None:
                parts.append(f" {item['progress']}%")
            if item["due_date"]:
                parts.append(f" 截止{item['due_date']}")
            lines.append("".join(parts).strip())
        return lines

    lines = [f"【进行中任务】（共 {len(in_progress_list)} 个）"]
    lines.extend(fmt(in_progress_list) or ["- 无"])
    lines.append("")
    lines.append(f"【已完成任务】（共 {len(done_list)} 个）")
    lines.extend(fmt(done_list) or ["- 无"])
    lines.append("")
    lines.append(f"共 {len(in_progress_list) + len(done_list)} 个任务")

    return {
        "status": "success",
        "formatted_text": "\n".join(lines),
        "in_progress_count": len(in_progress_list),
        "done_count": len(done_list),
        "total_count": len(in_progress_list) + len(done_list),
        "rich_block_type": None,
    }


# ============================================================================
# 2. get_task_stats
# ============================================================================


class GetTaskStatsInput(BaseModel):
    project_name: Optional[str] = Field(None, description="按项目统计（可选）")
    member_name: Optional[str] = Field(None, description="按成员统计（可选）")


class TaskStats(BaseModel):
    total: int
    todo: int
    in_progress: int
    blocked: int
    review: int
    done: int
    cancelled: int
    overdue: int


class GetTaskStatsOutput(BaseModel):
    status: str
    stats: TaskStats
    rich_block_type: Optional[str] = None


@tool(
    name="get_task_stats",
    description="获取任务统计数据。当用户询问整体进度、任务统计等时使用。",
    input_model=GetTaskStatsInput,
    output_model=GetTaskStatsOutput,
)
async def get_task_stats(input: GetTaskStatsInput, ctx: ToolContext) -> dict:
    """任务统计（按项目/成员筛选）"""
    from app.services.task_service import TaskService
    from app.services.member_service import MemberService
    from app.services.project_service import ProjectService
    from app.models.base import utcnow
    from app.models.task import TaskStatus

    member_id = None
    if input.member_name:
        member_svc = MemberService(ctx.db)
        m = await member_svc.get_member_by_name(input.member_name)
        if m:
            member_id = m.id

    project_id = None
    if input.project_name:
        proj_svc = ProjectService(ctx.db)
        projects = await proj_svc.get_projects()
        for p in projects:
            if p.name == input.project_name:
                project_id = p.id
                break

    task_svc = TaskService(ctx.db)

    if member_id:
        stats = await task_svc.get_member_workload(member_id)
        # get_member_workload 返回的格式直接转
        return {
            "status": "success",
            "stats": {
                "total": stats.get("total", 0),
                "todo": stats.get("todo", 0),
                "in_progress": stats.get("in_progress", 0),
                "blocked": stats.get("blocked", 0),
                "review": stats.get("review", 0),
                "done": stats.get("done", 0),
                "cancelled": stats.get("cancelled", 0),
                "overdue": stats.get("overdue", 0),
            },
            "rich_block_type": None,
        }

    # 全局统计
    tasks = await task_svc.get_tasks(project_id=project_id)
    now = utcnow()
    todo_count = sum(1 for t in tasks if t.status == TaskStatus.TODO.value)
    in_progress_count = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS.value) + todo_count
    overdue_count = sum(
        1 for t in tasks
        if t.due_date and t.due_date < now and t.status not in [TaskStatus.DONE.value, TaskStatus.CANCELLED.value]
    )

    stats = {
        "total": len(tasks),
        "todo": todo_count,
        "in_progress": in_progress_count,
        "blocked": sum(1 for t in tasks if t.status == TaskStatus.BLOCKED.value),
        "review": sum(1 for t in tasks if t.status == TaskStatus.REVIEW.value),
        "done": sum(1 for t in tasks if t.status == TaskStatus.DONE.value),
        "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED.value),
        "overdue": overdue_count,
    }
    return {
        "status": "success",
        "stats": stats,
        "rich_block_type": None,
    }
