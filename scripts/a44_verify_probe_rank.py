"""agent44 验收 (严格版) — 探针词是否**真的**被召回, 而不是「碰巧有相似结果」。

判定口径:
  1. 先在库里定位**字面包含**探针词的页 (ground truth)
  2. 再看该页在 PageTranscriptRetriever 排序里的名次
  3. top-5 命中该页才算 PASS —— 「有 3 条结果」不等于「命中」

同时跑一组**反例探针** (库里根本不存在的词), 确认检索不会无差别返回。
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

import logging as _logging

_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from sqlalchemy import text as sqlt
from app.core.database import async_session
from app.services.page_transcript_retriever import PageTranscriptRetriever

PROBES = [
    "acidobacteria_subgroup_6_ge",
    "acinetobacter_johnsonii",
    "anaerotruncus",
    "algoriphagus_aquatilis",
    "alphafold",
    "air-nanobubble",
]

# 反例: 这些串在任何表里都不该出现, 用来确认检索不是「随便返回 top_k」
NEGATIVES = ["zzqx_nonexistent_probe_8891", "completely_absent_term_4471"]


async def main() -> None:
    async with async_session() as db:
        pool = await PageTranscriptRetriever(db)._load_candidates()
        print(f"[候选池] {len(pool)} 页\n")
        r = PageTranscriptRetriever(db)

        passed = 0
        for probe in PROBES:
            # 1) ground truth: 字面包含该词的页
            gt = (await db.execute(
                sqlt("""
                    SELECT id, knowledge_id, page_number, file_name, char_count
                    FROM knowledge_page_transcripts
                    WHERE blocked = FALSE AND content ILIKE :pat
                    ORDER BY char_count DESC
                """),
                {"pat": f"%{probe}%"},
            )).all()
            gt_ids = {row.id for row in gt}

            # 2) 检索排序
            hits = await r.search_pages(probe, top_k=20)
            ranked_ids = [h["page_transcript_id"] for h in hits]
            rank = next(
                (i + 1 for i, pid in enumerate(ranked_ids) if pid in gt_ids),
                None,
            )
            top5 = any(pid in gt_ids for pid in ranked_ids[:5])
            ok = top5 and rank is not None
            passed += int(ok)

            print(f"{'PASS' if ok else 'FAIL'} {probe!r}")
            print(f"     ground-truth 页数={len(gt)}  "
                  f"该词在 top-5 内={top5}  首次名次={rank}")
            for row in gt[:2]:
                print(f"     gt: p{row.page_number} chars={row.char_count} "
                      f"kid={row.knowledge_id} {row.file_name}")
            for i, h in enumerate(hits[:3], 1):
                mark = "★" if h["page_transcript_id"] in gt_ids else " "
                print(f"     {mark} rank{i} sim={h['similarity']:.4f} "
                      f"p{h['page_number']} kid={h['knowledge_id']} "
                      f"{h['file_name']}")

        print(f"\n[严格召回] {passed}/{len(PROBES)} 个探针词 top-5 命中字面页")

        print("\n=== 反例探针 (库里不存在, 应无命中) ===")
        for neg in NEGATIVES:
            n = (await db.execute(
                sqlt("SELECT count(*) FROM knowledge_page_transcripts "
                     "WHERE blocked=FALSE AND content ILIKE :pat"),
                {"pat": f"%{neg}%"},
            )).scalar_one()
            hits = await r.search_pages(neg, top_k=3)
            print(f"  {neg!r}: 库内字面命中={n}  检索返回={len(hits)} 条 "
                  f"(sim={[round(h['similarity'], 3) for h in hits]})")

        print("\n[done]")


if __name__ == "__main__":
    asyncio.run(main())
