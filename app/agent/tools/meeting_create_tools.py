"""会议创建域工具（v3 迁移）

迁移自 core.py._execute_tool：
- create_meeting (line 950) — 高复杂度（含腾讯会议 API + 二级 DB 写）
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.meeting_create")


class CreateMeetingInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="会议主题")
    start_time: str = Field(..., description="开始时间 YYYY-MM-DD HH:MM")
    participants: Optional[List[str]] = Field(None, description="参与者姓名列表（可选）")
    agenda: Optional[str] = Field(None, description="会议议程（可选）")
    location: Optional[str] = Field(None, description="会议地点（可选）")
    description: Optional[str] = Field(None, description="会议描述（可选）")


class CreateMeetingOutput(BaseModel):
    status: str
    meeting_id: Optional[int] = None
    title: Optional[str] = None
    join_url: Optional[str] = None
    tencent_meeting_id: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="create_meeting",
    description="创建会议。当用户要求预约会议、安排组会等时使用。如腾讯会议已配置，会自动创建线上会议。",
    input_model=CreateMeetingInput,
    output_model=CreateMeetingOutput,
)
async def create_meeting(input: CreateMeetingInput, ctx: ToolContext) -> dict:
    """创建会议（含腾讯会议 API 副作用）"""
    from app.services.meeting_service import MeetingService
    from app.services.member_service import MemberService
    from app.models.base import BEIJING_TZ

    start_time_beijing = datetime.strptime(input.start_time, "%Y-%m-%d %H:%M")
    start_time = start_time_beijing.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)

    # 解析参与者姓名 → ID
    participant_ids = []
    if input.participants:
        member_svc = MemberService(ctx.db)
        for name_str in input.participants:
            member = await member_svc.get_member_by_name(name_str)
            if member:
                participant_ids.append(member.id)

    # 创建本地会议
    meeting_svc = MeetingService(ctx.db)
    meeting = await meeting_svc.create_meeting(
        title=input.title,
        start_time=start_time,
        description=input.description,
        agenda=input.agenda,
        location=input.location,
        participant_ids=participant_ids,
    )

    result = {
        "status": "success",
        "meeting_id": meeting.id,
        "title": meeting.title,
    }

    # 如腾讯会议已配置，自动创建线上会议
    from app.services.tencent_meeting_service import tencent_meeting
    if tencent_meeting.is_configured:
        try:
            start_ts = start_time.strftime("%Y-%m-%d %H:%M:%S")
            tm_result = await tencent_meeting.create_meeting(
                subject=input.title,
                start_time=start_ts,
            )
            meeting_info = tm_result.get("meeting_info", {})
            join_url = meeting_info.get("join_url", "")
            tm_meeting_id = meeting_info.get("meeting_id", "")
            if join_url:
                await meeting_svc.update_meeting(
                    meeting.id,
                    meeting_url=join_url,
                    meeting_id=tm_meeting_id,
                )
                result["join_url"] = join_url
                result["tencent_meeting_id"] = tm_meeting_id
        except Exception as e:
            logger.warning(f"创建腾讯会议失败（本地会议已创建）: {e}")

    return result
