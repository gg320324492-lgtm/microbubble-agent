#!/usr/bin/env python3
"""单图 OCR 定向重跑 —— agent31 首次入库（2026-10-09）。

## 为什么存在

``scripts/rerun_failed_ocr.py``（agent28）的重跑单位是**文档**：
``extract_for_knowledge(knowledge_id, reset_status=True)`` 内部先调
``_reset_multimodal_data``，对整个文档做四件事：

1. DELETE 全部 ``knowledge_images`` 行
2. DELETE 全部 ``knowledge_extractions`` 行 —— **含 formula / table / chart**
3. 剥掉 ``knowledge.content`` / ``formatted_content`` 里
   ``<!-- MULTIMODAL_INLINED v2 -->`` 之后的 inline 内容 —— **主文本是 RAG /
   BM25 / tsvector 的索引源**
4. ``knowledge.analysis_status`` 翻成 ``'analyzing'``

所以它适合「整份文档的多模态数据要重建」，**不适合**「一张图的 OCR 漏检了」。
后者只要重调一次 OCR + UPDATE 一行，用不着把整个文档的多模态层推倒重来。

本脚本只做这件事，且爆炸半径 = **指定的 N 行**：

- 调 ``ocr_service.classify_and_extract(image_bytes, mime)`` 拿文字
- ``UPDATE knowledge_images SET ocr_text / ocr_at / ocr_model / ocr_status
  WHERE id = <指定 id>``

不碰其他 ``knowledge_images`` 行、不碰任何 ``knowledge_extractions`` 行、
不碰 ``knowledge.content`` / ``formatted_content``、不碰任何其他表。

## 关键前置：``classify_and_extract`` 是纯函数

``app/services/ocr_service.py:570`` 的 ``classify_and_extract`` 只做一件事：
把图片字节 + prompt 丢给后端，解析 JSON 返回 dict。它**不碰数据库、不碰
MinIO、不碰知识库**。这是本脚本能安全单图重跑的根本原因 —— 没有中间状态
需要回滚。

⚠️ **失败契约（2026-10-09 修复）**：后端调用失败时它**不抛异常**，而是返回
一个带 ``error`` 键的 dict。本脚本用 ``ocr_result_failed(result)`` 判定失败，
**不能**用 ``text`` 是否为空判定 —— 图里本就没文字时 ``text`` 合法为空但无
``error`` 键（类 20.220 的同款陷阱：状态/空值会撒谎）。

## 落库语义：``done`` vs ``done_no_text``

OCR 成功但没抽到文字时落 ``done_no_text`` 而非 ``done``，让「成功且有文字」
与「成功但无文字」在数据上可区分（``knowledge_images.ocr_status`` 列是
``varchar(20)``，**无 CHECK 约束** —— 2026-10-09 实测，只有 PK + FK）。
检索侧无影响：``multimodal_retriever._load_candidates`` 与
``backfill_image_embeddings.py`` **都**额外带 ``ocr_text != ''`` 过滤，
本来就把空文本行挡住了。

## ⚠️ 空结果不等于「图里没字」—— classify prompt 会随机吐 null（2026-10-09 实测）

首次用来重跑 id=6368（本项目核心装置标注图，图上明确有「出水管/进水管/
取样口/O₂MNBs/O₃CBs…」等十余处标注）时，**5/5 全部返回空**。但同一张图、
同一个 prompt，改调 ``extract_text``（单一「提取所有文字」指令）**5/5 全部拿到
文字**。交替调用测得：

    round1: classify=0    extract_text=60
    round2: classify=166  extract_text=182
    round3: classify=0    extract_text=348

根因：``classify_and_extract`` 给模型的是**多任务 JSON 指令**（分类 + latex +
table_md + chart_description + caption），模型经常把 ``text`` 字段直接填
``null``；``extract_text`` 只让模型干「把图里所有字抄出来」一件事，输出稳定。
**JSON 解析层没问题**（``parse_llm_json`` 对同一段 raw 返回完整 text，已单测）。

所以本脚本在 classify 返回空时**自动换 ``extract_text`` 再试一次** ——
这是换 prompt，不是重试同一件事。全库 3320 行 ``done`` + 空文本里有多少是
这种抖动（而非真的没字），尚未普查，但至少这一类是真丢数据。

⚠️ 另一面：**镜像/旋转文字会产出幻觉**。id=7867（曝气管管壁镜像字
"ZHONGCE STAINLESS"）三次调用分别返回 ``1ZKBWR ECH OLO5Y 500`` /
``BEAM 01 00217 12001`` / ``TECH OIL 1057 12X89MM`` —— 三个都是编的。
本脚本不判真假（无 ground truth 可比），**这类行需人工复核后再入库**，
别把幻觉文本喂进 RAG 索引。

## 安全边界

- **默认 dry-run**，只 SELECT 打印将要改的行 + 当前值，**不写库**不调 LLM。
  必须显式 ``--apply`` 才动手。
- ``--apply`` 先把这几行的完整旧值落 JSON 备份到 ``--backup`` 指定路径
  （默认 ``data/backups/ocr_single_rerun_<ts>.json``），**备份失败即中止**。
- 每张图独立 try/except：某张失败不影响其余，也不影响已成功的写入。
- ``--with-structured`` 默认**关**：不重跑 ``extract_figure_structured``，
  不覆盖已有的 v28 字段（``visual_summary`` / ``figure_type`` /
  ``is_core_figure`` ...）。视觉模型输出非确定，重跑会无谓搅动这些字段。
  确需刷新时显式加该 flag。
- 不删任何行（只 UPDATE 同一行）。

## 用法（容器内，cwd = /app）

    # 1) 先 dry-run：看会动哪几行、当前值是什么
    docker cp scripts/rerun_single_image_ocr.py microbubble-agent-app-1:/app/scripts/
    docker exec microbubble-agent-app-1 python scripts/rerun_single_image_ocr.py --ids 6368 11360

    # 2) 真写（先自动备份，再重跑）
    docker exec microbubble-agent-app-1 python scripts/rerun_single_image_ocr.py \
        --ids 6368 11360 10060 7867 7146 --apply

    # 3) 顺带刷新 v28 结构化字段（谨慎：会覆盖 visual_summary 等）
    docker exec microbubble-agent-app-1 python scripts/rerun_single_image_ocr.py \
        --ids 6368 --apply --with-structured

## 幂等性

非幂等但收敛：跑完 ``ocr_text`` 有值的行不再命中「空文本」判据。
真失败的行保持 ``failed``，下一跑还会选中，是天然的「重试直到成功」语义。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rerun_single_image_ocr")

for noisy in ("httpx", "httpcore", "aiohttp", "urllib3", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# 落库的四个字段 = 爆炸半径（只 UPDATE 同一行）
MUTATED_COLUMNS = ("ocr_text", "ocr_at", "ocr_model", "ocr_status")

# 备份要覆盖的列（超集：即使将来加字段，备份仍完整）
BACKUP_COLUMNS = (
    "id", "knowledge_id", "image_object_name", "mime_type", "width", "height",
    "page_number", "ocr_status", "ocr_text", "ocr_at", "ocr_model", "ocr_error",
    "figure_type", "visual_summary", "is_core_figure", "embedding",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="单图 OCR 定向重跑（默认 dry-run；--apply 才写库）"
    )
    p.add_argument("--ids", type=int, nargs="+", required=True, help="要重跑的 knowledge_images.id")
    p.add_argument("--apply", action="store_true", help="真写库（默认只读，不调 LLM）")
    p.add_argument("--with-structured", action="store_true",
                   help="同时重跑 extract_figure_structured 并覆盖 v28 字段（默认关）")
    p.add_argument("--backup", type=str, default="",
                   help="备份 JSON 路径（默认 data/backups/ocr_single_rerun_<ts>.json）")
    return p.parse_args()


async def _fetch_rows(db, ids: list[int]) -> list[dict]:
    rows = (await db.execute(
        text(
            "SELECT id, knowledge_id, image_object_name, mime_type, width, height, "
            "page_number, ocr_status, ocr_text, ocr_at, ocr_model, ocr_error, "
            "figure_type, visual_summary, is_core_figure, "
            "(embedding IS NOT NULL) AS has_embedding "
            "FROM knowledge_images WHERE id = ANY(:ids) ORDER BY id"
        ),
        {"ids": ids},
    )).mappings().all()
    return [dict(r) for r in rows]


def _print_plan(rows: list[dict]) -> None:
    logger.info("=== DRY-RUN：将 UPDATE 以下 %d 行（只改 %s） ===", len(rows), ", ".join(MUTATED_COLUMNS))
    for r in rows:
        text_now = r["ocr_text"]
        preview = "<NULL>" if text_now is None else (repr(text_now[:80]) if text_now else "<EMPTY>")
        logger.info("  id=%s knowledge_id=%s %sx%s page=%s", r["id"], r["knowledge_id"],
                    r["width"], r["height"], r["page_number"])
        logger.info("     ocr_status=%r ocr_model=%r ocr_at=%s", r["ocr_status"], r["ocr_model"], r["ocr_at"])
        logger.info("     ocr_text=%s (len=%s)", preview, "NULL" if text_now is None else len(text_now))
        logger.info("     object=%s", r["image_object_name"])
    missing = set(_requested_ids_holder[0]) - {r["id"] for r in rows}
    if missing:
        logger.warning("⚠️ 以下 id 在库中不存在: %s", sorted(missing))


_requested_ids_holder: list[list[int]] = [[]]


async def main() -> int:
    args = parse_args()
    _requested_ids_holder[0] = args.ids

    from app.core.database import async_session

    async with async_session() as db:
        rows = await _fetch_rows(db, args.ids)
        _print_plan(rows)

        if not args.apply:
            logger.info("DRY-RUN 结束（未写库、未调 LLM）。确认无误后加 --apply。")
            return 0
        if not rows:
            logger.error("没有匹配到任何行，退出。")
            return 1

        # ── 1. 备份（失败即中止，绝不先改后补备份）──────────────────────
        backup_path = Path(args.backup) if args.backup else Path(
            "data/backups") / f"ocr_single_rerun_{datetime.now():%Y%m%d_%H%M%S}.json"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "backed_up_at": datetime.now().isoformat(),
            "script": "scripts/rerun_single_image_ocr.py",
            "ids": args.ids,
            "mutated_columns": list(MUTATED_COLUMNS),
            "rows": [
                {k: (str(r[k]) if isinstance(r[k], (datetime,)) else r[k]) for k in BACKUP_COLUMNS if k in r}
                for r in rows
            ],
        }
        backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("✅ 备份已写: %s (%d 行)", backup_path, len(payload["rows"]))
        if not backup_path.exists() or backup_path.stat().st_size == 0:
            logger.error("备份文件为空/缺失，中止（不写库）。")
            return 1

    # ── 2. 逐张重跑（LLM 调用在 DB 事务外，避免长事务挂连接）─────────────
    from app.config import settings
    from app.services.ocr_service import ocr_result_failed, ocr_service
    from app.services.file_service import file_service

    logger.info("OCR backend=%s vision_model=%s", settings.MULTIMODAL_OCR_BACKEND, settings.VISION_MODEL)
    outcomes: list[dict] = []
    for r in rows:
        img_id = r["id"]
        try:
            img_bytes = await file_service.download_file(r["image_object_name"])
            mime = r["mime_type"] or "image/png"
            logger.info("[id=%s] 下载 %d bytes, 调用 OCR ...", img_id, len(img_bytes))

            result = await ocr_service.classify_and_extract(img_bytes, mime)

            # 失败契约：判据是 error 键，不是 text 为空
            err = ocr_result_failed(result)
            if err:
                logger.error("[id=%s] OCR 调用失败: %s", img_id, err)
                await _mark_failed(img_id, f"single-rerun: {err}"[:1000])
                outcomes.append({"id": img_id, "ok": False, "error": err})
                continue

            new_text = (result.get("text") or "").strip()
            caption = (result.get("caption") or "").strip()
            source = "classify"
            if not new_text and caption:
                new_text = f"[caption] {caption}"

            # ── 兜底：classify 的 JSON prompt 会随机把 text 吐成 null ──────
            # 2026-10-09 agent31 实测（id=6368，核心装置标注图，同图同 prompt）：
            #   classify_and_extract  text_len = 0 / 166 / 0   （成功 ~1/3）
            #   extract_text          text_len = 60 / 182 / 348（成功 3/3）
            # 模型收到「分类 + 抽 latex + 抽表格 + 抽图注」的多任务 JSON 指令时，
            # 会把 text 字段填成 null 而不是抽字；改成单一「提取所有文字」指令
            # 就稳定。**空结果不是「图里没字」，是 prompt 触发的抖动**（类 20.220
            # 同款陷阱：空值会撒谎）。所以这里换 prompt 再试一次，不是重试。
            if not new_text:
                logger.info("[id=%s] classify 返回空, 换 extract_text 单一指令再试一次 ...", img_id)
                try:
                    plain = await ocr_service.extract_text(img_bytes, mime)
                    plain = (plain or "").strip()
                    if plain:
                        new_text, source = plain, "extract_text_fallback"
                        logger.info("[id=%s] fallback 拿到 %d 字符", img_id, len(new_text))
                except Exception as fe:
                    logger.warning("[id=%s] extract_text fallback 也失败: %s", img_id, fe)

            category = result.get("category")
            logger.info("[id=%s] category=%s source=%s text_len=%s caption_len=%s",
                        img_id, category, source, len(new_text), len(caption))

            structured = None
            if args.with_structured:
                structured = await ocr_service.extract_figure_structured(img_bytes, mime)
                s_err = ocr_result_failed(structured)
                if s_err:
                    logger.warning("[id=%s] structured 失败（不写默认值）: %s", img_id, s_err)
                    structured = None

            await _write_back(img_id, new_text, structured)
            outcomes.append({
                "id": img_id, "ok": True, "category": category, "source": source,
                "text_len": len(new_text), "text": new_text[:2000],
            })
        except Exception as e:  # 单图失败不影响其余
            logger.exception("[id=%s] 重跑异常", img_id)
            await _mark_failed(img_id, f"single-rerun exception: {e}"[:1000])
            outcomes.append({"id": img_id, "ok": False, "error": str(e)})

    # ── 3. 验证回读 ─────────────────────────────────────────────────────
    async with async_session() as db:
        after = await _fetch_rows(db, [o["id"] for o in outcomes])
    logger.info("=== 回读验证 ===")
    by_id = {r["id"]: r for r in after}
    for o in outcomes:
        r = by_id.get(o["id"])
        if not r:
            logger.error("  id=%s 回读不到！", o["id"])
            continue
        t = r["ocr_text"]
        logger.info("  id=%s status=%r model=%r text_len=%s", r["id"], r["ocr_status"], r["ocr_model"],
                    "NULL" if t is None else len(t))
        if t:
            logger.info("     text[:300]=%s", t[:300].replace("\n", " | "))

    logger.info("=== 汇总 ===")
    logger.info("成功并写入文字: %s", [o["id"] for o in outcomes if o["ok"] and o.get("text_len")])
    logger.info("成功但仍无文字: %s", [o["id"] for o in outcomes if o["ok"] and not o.get("text_len")])
    logger.info("失败: %s", [o["id"] for o in outcomes if not o["ok"]])
    return 0


async def _write_back(img_id: int, new_text: str, structured: dict | None) -> None:
    """只 UPDATE 指定那一行。空文字落 'done_no_text'，有文字落 'done'。

    ``structured`` 为 None（默认）时走裸 SQL，爆炸半径 = 4 个 ocr_* 列。
    给了 ``structured`` 才走 ORM，复用主链路同一个
    ``_apply_v28_structured_fields``，保证字段映射语义完全一致（不复制粘贴）。
    """
    from app.core.database import async_session
    from app.services.ocr_service import _clean_ocr_text
    from app.config import settings

    status = "done" if new_text else "done_no_text"

    if structured:
        from app.models.knowledge_multimodal import KnowledgeImage
        from app.services.multimodal_extraction_service import (
            multimodal_extraction_service as svc,
        )
        from sqlalchemy import select

        async with async_session() as db:
            img = (await db.execute(
                select(KnowledgeImage).where(KnowledgeImage.id == img_id)
            )).scalar_one_or_none()
            if img is None:
                raise RuntimeError(f"image {img_id} 不存在")
            if new_text:
                img.ocr_text = _clean_ocr_text(new_text)[:10000]
            img.ocr_status = status
            img.ocr_model = settings.VISION_MODEL
            img.ocr_at = datetime.utcnow()
            svc._apply_v28_structured_fields(img, structured)
            await db.commit()
        logger.info("  [id=%s] 已落库 status=%s text_len=%s (含 v28 字段刷新)", img_id, status, len(new_text))
        return

    params: dict = {
        "id": img_id,
        "status": status,
        "model": settings.VISION_MODEL,
    }
    sets = ["ocr_status = :status", "ocr_model = :model", "ocr_at = now()"]
    if new_text:
        # 只在拿到文字时写 ocr_text；空文字不覆盖已有文本（防御：不该发生，
        # 因为候选本就是空文本行，但显式化比隐含更安全）
        sets.append("ocr_text = :text")
        params["text"] = _clean_ocr_text(new_text)[:10000]

    sql = f"UPDATE knowledge_images SET {', '.join(sets)} WHERE id = :id"
    async with async_session() as db:
        await db.execute(text(sql), params)
        await db.commit()
    logger.info("  [id=%s] 已落库 status=%s text_len=%s", img_id, status, len(new_text))


async def _mark_failed(img_id: int, error: str) -> None:
    from app.core.database import async_session
    async with async_session() as db:
        await db.execute(
            text("UPDATE knowledge_images SET ocr_status='failed', ocr_error=:e WHERE id=:id"),
            {"id": img_id, "e": error},
        )
        await db.commit()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
