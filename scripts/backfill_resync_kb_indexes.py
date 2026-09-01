"""WP3 (2026-09-02): 多模态 inline 后索引重刷 存量回填

背景: _run_analyze_and_embed 旧时序中 Step 1 (embedding/chunks/BM25) 先于
Step 7/7b (提取 + inline 回写 content) — 已 inline 进 content 的 OCR/表格
文字从未进任何索引。本脚本对"有提取产物"的 kb 文档重刷全套索引。

判定: knowledge_images (ocr 行) 或 knowledge_extractions 行存在 → 视为有
提取产物; resync_content_indexes 幂等可重跑。

dry-run 默认。

用法 (容器内):
    docker compose exec app python scripts/backfill_resync_kb_indexes.py
    docker compose exec app python scripts/backfill_resync_kb_indexes.py --apply
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
logger = logging.getLogger("backfill_resync_kb")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP3: 多模态 inline 后索引重刷回填")
    parser.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    parser.add_argument("--knowledge-id", type=int, default=0, help="只处理指定文档")
    return parser.parse_args()


async def _targets(db, knowledge_id: int):
    """有提取产物 (图片 OCR 行 或 extraction 行) 的 kb 文档 id 集合"""
    from app.models.knowledge import Knowledge
    from app.models.knowledge_multimodal import KnowledgeExtraction, KnowledgeImage

    img_ids = set(
        (await db.execute(select(KnowledgeImage.knowledge_id))).scalars().all()
    )
    ext_ids = set(
        (await db.execute(select(KnowledgeExtraction.knowledge_id))).scalars().all()
    )
    todo_ids = (img_ids | ext_ids)
    stmt = select(Knowledge).where(
        Knowledge.deleted_at.is_(None),
        Knowledge.storage_mode == "kb",
    )
    if knowledge_id:
        stmt = stmt.where(Knowledge.id == knowledge_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [k for k in rows if k.id in todo_ids]


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"targets": 0, "resynced": 0, "failed": 0, "dry_run": not args.apply}
    try:
        from app.services.knowledge_service import resync_content_indexes

        async with Session() as db:
            targets = await _targets(db, args.knowledge_id)
        stats["targets"] = len(targets)
        logger.info(
            "有提取产物的 kb 文档: %d 篇%s",
            len(targets), " (dry-run)" if not args.apply else "",
        )

        for i, k in enumerate(targets, 1):
            if not args.apply:
                logger.info("  [dry-run] 待重刷 knowledge_id=%s (%s)", k.id, (k.title or "")[:30])
                continue
            try:
                r = await resync_content_indexes(k.id, k.content or "", Session)
                ok = all(r.values())
                stats["resynced" if ok else "failed"] += 1 if ok else 1
                if not ok:
                    stats["failed"] += 0  # 部分失败已计 resynced, 明细在日志
                logger.info("[%d/%d] knowledge_id=%s → %s", i, len(targets), k.id, r)
            except Exception as e:
                stats["failed"] += 1
                logger.warning("knowledge_id=%s 重刷失败: %s", k.id, e)
    finally:
        await engine.dispose()

    import json

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
