#!/usr/bin/env python3
"""批量重跑失败 / 脏的图片 OCR —— agent28 首次入库（2026-10-09）。

## 为什么存在

多模态提取（``multimodal_extraction_service``）跑过一轮后，``knowledge_images``
里会沉淀两类需要重跑的坏数据：

- **A 组：真失败** —— ``ocr_status='failed'``（OCR 调用本身报错）
- **B 组：假成功脏数据** —— ``ocr_status='done'`` 但 ``ocr_text`` 为空
  （模型返回空 / 解析丢结果，但状态已被写成 done，永远不会被自动重试覆盖）

本脚本一次处理两组，并把「哪些文档要重跑」收敛成**一次文档维度的 SELECT**
（而不是逐图重试），逐文档调
``multimodal_extraction_service.extract_for_knowledge(knowledge_id, reset_status=True)``。

2026-10-09 实际用过 3 次：全量重跑 4573 张、一次回滚验证、一次假成功清理。
属于**可复用的运维手段**，故入库（此前一直是 untracked，而
``multimodal_extraction_service.extract_for_knowledge`` 的 docstring 第 336 行
已经把本脚本列为已知调用方，代码引用了一个不存在的文件）。

## ⚠️ 爆炸半径 —— 比「重跑 OCR」大得多，读完再跑

``extract_for_knowledge(reset_status=True)`` 内部先调
``_reset_multimodal_data(knowledge_id)``，它对**整个文档**做四件事
（``app/services/multimodal_extraction_service.py:250-291``）：

1. **DELETE 全部** ``knowledge_images`` 行（该文档的图，不是只删失败的那些）
2. **DELETE 全部** ``knowledge_extractions`` 行 —— **含 formula / table / chart**，
   不只是 image_block
3. 从 ``knowledge.content`` 和 ``knowledge.formatted_content`` 里**剥掉**
   ``<!-- MULTIMODAL_INLINED v2 -->`` 之后的 inline 内容 —— 即**主文本被改写**，
   而主文本是 RAG / BM25 / tsvector 的索引源
4. ``knowledge.analysis_status`` 翻成 ``'analyzing'``（仅当该文档有 ``file_path``）

所以这是「**该文档多模态重新提取**」而不是「OCR 重试」。**只想修 OCR 别用本脚本**，
直接 UPDATE 单张图的 ``ocr_status='failed'`` 再走单图链路更安全。

已经处理掉的一个坑（agent25，2026-10-09）：第 4 步的中间态必须由**同一次重跑**
收尾，否则永久卡 analyzing。``extract_for_knowledge`` 现在会快照并在 ``finally``
里恢复重跑前的状态，pipeline 调用（``reset_status=False``）不受影响。

## 安全边界

- **默认 dry-run**，只 SELECT 出受影响文档 + 分布统计，**不写库**。必须显式
  ``--apply`` 才动手。（原版没有这个保护，且 ``--limit`` 默认 0 = 不限、
  ``--group`` 默认 ``both``，一条裸命令就是全库重跑 —— 本次入库时收紧了。）
- **默认不限条数这件事仍要当心**：``--apply`` 且不带 ``--limit`` / ``--ids``
  时会对**全部**受影响文档动手，脚本会打一条 WARNING 提示。
- 不碰 ``knowledge.content`` 以外的任何东西；不碰 meetings / drive / 会议转写。
- 每个文档独立 try/except，单文档失败不影响其余；失败原因进日志与 journal。

## 用法（容器内，cwd = /app）

    # 1) 先 dry-run：看会动哪些文档
    docker cp scripts/rerun_failed_ocr.py microbubble-agent-app-1:/app/scripts/
    docker exec microbubble-agent-app-1 python scripts/rerun_failed_ocr.py

    # 2) 试水 5 个文档（真写）
    docker exec microbubble-agent-app-1 python scripts/rerun_failed_ocr.py --apply --limit 5

    # 3) 只跑 A 组（真失败）
    docker exec microbubble-agent-app-1 python scripts/rerun_failed_ocr.py --apply --group failed

    # 4) 指定文档 + 落 journal（每行一条 JSON，便于事后核对）
    docker exec microbubble-agent-app-1 python scripts/rerun_failed_ocr.py \
        --apply --ids 2822 1234 --journal data/backups/ocr_rerun.jsonl

    # 5) 全量（真写，WARNING 会提示）
    docker exec microbubble-agent-app-1 python scripts/rerun_failed_ocr.py --apply

## 幂等性

**不是幂等的**，且不该假设幂等：

- A 组（``ocr_status='failed'``）失败后仍是 failed → 下一跑还会选中，是天然的
  「重试直到成功」语义；
- B 组（``done`` 且文本空）重跑成功后会写入真实 ``ocr_text`` → 不再命中，是
  收敛的；
- 但每次 ``--apply`` 都会**删掉该文档全部 extraction**再重建，若重跑过程中
  进程被 kill，文档会停在「图和 extraction 都空」的中间态，直到下次重跑补上。
  故大范围重跑请用 ``--journal`` 记录进度，便于断点续跑。
- dry-run（不加 ``--apply``）**完全只读**，可反复执行。

## 输出

最后一行是 ``SUMMARY_JSON {...}``（机器可读），含 before/after 的
``(ocr_status, 是否空文本, 行数)`` 分布，用来一眼确认重跑有没有把 failed 压下去、
有没有把空文本压下去。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rerun_failed_ocr")

# 关掉底层噪声 (aiohttp/urllib3) + sqlalchemy echo 刷屏
for noisy in ("httpx", "httpcore", "aiohttp", "urllib3", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

SAMPLE_N = 20


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="批量重跑失败/脏图片的 OCR（默认 dry-run；--apply 才写库）"
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="真写库（会删该文档全部 images/extractions 并重建！默认只读）",
    )
    p.add_argument("--limit", type=int, default=0, help="最多处理 N 个文档（0=不限）")
    p.add_argument("--ids", type=int, nargs="*", default=None, help="直接指定 knowledge_id，忽略 --group/--limit")
    p.add_argument("--group", choices=["failed", "done_empty", "both"], default="both",
                   help="failed=调用失败；done_empty=done 但文本空（假成功）；both=全部（默认）")
    p.add_argument("--journal", type=str, default="", help="逐行 JSON 落盘路径（追加写）")
    return p.parse_args()


async def _fetch_doc_ids(group: str):
    """一次 SELECT 拿全库受影响文档（按坏图数量降序，--limit 试水时优先打最脏的）。"""
    from app.core.database import async_session

    clauses = []
    if group in ("failed", "both"):
        clauses.append("(ocr_status = 'failed')")
    if group in ("done_empty", "both"):
        clauses.append("(ocr_status = 'done' AND (ocr_text IS NULL OR btrim(ocr_text) = ''))")
    where = " OR ".join(clauses)

    async with async_session() as db:
        res = await db.execute(
            text(
                f"SELECT DISTINCT knowledge_id, count(*) AS n "
                f"FROM knowledge_images WHERE {where} "
                f"GROUP BY knowledge_id ORDER BY n DESC"
            )
        )
        rows = res.all()
    return [(r[0], r[1]) for r in rows]


async def _pre_stats():
    from app.core.database import async_session

    async with async_session() as db:
        res = await db.execute(
            text(
                "SELECT ocr_status, "
                "(ocr_text IS NULL OR btrim(ocr_text)='') AS empty, count(*) "
                "FROM knowledge_images GROUP BY 1,2"
            )
        )
        return res.all()


async def main() -> int:
    args = parse_args()

    if args.ids:
        docs = [(int(i), -1) for i in args.ids]
    else:
        docs = await _fetch_doc_ids(args.group)
        if args.limit and args.limit > 0:
            docs = docs[: args.limit]

    logger.info("待处理文档数 = %d (group=%s)", len(docs), args.group)
    before = await _pre_stats()
    logger.info("跑前分布: %s", before)

    summary = {
        "apply": bool(args.apply),
        "group": args.group,
        "docs": len(docs),
        "before": [list(map(str, x)) for x in before],
    }

    # ── dry-run：只报不动 ────────────────────────────────────────────────
    if not args.apply:
        logger.info("受影响文档（坏图数降序，前 %d 条）:", min(SAMPLE_N, len(docs)))
        for kid, n in docs[:SAMPLE_N]:
            logger.info("  knowledge_id=%s 坏图数=%s", kid, n)
        if len(docs) > SAMPLE_N:
            logger.info("  ... 其余 %d 个文档省略", len(docs) - SAMPLE_N)
        logger.info(
            "[dry-run] 未写库。确认无误后加 --apply（注意：会删除这些文档的"
            "全部 knowledge_images 与 knowledge_extractions 并重建，含 formula/table/chart）。"
        )
        print("SUMMARY_JSON " + json.dumps(summary, ensure_ascii=False))
        return 0

    if not args.limit and not args.ids:
        logger.warning(
            "--apply 且未指定 --limit/--ids，将对**全部** %d 个受影响文档动手"
            "（每个文档的 images/extractions 全部删除重建）。", len(docs),
        )

    from app.services.multimodal_extraction_service import multimodal_extraction_service

    t0 = time.time()
    total_ok = total_err = total_imgs = 0
    report = []
    for idx, (kid, _n) in enumerate(docs, 1):
        dt0 = time.time()
        try:
            r = await multimodal_extraction_service.extract_for_knowledge(kid, reset_status=True)
        except Exception as e:  # 单文档失败不拖垮整批
            logger.exception("doc %s 顶层异常", kid)
            r = {"ok": False, "reason": f"exception: {e}"}
        dt = time.time() - dt0
        ok = bool(r.get("ok"))
        if ok:
            total_ok += 1
            total_imgs += r.get("images_total", 0)
        else:
            total_err += 1
        item = {
            "kid": kid,
            "ok": ok,
            "reason": r.get("reason"),
            "images_total": r.get("images_total"),
            "images_ocr_ok": r.get("images_ocr_ok"),
            "secs": round(dt, 1),
        }
        report.append(item)
        logger.info(
            "[%d/%d] doc=%s ok=%s imgs=%s ocr_ok=%s %.1fs %s",
            idx, len(docs), kid, ok, r.get("images_total"),
            r.get("images_ocr_ok"), dt, r.get("reason") or "",
        )
        if args.journal:
            with open(args.journal, "a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    elapsed = time.time() - t0
    after = await _pre_stats()
    summary.update(
        {
            "docs_ok": total_ok,
            "docs_err": total_err,
            "images_total": total_imgs,
            "elapsed_sec": round(elapsed, 1),
            "after": [list(map(str, x)) for x in after],
        }
    )
    logger.info("SUMMARY %s", json.dumps(summary, ensure_ascii=False))
    print("SUMMARY_JSON " + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
