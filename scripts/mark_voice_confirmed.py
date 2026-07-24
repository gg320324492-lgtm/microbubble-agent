#!/usr/bin/env python3
"""标记成员声纹为已 confirmed (anchor 锁定, embedding 永不再修改)

W68 第 7 批 A-2 (cheerful-questing-kite Plan 闭环): mark_voice_confirmed.py
锚点范式第 76 守恒.

含义: 把 member 的 voice_confirmed_at / voice_confirmed_by / voice_confirmed_meeting_id
     3 字段同时写入. 后续 strict pipeline 会跳过此成员 (purify_voiceprints_from_meeting.py
     已有 'skipped_confirmed' 守卫), 永不再修改其 voice_embedding.

用法:
  # 默认 dry-run (只显示将要写入什么, 不实际写库)
  python scripts/mark_voice_confirmed.py --member-id 3 --meeting-id 167 --confirmed-by 1

  # 真正写入
  python scripts/mark_voice_confirmed.py --member-id 3 --meeting-id 167 --confirmed-by 1 --apply

  # 显式指定确认人字符串 (e.g. "user", "audit_2026_07_24")
  python scripts/mark_voice_confirmed.py --member-id 3 --meeting-id 167 --confirmed-by "user" --apply

  # 用 name 而非 id (二选一)
  python scripts/mark_voice_confirmed.py --member-name "杜同贺" --meeting-id 167 --confirmed-by "user" --apply

  # 强制覆盖已 confirmed (默认拒绝, 防误操作)
  python scripts/mark_voice_confirmed.py --member-name "陈金薪" --meeting-id 167 \\
      --confirmed-by "user" --apply --force

  # JSON 输出 (供 CI / 自动化消费)
  python scripts/mark_voice_confirmed.py --member-id 3 --meeting-id 167 --confirmed-by 1 --json

参数:
  --member-id <int>          成员 ID (与 --member-name 二选一)
  --member-name <str>        成员 name (与 --member-id 二选一)
  --meeting-id <int>         触发确认的会议 ID (写入 voice_confirmed_meeting_id)
  --confirmed-by <str|int>   确认者 (username / "user" / member_id)
  --apply                    实际写入 (默认 dry-run)
  --force                    允许覆盖已 confirmed 成员 (默认拒绝)
  --json                     JSON 输出

设计:
  - 0 production code 改动铁律维持 — 仅 scripts/+tests/+docs/+memory/
  - dry-run by default (任何脚本默认不修改 DB, 2026-06-29 W66 范式)
  - 复用 SQLAlchemy async session + 直接 ORM 字段写入
  - 写入 MemberVoiceHistory audit 记录 (source="anchor_confirmed")
  - 越权防护: 不需要, 脚本直接走 root DB (主指挥 SSH 跑)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.member_voice_history import MemberVoiceHistory


# audit source 字段约定常量 (与现有 history source 命名一致)
AUDIT_SOURCE_ANCHOR_CONFIRMED = "anchor_confirmed"


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def find_member_by_id(sf, member_id: int) -> Optional[Member]:
    async with sf() as db:
        r = await db.execute(select(Member).where(Member.id == member_id))
        return r.scalar_one_or_none()


async def find_member_by_name(sf, name: str) -> Optional[Member]:
    async with sf() as db:
        r = await db.execute(select(Member).where(Member.name == name))
        return r.scalar_one_or_none()


async def mark_voice_confirmed(
    session_factory,
    member: Member,
    meeting_id: int,
    confirmed_by: str,
    apply: bool,
    force: bool,
) -> Dict[str, Any]:
    """执行 mark_voice_confirmed 主流程.

    Returns: dict (含 before/after status + audit 是否写入)
    """
    result: Dict[str, Any] = {
        "member_id": member.id,
        "name": member.name,
        "username": member.username,
        "meeting_id": meeting_id,
        "confirmed_by": confirmed_by,
        "before": {
            "voice_confirmed_at": _to_iso(member.voice_confirmed_at),
            "voice_confirmed_by": member.voice_confirmed_by,
            "voice_confirmed_meeting_id": member.voice_confirmed_meeting_id,
            "voice_sample_count": int(member.voice_sample_count or 0),
        },
    }

    # 守卫: 已 confirmed 默认拒绝 (除非 --force)
    if member.voice_confirmed_at is not None and not force:
        result["status"] = "skipped_already_confirmed"
        result["msg"] = (
            f"成员 {member.name} (id={member.id}) 已是 anchor "
            f"(voice_confirmed_at={result['before']['voice_confirmed_at']}). "
            f"如需覆盖请加 --force"
        )
        result["dry_run"] = True
        return result

    # 守卫: 已 confirmed + --force 时记录覆盖
    if member.voice_confirmed_at is not None and force:
        result["force_override"] = True
        result["overridden_prev"] = {
            "voice_confirmed_at": result["before"]["voice_confirmed_at"],
            "voice_confirmed_by": member.voice_confirmed_by,
            "voice_confirmed_meeting_id": member.voice_confirmed_meeting_id,
        }

    now = datetime.utcnow()
    if not apply:
        result["after"] = {
            "voice_confirmed_at": now.isoformat() + " (DRY-RUN)",
            "voice_confirmed_by": confirmed_by,
            "voice_confirmed_meeting_id": meeting_id,
        }
        result["status"] = "dry_run"
        result["dry_run"] = True
        return result

    # 实际写 DB
    async with session_factory() as db:
        # 1. 更新 Member 3 字段
        r = await db.execute(select(Member).where(Member.id == member.id))
        m = r.scalar_one()
        m.voice_confirmed_at = now
        m.voice_confirmed_by = confirmed_by
        m.voice_confirmed_meeting_id = meeting_id

        # 2. 写 MemberVoiceHistory audit (source="anchor_confirmed")
        # notes 含具体动作链, 方便后续 audit 回查
        new_emb = list(m.voice_embedding) if m.voice_embedding is not None else []
        notes = (
            f"anchor_confirmed: meeting_id={meeting_id}, confirmed_by={confirmed_by}"
        )
        if result.get("force_override"):
            notes += f" (FORCE OVERRIDE prev meeting_id={result['overridden_prev']['voice_confirmed_meeting_id']})"
        history = MemberVoiceHistory(
            member_id=m.id,
            source=AUDIT_SOURCE_ANCHOR_CONFIRMED,
            old_embedding=list(m.voice_embedding) if m.voice_embedding is not None else None,
            new_embedding=new_emb,
            sample_count_before=int(m.voice_sample_count or 0),
            sample_count_after=int(m.voice_sample_count or 0),
            weight=None,
            notes=notes,
        )
        db.add(history)
        await db.commit()

    # 重新读回来给前端显示
    async with session_factory() as db:
        r2 = await db.execute(select(Member).where(Member.id == member.id))
        m_after = r2.scalar_one()

    result["after"] = {
        "voice_confirmed_at": _to_iso(m_after.voice_confirmed_at),
        "voice_confirmed_by": m_after.voice_confirmed_by,
        "voice_confirmed_meeting_id": m_after.voice_confirmed_meeting_id,
        "voice_sample_count": int(m_after.voice_sample_count or 0),
        "audit_id": history.id,
    }
    result["status"] = "applied"
    result["dry_run"] = False
    return result


def _print_table(result: Dict[str, Any]) -> None:
    """人类可读的 table 输出."""
    print(f"=== mark_voice_confirmed ===")
    print(f"  member: {result['name']} (id={result['member_id']})")
    print(f"  username: {result.get('username') or '—'}")
    print(f"  meeting_id: {result['meeting_id']}")
    print(f"  confirmed_by: {result['confirmed_by']}")
    print(f"  status: {result['status']}")
    if result.get("dry_run"):
        print("  [DRY-RUN] 未实际写库")
    if result.get("force_override"):
        print(f"  ⚠️ FORCE OVERRIDE: 已覆盖前态 {result['overridden_prev']}")
    print()
    print(f"  before:")
    for k, v in result["before"].items():
        print(f"    {k}: {v}")
    if "after" in result:
        print(f"  after:")
        for k, v in result["after"].items():
            print(f"    {k}: {v}")


def _print_json(result: Dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


async def amain():
    parser = argparse.ArgumentParser(
        description="标记成员声纹为已 confirmed (anchor 锁定, embedding 永不再修改)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--member-id", type=int, help="成员 ID")
    group.add_argument("--member-name", type=str, help="成员 name (e.g. '杜同贺')")
    parser.add_argument("--meeting-id", type=int, required=True, help="触发确认的会议 ID")
    parser.add_argument(
        "--confirmed-by",
        type=str,
        required=True,
        help='确认者 (username / "user" / member_id). 与 schema 字段一致, str 类型',
    )
    parser.add_argument("--apply", action="store_true", help="实际写入 (默认 dry-run)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已 confirmed 成员 (默认拒绝, 防误操作)",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        # 1. 查 member
        if args.member_id is not None:
            member = await find_member_by_id(session_factory, args.member_id)
        else:
            member = await find_member_by_name(session_factory, args.member_name)
        if not member:
            print(f"❌ 成员不存在 (id={args.member_id}, name={args.member_name})")
            sys.exit(1)

        # 2. 执行 mark
        result = await mark_voice_confirmed(
            session_factory,
            member,
            meeting_id=args.meeting_id,
            confirmed_by=args.confirmed_by,
            apply=args.apply,
            force=args.force,
        )

        if args.json:
            _print_json(result)
        else:
            _print_table(result)

        # 退出码语义: dry_run + skipped = 0 (正常), applied = 0, 错误 = 1
        if result["status"] in ("applied", "dry_run", "skipped_already_confirmed"):
            sys.exit(0)
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(amain())
