"""agent45 验收 — 罕见词探针: 语义路 (agent44, 0/6) vs 词法路 (agent45)。

判定口径与 agent44 的 scripts/a44_verify_probe_rank.py 一致:
  1. 库里字面包含探针词的页 = ground truth (按 page_transcript_id)
  2. 看该页在检索排序里的名次, top-5 命中才算 PASS

三组: 英文罕见词 / 中文词 / 中英混合。
"""
from __future__ import annotations

import asyncio
import logging as _logging
import sys

sys.path.insert(0, "/app")
_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from sqlalchemy import text as sqlt
from app.core.database import async_session
from app.services.page_transcript_retriever import PageTranscriptRetriever

# 英文罕见词 (agent44 的 6 探针, 只保留库内真实存在的 5 个)
EN_PROBES = [
    "acidobacteria_subgroup_6_ge",
    "algoriphagus_aquatilis",
    "anaerotruncus",
    "alphafold",
    "air-nanobubble",
]
# 中文
ZH_PROBES = ["纳米气泡", "硝化", "单胞菌"]
# 中英混合 —— 探针是「单个罕见表达」, gt 用该表达到底哪些页有。
# 库里真实存在: "nanobubble" 与中文「气泡」常在气泡主题页共现。
MIX_PROBES = ["nanobubble", "Microbubble"]
NEGATIVES = ["zzqx_nonexistent_probe_8891", "completely_absent_term_4471"]


async def _gt_ids(db, probe):
    rows = (await db.execute(
        sqlt("""
            SELECT id FROM knowledge_page_transcripts
            WHERE blocked = FALSE AND content ILIKE :pat
        """),
        {"pat": f"%{probe}%"},
    )).all()
    return {r.id for r in rows}


async def _rank(hits, gt_ids):
    ids = [h["page_transcript_id"] for h in hits]
    return next((i + 1 for i, pid in enumerate(ids) if pid in gt_ids), None)


async def main() -> None:
    async with async_session() as db:
        r = PageTranscriptRetriever(db)
        for label, probes in [("英文罕见词", EN_PROBES), ("中文词", ZH_PROBES),
                              ("中英混合", MIX_PROBES)]:
            print(f"\n===== {label} =====")
            sem_pass = lex_pass = 0
            for p in probes:
                gt = await _gt_ids(db, p)
                sem = await r.search_pages(p, top_k=5)
                lex = await r.search_pages_lexical(p, top_k=5)
                s_rank = await _rank(sem, gt)
                l_rank = await _rank(lex, gt)
                s_ok = bool(gt) and any(h["page_transcript_id"] in gt for h in sem)
                l_ok = bool(gt) and any(h["page_transcript_id"] in gt for h in lex)
                sem_pass += int(s_ok)
                lex_pass += int(l_ok)
                print(f"  {p!r}  gt={len(gt)}页  "
                      f"语义PASS={s_ok}(rank={s_rank})  "
                      f"词法PASS={l_ok}(rank={l_rank} "
                      f"{'ts' if lex and lex[0].get('lexical_match')=='tsvector' else 'ilike'})")
            print(f"  >>> {label}: 语义 {sem_pass}/{len(probes)}  词法 {lex_pass}/{len(probes)}")

        print("\n===== 反例 (库内不存在, 应无命中) =====")
        for neg in NEGATIVES:
            lex = await r.search_pages_lexical(neg, top_k=5)
            print(f"  {neg!r}: 词法返回 {len(lex)} 条 (期望 0)")

        # E2E: 走完整 retrieve_with_weights (rerank + pin), 命中必须在 final top-5
        print("\n===== E2E retrieve_with_weights (rerank + pin) =====")
        from app.services.hybrid_retriever import retrieve_with_weights
        for p, gt_kid in [
            ("air-nanobubble", 2651),
            ("alphafold", 2650),
            ("acidobacteria_subgroup_6_ge", 2409),
        ]:
            res = await retrieve_with_weights(db, query=p, top_k=5)
            ids = [x.get("id") for x in res]
            pinned = [x.get("id") for x in res if x.get("lexical_pinned")]
            print(f"  {p!r}: final_ids={ids} gt={gt_kid} "
                  f"HIT={gt_kid in ids} pinned={pinned}")

        print("\n[done]")


if __name__ == "__main__":
    asyncio.run(main())
