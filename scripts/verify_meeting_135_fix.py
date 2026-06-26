"""验证 #135 修复结果"""
import asyncio
from app.core.database import async_session
from app.models.meeting import Meeting, MeetingParticipant
from app.models.member import Member
from sqlalchemy import select


async def main():
    async with async_session() as db:
        m = await db.get(Meeting, 135)
        print(f"=== 会议 #135 修复后状态 ===")
        print(f"title: {m.title!r}")
        print()
        r = await db.execute(select(MeetingParticipant).where(MeetingParticipant.meeting_id == 135))
        ps = r.scalars().all()
        print(f"meeting_participants ({len(ps)}):")
        for p in ps:
            rm = await db.get(Member, p.member_id)
            print(f"  {rm.name} (id={p.member_id}, role={p.role})")


asyncio.run(main())
