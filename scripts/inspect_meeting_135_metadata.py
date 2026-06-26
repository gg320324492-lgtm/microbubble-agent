"""检查会议 #135 的所有 metadata 字段"""
import asyncio
from app.core.database import async_session
from app.models.meeting import Meeting
from app.models.meeting import MeetingParticipant
from sqlalchemy import select


async def main():
    async with async_session() as db:
        m = await db.get(Meeting, 135)
        print(f"title: {m.title!r}")
        print(f"description: {m.description!r}")
        print(f"agenda: {m.agenda!r}")
        print(f"location: {m.location!r}")
        print(f"presenter_ids: {m.presenter_ids!r}")
        print(f"related_meeting_ids: {m.related_meeting_ids!r}")
        print(f"created_by: {m.created_by}")
        # meeting_participants
        r = await db.execute(select(MeetingParticipant).where(MeetingParticipant.meeting_id == 135))
        ps = r.scalars().all()
        if ps:
            print(f"meeting_participants ({len(ps)}):")
            for p in ps:
                print(f"  member_id={p.member_id}, role={p.role}")
        else:
            print("meeting_participants: 0 条")


asyncio.run(main())
