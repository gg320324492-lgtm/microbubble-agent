"""WP3 (2026-09-01): 存量 kb 文档 chunk 回填 — citation 段落级溯源数据补齐

背景 (fuzzy-questing-prism WP3/WP10):
  knowledge_chunks 此前仅 9 行且全是 Playwright 测试残留; 检索链 (WP1.2)
  已把 chunk_id 接进 citation, 但存量文档无 chunk → citation 对老文档不生效。
  本脚本遍历 kb + 未软删除且无 chunk 的文档, 调 write_chunks_for_knowledge
  (切分 + 落库 + chunk embedding 批量回填, WP2.1)。纯本地切分 + 本地
  embedding 推理, 无 LLM 调用。

幂等: write_chunks_for_knowledge 先 DELETE 该文档全部 chunk 再 INSERT, 可重跑。
范围: storage_mode='kb' AND deleted_at IS NULL AND content 非空
      (drive/private 文档不入检索, 不需要 chunk)。

用法 (容器内):
    docker compose exec app python scripts/backfill_kb_chunks.py --dry-run
    docker compose exec app python scripts/backfill_kb_chunks.py --apply
    docker compose exec app python scripts/backfill_kb_chunks.py --apply --limit 20
    docker compose exec app python scripts/backfill_kb_chunks.py --apply --knowledge-id 42
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_kb_chunks")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP3: 存量 kb 文档 chunk 回填")
    parser.add_argument(
        "--apply", action="store_true", help="真写库 (默认 dry-run 只统计)"
    )
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 篇 (0 = 全部)")
    parser.add_argument("--knowledge-id", type=int, default=0, help="只处理指定文档")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge import Knowledge
    from app.models.knowledge_chunk import KnowledgeChunk
    from app.services.chunking_service import write_chunks_for_knowledge
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"scanned": 0, "todo": 0, "chunked": 0, "failed": 0, "dry_run": not args.apply}
    try:
        async with Session() as db:
            stmt = select(Knowledge.id, Knowledge.title).where(
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "kb",
                Knowledge.content.isnot(None),
                Knowledge.content != "",
            )
            if args.knowledge_id:
                stmt = stmt.where(Knowledge.id == args.knowledge_id)
            if args.limit:
                stmt = stmt.limit(args.limit)
            rows = (await db.execute(stmt)).all()
            stats["scanned"] = len(rows)
            logger.info("扫描 kb 文档: %d 篇", len(rows))

            # 找出无 chunk 的文档 (LEFT JOIN 语义: 分两次查询, 简单可靠)
            todo_ids: List[int] = []
            for kid, title in rows:
                has = (
                    await db.execute(
                        select(KnowledgeChunk.id).where(KnowledgeChunk.knowledge_id == kid).limit(1)
                    )
                ).scalar()
                if has is None:
                    todo_ids.append(kid)
            stats["todo"] = len(todo_ids)
            logger.info("缺 chunk 文档: %d 篇%s", len(todo_ids), " (dry-run)" if not args.apply else "")

            if not args.apply:
                for kid in todo_ids[:50]:
                    logger.info("  [dry-run] 待回填 knowledge_id=%s", kid)
                if len(todo_ids) > 50:
                    logger.info("  ... 其余 %d 篇省略", len(todo_ids) - 50)
                return 0

            for i, kid in enumerate(todo_ids, 1):
                try:
                    async with Session() as wdb:
                        row = (await wdb.execute(select(Knowledge).where(Knowledge.id == kid))).scalar_one_or_none()
                    if row is None:
                        continue
                    inserted = await write_chunks_for_knowledge(
                        knowledge_id=kid,
                        content=row.content,
                        session_factory=Session,
                    )
                    stats["chunked"] += 1
                    logger.info("[%d/%d] knowledge_id=%s → %d chunks", i, len(todo_ids), kid, inserted)
                except Exception as e:
                    stats["failed"] += 1
                    logger.warning("knowledge_id=%s 回填失败: %s", kid, e)
    finally:
        await engine.dispose()

    import json

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
