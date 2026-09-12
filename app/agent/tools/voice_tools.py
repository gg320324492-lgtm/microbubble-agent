"""声纹 / 个性化域工具（v3 迁移）

迁移自 core.py._execute_tool：
- enroll_voice (line 1209) — 高复杂度（Redis 多通道 + 微信状态机）
- set_custom_instructions (line 1197)
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.voice")


# ============================================================================
# 1. set_custom_instructions
# ============================================================================


class SetCustomInstructionsInput(BaseModel):
    instructions: str = Field(..., min_length=1, max_length=2000,
                              description="用户自定义指令，如「回复要简洁」「用英文回复」「多用表格」等")


class SetCustomInstructionsOutput(BaseModel):
    status: str
    message: str
    preview: str
    rich_block_type: Optional[str] = None


@tool(
    name="set_custom_instructions",
    description="设置用户的自定义指令。当用户说「设置你的风格」「以后回复要...」「记住我的偏好」等个性化要求时使用。",
    input_model=SetCustomInstructionsInput,
    output_model=SetCustomInstructionsOutput,
)
async def set_custom_instructions(input: SetCustomInstructionsInput, ctx: ToolContext) -> dict:
    """保存用户的自定义指令（注入到 system prompt）"""
    from app.models.member import Member

    if not ctx.user_id:
        return {
            "status": "error",
            "message": "需要登录才能设置自定义指令",
            "preview": "",
        }

    member = await ctx.db.get(Member, ctx.user_id)
    if not member:
        return {
            "status": "error",
            "message": "用户不存在",
            "preview": "",
        }

    member.custom_instructions = input.instructions[:2000]
    await ctx.db.commit()
    return {
        "status": "success",
        "message": f"已保存你的自定义指令：{input.instructions[:100]}...",
        "preview": input.instructions[:200],
    }


# ============================================================================
# 2. enroll_voice（高复杂度 — Redis pending_enroll + 多通道）
# ============================================================================


class EnrollVoiceInput(BaseModel):
    member_name: str = Field(..., min_length=1, description="要录入声纹的成员姓名")


class EnrollVoiceOutput(BaseModel):
    status: str
    message: str
    member_id: Optional[int] = None
    rich_block_type: Optional[str] = None


@tool(
    name="enroll_voice",
    description="录入用户的声纹特征。当用户说「小气，我是XXX」「帮我录入声纹」「记住我的声音」等时使用。需要先通过 query_members 确认成员身份。",
    input_model=EnrollVoiceInput,
    output_model=EnrollVoiceOutput,
)
async def enroll_voice(input: EnrollVoiceInput, ctx: ToolContext) -> dict:
    """录入声纹（站内文字指导，用户上传音频到 voiceprint enroll API）"""
    from app.models.member import Member

    member_result = await ctx.db.execute(
        select(Member).where(Member.name == input.member_name)
    )
    member = member_result.scalar_one_or_none()
    if not member:
        return {
            "status": "error",
            "message": f"未找到成员「{input.member_name}」，请先确认姓名",
            "member_id": None,
        }

    # 站内文字指导 (2026-09 企业微信下线, 原微信 pending_enroll 分支已删)
    # 非微信通道（Web 端 / 内部 API）走原文字指导
