"""agent 23 号 (2026-10-09): 清除模板装饰横幅在 ``knowledge_images.ocr_text``
里的幻觉噪声（只清这一个字段）。

## 背景（承接 agent22 的 commit ``ed0358faf``）

用第三方模板做的 PPT/报告，母版（slide master）里嵌了一张装饰横幅
（校徽 + 校名 + 校门照），在**每一页**重复出现。``ed0358faf`` 已经在两侧堵住
"再生"：写入侧 ``multimodal_extraction_service`` 在 OCR **之前**按几何判据拦下
装饰图（标 ``ocr_status='skipped'``，不发 LLM 调用）；检索侧
``MultimodalRetriever._not_banner_predicate`` 让存量装饰图不进第 5 路候选。

但**存量 2051 张 / 261 文档**的 ``ocr_text`` 仍留着幻觉文本（本库最大受害者
doc 2822 的 1055×203 横幅，视觉模型在 4 条记录上给出 3 个互不相同的说法：
"台湾大学校门" / "台湾清华大学成功湖畔的纪念亭" / "疑似清华大学校门…"）。
这些文本同时污染：① 前端图片详情展示；② ``rag_evaluator`` 的 image_ref 抽答；
③ 任何按 ``ocr_text`` 过滤/统计的下游。判据本身零实质损失已验证：
chart / table / formula 三类 extraction 与装饰图的关联数均为 0。

## 判据：**复用** ``app/services/image_decoration_filter.py``，不复制第二份实现

本脚本 import `find_banner_image_ids`（两个信号取交集：极端宽高比 + 同文档内
同尺寸出现在 >= 2 个不同页 + ``height <= 300`` 保险丝；阈值 2026-10-09 由
agent33 从 3 降到 2，判据阈值一律以 image_decoration_filter 的常量为准）。
**绝不**在这里重写
判据常量或再写一份几何判断 —— 两份判据会各自漂移，届时清理集与检索侧排除集
不再一致，"已清干净"这句话就是假的（同 agent22 的设计意图）。

## 范围限制（重要，主指挥 2026-10-09 拍板）

**只把 ``ocr_text`` 置空，不动其他任何东西**：

- ❌ 不 DELETE ``knowledge_images`` 行（图片本体还要在详情页显示）
- ❌ 不动 ``visual_summary``（纯展示字段，留待观察）
- ❌ 不动 ``embedding``（第 5 路候选已被 predicate 排除，无需清）
- ❌ 不动 ``image_block`` extraction（主指挥明确保留；实测装饰图上仍挂着
  1350 条 image_block，内容可能含同一批横幅文字，**属本次范围外残留**）
- ❌ 不动 ``figure_type`` / ``page_number`` / ``ocr_status`` / 任何其他字段

## 用法

    # 默认 dry-run：只打印统计 + 前 10 个样本，不写库
    docker cp scripts/purge_banner_image_noise.py microbubble-agent-app-1:/app/scripts/
    docker exec microbubble-agent-app-1 python scripts/purge_banner_image_noise.py

    # 试水 20 行
    docker exec microbubble-agent-app-1 python scripts/purge_banner_image_noise.py --apply --limit 20

    # 全量（先备份，再写）
    docker exec microbubble-agent-app-1 python scripts/purge_banner_image_noise.py --apply

## 备份 / 回滚

``--apply`` 时**先**把将要改的行（id + 原文 ``ocr_text`` + 定位字段）导出到
``data/backups/banner_ocr_text_backup-<时间戳>.jsonl``（data 是 bind mount，
文件直接落在宿主机 ``E:\\microbubble-agent\\data\\backups\\``）。写库前会
fsync 并回读行数校验；行数与待改行数不符则中止，**不写库**。

回滚（把备份文件 docker cp 进容器再执行）：

    docker cp data/backups/banner_ocr_text_backup-<ts>.jsonl \\
        microbubble-agent-app-1:/app/data/backups/
    docker exec microbubble-agent-app-1 python - \\
        /app/data/backups/banner_ocr_text_backup-<ts>.jsonl <<'PY'
    import asyncio, json, sys, pathlib
    from app.config import settings
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def main():
        url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        eng = create_async_engine(url)
        rows = [json.loads(l) for l in pathlib.Path(sys.argv[1]).read_text("utf-8").splitlines() if l.strip()]
        async with eng.begin() as c:
            for r in rows:
                await c.execute(text("UPDATE knowledge_images SET ocr_text=:t WHERE id=:i"),
                                {"t": r["ocr_text"], "i": r["id"]})
        await eng.dispose()
        print("restored", len(rows))

    asyncio.run(main())
    PY

## 幂等性

只处理 ``ocr_text`` **当前非空**的装饰图行；第二跑命中集为空 → 0 行 → 无操作。
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

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("purge_banner_image_noise")

# 备份文件名时间戳用北京时间（容器 TZ 通常是 UTC，裸文件名会误导排查）
CST = timezone(timedelta(hours=8))
BACKUP_DIR = "data/backups"

# 样本打印条数（人工过目用）
SAMPLE_N = 10
# 写库分批大小
CHUNK = 500
# 样本片段长度
SNIPPET = 60


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="清除模板装饰横幅 knowledge_images.ocr_text 的幻觉噪声（只清 ocr_text）"
    )
    p.add_argument("--apply", action="store_true", help="真写库（默认 dry-run）")
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 行（0=全部）")
    p.add_argument("--backup-dir", default=BACKUP_DIR, help=f"备份目录（默认 {BACKUP_DIR}）")
    return p.parse_args()


def _snippet(s: str) -> str:
    """ocr_text 片段：压空白 + 截断，便于人工一眼看出是横幅噪声。"""
    flat = " ".join((s or "").split())
    return flat[:SNIPPET] + ("…" if len(flat) > SNIPPET else "")


async def main() -> int:
    args = parse_args()

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.models.knowledge_multimodal import KnowledgeImage
    from app.services.image_decoration_filter import find_banner_image_ids

    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, pool_size=2)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats: Dict[str, object] = {"dry_run": not args.apply}

    try:
        # ── 1. 载入全部图片的几何字段（只 select 需要的列，避开 selectin 关系加载）──
        geom_sql = text(
            "SELECT id, knowledge_id, page_number, width, height "
            "FROM knowledge_images ORDER BY id"
        )
        async with Session() as db:
            total_images = (await db.execute(text("SELECT count(*) FROM knowledge_images"))).scalar()
            geom_rows = (await db.execute(geom_sql)).all()

        # 判据函数只要求 .id/.width/.height/.page_number —— 用 namedtuple 当同形替身
        Geom = type("Geom", (), {})
        by_doc = defaultdict(list)
        doc_of: Dict[int, int] = {}
        for rid, kid, page, w, h in geom_rows:
            g = Geom()
            g.id, g.knowledge_id, g.page_number, g.width, g.height = rid, kid, page, w, h
            by_doc[kid].append(g)
            doc_of[rid] = kid

        # ── 2. 复用 image_decoration_filter 的判据（逐文档分组调用）──
        banner_ids: set = set()
        for _kid, group in by_doc.items():
            banner_ids |= find_banner_image_ids(group)
        banner_docs = {doc_of[i] for i in banner_ids}
        logger.info("knowledge_images 总行数: %s", total_images)
        logger.info("装饰横幅判定命中: %d 张 / %d 文档（全库口径）",
                    len(banner_ids), len(banner_docs))
        stats["total_images"] = total_images
        stats["banner_total"] = len(banner_ids)
        stats["banner_docs_total"] = len(banner_docs)

        # ── 3. 取命中集的明细，筛出 ocr_text 非空的待清行 ──
        ids = sorted(banner_ids)
        detail_sql = text(
            "SELECT id, knowledge_id, page_number, width, height, ocr_status, "
            "       figure_type, length(ocr_text) AS ocr_len, ocr_text "
            "FROM knowledge_images WHERE id = ANY(:ids) ORDER BY id"
        )
        async with Session() as db:
            rows = (await db.execute(detail_sql, {"ids": ids})).mappings().all()

        targets = [r for r in rows if (r["ocr_text"] or "").strip() != ""]
        docs = {r["knowledge_id"] for r in targets}
        stats["banner_docs"] = len(docs)
        stats["targets"] = len(targets)
        selected = targets[: args.limit] if args.limit else targets
        stats["selected"] = len(selected)
        stats["limit"] = args.limit

        # ── 4. 打印统计 + 样本（人工过目）──
        logger.info("其中 ocr_text 非空待清: %d 行 / %d 文档%s",
                    len(targets), len(docs),
                    f"；本次 --limit 取前 {len(selected)} 行" if args.limit else "")
        logger.info("--- 待清样本（前 %d 条）---", min(SAMPLE_N, len(selected)))
        for r in selected[:SAMPLE_N]:
            logger.info("  id=%s kb=%s page=%s %sx%s status=%s ocr_text=%r",
                        r["id"], r["knowledge_id"], r["page_number"],
                        r["width"], r["height"], r["ocr_status"], _snippet(r["ocr_text"]))
        if len(selected) > SAMPLE_N:
            logger.info("  ... 其余 %d 条省略", len(selected) - SAMPLE_N)

        if not args.apply:
            logger.info("[dry-run] 未写库。加 --apply 执行。")
            print(json.dumps(stats, ensure_ascii=False))
            return 0

        # ── 5. 备份（回滚依据，必须先落盘）──
        backup_dir = Path(args.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(CST).strftime("%Y%m%d-%H%M%S")
        backup_path = backup_dir / f"banner_ocr_text_backup-{stamp}.jsonl"

        payload = [
            {
                "id": r["id"],
                "knowledge_id": r["knowledge_id"],
                "page_number": r["page_number"],
                "width": r["width"],
                "height": r["height"],
                "ocr_status": r["ocr_status"],
                "ocr_text": r["ocr_text"],
            }
            for r in selected
        ]
        with open(backup_path, "w", encoding="utf-8") as f:
            for item in payload:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # 回读校验：行数与内容长度都对不上就不许写库
        with open(backup_path, "r", encoding="utf-8") as f:
            backed = [json.loads(line) for line in f if line.strip()]
        if len(backed) != len(selected) or any(
            backed[i]["id"] != payload[i]["id"] or backed[i]["ocr_text"] != payload[i]["ocr_text"]
            for i in range(len(backed))
        ):
            logger.error("备份校验失败（行数或内容不匹配），中止写库。文件: %s", backup_path)
            return 1
        logger.info("备份已落盘: %s (%d 行, %d 字节) —— 回滚依据",
                    backup_path, len(backed), backup_path.stat().st_size)
        stats["backup"] = str(backup_path)

        # ── 6. 只更新 ocr_text 一列（"图里本就没文字" 的合法空值语义，与写入侧一致）──
        cleared = 0
        async with Session() as db:
            for start in range(0, len(selected), CHUNK):
                chunk = selected[start : start + CHUNK]
                await db.execute(
                    text("UPDATE knowledge_images SET ocr_text='' WHERE id = ANY(:ids)"),
                    {"ids": [r["id"] for r in chunk]},
                )
                await db.commit()
                cleared += len(chunk)
                logger.info("[%d/%d] 已清 ocr_text", cleared, len(selected))
        stats["cleared"] = cleared

        # ── 7. 写后校验：总行数不变 + 待清行已空 ──
        async with Session() as db:
            after_total = (await db.execute(text("SELECT count(*) FROM knowledge_images"))).scalar()
            after_left = (
                await db.execute(
                    text(
                        "SELECT count(*) FROM knowledge_images "
                        "WHERE id = ANY(:ids) AND coalesce(ocr_text,'') <> ''"
                    ),
                    {"ids": [r["id"] for r in selected]},
                )
            ).scalar()
        stats["total_images_after"] = after_total
        stats["still_non_empty"] = after_left
        logger.info("写后校验: 总行数 %s -> %s（应相等）; 待清行残留非空 ocr_text: %d（应为 0）",
                    total_images, after_total, after_left)

        if after_total != total_images or after_left != 0:
            logger.error("写后校验不通过，请用备份回滚。")
            return 1
    finally:
        await engine.dispose()

    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))