"""agent28 (2026-10-09): 删除挂在模板装饰横幅上的 ``image_block`` extraction。

承接 agent22 的 ``ed0358faf`` 与 agent 的 ``scripts/purge_banner_image_noise.py``

## 背景：这是同一批噪声的**最后一块藏身处**

用第三方模板做的 PPT/报告，母版（slide master）里嵌了一张装饰横幅
（校徽 + 校名 + 校门照），在**每一页**重复出现。三层修复已经做完两层：

1. **写入侧**（agent22 ``ed0358faf``）—— ``multimodal_extraction_service``
   在 OCR **之前**按几何判据拦下装饰图（标 ``ocr_status='skipped'``）
2. **检索侧**（agent22）—— ``MultimodalRetriever._not_banner_predicate``
   让存量装饰图不进第 5 路候选
3. **存量清理第一刀**（``purge_banner_image_noise.py``）—— 把 2051 张装饰图的
   ``knowledge_images.ocr_text`` 全部置空。**实测已 2051/2051 全空**

但 ``knowledge_extractions`` 里还挂着 **1350 条** ``kind='image_block'`` 行
（261 文档），它们的 ``source_image_id`` 指向装饰图，``content_text`` 装的是
**同一批横幅文字**。由于 ``ocr_text`` 已被清空，这些 extraction 行现在是那段
噪声的**唯一载体** —— 前端图片详情 / OCR 块面板看到的就是它。

实测内容（前 15 高频值覆盖 660/1350 = 49%）全部是模板资产，不是正文：

    [x143] 天津大学 Tianjin University
    [x106] 天津大学 Tianjin University
    [x67 ] 人民英雄永垂不朽          ← 纪念碑题字，同一张母版横幅的另一半
    [x52 ] 天津大学环境科学与工程学院 SCHOOL OF ENVIRONMENTAL SCIENCE&ENGINEERING,TIANJIN UNIVERSITY
    [x46] 天津大学 Tianjin University 1895
    ...

## 判据：**复用** ``app/services/image_decoration_filter.py``

本脚本 import ``find_banner_image_ids``，与 ``purge_banner_image_noise.py``
走**同一个**判据函数（两个信号取交集：极端宽高比 + 同文档内同尺寸出现在
>= 3 个不同页 + ``height <= 300`` 保险丝）。**绝不**在这里重写判据常量 ——
两份判据会各自漂移，届时清理集与检索侧排除集不再一致，"已清干净"就是假的。

> ⚠️ 顺便记一个坑：**用 SQL 复刻判据会得到 1439 而不是 1350**。
> 只按几何（AR>=5 且 height<=300）筛会多命中 89 条，因为漏了「同文档多页复用」
> 这一半条件 —— 那 89 条是**真实内容图**里恰好很扁的。必须调函数。

## 为什么可以删：消费方全查过

`image_block` **不进任何 RAG / 检索 / 索引链路**，只用于展示与导出：

| 消费方 | 是否读 image_block |
|---|---|
| `MultimodalRetriever`（第 5 路召回） | ❌ 只查 ``KnowledgeImage``（ocr_text + embedding），根本不 JOIN extractions |
| ``_inject_multimodal_into_formatted_content`` | ❌ 显式筛 formula/table/chart 三类，``if not (formulas or tables or charts): return`` |
| ``_format_inline_markdown``（inline 回写） | ❌ 只处理 formula/table/chart |
| ``resync_content_indexes``（BM25/tsvector/embedding 源） | ❌ 只用 ``knowledge.content`` |
| ``backfill_resync_kb_indexes.py`` | ⚠️ 存在性判定，但取的是 ``img_ids \| ext_ids`` 并集 —— 装饰图本身就是 knowledge_images 行，删 extraction 不影响该文档是否入选 |
| `GET /knowledge/{id}/extractions` → 前端 | ✅ 展示（``ExtractionPanel.vue`` "OCR 块" / ``figures.js`` caption 匹配 / ``normalize.js``） |
| 导出 / 全文检索索引 | ❌ 该表**无触发器、无 tsvector**（实测 ``pg_trigger`` 0 行、只有 pkey + 5 个普通索引） |

另外两个安全性检查：

- **chart / table / formula 与装饰图的关联数实测为 0**（本脚本 ``--apply`` 前会
  再 assert 一次，不为 0 直接中止），所以不存在误伤。
- **``figures.js`` 的 ``matchFiguresWithCaptions`` 只在 ``data.caption`` 非空时**
  用 image_block 补图注，且按 ``source_image_id`` 归到该图自己 —— 装饰图的
  caption 只可能标到装饰图上，删掉不影响任何真实图。实测 1350 条里 caption
  非空的仅个位数。

## 范围限制

- ❌ **不 DELETE** ``knowledge_images`` 行 —— 图片本体还要在详情页显示
- ❌ **不动** chart / table / formula 任何一行
- ❌ **不动** ``knowledge_images`` 的其他字段（含 ``visual_summary`` /
  ``embedding`` / ``figure_type``）
- ❌ 不碰任何其他表

## 用法

    # 默认 dry-run：只打印统计 + 样本，不写库
    docker cp scripts/purge_banner_image_block_extractions.py microbubble-agent-app-1:/app/scripts/
    docker exec microbubble-agent-app-1 python scripts/purge_banner_image_block_extractions.py

    # 试水
    docker exec microbubble-agent-app-1 python scripts/purge_banner_image_block_extractions.py --apply --limit 20

    # 全量（先备份，再写）
    docker exec microbubble-agent-app-1 python scripts/purge_banner_image_block_extractions.py --apply

## 备份 / 回滚

``--apply`` 时**先**把将要删的行（id + kind + knowledge_id + source_image_id +
page_number + content_text + data + confidence + model_used）导出到
``data/backups/banner_image_block_extractions_backup-<时间戳>.jsonl``（data 是
bind mount，文件直接落在宿主机 ``E:\\microbubble-agent\\data\\backups\\``）。
落盘后 **fsync + 回读校验**，行数或内容对不上则中止，**不写库**。

回滚（把备份文件 docker cp 进容器后执行）：

    docker cp data/backups/banner_image_block_extractions_backup-<ts>.jsonl \\
        microbubble-agent-app-1:/app/data/backups/
    docker exec microbubble-agent-app-1 python /app/data/backups/restore_banner_extractions.py

## 幂等性

只删除 ``source_image_id`` 命中装饰图集且 ``kind='image_block'`` 的行；
删完之后这些行不复存在 → 第二跑命中集为空 → 0 行 → 无操作。
故本脚本可反复运行，天然幂等。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("purge_banner_image_block_extractions")

# 备份文件名时间戳用北京时间（容器 TZ 通常是 UTC，裸文件名会误导排查）
CST = timezone(timedelta(hours=8))
BACKUP_DIR = "data/backups"

SAMPLE_N = 10
# 写库分批大小（DELETE 分批，避免一条长事务锁表）
CHUNK = 500
SNIPPET = 90
# 允许删除的 kind —— 唯一的删除闸门
TARGET_KIND = "image_block"
# 这些 kind 若在装饰图上有任何关联就中止（防误伤闸门）
FORBIDDEN_KINDS = ("chart", "table", "formula")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="删除挂在模板装饰横幅上的 image_block extraction（默认 dry-run）"
    )
    p.add_argument("--apply", action="store_true", help="真删（默认 dry-run）")
    p.add_argument("--limit", type=int, default=0, help="最多删 N 行（0=全部）")
    p.add_argument("--backup-dir", default=BACKUP_DIR, help=f"备份目录（默认 {BACKUP_DIR}）")
    return p.parse_args()


def _snippet(s: str) -> str:
    flat = " ".join((s or "").split())
    return flat[:SNIPPET] + ("…" if len(flat) > SNIPPET else "")


async def _count_selected(Session, kind: str, ext_ids: List[int], banner_ids: List[int]) -> int:
    """本次选中的那批 extraction id 还剩几行（写后校验用，应为 0）。"""
    async with Session() as db:
        return (
            await db.execute(
                text(
                    "SELECT count(*) FROM knowledge_extractions "
                    "WHERE kind = :kind AND id = ANY(:ids) AND source_image_id = ANY(:bids)"
                ),
                {"kind": kind, "ids": ext_ids, "bids": banner_ids},
            )
        ).scalar()


async def _banner_ids(Session) -> set:
    """复用 image_decoration_filter.find_banner_image_ids 算全库装饰图 id 集。"""
    from app.services.image_decoration_filter import find_banner_image_ids

    async with Session() as db:
        geom_rows = (
            await db.execute(
                text("SELECT id, knowledge_id, page_number, width, height FROM knowledge_images ORDER BY id")
            )
        ).all()

    Geom = type("Geom", (), {})
    by_doc = defaultdict(list)
    doc_of: Dict[int, int] = {}
    for rid, kid, page, w, h in geom_rows:
        g = Geom()
        g.id, g.knowledge_id, g.page_number, g.width, g.height = rid, kid, page, w, h
        by_doc[kid].append(g)
        doc_of[rid] = kid

    banner: set = set()
    for _kid, group in by_doc.items():
        banner |= find_banner_image_ids(group)
    return set(banner), doc_of


async def main() -> int:
    args = parse_args()

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats: Dict[str, object] = {"dry_run": not args.apply, "target_kind": TARGET_KIND}

    try:
        banner, doc_of = await _banner_ids(Session)
        logger.info("装饰横幅判定命中: %d 张 / %d 文档（判据来自 app/services/image_decoration_filter.py）",
                    len(banner), len({doc_of[i] for i in banner}))
        stats["banner_images"] = len(banner)
        stats["banner_docs"] = len({doc_of[i] for i in banner})
        ids = sorted(banner)

        # ── 1. 防误伤闸门：chart/table/formula 在装饰图上必须为 0 ──────────
        async with Session() as db:
            forbidden = (
                await db.execute(
                    text(
                        "SELECT kind, count(*) FROM knowledge_extractions "
                        "WHERE kind = ANY(:kinds) AND source_image_id = ANY(:ids) GROUP BY 1"
                    ),
                    {"kinds": list(FORBIDDEN_KINDS), "ids": ids},
                )
            ).all()
        if forbidden:
            logger.error("防误伤闸门不通过：装饰图上仍有非 image_block 提取物 %r —— 中止，不删任何行。", forbidden)
            return 1
        logger.info("防误伤闸门通过: chart/table/formula 在装饰图上的关联数均为 0")
        stats["forbidden_hits"] = 0

        # ── 2. 总量基线 + 待删明细 ────────────────────────────────────────
        async with Session() as db:
            before_by_kind = {
                r[0]: r[1]
                for r in (await db.execute(
                    text("SELECT kind, count(*) FROM knowledge_extractions GROUP BY 1")
                )).all()
            }
            rows = (
                await db.execute(
                    text(
                        "SELECT id, knowledge_id, source_image_id, page_number, content_text, "
                        "       data, confidence, model_used, source, is_active "
                        "FROM knowledge_extractions "
                        "WHERE kind = :kind AND source_image_id = ANY(:ids) ORDER BY id"
                    ),
                    {"kind": TARGET_KIND, "ids": ids},
                )
            ).mappings().all()

        logger.info("knowledge_extractions 总量按 kind（跑前）: %s", before_by_kind)
        logger.info("其中挂在装饰图上的 %s: %d 行 / %d 文档",
                    TARGET_KIND, len(rows), len({r["knowledge_id"] for r in rows}))
        stats["before_by_kind"] = before_by_kind
        stats["banner_extractions"] = len(rows)
        stats["banner_extraction_docs"] = len({r["knowledge_id"] for r in rows})

        selected = rows[: args.limit] if args.limit else rows
        stats["selected"] = len(selected)
        stats["limit"] = args.limit

        # ── 3. 样本（人工过目：一眼确认是横幅噪声而不是正文）──────────────
        logger.info("--- 待删样本（前 %d 条）---", min(SAMPLE_N, len(selected)))
        for r in selected[:SAMPLE_N]:
            logger.info("  ext_id=%s kb=%s img=%s page=%s text=%r",
                        r["id"], r["knowledge_id"], r["source_image_id"],
                        r["page_number"], _snippet(r["content_text"]))
        if len(selected) > SAMPLE_N:
            logger.info("  ... 其余 %d 条省略", len(selected) - SAMPLE_N)

        # 高频值分布：横幅噪声的指纹
        freq = defaultdict(int)
        for r in selected:
            freq[" ".join((r["content_text"] or "").split())] += 1
        logger.info("--- content_text 高频值 top 10（横幅噪声指纹）---")
        for txt, n in sorted(freq.items(), key=lambda kv: -kv[1])[:10]:
            logger.info("  [x%-4d] %s", n, txt[:100])

        if not args.apply:
            logger.info("[dry-run] 未写库。加 --apply 执行。")
            print(json.dumps(stats, ensure_ascii=False))
            return 0

        # ── 4. 备份（回滚依据，必须先落盘）───────────────────────────────
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(CST).strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"banner_image_block_extractions_backup-{stamp}.jsonl"

        payload = [dict(r) for r in selected]
        with open(backup_path, "w", encoding="utf-8") as f:
            for item in payload:
                f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # 回读校验：行数或内容对不上就不许删
        with open(backup_path, "r", encoding="utf-8") as f:
            backed = [json.loads(line) for line in f if line.strip()]
        if len(backed) != len(payload) or any(
            backed[i]["id"] != payload[i]["id"]
            or backed[i]["content_text"] != payload[i]["content_text"]
            for i in range(len(backed))
        ):
            logger.error("备份校验失败（行数或内容不匹配），中止删除。文件: %s", backup_path)
            return 1
        logger.info("备份已落盘: %s (%d 行, %d 字节) —— 回滚依据",
                    backup_path, len(backed), backup_path.stat().st_size)
        stats["backup"] = str(backup_path)

        # ── 5. 分批删除（kind 与 source_image_id 双重锁死在 WHERE 里）─────
        deleted = 0
        async with Session() as db:
            for start in range(0, len(selected), CHUNK):
                chunk_ids = [r["id"] for r in selected[start : start + CHUNK]]
                await db.execute(
                    text(
                        "DELETE FROM knowledge_extractions "
                        "WHERE kind = :kind AND id = ANY(:ids) AND source_image_id = ANY(:bids)"
                    ),
                    {"kind": TARGET_KIND, "ids": chunk_ids, "bids": ids},
                )
                await db.commit()
                deleted += len(chunk_ids)
                logger.info("[%d/%d] 已删", deleted, len(selected))
        stats["deleted"] = deleted

        # ── 6. 写后校验 ─────────────────────────────────────────────────
        async with Session() as db:
            after_by_kind = {
                r[0]: r[1]
                for r in (await db.execute(
                    text("SELECT kind, count(*) FROM knowledge_extractions GROUP BY 1")
                )).all()
            }
            left = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM knowledge_extractions "
                        "WHERE kind = :kind AND source_image_id = ANY(:ids)"
                    ),
                    {"kind": TARGET_KIND, "ids": ids},
                )
            ).scalar()
            forbidden_after = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM knowledge_extractions "
                        "WHERE kind = ANY(:kinds) AND source_image_id = ANY(:ids)"
                    ),
                    {"kinds": list(FORBIDDEN_KINDS), "ids": ids},
                )
            ).scalar()
            img_total = (
                await db.execute(text("SELECT count(*) FROM knowledge_images"))
            ).scalar()

        stats["after_by_kind"] = after_by_kind
        stats["banner_left"] = left
        stats["forbidden_after"] = forbidden_after
        stats["images_total_after"] = img_total

        # --limit 试水时只删了 selected 条，残留应为 (跑前总数 - 已删)；
        # 全量跑（--limit 0）时它恰好等于 0。
        expected_left = len(rows) - deleted
        selected_left = (
            await _count_selected(Session, TARGET_KIND, [r["id"] for r in selected], ids)
            if selected
            else 0
        )

        logger.info("写后校验:")
        logger.info("  本次选中 %d 行，已删 %d 行；选中集残留: %d（应为 0）",
                    len(selected), deleted, selected_left)
        logger.info("  装饰图上剩余 %s: %d（%s）", TARGET_KIND, left,
                    f"应为 {expected_left}" + ("，即已清干净" if expected_left == 0 else "，--limit 试水正常"))
        logger.info("  装饰图上 chart/table/formula: %d（应恒为 0）", forbidden_after)
        logger.info("  knowledge_extractions 按 kind（跑后）: %s", after_by_kind)
        logger.info("  knowledge_images 仍为: %d（本脚本不删图片，应与跑前一致）", img_total)

        ok = (
            selected_left == 0
            and left == expected_left
            and forbidden_after == 0
            and all(after_by_kind.get(k, 0) == before_by_kind.get(k, 0) for k in FORBIDDEN_KINDS)
        )
        if not ok:
            logger.error("写后校验不通过，请用备份回滚。")
            return 1
    finally:
        await engine.dispose()

    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
