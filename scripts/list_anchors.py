#!/usr/bin/env python3
"""列出当前所有 anchor 成员 (声纹循环净化 Cross-Anchor 策略)

W68 第 7 批 A-2 (cheerful-questing-kite Plan 闭环): list_anchors.py
锚点范式第 76 守恒.

Anchor 定义: voice_confirmed_at IS NOT NULL 的成员 (声纹 embedding 永不再修改)

用法:
  # 默认打印 (table 格式)
  python scripts/list_anchors.py

  # JSON 输出 (供下游自动化消费, e.g. CI 巡检)
  python scripts/list_anchors.py --json

  # 同时显示未 confirmed 但已 enrolled 的成员 (用于排查)
  python scripts/list_anchors.py --include-unconfirmed

输出字段:
  member_id         int
  username          str
  confirmed_at      ISO 8601 (anchor only)
  confirmed_by      str (anchor only)
  confirmed_meeting_id  int (anchor only)
  voice_sample_count    int
  enrolled_at       ISO 8601
  voice_embedding_norm  float

设计:
  - 0 production code 改动铁律维持 — 仅 scripts/+tests/+docs/+memory/
  - dry-run by default (read-only, 不修改任何 DB 状态)
  - 复用 SQLAlchemy session + VoiceprintService.get_anchor_members 已在 main app 闭环
  - 跨环境: 与 confirm 脚本共用同一 session factory 模式 (NullPool + 替换 url)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member


# anchor 链扩展顺序: 按 voice_confirmed_at 升序 (anchor #1 是最早)
ANCHOR_ORDER_BY = Member.voice_confirmed_at.asc()


def _to_iso(value: Any) -> str | None:
    """datetime → ISO 8601 (兼容 naive / aware)."""
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


async def fetch_anchors_and_enrolled(
    session_factory,
    include_unconfirmed: bool = False,
) -> tuple[List[Member], List[Member]]:
    """返回 (anchors, unconfirmed_enrolled) 双 tuple.

    anchors: voice_confirmed_at IS NOT NULL 的成员 (按 confirm 时间升序)
    unconfirmed_enrolled: voice_embedding IS NOT NULL 但 voice_confirmed_at IS NULL
    """
    async with session_factory() as db:
        # anchors
        r = await db.execute(
            select(Member)
            .where(
                Member.voice_embedding.isnot(None),
                Member.voice_confirmed_at.isnot(None),
            )
            .order_by(ANCHOR_ORDER_BY)
        )
        anchors = list(r.scalars().all())

        # unconfirmed enrolled (只在 --include-unconfirmed 时拉)
        unconfirmed = []
        if include_unconfirmed:
            r2 = await db.execute(
                select(Member)
                .where(
                    Member.voice_embedding.isnot(None),
                    Member.voice_confirmed_at.is_(None),
                )
                .order_by(Member.voice_sample_count.desc().nullslast(), Member.id.asc())
            )
            unconfirmed = list(r2.scalars().all())

    return anchors, unconfirmed


def _member_to_dict(m: Member) -> Dict[str, Any]:
    """统一序列化为下游可消费的 dict."""
    return {
        "member_id": m.id,
        "name": m.name,
        "username": m.username,
        "voice_sample_count": int(m.voice_sample_count or 0),
        "voice_enrolled_at": _to_iso(m.voice_enrolled_at),
        "voice_embedding_norm": _emb_norm(m.voice_embedding),
        "voice_confirmed_at": _to_iso(m.voice_confirmed_at),
        "voice_confirmed_by": m.voice_confirmed_by,
        "voice_confirmed_meeting_id": m.voice_confirmed_meeting_id,
    }


def _print_table(anchors: List[Member], unconfirmed: List[Member]) -> None:
    """人类可读的 table 输出."""
    print(f"=== 声纹 Anchor 列表 (Cross-Anchor 策略, {len(anchors)} 个) ===")
    if not anchors:
        print("  (无 anchor — 还没有成员被 mark_confirmed)")
        return
    header = (
        f"{'#':>3} | {'id':>4} | {'name':10} | {'username':12} | "
        f"{'confirmed_at':19} | {'by':8} | {'meet':>5} | "
        f"{'samples':>7} | {'norm':>6}"
    )
    print(header)
    print("-" * len(header))
    for i, m in enumerate(anchors, start=1):
        iso = _to_iso(m.voice_confirmed_at) or "—"
        if iso != "—":
            iso = iso[:19]  # 截掉时区秒后部分
        print(
            f"{i:>3} | {m.id:>4} | {m.name or '?':10} | "
            f"{(m.username or '—'):12} | {iso:19} | "
            f"{(m.voice_confirmed_by or '—'):8} | "
            f"{(m.voice_confirmed_meeting_id if m.voice_confirmed_meeting_id is not None else '—'):>5} | "
            f"{int(m.voice_sample_count or 0):>7} | "
            f"{_emb_norm(m.voice_embedding) or 0.0:>6.3f}"
        )

    if unconfirmed:
        print()
        print(f"=== 未 confirmed 但已 enrolled ({len(unconfirmed)} 个, 候选 anchor) ===")
        header2 = (
            f"{'id':>4} | {'name':10} | {'username':12} | "
            f"{'samples':>7} | {'norm':>6} | {'enrolled_at':19}"
        )
        print(header2)
        print("-" * len(header2))
        for m in unconfirmed:
            iso = _to_iso(m.voice_enrolled_at) or "—"
            if iso != "—":
                iso = iso[:19]
            print(
                f"{m.id:>4} | {m.name or '?':10} | "
                f"{(m.username or '—'):12} | "
                f"{int(m.voice_sample_count or 0):>7} | "
                f"{_emb_norm(m.voice_embedding) or 0.0:>6.3f} | "
                f"{iso:19}"
            )


def _print_json(anchors: List[Member], unconfirmed: List[Member]) -> None:
    """JSON 输出 (供 CI / 自动化消费)."""
    payload = {
        "count": len(anchors),
        "anchors": [_member_to_dict(m) for m in anchors],
        "unconfirmed_enrolled": [_member_to_dict(m) for m in unconfirmed],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


async def amain():
    parser = argparse.ArgumentParser(
        description="列出当前所有声纹 anchor 成员 (Cross-Anchor 策略)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出 (供 CI / 自动化消费)",
    )
    parser.add_argument(
        "--include-unconfirmed",
        action="store_true",
        help="同时输出未 confirmed 但已 enrolled 的成员 (用于排查候选 anchor)",
    )
    args = parser.parse_args()

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        anchors, unconfirmed = await fetch_anchors_and_enrolled(
            session_factory,
            include_unconfirmed=args.include_unconfirmed,
        )
    finally:
        await engine.dispose()

    if args.json:
        _print_json(anchors, unconfirmed)
    else:
        _print_table(anchors, unconfirmed)


if __name__ == "__main__":
    asyncio.run(amain())
