"""成员域工具（v2 架构）

迁移：
- query_members: 字段补全（skills/custom_instructions/voice_enrolled/bio）
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.member")


class QueryMembersInput(BaseModel):
    name: Optional[str] = Field(None, description="按姓名查询")
    research_area: Optional[str] = Field(None, description="按研究方向查询")
    grade: Optional[str] = Field(None, description="按年级查询")


class MemberListItem(BaseModel):
    id: int
    name: str
    grade: Optional[str] = None
    research_area: Optional[str] = None
    email: Optional[str] = None
    role: str
    # === 字段补全（2026-06-12 优化）===
    skills: list[str] = Field(default_factory=list)
    custom_instructions: Optional[str] = None
    voice_enrolled: bool = False
    voice_enrolled_at: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    rich_block_type: str = "member"


class QueryMembersOutput(BaseModel):
    status: str
    count: int
    members: list[MemberListItem]


@tool(
    name="query_members",
    description="查询成员信息。当用户询问某人信息、某研究方向的成员等时使用。",
    input_model=QueryMembersInput,
    output_model=QueryMembersOutput,
)
async def query_members(input: QueryMembersInput, ctx: ToolContext) -> dict:
    """查询成员列表（含字段补全）"""
    from app.services.member_service import MemberService

    svc = MemberService(ctx.db)
    members = await svc.get_members(
        name=input.name,
        research_area=input.research_area,
        grade=input.grade,
    )

    items = []
    for m in members:
        items.append({
            "id": m.id,
            "name": m.name,
            "grade": m.grade,
            "research_area": m.research_area,
            "email": m.email,
            "role": m.role or "member",
            "skills": list(m.skills or []),
            "custom_instructions": (m.custom_instructions or "")[:200] if m.custom_instructions else None,
            "voice_enrolled": m.voice_embedding is not None,
            "voice_enrolled_at": m.voice_enrolled_at.isoformat() if m.voice_enrolled_at else None,
            "bio": (m.bio or "")[:200] if m.bio else None,
            "avatar": m.avatar,
            "rich_block_type": "member",
        })

    return {"status": "success", "count": len(items), "members": items}


# ============================================================================
# 2. get_member_profile（新增）
# ============================================================================


class GetMemberProfileInput(BaseModel):
    member_name: str = Field(..., min_length=1, description="成员姓名")
    include_tasks: bool = Field(False, description="是否包含成员的任务列表")
    include_projects: bool = Field(True, description="是否包含成员参与的项目")


class MemberProjectInfo(BaseModel):
    id: int
    name: str
    status: Optional[str] = None


class MemberTaskInfo(BaseModel):
    id: int
    title: str
    status: str
    due_date: Optional[str] = None
    priority: Optional[str] = None


class GetMemberProfileOutput(BaseModel):
    status: str
    id: int
    name: str
    grade: Optional[str] = None
    research_area: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    skills: list[str] = Field(default_factory=list)
    bio: Optional[str] = None
    custom_instructions: Optional[str] = None
    voice_enrolled: bool = False
    voice_enrolled_at: Optional[str] = None
    voice_sample_count: int = 0
    projects: list[MemberProjectInfo] = Field(default_factory=list)
    tasks: list[MemberTaskInfo] = Field(default_factory=list)
    rich_block_type: str = "member"


@tool(
    name="get_member_profile",
    description="获取单个成员的完整资料（bio / skills / 声纹状态 / 参与项目 / 任务）。用户问「XX 的联系方式」「XX 在做什么」「XX 的研究方向」「XX 有多少任务」时调用。比 query_members 字段更全。",
    input_model=GetMemberProfileInput,
    output_model=GetMemberProfileOutput,
)
async def get_member_profile(input: GetMemberProfileInput, ctx: ToolContext) -> dict:
    """获取单个成员完整资料"""
    from app.services.member_service import MemberService
    from app.services.task_service import TaskService
    from sqlalchemy import select
    from app.models.project import Project, ProjectMember

    svc = MemberService(ctx.db)
    # 先精确匹配；失败再 ilike 模糊匹配（应对 LLM 抽名时多带空格/标点/同音字）
    m = await svc.get_member_by_name(input.member_name.strip())
    if not m:
        # 模糊匹配：用 name ilike 找第一个
        fuzzy = await svc.get_members(name=input.member_name.strip())
        m = fuzzy[0] if fuzzy else None
    if not m:
        return {
            "status": "error", "code": "NOT_FOUND",
            "message": f"未找到成员 {input.member_name!r}，请确认姓名拼写",
            "id": 0, "name": input.member_name, "role": "member",
        }

    result = {
        "status": "success",
        "id": m.id, "name": m.name,
        "grade": m.grade, "research_area": m.research_area,
        "email": m.email, "phone": m.phone,
        "role": m.role or "member",
        "skills": list(m.skills or []),
        "bio": m.bio, "custom_instructions": m.custom_instructions,
        "voice_enrolled": m.voice_embedding is not None,
        "voice_enrolled_at": m.voice_enrolled_at.isoformat() if m.voice_enrolled_at else None,
        "voice_sample_count": m.voice_sample_count or 0,
        "projects": [], "tasks": [],
    }

    # 关联项目（Project.members 是 ARRAY(Integer)，用 ANY 查询）
    if input.include_projects:
        from app.models.project import Project
        rows = await ctx.db.execute(
            select(Project).where(Project.members.any(m.id))
        )
        for p in rows.scalars().all():
            result["projects"].append({
                "id": p.id, "name": p.name, "status": p.status,
            })

    # 关联任务
    if input.include_tasks:
        task_svc = TaskService(ctx.db)
        tasks = await task_svc.get_tasks(assignee_id=m.id)
        for t in tasks[:20]:  # 限制 20 条
            result["tasks"].append({
                "id": t.id, "title": t.title, "status": t.status,
                "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
                "priority": t.priority,
            })

    return result
