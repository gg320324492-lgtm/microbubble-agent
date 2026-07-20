"""Benchmark 测试数据清理 (2026-07-14 一次性)

清理范围 (最小化, 不误伤历史数据):
  1. chat_sessions + chat_messages (CASCADE) where user_id=59 (xiaoqi_testbot) AND created_at >= benchmark 启动时间
  2. 任何测试期间产生的 probe 数据 (本地 probes/ 目录)
  3. 不动: tasks / knowledge / MinIO / 其他表 (历史测试可能产生过)

三段式 (与项目 admin CLI 范式一致):
  1) --scan 列影响行数
  2) --backup 备份到 /tmp
  3) --apply --confirm 真删

Usage:
  docker cp scripts/cleanup_benchmark_chat_data.py microbubble-agent-app-1:/tmp/
  docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/cleanup_benchmark_chat_data.py --scan
  docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/cleanup_benchmark_chat_data.py --backup
  docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 python /tmp/cleanup_benchmark_chat_data.py --apply --confirm
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone


def _to_naive(dt: datetime) -> datetime:
    """转 naive datetime (DB 列是 naive, 2026-06-05 教训).

    CLAUDE.md 永久教训: tz-aware datetime 不能直接和 PG naive datetime 比较,
    'can't subtract offset-naive and offset-aware datetimes' 500.
    """
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
from pathlib import Path

# 强制模块级 import (让测试 patch 生效, CLAUDE.md 2026-07-02 铁律 4)
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

# 防御性常量
TEST_USER_ID = 59  # xiaoqi_testbot
BENCHMARK_DATE = "2026-07-14"  # 今天的 benchmark 启动日期


async def scan(test_only_after: datetime) -> dict:
    """预览要删的行数."""
    # 把 postgresql:// 转 postgresql+asyncpg:// (psycopg2 → asyncpg for async)
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    # 转 naive datetime (DB 列是 naive, 2026-06-05 教训)
    ts = _to_naive(test_only_after)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    plan = {}
    try:
        async with Session() as session:
            # chat_sessions
            r = await session.execute(
                text(
                    "SELECT count(*) FROM chat_sessions "
                    "WHERE user_id = :uid AND created_at >= :ts"
                ),
                {"uid": TEST_USER_ID, "ts": ts},
            )
            plan["chat_sessions"] = r.scalar() or 0
            # chat_messages (CASCADE 自动, 但统计一下)
            r = await session.execute(
                text(
                    "SELECT count(*) FROM chat_messages m "
                    "JOIN chat_sessions s ON m.session_id = s.id "
                    "WHERE s.user_id = :uid AND s.created_at >= :ts"
                ),
                {"uid": TEST_USER_ID, "ts": ts},
            )
            plan["chat_messages_via_cascade"] = r.scalar() or 0
    finally:
        await engine.dispose()
    return plan


async def backup(test_only_after: datetime, out_path: Path) -> int:
    """备份 chat_sessions 到 JSON."""
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    ts = _to_naive(test_only_after)
    rows = []
    try:
        async with Session() as session:
            r = await session.execute(
                text(
                    "SELECT id, user_id, title, session_id, "
                    "created_at, updated_at, deleted_at, is_partial "
                    "FROM chat_sessions "
                    "WHERE user_id = :uid AND created_at >= :ts"
                ),
                {"uid": TEST_USER_ID, "ts": ts},
            )
            for row in r.fetchall():
                rows.append({
                    "id": row[0],
                    "user_id": row[1],
                    "title": row[2],
                    "session_id": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "updated_at": row[5].isoformat() if row[5] else None,
                    "deleted_at": row[6].isoformat() if row[6] else None,
                    "is_partial": row[7],
                })
    finally:
        await engine.dispose()
    out_path.write_text(
        json.dumps({"test_user_id": TEST_USER_ID, "backup_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(rows)


async def apply(test_only_after: datetime) -> dict:
    """真删 (CASCADE 自动删 chat_messages)."""
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    ts = _to_naive(test_only_after)
    result = {}
    try:
        async with Session() as session:
            async with session.begin():
                # chat_messages 单独删 (虽然 CASCADE 也会删, 显式更清楚)
                r = await session.execute(
                    text(
                        "DELETE FROM chat_messages WHERE session_id IN "
                        "(SELECT id FROM chat_sessions "
                        "WHERE user_id = :uid AND created_at >= :ts)"
                    ),
                    {"uid": TEST_USER_ID, "ts": ts},
                )
                result["chat_messages_deleted"] = r.rowcount
                # chat_sessions
                r = await session.execute(
                    text(
                        "DELETE FROM chat_sessions "
                        "WHERE user_id = :uid AND created_at >= :ts"
                    ),
                    {"uid": TEST_USER_ID, "ts": ts},
                )
                result["chat_sessions_deleted"] = r.rowcount
    finally:
        await engine.dispose()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="预览")
    ap.add_argument("--backup", action="store_true", help="备份到 /tmp")
    ap.add_argument("--apply", action="store_true", help="真删 (必须 --confirm)")
    ap.add_argument("--confirm", action="store_true", help="二次确认门")
    ap.add_argument("--since", default=f"{BENCHMARK_DATE} 00:00:00", help="起始时间 (默认今天 0 点)")
    args = ap.parse_args()

    if not (args.scan or args.backup or args.apply):
        ap.print_help()
        sys.exit(1)

    since_dt = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)

    if args.scan:
        plan = asyncio.run(scan(since_dt))
        print(f"=== SCAN (test_user_id={TEST_USER_ID}, since={args.since}) ===")
        for k, v in plan.items():
            print(f"  {k}: {v}")
        print("Run --backup then --apply --confirm to clean.")
    elif args.backup:
        out = Path(f"/tmp/benchmark_chat_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        n = asyncio.run(backup(since_dt, out))
        print(f"Backed up {n} chat_sessions rows to {out}")
    elif args.apply:
        if not args.confirm:
            print("ERROR: --apply 必须配合 --confirm 二次确认门", file=sys.stderr)
            sys.exit(1)
        result = asyncio.run(apply(since_dt))
        print(f"=== APPLY RESULT ===")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()