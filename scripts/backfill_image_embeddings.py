"""WP5 (2026-09-01): knowledge_images 存量 OCR embedding 回填

背景 (fuzzy-questing-prism WP5/WP10):
  迁移 129 给 knowledge_images 加了 embedding vector(1024) 列;
  multimodal_retriever 已改为 "有值直接用, NULL 才实时算"。
  本脚本把存量 ocr_status='done' 且 embedding IS NULL 的图片批量算好回填,
  使第 5 路多模态召回对存量图片立即生效 (否则首次 query 仍会现算)。

幂等: 只处理 embedding IS NULL 的行, 可重跑。
推理: 本地 embedding 模型 (generate_embeddings), 无 LLM/网络调用。

用法 (容器内):
    docker compose exec app python scripts/backfill_image_embeddings.py --dry-run
    docker compose exec app python scripts/backfill_image_embeddings.py --apply
    docker compose exec app python scripts/backfill_image_embeddings.py --apply --batch-size 8
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_image_embeddings")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WP5: 存量图片 OCR embedding 回填")
    parser.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run 只统计)")
    parser.add_argument("--batch-size", type=int, default=16, help="每批 embedding 条数")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 张 (0 = 全部)")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge_multimodal import KnowledgeImage
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"scanned": 0, "embedded": 0, "failed": 0, "dry_run": not args.apply}
    try:
        async with Session() as db:
            todo = (
                await db.execute(
                    select(
                        KnowledgeImage.id,
                        KnowledgeImage.ocr_text,
                    )
                    .where(
                        KnowledgeImage.embedding.is_(None),
                        KnowledgeImage.ocr_status == "done",
                        KnowledgeImage.ocr_text.isnot(None),
                        KnowledgeImage.ocr_text != "",
                    )
                    .order_by(KnowledgeImage.id)
                    .limit(args.limit or None)
                )
            ).all()
            stats["scanned"] = len(todo)
            logger.info("待回填图片: %d 张%s", len(todo), " (dry-run)" if not args.apply else "")

            if not args.apply:
                for image_id, _text in todo[:50]:
                    logger.info("  [dry-run] 待回填 image_id=%s", image_id)
                return 0

            from app.services.embedding_service import generate_embeddings
            from app.services.embedding_truncation_policy import truncate_for_embedding

            for i in range(0, len(todo), args.batch_size):
                batch = todo[i : i + args.batch_size]
                texts = [truncate_for_embedding(str(t or "")) for _iid, t in batch]
                embeddings = await generate_embeddings(texts, for_query=False)
                if not embeddings or len(embeddings) != len(batch):
                    stats["failed"] += len(batch)
                    logger.warning("批次 embedding 生成失败 (size=%d), 跳过", len(batch))
                    continue
                for (image_id, _t), emb in zip(batch, embeddings):
                    if emb is None:
                        stats["failed"] += 1
                        continue
                    await db.execute(
                        update(KnowledgeImage)
                        .where(KnowledgeImage.id == image_id)
                        .values(embedding=emb)
                    )
                    stats["embedded"] += 1
                await db.commit()
                logger.info(
                    "进度: %d/%d (embedded=%d failed=%d)",
                    min(i + args.batch_size, len(todo)),
                    len(todo),
                    stats["embedded"],
                    stats["failed"],
                )
    finally:
        await engine.dispose()

    import json

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
