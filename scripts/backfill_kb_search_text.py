"""agent 14 号 (2026-10-09): 回填 kb 行 search_text (全文检索通道)

问题:
  `knowledge.search_text` 是 PG 全文检索通道的源 (content_tsvector 是
  GENERATED ALWAYS AS to_tsvector('simple', COALESCE(search_text,'')) STORED)。
  入库时的 PR3 钩子 (app/services/knowledge_service.py:198-213) 会把父行 content
  经 split_for_tsvector 写入 search_text —— 但**存量**有 100 个 kb 行早于该钩子
  上线 (或走了绕过钩子的路径), search_text 至今 IS NULL, content_tsvector 全空,
  这些文档在全文/BM25 检索里等于不存在。

  实测 (2026-10-09): kb 侧 search_text IS NULL = 100 行, 其中:
    - 98 行 content 有真实文本 (含 PPT/PDF 的 [PAGE:N] 解析产物, 60~8621 字符)
    - 2 行是占位 (id=253 "[RECOVERED]" 11 字, id=540 "test content" 12 字)

修复策略 (与 drive 回填的**关键差异**):
  drive 行的父行 content 只是 29-37 字符占位串 ("[drive upload] <file>"), 真内容
  在 knowledge_chunks, 所以 drive 脚本**拼 chunk 正文**当源。
  **kb 行的 content 本体就是真实文本** (与入库钩子 line 208 喂给 split_for_tsvector
  的是同一个 content), 因此直接用 content 作源, **不拼 chunk** —— 这样与线上
  入库路径逐字节同语义, 也避免 chunk 边界造成的重复/截断偏差。

  content_tsvector 是 GENERATED STORED 列, search_text 更新后 PG 自动重算,
  无需手工重建 tsvector。

幂等: 只处理 storage_mode='kb' 且 search_text IS NULL/'' 的行; 重跑安全
      (--refresh-all 可强制覆盖全部 kb 行, 用于修占位污染行)。

用法 (容器内):
    docker exec microbubble-agent-app-1 python scripts/backfill_kb_search_text.py
    docker exec microbubble-agent-app-1 python scripts/backfill_kb_search_text.py --apply --limit 3
    docker exec microbubble-agent-app-1 python scripts/backfill_kb_search_text.py --apply --refresh-all

⚠️ 输出长度 (2026-10-09 agent24 已修, agent36 删兜底):
   split_for_tsvector 的 max_chars=6000 现在是**最终输出预算** (按 token 边界
   裁剪), 保证 len(out) <= 6000, 不会再撞 ck_knowledge_search_text_len。
   本脚本原先的 `st[:6000]` 字符级兜底已删除 —— 它是**半词污染的源头**
   (从词中间劈开, 如 "核心 水质 传"; PG 把半词当独立 lexeme 建索引)。
   现改为 assert: 真超限就 fail loud, 绝不静默造半词。
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
logger = logging.getLogger("backfill_kb_search_text")

# ck_knowledge_search_text_len 约束上限
SEARCH_TEXT_MAX = 6000


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填 kb 行 search_text")
    p.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    p.add_argument("--refresh-all", action="store_true",
                   help="覆盖所有 kb 行 (含已被占位 token 污染的行)")
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 行 (0=全部)")
    return p.parse_args()


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.models.knowledge import Knowledge
    from app.services.text_splitter import split_for_tsvector
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats: Dict[str, object] = {
        "scanned": 0, "updated": 0, "skipped_empty_content": 0, "failed": 0,
        "dry_run": not args.apply,
    }

    # 选行: kb + 未软删; 默认仅 search_text 空的行
    cond = "k.deleted_at IS NULL AND k.storage_mode='kb'"
    if args.refresh_all:
        pass  # 全部 kb
    else:
        cond += " AND (k.search_text IS NULL OR k.search_text='')"

    sel = text(f"SELECT k.id, k.title, length(btrim(coalesce(k.content,''))) AS clen "
               f"FROM knowledge k WHERE {cond} ORDER BY k.id"
               + (f" LIMIT {args.limit}" if args.limit else ""))

    try:
        async with Session() as db:
            rows = (await db.execute(sel)).all()
        stats["scanned"] = len(rows)
        logger.info("待回填 kb 行: %d", len(rows))

        if not args.apply:
            for kid, title, clen in rows[:20]:
                logger.info("  [dry-run] id=%s content_len=%s title=%s", kid, clen, (title or "")[:35])
            if len(rows) > 20:
                logger.info("  ... 其余 %d 行省略", len(rows) - 20)
            return 0

        for i, (kid, title, _clen) in enumerate(rows, 1):
            try:
                async with Session() as db:
                    k = (await db.execute(select(Knowledge).where(Knowledge.id == kid))).scalar_one_or_none()
                    if k is None:
                        continue
                    body = (k.content or "").strip()
                    if not body:
                        stats["skipped_empty_content"] += 1
                        logger.warning("[%d/%d] id=%s content 为空, 跳过", i, len(rows), kid)
                        continue
                    # kb 直接用 content 作源 (与线上入库钩子 line 208 同语义)
                    st = split_for_tsvector(body)
                    # ⚠️ 不做 `st[:6000]` 字符级硬切 (2026-10-09 agent36 删):
                    #   agent24 已把 max_chars 改成**输出预算**, split_for_tsvector
                    #   保证 len(out) <= 6000, 这里的兜底已是死代码; 保留反而在
                    #   将来出 bug 时从词中间劈开 (实测留下 "核心 水质 传" 半词,
                    #   PG to_tsvector 把半词当独立 lexeme 建索引, 污染召回)。
                    #   存量受害者: kb 2461/2601/2614 + drive 1086/1226/1239
                    #   (drive 侧已由 backfill_drive_search_text.py 修复)。
                    assert len(st) <= SEARCH_TEXT_MAX, (
                        f"id={kid} split_for_tsvector 输出 {len(st)} > {SEARCH_TEXT_MAX}; "
                        f"max_chars 语义疑似回退, 拒绝写入以免造半词"
                    )
                    # 幂等: 与存量逐字比对, --refresh-all 才不会把 429 行
                    # 无差别重写 (白白 bump updated_at + 触发 GENERATED 列重算)
                    if st == (k.search_text or ""):
                        stats["unchanged"] = stats.get("unchanged", 0) + 1
                        continue
                    k.search_text = st
                    await db.commit()
                stats["updated"] += 1
                logger.info("[%d/%d] id=%s search_text=%d chars | %s",
                            i, len(rows), kid, len(st), (title or "")[:35])
            except Exception as e:
                stats["failed"] += 1
                logger.warning("[%d/%d] id=%s 回填失败: %s", i, len(rows), kid, e)
    finally:
        await engine.dispose()

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
