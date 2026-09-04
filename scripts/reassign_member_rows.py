"""成员网盘归属转移脚本 — 删号前把成员名下行转给工作区锚点 (2026-09 单一团队盘)

背景:
  2026-09-05 删除测试小助手账号时, folders.owner_id (RESTRICT) / agent_traces.user_id
  (NO ACTION) 等 FK 把 DELETE members 卡死, 只能人肉逐表 UPDATE. 本脚本把这个流程
  固化: 先清点 (census), 再转移 (reassign), 可选连带物理删号 (--delete-member).

  语义: 单一团队盘改造后 owner_id/created_by 是"创建人溯源"而非权限, 转移即溯源改写,
  锚点成员 (默认 settings.DRIVE_WORKSPACE_ANCHOR_ID=1 王天志) 承接归属。

三段式执行 (CLAUDE.md purge 铁律: dry-run + 二次确认 + 单事务):
  # 1) dry-run 清点 (默认, 不动库)
  $ docker cp scripts/reassign_member_rows.py microbubble-agent-app-1:/tmp/
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/reassign_member_rows.py --member 116

  # 2) 真转移
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/reassign_member_rows.py --member 116 --confirm

  # 3) 转移 + 物理删号 (仅确认是垃圾/测试号时用; CASCADE 自动带走 chat_sessions 等)
  $ docker exec -i -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/reassign_member_rows.py --member 116 --confirm --delete-member

防御:
  - 默认 dry-run, 无 --confirm 一律 rollback
  - member == anchor / 任一不存在 → 直接退出
  - 单事务包裹, 行数打印后校验 (转移后引用数应为 0)
  - 表列清单与 app/services/drive_ownership.py::reassign_member_rows 保持一致
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
if (Path("/app") / "app" / "__init__.py").exists():
    sys.path.insert(0, "/app")

# (表, 列, 动作) — 与 app/services/drive_ownership.py::REASSIGN_TARGETS 严格一致:
# reassign 7 项 = service 转移清单; set_null/cascade 项在 FK 上声明了 SET NULL/CASCADE,
# 硬删时由数据库自身处理, 仅清点展示不转移。
REFS: list[tuple[str, str, str]] = [
    ("folders", "owner_id", "reassign"),
    ("team_folders", "owner_id", "reassign"),
    ("knowledge", "created_by", "reassign"),
    ("knowledge_versions", "uploaded_by", "reassign"),
    ("drive_file_versions", "uploader_id", "reassign"),
    ("file_requests", "created_by", "reassign"),
    ("agent_traces", "user_id", "reassign"),
    ("chat_sessions", "user_id", "reassign"),  # CASCADE 也覆盖, 转移保聊天历史
    ("team_folders", "owner_id", "reassign"),
    ("drive_folder_shares", "created_by", "reassign"),
    ("drive_folder_members", "invited_by", "reassign"),
    ("drive_version_tags", "created_by", "reassign"),
    ("drive_folder_members", "member_id", "cascade"),
    ("drive_reactions", "member_id", "cascade"),
    ("drive_comments", "author_id", "cascade"),
    ("file_comments", "user_id", "set_null"),
    ("activity_events", "actor_id", "set_null"),
    ("audit_log", "user_id", "set_null"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="成员网盘归属转移 (dry-run 默认)")
    p.add_argument("--member", type=int, required=True, help="被删/退休成员 id")
    p.add_argument("--anchor", type=int, default=None,
                   help="承接锚点成员 id (默认 settings.DRIVE_WORKSPACE_ANCHOR_ID)")
    p.add_argument("--confirm", action="store_true", help="真正写库 (必须显式)")
    p.add_argument("--delete-member", action="store_true",
                   help="转移后物理删除该成员行 (隐含要求 --confirm)")
    return p.parse_args()


async def _census(s, member_id: int) -> dict[str, int]:
    """清点成员在各表列上的引用行数 (含 set_null 类)"""
    from sqlalchemy import text
    out: dict[str, int] = {}
    for table, col, _action in REFS:
        n = (await s.execute(
            text(f"SELECT count(*) FROM {table} WHERE {col} = :m"), {"m": member_id}
        )).scalar()
        if n:
            out[f"{table}.{col}"] = int(n)
    return out


async def main() -> int:
    args = parse_args()
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.config import settings

    anchor = args.anchor or int(getattr(settings, "DRIVE_WORKSPACE_ANCHOR_ID", 1) or 1)
    if args.delete_member and not args.confirm:
        print("!! --delete-member 必须搭配 --confirm")
        return 2
    if args.member == anchor:
        print(f"!! member == anchor ({anchor}), 拒绝")
        return 2

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with sf() as s:
        for label, mid in (("member", args.member), ("anchor", anchor)):
            row = (await s.execute(
                text("SELECT username, name FROM members WHERE id = :i"), {"i": mid}
            )).first()
            if row is None:
                print(f"!! {label} id={mid} 不存在, 退出")
                return 2
            print(f"{label}: id={mid} {row.username} ({row.name})")

        before = await _census(s, args.member)
        total = sum(before.values())
        print(f"\n引用清点 ({args.member} → {anchor}):")
        for k, v in before.items():
            print(f"  {k}: {v}")
        if not total:
            print("  (无引用, 可直接删号)")

        if not args.confirm:
            print("\n[dry-run] 未写库。加 --confirm 执行转移"
                  + (" + 删号" if args.delete_member else ""))
            await s.rollback()
            return 0

        for table, col, action in REFS:
            if action != "reassign":
                continue  # cascade/set_null 交给 FK 行为, 不转移
            r = await s.execute(
                text(f"UPDATE {table} SET {col} = :a WHERE {col} = :m"),
                {"m": args.member, "a": anchor},
            )
            if r.rowcount:
                print(f"  转移 {table}.{col}: {r.rowcount}")
        if args.delete_member:
            r = await s.execute(text("DELETE FROM members WHERE id = :m"), {"m": args.member})
            print(f"  删除成员行: {r.rowcount}")
        await s.commit()

        after = await _census(s, args.member)
        if after and not args.delete_member:
            print(f"!! 转移后仍有残留引用: {after}")
            return 1
        print("\nOK: 转移完成, 引用清零" + (" + 成员已删除" if args.delete_member else ""))
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
