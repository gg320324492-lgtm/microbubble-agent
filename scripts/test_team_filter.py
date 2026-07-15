"""scripts/test_team_filter.py — 验证测试账号过滤 (2026-07-15 #P2)

跑法: docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && PYTHONPATH=/app python scripts/test_team_filter.py'
"""
import asyncio
from app.core.database import async_session
from app.agent.micro_bubble_agent import _build_team_overview_text
from app.core.redis import get_redis


async def main():
    r = await get_redis()
    await r.delete("team_overview:v1")

    async with async_session() as db:
        result = await _build_team_overview_text(db)
    print(f"Length: {len(result)} chars")
    print()
    for test_name in ["Alice Drive Test", "Bob Drive Test", "Charlie Drive Test", "测试小助手"]:
        present = test_name in result
        marker = "[X] 仍在" if present else "[OK] 已过滤"
        print(f"  {marker}: {test_name}")
    for real_name in ["王天志", "杜同贺", "赵航佳"]:
        present = real_name in result
        marker = "[OK] 在" if present else "[X] 不在"
        print(f"  {marker}: {real_name}")
    print()
    print("=== First 800 chars ===")
    print(result[:800])


asyncio.run(main())