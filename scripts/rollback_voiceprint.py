#!/usr/bin/env python3
"""回滚 member voice_embedding 到历史 audit 状态 (2026-06-27 新增, P0 防护配套)

083 事件: 杜同贺 embedding 被 183 段噪声污染, 需要从 member_voice_history 还原.
本脚本提供 CLI:
  --list-history <member>: 打印该 member 的 history 链
  --rollback-to-history-id <id>: 精确回滚
  --rollback-to-before-meeting <id>: 智能回滚到该会议处理前的状态
  --dry-run: 列出影响范围, 不修改 DB

用法:
  python scripts/rollback_voiceprint.py --member "杜同贺" --list-history
  python scripts/rollback_voiceprint.py --member "杜同贺" --rollback-to-history-id 8 --dry-run
  python scripts/rollback_voiceprint.py --member "杜同贺" --rollback-to-before-meeting 83 --dry-run
  python scripts/rollback_voiceprint.py --member "杜同贺" --rollback-to-before-meeting 83
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.member_voice_history import MemberVoiceHistory
from app.models.meeting import Meeting


def cos(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


async def get_member_by_name(session_factory, name: str) -> Optional[Member]:
    async with session_factory() as db:
        r = await db.execute(select(Member).where(Member.name == name))
        return r.scalar_one_or_none()


async def list_history(session_factory, member: Member) -> List[MemberVoiceHistory]:
    async with session_factory() as db:
        r = await db.execute(
            select(MemberVoiceHistory)
            .where(MemberVoiceHistory.member_id == member.id)
            .order_by(MemberVoiceHistory.created_at.desc())
        )
        return list(r.scalars().all())


async def print_history(session_factory, member_name: str):
    member = await get_member_by_name(session_factory, member_name)
    if not member:
        print(f"❌ 成员 '{member_name}' 不存在")
        return

    print(f"=== 成员 {member_name} (id={member.id}) 当前状态 ===")
    print(f"  voice_sample_count: {member.voice_sample_count}")
    print(f"  voice_enrolled_at: {member.voice_enrolled_at}")
    print(f"  voice_embedding norm: {np.linalg.norm(member.voice_embedding):.4f}" if member.voice_embedding is not None else "  voice_embedding: None")
    print()

    history = await list_history(session_factory, member)
    print(f"=== audit 链 (共 {len(history)} 条, 按 created_at 倒序) ===")
    print(f"{'id':>5} | {'source':20} | {'cnt_bef':>8} → {'cnt_aft':>8} | {'weight':>6} | {'cos':>6} | {'created_at':19} | notes")
    print("-" * 130)
    for h in history:
        weight_str = f"{h.weight:.3f}" if h.weight is not None else "—"
        print(
            f"{h.id:>5} | {h.source:20} | {h.sample_count_before:>8} → {h.sample_count_after:>8} | "
            f"{weight_str:>6} | — | {h.created_at.strftime('%Y-%m-%d %H:%M:%S') if h.created_at else '—':19} | "
            f"{(h.notes or '')[:60]}"
        )


async def find_history_before_meeting(session_factory, member: Member, meeting_id: int) -> Optional[MemberVoiceHistory]:
    """找到 member 在指定会议处理前的最后一条 audit entry

    策略: 找 notes 含 f"meeting {meeting_id}" 之前的最后一条 entry
    选择方法: max(sample_count_after) AND created_at < target_ts 的 entry (按 sample_count 链追踪状态)

    为什么不用 created_at: 同一秒的多条 audit 排序不稳定 (id=13 / id=15 都是 16:20:41)
    用 sample_count_after 链: count 21→25 是 cluster_2 merge, 一定在 cluster_0 merge (count 16→21) 之后
    """
    history = await list_history(session_factory, member)
    target_ts = None
    target_entry = None
    for h in history:
        if h.source == "recover_from_meeting" and f"meeting {meeting_id}" in (h.notes or ""):
            target_ts = h.created_at
            target_entry = h
            break
    if not target_ts:
        print(f"❌ 没找到会议 {meeting_id} 的 recover_from_meeting audit entry")
        return None

    # 找 target_ts 之前 (更早) 的所有 entry, 取 created_at 最近的一个 (083 之前的最后状态)
    candidates = [h for h in history if h.created_at < target_ts]
    if not candidates:
        return None
    # 按 created_at 倒序取最近, sample_count_after desc 为次级 (同秒时取 count 大的)
    candidates.sort(key=lambda h: (h.created_at, h.sample_count_after), reverse=True)
    return candidates[0]


async def rollback_to_history(
    session_factory,
    member: Member,
    target_history: MemberVoiceHistory,
    dry_run: bool = False,
) -> dict:
    """回滚 member voice_embedding 到 target_history 记录的 old_embedding

    target_history.new_embedding = 当前状态的来源
    target_history.old_embedding = 回滚目标
    """
    if target_history.old_embedding is None:
        return {"status": "error", "msg": f"history #{target_history.id} 的 old_embedding 为空 (首次录入无前态), 无法回滚"}

    target_emb = list(target_history.old_embedding)
    target_cnt = target_history.sample_count_before

    # 计算影响范围: 找所有用当前 embedding 识别的段
    async with session_factory() as db:
        # 简单估算: 找 speaker_mapping 或 transcript 中出现该 member name 的会议
        from sqlalchemy import text
        r = await db.execute(text("""
            SELECT id, title FROM meetings
            WHERE transcript::text LIKE :pattern
               OR speaker_mapping::text LIKE :pattern
            ORDER BY id DESC LIMIT 20
        """), {"pattern": f"%{member.name}%"})
        affected_meetings = [(row[0], row[1]) for row in r.fetchall()]

    print(f"\n=== 回滚预览 ===")
    print(f"  member: {member.name} (id={member.id})")
    print(f"  target history: #{target_history.id} ({target_history.source})")
    print(f"  target sample_count: {target_history.sample_count_before}")
    print(f"  target notes: {(target_history.notes or '')[:80]}")
    if member.voice_embedding is not None:
        cur_emb = list(member.voice_embedding)
        sim = cos(target_emb, cur_emb)
        print(f"  current → target cos similarity: {sim:.4f} (差异: {1 - sim:.4f})")
    print(f"\n  受影响会议 (用该 member name 的):")
    for mid, title in affected_meetings:
        print(f"    meeting {mid}: {title}")
    if len(affected_meetings) >= 20:
        print(f"    ... (只显示前 20)")

    if dry_run:
        print(f"\n[DRY-RUN] 不修改 DB. 实际执行请去掉 --dry-run")
        return {"status": "dry_run"}

    # 实际回滚
    async with session_factory() as db:
        # 写一条 audit (source="rollback")
        history = MemberVoiceHistory(
            member_id=member.id,
            source="rollback",
            old_embedding=list(member.voice_embedding) if member.voice_embedding is not None else None,
            new_embedding=target_emb,
            sample_count_before=member.voice_sample_count or 0,
            sample_count_after=target_cnt,
            weight=None,
            notes=f"rollback from history #{target_history.id}: {(target_history.notes or '')[:120]}",
        )
        db.add(history)

        # 更新 member
        r = await db.execute(select(Member).where(Member.id == member.id))
        m = r.scalar_one()
        m.voice_embedding = target_emb
        m.voice_sample_count = target_cnt

        from datetime import datetime
        m.voice_enrolled_at = datetime.utcnow()

        await db.commit()
        print(f"\n✅ 已回滚 {member.name}: sample_count → {target_cnt}")
        return {"status": "ok"}


async def amain():
    parser = argparse.ArgumentParser(description="回滚 member voice_embedding 到历史 audit 状态")
    parser.add_argument("--member", type=str, required=True, help="成员名称, 如 '杜同贺'")
    parser.add_argument("--list-history", action="store_true", help="列出该 member 的 audit 链")
    parser.add_argument("--rollback-to-history-id", type=int, help="精确回滚到指定 history id")
    parser.add_argument("--rollback-to-before-meeting", type=int, help="智能回滚到该会议处理前的状态")
    parser.add_argument("--dry-run", action="store_true", help="只显示影响范围, 不修改 DB")
    args = parser.parse_args()

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, expire_on_commit=False)

    member = await get_member_by_name(sf, args.member)
    if not member:
        print(f"❌ 成员 '{args.member}' 不存在")
        await engine.dispose()
        sys.exit(1)

    if args.list_history:
        await print_history(sf, args.member)
    elif args.rollback_to_history_id:
        async with sf() as db:
            r = await db.execute(
                select(MemberVoiceHistory)
                .where(MemberVoiceHistory.id == args.rollback_to_history_id)
            )
            h = r.scalar_one_or_none()
            if not h:
                print(f"❌ history #{args.rollback_to_history_id} 不存在")
                await engine.dispose()
                sys.exit(1)
            if h.member_id != member.id:
                print(f"❌ history #{args.rollback_to_history_id} 不属于 {args.member}")
                await engine.dispose()
                sys.exit(1)
        await rollback_to_history(sf, member, h, dry_run=args.dry_run)
    elif args.rollback_to_before_meeting:
        h = await find_history_before_meeting(sf, member, args.rollback_to_before_meeting)
        if not h:
            print(f"❌ 找不到会议 {args.rollback_to_before_meeting} 之前的 audit entry")
            await engine.dispose()
            sys.exit(1)
        await rollback_to_history(sf, member, h, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(amain())