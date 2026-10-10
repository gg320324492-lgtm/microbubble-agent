"""agent44 验收 — 用「只存在于整页视觉转写」的探针词验证真的检索得到。

探针词由 :mod:`scripts.a44_find_probe_terms` 选出, 口径是: 在
``knowledge.content`` / ``formatted_content`` / ``knowledge_chunks.content`` /
``knowledge_images.ocr_text`` / 文件名里**一个都不出现**, 只有新表里有。

用法 (容器内):
    python /tmp/a44/verify_pt.py            # 直接打 PageTranscriptRetriever
    python /tmp/a44/verify_pt.py --e2e      # 走完整 hybrid_retriever 链路
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

import logging as _logging

_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from app.core.database import async_session
from app.services.page_transcript_retriever import PageTranscriptRetriever

# acidobacteria_subgroup_6_ge / acinetobacter_johnsonii / anaerotruncus /
# algoriphagus_aquatilis / alphafold / air-nanobubble —— 全部取自
# a44_find_probe_terms 的 top 候选, 既有索引零命中。
PROBES = [
    "acidobacteria_subgroup_6_ge",
    "acinetobacter_johnsonii",
    "anaerotruncus",
    "algoriphagus_aquatilis",
    "alphafold",
    "air-nanobubble",
]


async def direct() -> None:
    async with async_session() as db:
        r = PageTranscriptRetriever(db)
        pool = await r._load_candidates()
        print(f"[候选池] {len(pool)} 页可召回 "
              f"(blocked 行 content IS NULL, 由 CK 约束保证不入池)")
        print()
        hit_terms = 0
        for p in PROBES:
            hits = await r.search_pages(p, top_k=3)
            if hits:
                hit_terms += 1
            print(f"=== 探针 {p!r} -> {len(hits)} 命中")
            for h in hits:
                snippet = (h["content"] or "")[:88].replace("\n", " ")
                print(f"    sim={h['similarity']:.4f}  p{h['page_number']}  "
                      f"kid={h['knowledge_id']}  {h['file_name']}")
                print(f"       {snippet}")
        print(f"\n[直接召回] {hit_terms}/{len(PROBES)} 个探针词有命中")


async def e2e() -> None:
    """走完整 hybrid_retriever 链路 (含新 hook), 验证真正的前台检索路径。"""
    from app.services.hybrid_retriever import retrieve_with_weights

    async with async_session() as db:
        print("[E2E] 走 retrieve_with_weights (含 agent44 page_transcript hook)\n")
        for p in PROBES:
            res = await retrieve_with_weights(query=p, db=db, top_k=5)
            methods = set()
            for item in res:
                methods.update(item.get("retrieval_methods") or [])
            pt = [i for i in res if i.get("page_transcript_score")]
            print(f"=== {p!r} -> {len(res)} 条; "
                  f"带 page_transcript 信号的 {len(pt)} 条; methods={sorted(methods)}")
            for item in res[:3]:
                extra = []
                if item.get("page_transcript_score"):
                    extra.append(
                        f"pt_sim={item['page_transcript_score']:.4f}"
                    )
                if item.get("image_score"):
                    extra.append(f"img_sim={item['image_score']:.4f}")
                print(f"    score={float(item.get('score') or 0):.4f} "
                      f"kid={item.get('id')} {str(item.get('title'))[:40]} "
                      f"{' '.join(extra)}")
                for m in (item.get("page_transcript_matches") or [])[:2]:
                    print(f"       ↳ 命中页 p{m.get('page_number')} "
                          f"sim={float(m.get('similarity') or 0):.4f}")
            print()


if __name__ == "__main__":
    if "--e2e" in sys.argv:
        asyncio.run(e2e())
    else:
        asyncio.run(direct())
