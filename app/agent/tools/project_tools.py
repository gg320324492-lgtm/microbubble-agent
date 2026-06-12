"""项目域工具（v2 架构）

迁移：
- query_projects: 列表查询
- generate_project_plan: 生成项目计划

新增：
- get_project_summary: 单个项目详情 + 任务统计 + 里程碑
"""

import logging
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.project")


# ============================================================================
# 1. query_projects（迁移）
# ============================================================================


class QueryProjectsInput(BaseModel):
    status: Optional[str] = Field(None, description="按状态筛选：active / paused / completed / archived")


class ProjectListItem(BaseModel):
    id: int
    name: str
    status: Optional[str] = None
    research_area: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    member_count: int = 0
    task_count: int = 0
    rich_block_type: str = "project"


class QueryProjectsOutput(BaseModel):
    status: str
    count: int
    projects: list[ProjectListItem]


@tool(
    name="query_projects",
    description="查询项目信息。当用户询问课题进度、项目列表等时使用。",
    input_model=QueryProjectsInput,
    output_model=QueryProjectsOutput,
)
async def query_projects(input: QueryProjectsInput, ctx: ToolContext) -> dict:
    """查询项目列表（含任务统计）"""
    from app.services.project_service import ProjectService
    from app.models.task import Task

    svc = ProjectService(ctx.db)
    projects = await svc.get_projects(status=input.status)

    items = []
    for p in projects:
        # 任务数
        task_count_result = await ctx.db.execute(
            select(Task).where(Task.project_id == p.id)
        )
        task_count = len(task_count_result.scalars().all())
        items.append({
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "research_area": p.research_area,
            "start_date": str(p.start_date) if p.start_date else None,
            "end_date": str(p.end_date) if p.end_date else None,
            "member_count": len(p.members or []),
            "task_count": task_count,
            "rich_block_type": "project",
        })
    return {"status": "success", "count": len(items), "projects": items}


# ============================================================================
# 2. get_project_summary（新增）
# ============================================================================


class GetProjectSummaryInput(BaseModel):
    project_name: str = Field(..., min_length=1, description="项目名称")
    recent_task_limit: int = Field(5, ge=1, le=20, description="最近任务显示数量")


class MilestoneInfo(BaseModel):
    id: int
    name: str
    due_date: Optional[str] = None
    status: Optional[str] = None


class ProjectTaskStats(BaseModel):
    total: int
    todo: int
    in_progress: int
    blocked: int
    review: int
    done: int
    cancelled: int
    overdue: int


class RecentTaskItem(BaseModel):
    id: int
    title: str
    status: str
    priority: Optional[str] = None
    progress: Optional[int] = None
    assignee_name: Optional[str] = None
    due_date: Optional[str] = None


class GetProjectSummaryOutput(BaseModel):
    status: str
    id: int
    name: str
    description: Optional[str] = None
    status_field: Optional[str] = None
    research_area: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    member_count: int
    member_ids: list[int] = Field(default_factory=list)
    task_stats: ProjectTaskStats
    milestones: list[MilestoneInfo] = Field(default_factory=list)
    recent_tasks: list[RecentTaskItem] = Field(default_factory=list)
    rich_block_type: str = "project"


