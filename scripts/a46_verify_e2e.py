"""agent46 验收 — 走完整 hybrid_retriever, 验证新入的 179 页在前台检索路径可达。

用法 (容器内): PYTHONPATH=/app python3 /tmp/a46_verify_e2e.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

import logging as _L
_L.getLogger("sqlalchemy.engine").setLevel(_L.WARNING)

from app.core.database import async_session
from app.services.hybrid_retriever import retrieve_with_weights

PROBES = [
    "NB-O2改善噬菌体对鱼的附着和摄取",
    "黑臭水体 的定义 GB 3838-2002 地表水环境质量标准",
    "Nitrospira 微生物群落结构 底泥",
]


async def main() -> None:
    async with async_session() as db:
        for p in PROBES:
            res = await retrieve_with_weights(query=p, db=db, top_k=5)
            pt = [i for i in res if i.get("page_transcript_score")]
            print("\n=== %r -> %d 条, 带 page_transcript 信号 %d 条"
                  % (p, len(res), len(pt)))
            for it in res[:3]:
                extra = []
                if it.get("page_transcript_score"):
                    extra.append("pt=%.4f" % it["page_transcript_score"])
                if it.get("image_score"):
                    extra.append("img=%.4f" % it["image_score"])
                print("   score=%s kid=%s %s %s" % (
                    round(it.get("score", 0), 4), it.get("id"),
                    (it.get("file_name") or it.get("title") or "")[:30],
                    " ".join(extra)))


asyncio.run(main())
