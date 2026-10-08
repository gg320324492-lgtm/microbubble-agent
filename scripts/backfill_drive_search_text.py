"""agent 12 号 (2026-10-09): 回填 drive 行 search_text (全文检索通道)

问题:
  knowledge.search_text 是 PG 全文检索 (content_tsvector GENERATED 列) 的源。
  drive 行入库时, ingestion 钩子把 **父行 content 的占位串**
  ("[drive upload] <filename>", 29-37 字符) 喂进 split_for_tsvector —— 真内容
  在 knowledge_chunks 里 (download 解析产物), 不在父行 content。结果 drive 文件
  的全文检索通道几乎全空 (实测 278/326 空, 另 48 个只有 "drive upload ..." 占位 token)。

修复:
  对 drive 行, 用**该行全部 chunk 的正文拼接**作为 search_text 源 (走
  split_for_tsvector 截断 + jieba 切词, 与 kb 路径同语义)。content_tsvector
  是 GENERATED STORED 列, search_text 更新后 PG 自动重算, 无需手工重建 tsvector。

幂等: 只更新 storage_mode='drive' 且当前 search_text 为空/占位的行; 重跑安全
      (--refresh-all 可强制覆盖所有 drive 行, 含已被占位污染的行)。

用法 (容器内):
    docker exec microbubble-agent-app-1 python scripts/backfill_drive_search_text.py
    docker exec microbubble-agent-app-1 python scripts/backfill_drive_search_text.py --apply
    docker exec microbubble-agent-app-1 python scripts/backfill_drive_search_text.py --apply --refresh-all
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_drive_search_text")

# 占位串特征: ingestion 写进父行 content 的 "[drive upload] xxx" 派生 token
PLACEHOLDER_PREFIX = "drive upload"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填 drive 行 search_text")
    p.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    p.add_argument("--refresh-all", action="store_true",
                   help="覆盖所有 drive 行 (含已被占位 token 污染的行)")
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 行 (0=全部)")
    return p.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge import Knowledge
    from app.models.knowledge_chunk import KnowledgeChunk
    from app.services.text_splitter import split_for_tsvector
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats: Dict[str, object] = {
        "scanned": 0, "todo": 0, "updated": 0, "failed": 0, "dry_run": not args.apply,
    }

    cond = (
        "k.deleted_at IS NULL AND k.storage_mode='drive' AND "
        "(k.search_text IS NULL OR k.search_text=''"
        + ("" if args.refresh_all else "")
        + ")"
    )
    if args.refresh_all:
        cond = "k.deleted_at IS NULL AND k.storage_mode='drive'"
    if not args.refresh_all:
        # 也纳入"只有占位 token"的已填行 (长度短 + 以 drive upload 开头)
        cond += " OR (k.search_text LIKE 'drive upload%')"

    sel = text(f"SELECT k.id, k.title, k.search_text FROM knowledge k WHERE {cond} ORDER BY k.id"
               + (f" LIMIT {args.limit}" if args.limit else ""))

    try:
        async with Session() as db:
            rows = (await db.execute(sel)).all()
        stats["scanned"] = len(rows)
        logger.info("待回填 drive 行: %d", len(rows))

        if not args.apply:
            for kid, title, st in rows[:20]:
                logger.info("  [dry-run] id=%s title=%s cur_search_text_len=%s", kid, (title or "")[:35], len(st or ""))
            if len(rows) > 20:
                logger.info("  ... 其余 %d 行省略", len(rows) - 20)
            return 0

        for i, (kid, title, _) in enumerate(rows, 1):
            try:
                async with Session() as db:
                    k = (await db.execute(select(Knowledge).where(Knowledge.id == kid))).scalar_one_or_none()
                    if k is None:
                        continue
                    chunks = (
                        await db.execute(
                            select(KnowledgeChunk.content)
                            .where(KnowledgeChunk.knowledge_id == kid)
                            .order_by(KnowledgeChunk.chunk_index)
                        )
                    ).scalars().all()
                    body = "\n".join(c for c in chunks if c)
                    if not body.strip():
                        logger.warning("[%d/%d] id=%s 无 chunk 正文, 跳过", i, len(rows), kid)
                        continue
                    # 注意: split_for_tsvector 的 max_chars 截的是**原始输入**,
                    # jieba 切词+空格拼接后 token 串可能 > 6000 (ck_knowledge_search_text_len
                    # 约束 ≤6000)。此处对最终输出再兜底截断 (实测 3 行撞过该约束)。
                    st = split_for_tsvector(body)
                    if len(st) > 6000:
                        st = st[:6000]
                    k.search_text = st
                    await db.commit()
                stats["updated"] += 1
                logger.info("[%d/%d] id=%s search_text=%d chars | %s",
                            i, len(rows), kid, len(k.search_text or ""), (title or "")[:35])
            except Exception as e:
                stats["failed"] += 1
                logger.warning("[%d/%d] id=%s 回填失败: %s", i, len(rows), kid, e)
    finally:
        await engine.dispose()

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
