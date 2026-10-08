"""agent 12 号 (2026-10-09): 重切分块 — 修 PPT/PDF 整份塌成 1 chunk 的存量数据

背景:
  chunking_service 的 `_chunk_by_page` 修复 (commit 10b060d08) 让 `paragraph`
  策略遇 `[PAGE:N]` 标记时自动按页优先切。但**存量** chunk 是用旧的纯 `\\n\\n`
  切法生成的 —— PPT/PDF 解析产物几乎不含 `\\n\\n` (实测 17 页 deck 0 次),
  整份塌成 1 个 chunk。全库 602 个文件 / 2017 个 chunk 含 `[PAGE:`, 其中
  1951 个是"无 `\\n\\n` 的单块"塌陷受害者。

  本脚本对这批文件重跑分块 (走修复后的代码), 把 1 块变成接近页数块。

两条分派路径 (关键, 不能混淆):
  - storage_mode='kb'  (304 个): 源在 `knowledge.content` 本体 →
    调 chunking_service.write_chunks_for_knowledge(knowledge_id, k.content)
  - storage_mode='drive' (298 个): 父行 content 只是 29-37 字符占位
    ("[drive upload] <file>"), 真内容在 MinIO 原文里 →
    调 drive_index_service.index_drive_content(knowledge_id) (重新下载+解析+切分)

两者都幂等 (先 DELETE 该 knowledge_id 全部 chunk 再 INSERT), 可安全重跑。

用法 (容器内):
    docker exec microbubble-agent-app-1 python scripts/rechunk_page_marker_docs.py --dry-run
    docker exec microbubble-agent-app-1 python scripts/rechunk_page_marker_docs.py --apply --limit 3
    docker exec microbubble-agent-app-1 python scripts/rechunk_page_marker_docs.py --apply
    docker exec microbubble-agent-app-1 python scripts/rechunk_page_marker_docs.py --apply --knowledge-id 42
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("rechunk_page_marker")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="重切含 [PAGE:N] 标记的塌陷 chunk")
    p.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 篇 (0=全部)")
    p.add_argument("--knowledge-id", type=int, default=0, help="只处理指定文档")
    return p.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge import Knowledge
    from app.services.chunking_service import write_chunks_for_knowledge
    from app.services.drive_index_service import index_drive_content
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 找受影响文件 (chunk 含 [PAGE:) + 处理前 chunk 数 (用于前后对比)
    sel_sql = text(
        """
        SELECT k.id, k.storage_mode, k.title,
               count(c.id) AS before_chunks,
               bool_or(c.content LIKE '%[PAGE:%') AS has_page
        FROM knowledge k
        JOIN knowledge_chunks c ON c.knowledge_id = k.id
        WHERE k.deleted_at IS NULL
        """
        + (" AND k.id = :kid" if args.knowledge_id else "")
        + """
        GROUP BY k.id, k.storage_mode, k.title
        HAVING bool_or(c.content LIKE '%[PAGE:%')
        ORDER BY k.id
        """
        + (f" LIMIT {args.limit}" if args.limit else "")
    )

    stats: Dict[str, object] = {
        "scanned": 0, "kb": 0, "drive": 0, "ok": 0, "failed": 0,
        "chunks_before": 0, "chunks_after": 0, "dry_run": not args.apply,
    }
    try:
        async with Session() as db:
            params = {"kid": args.knowledge_id} if args.knowledge_id else {}
            rows: List[Tuple] = (await db.execute(sel_sql, params)).all()

        stats["scanned"] = len(rows)
        stats["chunks_before"] = sum(r[3] for r in rows)
        logger.info("受影响文件: %d 篇, 处理前 chunk 总数: %d", len(rows), stats["chunks_before"])

        if not args.apply:
            for kid, mode, title, before, _ in rows[:30]:
                logger.info("  [dry-run] id=%s mode=%s before_chunks=%d title=%s", kid, mode, before, (title or "")[:40])
            if len(rows) > 30:
                logger.info("  ... 其余 %d 篇省略", len(rows) - 30)
            return 0

        for i, (kid, mode, title, before, _) in enumerate(rows, 1):
            try:
                if mode == "drive":
                    res = await index_drive_content(kid, Session)
                    after = res.get("chunks", 0)
                    stats["drive"] += 1
                    reason = res.get("reason", "")
                    if res.get("skipped"):
                        logger.warning("[%d/%d] drive id=%s skipped: %s (before=%d)", i, len(rows), kid, reason, before)
                    else:
                        stats["ok"] += 1
                else:
                    async with Session() as rdb:
                        k = (await rdb.execute(select(Knowledge).where(Knowledge.id == kid))).scalar_one_or_none()
                    if k is None or not k.content:
                        logger.warning("[%d/%d] kb id=%s 无 content, 跳过", i, len(rows), kid)
                        continue
                    after = await write_chunks_for_knowledge(knowledge_id=kid, content=k.content, session_factory=Session)
                    stats["kb"] += 1
                    stats["ok"] += 1
                stats["chunks_after"] += after
                logger.info("[%d/%d] id=%s mode=%s: %d -> %d chunks | %s",
                            i, len(rows), kid, mode, before, after, (title or "")[:40])
            except Exception as e:
                stats["failed"] += 1
                logger.warning("[%d/%d] id=%s 重切失败: %s", i, len(rows), kid, e)
    finally:
        await engine.dispose()

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
