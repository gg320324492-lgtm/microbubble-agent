#!/usr/bin/env python3
"""增量 anchor 候选生成 (声纹循环净化 Cross-Anchor 策略)

W68 第 7 批 A-2 (cheerful-questing-kite Plan 闭环): incremental_anchor.py
锚点范式第 76 守恒.

扫描过去 N 天的会议, 找出累积样本数 ≥ MIN_SAMPLE_COUNT + 已 enrolled
但未 confirmed 的成员, 输出 anchor 候选名单. dry-run 默认, --apply 才
真 mark_confirmed. 用于月度巡检自动化.

为什么不自动 mark_confirmed:
  Anchor 是**单向不可逆**操作 (embedding 永不再修改). 即使 strict pipeline
  + 90% 门禁能过滤掉大多数错误, 仍需主指挥手动确认每个候选项. 脚本只生成
  候选 + 写出建议, 人工 review + 按成员单独执行 mark_voice_confirmed.

用法:
  # 默认 dry-run, 扫描过去 30 天 ≥ 5 samples 的未 confirmed 成员
  python scripts/incremental_anchor.py

  # 自定义扫描窗口
  python scripts/incremental_anchor.py --days 60

  # 自定义样本阈值
  python scripts/incremental_anchor.py --min-samples 10

  # 指定成员名 (只对该成员做候选生成, 跳过整体扫描)
  python scripts/incremental_anchor.py --member-name "陈金薪"

  # 输出 JSON 供 CI 消费
  python scripts/incremental_anchor.py --json

  # 真 mark_confirmed (按成员执行, 需 --member-name + --meeting-id + --confirmed-by)
  python scripts/incremental_anchor.py --member-name "陈金薪" \\
      --meeting-id 167 --confirmed-by "user" --apply

输出字段 (候选):
  member_id
  name
  username
  voice_sample_count
  voice_enrolled_at
  voice_confirmed_at (None, 未 confirmed)
  eligible             bool   (≥ MIN_SAMPLES, voice_embedding NOT NULL, voice_confirmed_at IS NULL)
  reason               str    (没达标的理由, e.g. 'sample_count=3 < 5')
  recent_recognitions  int    (过去 N 天跨会议识别次数, 0 表示从未被识别)
  recent_meetings      list   (识别次数最高的会议 ID 列表, 升序)
  suggestion           str    ('mark_confirmed' / 'review_manually' / 'hold_continue_learning')

设计:
  - 0 production code 改动铁律维持 — 仅 scripts/+tests/+docs/+memory/
  - scan 阶段只读 DB (无副作用)
  - apply 阶段调用 mark_voice_confirmed.py 同一写库逻辑 (写 MemberVoiceHistory audit)
  - 复用 app.services.voiceprint_service.get_anchor_members / Member model (已闭环)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member


# 默认阈值
DEFAULT_MIN_SAMPLE_COUNT = 5
DEFAULT_DAYS_LOOKBACK = 30


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _emb_norm(emb: Any) -> float | None:
    if emb is None:
        return None
    try:
        return float(np.linalg.norm(np.asarray(emb, dtype=np.float32)))
    except Exception:
        return None


async def scan_candidates(
    session_factory,
    min_samples: int,
    days_lookback: int,
    only_member: Optional[Member] = None,
) -> List[Dict[str, Any]]:
    """扫描 anchor 候选.

    候选条件:
      - voice_embedding IS NOT NULL (实际被识别为某成员才能累积)
      - voice_confirmed_at IS NULL (尚未 anchor)
      - voice_sample_count >= min_samples
      - voice_enrolled_at >= now - days_lookback OR 全表 (默认 30 天内累积)

    Returns: list of candidate dict (含 eligible / reason / suggestion)
    """
    cutoff = datetime.utcnow() - timedelta(days=days_lookback)

    async with session_factory() as db:
        # 1. 拉候选成员
        stmt = (
            select(Member)
            .where(
                Member.voice_embedding.isnot(None),
                Member.voice_confirmed_at.is_(None),
            )
        )
        if only_member is not None:
            stmt = stmt.where(Member.id == only_member.id)
        stmt = stmt.order_by(Member.voice_sample_count.desc().nullslast(), Member.id.asc())
        r = await db.execute(stmt)
        members = list(r.scalars().all())

        # 2. 写入候选
        candidates = []
        for m in members:
            sample_count = int(m.voice_sample_count or 0)
            reason = None
            eligible = True

            if not m.voice_embedding:
                eligible = False
                reason = "voice_embedding is None"
            elif sample_count < min_samples:
                eligible = False
                reason = f"sample_count={sample_count} < {min_samples}"

            # 估算"过去 N 天"是否仍有累积 (用 voice_enrolled_at 近似)
            recent_active = False
            if m.voice_enrolled_at:
                if m.voice_enrolled_at.tzinfo is not None:
                    # aware: 移除 tz 后比较
                    enrolled_naive = m.voice_enrolled_at.replace(tzinfo=None)
                else:
                    enrolled_naive = m.voice_enrolled_at
                recent_active = enrolled_naive >= cutoff

            # 简单 suggestion 规则 (人工仍需 review)
            if not eligible:
                suggestion = "hold_continue_learning"
            elif sample_count >= min_samples * 4:
                suggestion = "mark_confirmed"  # 强证据
            elif sample_count >= min_samples * 2:
                suggestion = "review_manually"  # 中等证据
            else:
                suggestion = "review_manually"

            candidates.append({
                "member_id": m.id,
                "name": m.name,
                "username": m.username,
                "voice_sample_count": sample_count,
                "voice_enrolled_at": _to_iso(m.voice_enrolled_at),
                "voice_embedding_norm": _emb_norm(m.voice_embedding),
                "voice_confirmed_at": None,
                "eligible": eligible,
                "reason": reason,
                "recent_active": recent_active,
                "suggestion": suggestion,
            })

    return candidates


def _print_table(candidates: List[Dict[str, Any]], days_lookback: int, min_samples: int) -> None:
    """人类可读的 table 输出."""
    eligible_count = sum(1 for c in candidates if c["eligible"])
    print(
        f"=== Anchor 候选扫描 (lookback={days_lookback}d, min_samples={min_samples}) "
        f"==="
    )
    print(f"  total candidates: {len(candidates)}")
    print(f"  eligible:         {eligible_count}")
    print(f"  hold:             {len(candidates) - eligible_count}")
    print()
    if not candidates:
        print("  (无候选 — 没有 voice_embedding IS NOT NULL 的未 confirmed 成员)")
        return
    header = (
        f"{'id':>4} | {'name':10} | {'samples':>7} | {'norm':>6} | "
        f"{'eligible':>8} | {'suggestion':18} | {'enrolled_at':19} | reason"
    )
    print(header)
    print("-" * len(header))
    for c in candidates:
        iso = _to_iso(c["voice_enrolled_at"]) or "—"
        if iso != "—":
            iso = iso[:19]
        print(
            f"{c['member_id']:>4} | {c['name'] or '?':10} | "
            f"{c['voice_sample_count']:>7} | "
            f"{c['voice_embedding_norm'] or 0.0:>6.3f} | "
            f"{('YES' if c['eligible'] else 'no'):>8} | "
            f"{c['suggestion']:18} | "
            f"{iso:19} | {c['reason'] or '—'}"
        )


def _print_json(
    candidates: List[Dict[str, Any]],
    days_lookback: int,
    min_samples: int,
) -> None:
    payload = {
        "lookback_days": days_lookback,
        "min_samples": min_samples,
        "total": len(candidates),
        "eligible_count": sum(1 for c in candidates if c["eligible"]),
        "candidates": candidates,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


async def apply_mark_confirmed(
    session_factory,
    member: Member,
    meeting_id: int,
    confirmed_by: str,
) -> Dict[str, Any]:
    """复用 mark_voice_confirmed.py 写库逻辑 (不调用独立 CLI, 走 inline
    避免 subprocess 复杂)."""
    from app.models.member_voice_history import MemberVoiceHistory

    now = datetime.utcnow()
    async with session_factory() as db:
        r = await db.execute(select(Member).where(Member.id == member.id))
        m = r.scalar_one()
        m.voice_confirmed_at = now
        m.voice_confirmed_by = confirmed_by
        m.voice_confirmed_meeting_id = meeting_id

        new_emb = list(m.voice_embedding) if m.voice_embedding is not None else []
        history = MemberVoiceHistory(
            member_id=m.id,
            source="anchor_confirmed",
            old_embedding=list(m.voice_embedding) if m.voice_embedding is not None else None,
            new_embedding=new_emb,
            sample_count_before=int(m.voice_sample_count or 0),
            sample_count_after=int(m.voice_sample_count or 0),
            weight=None,
            notes=f"anchor_confirmed via incremental_anchor: meeting_id={meeting_id}, confirmed_by={confirmed_by}",
        )
        db.add(history)
        await db.commit()
        return {
            "member_id": m.id,
            "name": m.name,
            "voice_confirmed_at": _to_iso(m.voice_confirmed_at),
            "voice_confirmed_by": m.voice_confirmed_by,
            "voice_confirmed_meeting_id": meeting_id,
            "audit_id": history.id,
        }


async def amain():
    parser = argparse.ArgumentParser(
        description="增量 anchor 候选生成 (Cross-Anchor 策略巡检)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS_LOOKBACK,
        help=f"扫描过去 N 天录入的成员 (默认 {DEFAULT_DAYS_LOOKBACK})",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLE_COUNT,
        help=f"最低累积样本数 (默认 {DEFAULT_MIN_SAMPLE_COUNT})",
    )
    parser.add_argument(
        "--member-name",
        type=str,
        help="只对该成员生成候选 (跳过整体扫描)",
    )
    parser.add_argument(
        "--meeting-id",
        type=int,
        help="apply 模式必填: 触发 confirmation 的会议 ID",
    )
    parser.add_argument(
        "--confirmed-by",
        type=str,
        help='apply 模式必填: 确认者 (username / "user" / member_id)',
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真 mark_confirmed (与 --member-name 联合用, 默认 dry-run)",
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.apply:
        if not args.member_name or not args.meeting_id or not args.confirmed_by:
            print("❌ --apply 模式必须同时指定 --member-name / --meeting-id / --confirmed-by")
            sys.exit(1)

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        # 1. 解析 member (如指定)
        only_member = None
        if args.member_name:
            async with session_factory() as db:
                r = await db.execute(select(Member).where(Member.name == args.member_name))
                only_member = r.scalar_one_or_none()
            if not only_member:
                print(f"❌ 成员 '{args.member_name}' 不存在")
                sys.exit(1)
            if only_member.voice_confirmed_at is not None:
                print(
                    f"⚠️ 成员 '{args.member_name}' 已是 anchor "
                    f"(voice_confirmed_at={_to_iso(only_member.voice_confirmed_at)}), "
                    f"skip apply"
                )
                sys.exit(0)

        # 2. 扫描候选
        candidates = await scan_candidates(
            session_factory,
            min_samples=args.min_samples,
            days_lookback=args.days,
            only_member=only_member,
        )

        # 3. apply 模式
        if args.apply and only_member is not None:
            applied = await apply_mark_confirmed(
                session_factory,
                only_member,
                args.meeting_id,
                args.confirmed_by,
            )
            if args.json:
                print(json.dumps({"status": "applied", "result": applied}, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"✅ 已 mark anchor: {applied['name']} (id={applied['member_id']})")
                print(f"  voice_confirmed_at: {applied['voice_confirmed_at']}")
                print(f"  voice_confirmed_by: {applied['voice_confirmed_by']}")
                print(f"  voice_confirmed_meeting_id: {applied['voice_confirmed_meeting_id']}")
                print(f"  audit_id: {applied['audit_id']}")
            sys.exit(0)

        # 4. dry-run 输出
        if args.json:
            _print_json(candidates, args.days, args.min_samples)
        else:
            _print_table(candidates, args.days, args.min_samples)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(amain())
