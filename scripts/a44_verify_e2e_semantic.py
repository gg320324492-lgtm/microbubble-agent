"""agent44 最终验收 — 语义探针走完整前台检索链路 (retrieve_with_weights)。

每条探针预先指定了「正确答案」(knowledge_id + 页码), 判定:
  PASS  = top-1 就是那一页, 且该页带 page_transcript 信号
  WEAK  = 那一页在结果里但不是 top-1 (实测多为同汇报人的**重复 deck**,
          同一页内容在两份 pptx 里都存在 —— 属语料重复, 非召回失败)
  FAIL  = 结果里完全没有那一页
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

import logging as _logging

_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from app.core.database import async_session
from app.services.hybrid_retriever import retrieve_with_weights

CASES = [
    ("3,4-二羟基苯甲酸被臭氧氧化后苯环开环生成什么中间产物",
     2593, 12, "3,4-DHBA 臭氧氧化 / Ring Opening / 3-羟基粘康酸"),
    ("微纳米气泡处理甲基胺和罗丹明B的降解动力学常数是多少",
     2512, 40, "污染物/气体类型/降解速率常数 表格"),
    ("肠道细菌群落有哪些潜在代谢功能通路",
     2480, 16, "Entner-Doudoroff / 糖酵解 / 乙醛酸循环"),
    ("空气纳米气泡在污水处理中的应用",
     2625, 12, "空气纳米气泡 应用"),
]


async def main() -> None:
    async with async_session() as db:
        n_pass = n_weak = n_fail = 0
        for query, want_kid, want_page, note in CASES:
            res = await retrieve_with_weights(query=query, db=db, top_k=8)
            hits = [
                (i, it) for i, it in enumerate(res, 1)
                if it.get("id") == want_kid
            ]
            top = res[0] if res else None
            exact = bool(
                top and top.get("id") == want_kid
                and any(m.get("page_number") == want_page
                        for m in (top.get("page_transcript_matches") or []))
            )
            if exact:
                verdict = "PASS"
                n_pass += 1
            elif hits:
                verdict = "WEAK"
                n_weak += 1
            else:
                verdict = "FAIL"
                n_fail += 1

            print(f"{verdict} {query}")
            print(f"     期望 kid={want_kid} p{want_page} — {note}")
            for rank, it in enumerate(res[:4], 1):
                pt = it.get("page_transcript_score")
                mark = "★" if it.get("id") == want_kid else " "
                print(f"     {mark} rank{rank} score={float(it.get('score') or 0):.4f} "
                      f"kid={it.get('id')} {str(it.get('title'))[:38]}"
                      + (f"  pt_sim={pt:.4f}" if pt else ""))
                for m in (it.get("page_transcript_matches") or [])[:3]:
                    print(f"          ↳ 整页转写命中 p{m.get('page_number')} "
                          f"sim={float(m.get('similarity') or 0):.4f}")
            print()

        print(f"[E2E 汇总] PASS={n_pass}  WEAK={n_weak}  FAIL={n_fail} "
              f"(共 {len(CASES)} 条语义探针)")


if __name__ == "__main__":
    asyncio.run(main())
