"""声纹未识别时的辅助服务

职责：查询会议中尚未录入声纹的参与者，供 /live 端点推送弹窗候选人。
"""
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import MeetingParticipant
from app.models.member import Member

logger = logging.getLogger("microbubble.speaker_unidentified")


async def get_unenrolled_participants(
    db: AsyncSession, meeting_id: int
) -> List[Member]:
    """
    查询会议中尚未录入声纹的参与者。

    Returns: 列表（按 name 排序），空列表表示"全员已录入"或"无参与者"
    """
    stmt = (
        select(Member)
        .join(MeetingParticipant, MeetingParticipant.member_id == Member.id)
        .where(
            MeetingParticipant.meeting_id == meeting_id,
            Member.voice_embedding.is_(None),
            Member.is_active == True,
        )
        .order_by(Member.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
