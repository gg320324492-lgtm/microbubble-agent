"""WP1 (2026-09-02): 会议转录 chunk 索引 + 摘要 embedding 存量回填

背景: 会议转录从未被 RAG 索引 (hybrid 不查 meetings); compute_and_store_embedding
此前零调用方 — 12/22 场连摘要向量都缺。本脚本:
1. 全部会议: index_meeting_transcript (转录 chunk + embedding, 幂等)
2. 摘要 embedding 为空的会议: compute_and_store_embedding 补算

dry-run 默认: 只统计, 不写库。

用法 (容器内):
    docker compose exec app python scripts/backfill_meeting_index.py
    docker compose exec app python scripts/backfill_meeting_index.py --apply
    docker compose exec app python scripts/backfill_meeting_index.py --apply --meeting-id 12
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_meeting_index")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP1: 会议转录/摘要 embedding 回填")
    parser.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    parser.add_argument("--meeting-id", type=int, default=0, help="只处理指定会议")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.meeting import Meeting
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"meetings": 0, "indexed": 0, "chunks": 0, "summary_embedded": 0, "failed": 0, "dry_run": not args.apply}
    try:
        async with Session() as db:
            stmt = select(Meeting.id, Meeting.title)
            if args.meeting_id:
                stmt = stmt.where(Meeting.id == args.meeting_id)
            rows = (await db.execute(stmt)).all()
        stats["meetings"] = len(rows)
        logger.info("扫描会议: %d 场%s", len(rows), " (dry-run)" if not args.apply else "")

        from app.services.meeting_service import compute_and_store_embedding
        from app.services.meeting_chunk_service import index_meeting_transcript

        for i, (mid, title) in enumerate(rows, 1):
            if not args.apply:
                logger.info("  [dry-run] 待索引 meeting_id=%s (%s)", mid, (title or "")[:30])
                continue
            try:
                r = await index_meeting_transcript(mid, Session)
                stats["chunks"] += r.get("chunks", 0)
                # 摘要 embedding 缺失 → 补算
                async with Session() as db:
                    m = await db.get(Meeting, mid)
                    if m is not None and m.embedding is None:
                        await compute_and_store_embedding(db, mid)
                        stats["summary_embedded"] += 1
                stats["indexed"] += 1
                logger.info("[%d/%d] meeting_id=%s → %s", i, len(rows), mid, r)
            except Exception as e:
                stats["failed"] += 1
                logger.warning("meeting_id=%s 回填失败: %s", mid, e)
    finally:
        await engine.dispose()

    import json

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
