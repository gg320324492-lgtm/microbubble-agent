from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member


class MeetingService:
    """会议服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        """获取单个会议（含参与者）"""
        result = await self.db.execute(
            select(Meeting)
            .options(selectinload(Meeting.participants))
            .where(Meeting.id == meeting_id)
        )
        return result.scalar_one_or_none()

    async def get_meetings(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        keyword: Optional[str] = None
    ) -> List[Meeting]:
        """查询会议列表"""
        query = select(Meeting).options(selectinload(Meeting.participants))
        filters = []

        if date_from:
            filters.append(Meeting.start_time >= date_from)
        if date_to:
            filters.append(Meeting.start_time <= date_to)
        if keyword:
            filters.append(Meeting.title.ilike(f"%{keyword}%"))

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Meeting.start_time.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_meeting(
        self,
        title: str,
        start_time: datetime,
        description: Optional[str] = None,
        end_time: Optional[datetime] = None,
        location: Optional[str] = None,
        participant_ids: Optional[List[int]] = None,
        created_by: Optional[int] = None
    ) -> Meeting:
        """创建会议"""
        meeting = Meeting(
            title=title,
            start_time=start_time,
            end_time=end_time,
            description=description,
            location=location,
            created_by=created_by,
            status="scheduled"
        )
        self.db.add(meeting)
        await self.db.flush()

        if participant_ids:
            for member_id in participant_ids:
                participant = MeetingParticipant(
                    meeting_id=meeting.id,
                    member_id=member_id,
                    role="participant"
                )
                self.db.add(participant)

        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_meeting(self, meeting_id: int, **kwargs) -> Optional[Meeting]:
        """更新会议"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return None

        for key, value in kwargs.items():
            if hasattr(meeting, key) and value is not None:
                setattr(meeting, key, value)

        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def delete_meeting(self, meeting_id: int) -> bool:
        """删除会议"""
        meeting = await self.get_meeting(meeting_id)
        if not meeting:
            return False

        await self.db.delete(meeting)
        await self.db.commit()
        return True
