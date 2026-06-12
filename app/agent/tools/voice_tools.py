"""声纹 / 个性化域工具（v3 迁移）

迁移自 core.py._execute_tool：
- enroll_voice (line 1209) — 高复杂度（Redis 多通道 + 微信状态机）
- set_custom_instructions (line 1197)
"""

import json
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
    wechat_user_id: Optional[str] = Field(None, description="微信通道 user_id（来自外部通道）")


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
    """录入声纹（Web 端走文字指导 / 微信端写 Redis pending）"""
    from app.models.member import Member
    from app.core.redis import get_redis

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

    # 微信/外部通道：写 pending_enroll 状态（5 min TTL）
    wechat_user_id = input.wechat_user_id or ctx.channel_user_id
    if wechat_user_id:
        r = await get_redis()
        if member.voice_embedding is not None:
            # 已录入：清除 pending
            await r.delete(f"wechat:pending_enroll:{wechat_user_id}")
            return {
                "status": "success",
                "message": (
                    f"成员「{input.member_name}」已录入声纹（{member.voice_sample_count or 0}次采样）。"
                    "如需更新，请发一段10秒以上语音给我，小气会用新语音更新声纹。"
                ),
                "member_id": member.id,
            }
        # 未录入：写 pending_enroll
        await r.set(
            f"wechat:pending_enroll:{wechat_user_id}",
            json.dumps({"member_id": member.id, "member_name": member.name}, ensure_ascii=False),
            ex=300,
        )
        return {
            "status": "success",
            "message": (
                f"已找到成员「{input.member_name}」。要让小气认识你的声音，"
                "**请直接发一段10秒以上的语音**给我（可以说「我是{input.member_name}」），"
                "小气会自动用你的语音录入声纹。⏱ 5分钟内有效。"
            ),
            "member_id": member.id,
        }

    # 非微信通道（Web 端 / 内部 API）走原文字指导
    if member.voice_embedding is not None:
        return {
            "status": "success",
            "message": (
                f"成员「{input.member_name}」已录入声纹（{member.voice_sample_count or 0}次采样）。"
                "请该成员在安静环境下说一段话（10秒以上），然后上传音频到 "
                "/api/v1/voiceprint/enroll/{member.id} 来更新声纹。"
            ),
            "member_id": member.id,
        }
    return {
        "status": "success",
        "message": (
            f"已找到成员「{input.member_name}」(id={member.id})。"
            f"要让小气认识{input.member_name}的声音，请{input.member_name}录制一段10秒以上的语音"
            "（可以说'我是{input.member_name}'），然后上传音频到声纹录入接口。"
        ),
        "member_id": member.id,
    }
