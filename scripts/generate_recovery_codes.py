"""为成员生成恢复码 (一次性发放) — 2026-09-02

用途: 恢复码功能上线时, 给**当前已被锁死/未生成恢复码**的成员批量生成。
每人只跑一次; 之后用户可在【设置 → 账号安全】自行轮换。

用法 (在 app 容器内跑, 有 DB 连接和配置):
    # 给所有"能登录但还没生成恢复码"的在职成员生成:
    docker exec microbubble-agent-app-1 python scripts/generate_recovery_codes.py --all

    # 只给指定用户生成 (已生成过会用 --force 强制轮换):
    docker exec microbubble-agent-app-1 python scripts/generate_recovery_codes.py --username dutonghe
    docker exec microbubble-agent-app-1 python scripts/generate_recovery_codes.py --username dutonghe --force

⚠️ 明文码只在本命令输出里出现这一次, 跑完立即通过个人微信发给对应成员,
   让其保存到微信收藏; 输出含敏感凭据, 不要截图外传。
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import get_db  # noqa: E402
from app.models.member import Member  # noqa: E402
from app.services import recovery_code_service  # noqa: E402


async def main(username: str | None, force: bool, all_members: bool) -> None:
    rows = []
    async for db in get_db():
        if all_members:
            result = await db.execute(
                select(Member).where(Member.is_active.is_(True)).order_by(Member.id)
            )
            members = list(result.scalars().all())
        else:
            result = await db.execute(
                select(Member).where(Member.username == username)
            )
            members = [result.scalar_one_or_none()]
            if not members or members[0] is None:
                print(f"用户不存在: {username}")
                return

        for m in members:
            if m.recovery_code_hash and not force:
                rows.append((m.username, m.name, "(已有恢复码, 跳过 — 需轮换加 --force)", True))
                continue
            if not m.is_active and all_members:
                continue
            code = recovery_code_service.rotate_member_recovery_code(m)
            rows.append((m.username, m.name, code, False))
        await db.commit()

    print()
    print(f"{'用户名':<16} {'姓名':<10} 恢复码")
    print("-" * 60)
    skipped = 0
    for u, n, code, was_skipped in rows:
        if was_skipped:
            skipped += 1
            print(f"{u:<16} {n:<10} {code}")
        else:
            print(f"{u:<16} {n:<10} {code}")
    print("-" * 60)
    print(f"共 {len(rows)} 人 (跳过已有 {skipped})")
    print("⚠️  以上明文仅此一次, 请立即通过个人微信发给对应成员保存。")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="生成成员自助重置密码恢复码")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="所有在职成员 (已有码的跳过)")
    g.add_argument("--username", help="指定单个用户名")
    p.add_argument("--force", action="store_true", help="已有恢复码也强制轮换")
    args = p.parse_args()

    asyncio.run(main(args.username, args.force, args.all))
