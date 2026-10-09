"""回填 drive 行 search_text (全文检索通道)

问题:
  knowledge.search_text 是 PG 全文检索 (content_tsvector GENERATED 列) 的源。
  drive 行入库时, ingestion 钩子把**父行 content 的占位串**
  ("[drive upload] <filename>", 23-47 字符) 喂进 split_for_tsvector —— 真内容
  在 knowledge_chunks 里 (download 解析产物), 不在父行 content。

  实测 (2026-10-09 agent36): 326 个 drive 行**全部**是占位 content
  (min=23 / p50=36 / max=47 字符, `content LIKE '[drive upload]%'` = 326/326),
  而 kb 行 content 是真实文本 (p50=2473)。所以 drive **只能**用 chunk 正文作源,
  用 content 作源是设计错误 (这正是 agent12 初版脚本选择 chunk 拼接的理由)。

源的选择 (与 backfill_kb_search_text.py 的关键差异):
  drive: 优先 knowledge_chunks 正文拼接; **无 chunk 时回退 knowledge.content**
         (二进制文件 zip/png/m4a/mp4 等无解析产物, 回退至少让文件名可搜)
  kb:    直接用 content (kb 的 content 本体就是真实文本)

⚠️ split_for_tsvector 的 max_chars 语义 (2026-10-09 agent24 修正):
  max_chars=6000 是**最终输出预算**, 按 token 边界裁剪, 保证 len(out) <= 6000。
  本脚本**不再做 `st[:6000]` 字符级硬切** —— 那是 agent24 修掉的老 bug:
  字符级硬切会从词中间劈开 (实测留下 "核心 水质 传" 这种半词), PG to_tsvector
  把半词当独立 lexeme 建索引, 污染召回。旧脚本的兜底 `st[:6000]` 至今仍留在
  kb 脚本里, 曾导致 3 个 drive + 3 个 kb 行带半词 (见 --verify 输出)。

幂等:
  逐行重算并与存量**逐字比对**, 只写真正不同的行 —— 重跑安全, 且天然修复
  存量漂移 (如半词截断、content 变更后 search_text 未同步)。
  --refresh-all 可强制覆盖所有 drive 行 (含已被占位污染的行)。

用法 (⚠️ scripts/ **不是** bind mount, 容器内是镜像旧拷贝, 必须用 stdin 送入):
    docker exec -i -w /app microbubble-agent-app-1 python - < scripts/backfill_drive_search_text.py
    ... --apply                # 真写库 (默认 dry-run)
    ... --apply --backup       # 写前把 id + 旧值 + 新值预览导出到 data/backups/
    ... --apply --refresh-all  # 覆盖全部 drive 行
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_drive_search_text")

# 占位串特征: ingestion 写进父行 content 的 "[drive upload] xxx" 派生 token
PLACEHOLDER_PREFIX = "drive upload"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回填 drive 行 search_text")
    p.add_argument("--apply", action="store_true", help="真写库 (默认 dry-run)")
    p.add_argument("--refresh-all", action="store_true",
                   help="覆盖所有 drive 行 (含 search_text 已非空但漂移的行)")
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 行 (0=全部)")
    p.add_argument("--backup", action="store_true",
                   help="写库前把将被修改的行导出到 data/backups/ (建议 --apply 时必开)")
    p.add_argument("--preview-chars", type=int, default=220,
                   help="dry-run/日志里每行展示的 search_text 前缀长度")
    return p.parse_args()


def build_source_sql(refresh_all: bool) -> str:
    """选行条件。

    ⚠️ 括号纪律 (2026-10-09 agent36 修): SQL 里 AND 优先级高于 OR, 旧写法
    `... AND (st IS NULL OR st='') OR (st LIKE 'drive upload%')` 会被解析成
    `(A AND B AND C) OR (D)` —— **D 分支逃出了 storage_mode/deleted_at 守卫**,
    实测会误选已软删行 (id=2827 probe.txt)。整个 OR 组必须显式加括号。
    """
    guard = "k.deleted_at IS NULL AND k.storage_mode='drive'"
    if refresh_all:
        return guard
    return (
        f"{guard} AND ("
        "  k.search_text IS NULL OR k.search_text=''"
        f"  OR k.search_text LIKE '{PLACEHOLDER_PREFIX}%'"
        ")"
    )


async def compute_target(db, kid: int, split_for_tsvector) -> Tuple[Optional[str], str]:
    """重算目标 search_text, 返回 (新值, 源说明)。无源时返回 (None, 原因)。"""
    chunks = (
        await db.execute(
            text("SELECT content FROM knowledge_chunks "
                 "WHERE knowledge_id=:i ORDER BY chunk_index"),
            {"i": kid},
        )
    ).scalars().all()
    body = "\n".join(c for c in chunks if c).strip()
    if body:
        # drive 的真内容在 chunk 里 (父行 content 是占位串)
        return split_for_tsvector(body), f"chunks x{len(chunks)}"
    # 无 chunk (二进制 zip/png/m4a/mp4 等): 回退父行 content, 至少让文件名可搜
    parent = (await db.execute(
        text("SELECT content FROM knowledge WHERE id=:i"), {"i": kid}
    )).scalar_one_or_none()
    parent = (parent or "").strip()
    if parent:
        return split_for_tsvector(parent), "fallback:parent_content"
    return None, "no_source"


async def main() -> int:
    args = parse_args()

    from app.config import settings
    from app.services.text_splitter import split_for_tsvector
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats: Dict[str, object] = {
        "scanned": 0, "unchanged": 0, "updated": 0, "no_source": 0,
        "failed": 0, "dry_run": not args.apply,
    }
    backup_lines: List[dict] = []

    cond = build_source_sql(args.refresh_all)
    sel = text(f"SELECT k.id, k.title, k.search_text FROM knowledge k WHERE {cond} ORDER BY k.id"
               + (f" LIMIT {args.limit}" if args.limit else ""))

    try:
        async with Session() as db:
            rows = (await db.execute(sel)).all()
        stats["scanned"] = len(rows)
        logger.info("候选 drive 行: %d (refresh_all=%s)", len(rows), args.refresh_all)

        for i, (kid, title, cur_st) in enumerate(rows, 1):
            try:
                async with Session() as db:
                    target, src = await compute_target(db, kid, split_for_tsvector)
                    if target is None:
                        stats["no_source"] += 1
                        logger.warning("[%d/%d] id=%s 无任何可用源, 跳过 | %s",
                                       i, len(rows), kid, (title or "")[:35])
                        continue
                    # 幂等核心: 与存量逐字比对, 只写真正不同的
                    if target == (cur_st or ""):
                        stats["unchanged"] += 1
                        continue
                    if not args.apply:
                        logger.info("  [dry-run] id=%-5s src=%-24s %5d -> %5d chars | %s\n"
                                    "             new: %s",
                                    kid, src, len(cur_st or ""), len(target), (title or "")[:35],
                                    target[:args.preview_chars])
                        continue
                    await db.execute(
                        text("UPDATE knowledge SET search_text=:s, updated_at=now() WHERE id=:i"),
                        {"s": target, "i": kid},
                    )
                    await db.commit()
                backup_lines.append({
                    "id": kid, "title": title, "source": src,
                    "old_len": len(cur_st or ""), "old": cur_st,
                    "new_len": len(target), "new_preview": target[:400],
                })
                stats["updated"] += 1
                logger.info("[%d/%d] id=%-5s src=%-24s %5d -> %5d chars | %s",
                            i, len(rows), kid, src, len(cur_st or ""), len(target),
                            (title or "")[:35])
            except Exception as e:
                stats["failed"] += 1
                logger.warning("[%d/%d] id=%s 回填失败: %s", i, len(rows), kid, e)

        # 备份在**全部写库成功后**落盘 (data/ 是 bind mount, 宿主机可见)
        if args.apply and backup_lines:
            bdir = Path("/app/data/backups")
            bdir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            bpath = bdir / f"drive_search_text_backup-{stamp}.jsonl"
            with bpath.open("w", encoding="utf-8") as f:
                for line in backup_lines:
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")
            logger.info("备份已写入: %s (%d 行)", bpath, len(backup_lines))
            stats["backup_path"] = str(bpath)
    finally:
        await engine.dispose()

    print(json.dumps(stats, ensure_ascii=False))
    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))