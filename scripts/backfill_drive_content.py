"""WP2 (2026-09-02): drive 文件内容索引存量回填

背景: drive 模式文件 (277 个) 原文在 MinIO 不可检索。本脚本遍历
storage_mode='drive' 且未删除的行, 解析原文 → 分块 → embedding 入
knowledge_chunks (幂等)。

dry-run 默认: 只统计/列出, 不写库。
限速: 逐文件处理, embedding 批量 (内部), 失败仅记录。

用法 (容器内):
    docker compose exec app python scripts/backfill_drive_content.py
    docker compose exec app python scripts/backfill_drive_content.py --apply
    docker compose exec app python scripts/backfill_drive_content.py --apply --limit 50
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
logger = logging.getLogger("backfill_drive_content")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP2: drive 文件内容索引回填")
    parser.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个 (0 = 全部)")
    parser.add_argument("--knowledge-id", type=int, default=0, help="只处理指定文件")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge import Knowledge
    from app.services.drive_index_service import SUPPORTED_EXTS, _ext_of
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {
        "scanned": 0, "todo": 0, "indexed": 0, "skipped_ext": 0,
        "failed": 0, "dry_run": not args.apply,
    }
    try:
        async with Session() as db:
            stmt = select(Knowledge.id, Knowledge.file_name).where(
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
            if args.knowledge_id:
                stmt = stmt.where(Knowledge.id == args.knowledge_id)
            if args.limit:
                stmt = stmt.limit(args.limit)
            rows = (await db.execute(stmt)).all()

        stats["scanned"] = len(rows)
        todo = [(rid, fn) for rid, fn in rows if _ext_of(fn) in SUPPORTED_EXTS]
        stats["skipped_ext"] = len(rows) - len(todo)
        stats["todo"] = len(todo)
        logger.info(
            "扫描 drive 文件 %d, 可索引 %d (格式跳过 %d)%s",
            len(rows), len(todo), stats["skipped_ext"],
            " (dry-run)" if not args.apply else "",
        )

        if not args.apply:
            for rid, fn in todo[:50]:
                logger.info("  [dry-run] 待索引 knowledge_id=%s (%s)", rid, (fn or "")[:40])
            return 0

        from app.services.drive_index_service import index_drive_content

        for i, (rid, fn) in enumerate(todo, 1):
            try:
                r = await index_drive_content(rid, Session)
                stats["indexed"] += 1
                logger.info("[%d/%d] knowledge_id=%s → %s", i, len(todo), rid, r)
            except Exception as e:
                stats["failed"] += 1
                logger.warning("knowledge_id=%s 索引失败: %s", rid, e)
    finally:
        await engine.dispose()

    import json

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