@tool(
    name="get_project_summary",
    description="获取单个项目的完整摘要（描述 / 任务统计 / 里程碑 / 最近任务 / 成员数）。用户问「XX 项目进度如何」「XX 项目有多少任务」时调用。比 query_projects 字段更全。",
    input_model=GetProjectSummaryInput,
    output_model=GetProjectSummaryOutput,
)
async def get_project_summary(input: GetProjectSummaryInput, ctx: ToolContext) -> dict:
    """获取单个项目完整摘要"""
    from app.services.project_service import ProjectService
    from app.models.task import Task
    from app.models.member import Member
    from app.models.base import utcnow

    svc = ProjectService(ctx.db)
    projects = await svc.get_projects()
    p = next((p for p in projects if p.name == input.project_name), None)
    if not p:
        return {
            "status": "error", "code": "NOT_FOUND",
            "message": f"未找到项目 {input.project_name!r}",
            "id": 0, "name": input.project_name, "member_count": 0, "member_ids": [],
            "task_stats": ProjectTaskStats(total=0, todo=0, in_progress=0, blocked=0,
                                            review=0, done=0, cancelled=0, overdue=0).model_dump(),
            "milestones": [], "recent_tasks": [],
        }

    # 任务统计
    task_rows = await ctx.db.execute(select(Task).where(Task.project_id == p.id))
    tasks = task_rows.scalars().all()
    now = utcnow()
    stats = {
        "total": len(tasks),
        "todo": sum(1 for t in tasks if t.status == "todo"),
        "in_progress": sum(1 for t in tasks if t.status == "in_progress"),
        "blocked": sum(1 for t in tasks if t.status == "blocked"),
        "review": sum(1 for t in tasks if t.status == "review"),
        "done": sum(1 for t in tasks if t.status == "done"),
        "cancelled": sum(1 for t in tasks if t.status == "cancelled"),
        "overdue": sum(1 for t in tasks if t.due_date and t.due_date < now
                       and t.status not in ("done", "cancelled")),
    }

    # 里程碑
    milestones = [
        {
            "id": ms.id, "name": ms.name,
            "due_date": str(ms.due_date) if ms.due_date else None,
            "status": ms.status,
        }
        for ms in (p.milestones or [])
    ]

    # 最近任务（按 updated_at 倒序）
    sorted_tasks = sorted(tasks, key=lambda t: t.updated_at or t.created_at or now, reverse=True)
    recent = sorted_tasks[: input.recent_task_limit]
    # 批量取负责人姓名
    assignee_ids = {t.assignee_id for t in recent if t.assignee_id}
    assignee_map = {}
    if assignee_ids:
        rows = await ctx.db.execute(select(Member).where(Member.id.in_(assignee_ids)))
        assignee_map = {m.id: m.name for m in rows.scalars().all()}
    recent_tasks = [
        {
            "id": t.id, "title": t.title, "status": t.status,
            "priority": t.priority, "progress": t.progress,
            "assignee_name": assignee_map.get(t.assignee_id, "未分配") if t.assignee_id else "未分配",
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
        }
        for t in recent
    ]

    return {
        "status": "success",
        "id": p.id, "name": p.name, "description": p.description,
        "status_field": p.status, "research_area": p.research_area,
        "start_date": str(p.start_date) if p.start_date else None,
        "end_date": str(p.end_date) if p.end_date else None,
        "member_count": len(p.members or []),
        "member_ids": list(p.members or []),
        "task_stats": stats,
        "milestones": milestones,
        "recent_tasks": recent_tasks,
        "rich_block_type": "project",
    }


# ============================================================================
# 3. generate_project_plan（迁移）
# ============================================================================


class GenerateProjectPlanInput(BaseModel):
    project_name: str = Field(..., min_length=1, description="项目/课题名称")
    duration_months: Optional[int] = Field(None, ge=1, le=60, description="预计时长（月）")
    team_size: Optional[int] = Field(None, ge=1, le=50, description="团队人数")
    research_area: Optional[str] = Field(None, description="研究方向")


class GenerateProjectPlanOutput(BaseModel):
    status: str
    project_id: Optional[int] = None
    plan: str
    rich_block_type: Optional[str] = "fallback"


@tool(
    name="generate_project_plan",
    description="生成项目计划。当用户要求规划新课题、制定项目计划时使用。",
    input_model=GenerateProjectPlanInput,
    output_model=GenerateProjectPlanOutput,
)
async def generate_project_plan(input: GenerateProjectPlanInput, ctx: ToolContext) -> dict:
    """生成项目计划（委托 LLM）"""
    from app.services.project_service import ProjectService
    from app.core.llm import get_anthropic_client, get_default_model, extract_text_from_response

    proj_svc = ProjectService(ctx.db)
    plan_prompt = f"请为课题「{input.project_name}」生成一份详细的项目计划。"
    if input.duration_months:
        plan_prompt += f" 预计时长：{input.duration_months}个月。"
    if input.team_size:
        plan_prompt += f" 团队人数：{input.team_size}人。"
    if input.research_area:
        plan_prompt += f" 研究方向：{input.research_area}。"
    plan_prompt += "\n\n请分阶段列出：文献调研、方案设计、预实验、正式实验、数据分析、论文撰写，每阶段包含具体任务和时间安排。"

    client = get_anthropic_client()
    response = await client.messages.create(
        model=get_default_model(),
        max_tokens=4096,
        messages=[{"role": "user", "content": plan_prompt}],
    )
    plan_text = extract_text_from_response(response)

    project = await proj_svc.create_project(
        name=input.project_name,
        description=plan_text,
        research_area=input.research_area,
    )
    return {
        "status": "success",
        "project_id": project.id,
        "plan": plan_text,
        "rich_block_type": None,
    }
