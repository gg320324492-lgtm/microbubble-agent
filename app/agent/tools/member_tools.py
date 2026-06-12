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
