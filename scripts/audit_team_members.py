"""scripts/audit_team_members.py — 一次性审计, 打印成员数据质量 (2026-07-15 #P2 审查)

跑法: docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /app/scripts/audit_team_members.py
"""
import asyncio
from app.core.database import async_session
from sqlalchemy import select
from app.models.member import Member


async def main():
    async with async_session() as db:
        rows = await db.execute(
            select(Member.name, Member.username, Member.role,
                   Member.research_area, Member.wechat_id, Member.bio, Member.is_active)
            .order_by(Member.role.desc(), Member.name.asc())
        )
        members = rows.all()

        test = []
        null_backfill = []
        real_no_ra = []
        real_with_ra = []
        for n, u, r, ra, wid, bio, active in members:
            if not active:
                continue
            entry = (n, u, r, ra or "(no RA)")
            if u and (u.startswith("test") or "Test" in n or u in ("xiaoqi_testbot", "xiaoqi_testbot_2")):
                test.append(entry)
            elif wid and wid.startswith("__NULL_BACKFILL"):
                null_backfill.append(entry)
            elif not ra:
                real_no_ra.append(entry)
            else:
                real_with_ra.append(entry)

        print(f"=== Member Audit (active only) ===")
        print(f"Test accounts: {len(test)}")
        for e in test[:10]:
            print(f"  {e}")
        print(f"\nNull backfill wechat (placeholder, still need fill): {len(null_backfill)}")
        for e in null_backfill[:5]:
            print(f"  {e}")
        print(f"\nReal members WITHOUT research_area: {len(real_no_ra)}")
        for e in real_no_ra[:15]:
            print(f"  {e}")
        print(f"\nReal members WITH research_area: {len(real_with_ra)}")
        for e in real_with_ra[:5]:
            print(f"  {e}")


asyncio.run(main())