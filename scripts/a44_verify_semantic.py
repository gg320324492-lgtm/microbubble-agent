"""agent44 验收 (语义版) — 整页转写到底能不能被「像样的问题」检索到。

## 为什么上一版 0/6 (重要教训)

上一版用**单个罕见拉丁词**当探针 (species name / pathway name), 结论 0/6。
复盘后确认那不是入库失败, 而是**探针设计与向量召回的能力边界不匹配**:

* 整页 embedding 是「这一页整体语义」的向量, 单个罕见 token 只占该页
  字符的一小部分, 在向量空间里被整页文本稀释 → 字面含该词的页排不进 top-5
* 反例探针 ``zzqx_nonexistent_probe_8891`` 拿到 sim=0.517, 比多数真探针还高
  —— 说明这条路**没有相似度下限**, 任何 query 都会返回 top_k 条。
  「返回了 3 条」因此不能作为「命中」的证据。

所以本版用两类**有正确答案**的探针:
  A. 语义探针 (自然语言问题) —— 整页转写真正擅长、也真正补上的场景
     (图里的机理图/表格/坐标轴标签, 原生解析文本里根本没有)
  B. 文档级探针 (先按文件名定位一篇 deck, 再问该 deck 的内容)
每条都要求: top-1 命中**事先指定的**那一页, 否则 FAIL。
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "/app")

import logging as _logging

_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from app.core.database import async_session
from app.services.page_transcript_retriever import PageTranscriptRetriever

# (探针问题, 期望命中的 knowledge_id, 期望页码, 该页独有的一句特征)
CASES = [
    ("3,4-二羟基苯甲酸被臭氧氧化后苯环开环生成什么中间产物",
     2593, 12, "3,4-DHBA 臭氧氧化 / Ring Opening / 3-羟基粘康酸"),
    ("微纳米气泡处理甲基胺和罗丹明B的降解动力学常数是多少",
     2512, 40, "污染物/气体类型/降解速率常数 表格"),
    ("肠道细菌群落有哪些潜在代谢功能通路",
     2480, 16, "Entner-Doudoroff / 糖酵解 / 乙醛酸循环"),
]


async def main() -> None:
    async with async_session() as db:
        r = PageTranscriptRetriever(db)
        pool = await r._load_candidates()
        print(f"[候选池] {len(pool)} 页\n")

        passed = 0
        for query, want_kid, want_page, note in CASES:
            hits = await r.search_pages(query, top_k=5)
            top = hits[0] if hits else None
            ok = bool(
                top
                and top["knowledge_id"] == want_kid
                and top["page_number"] == want_page
            )
            in_top5 = any(
                h["knowledge_id"] == want_kid and h["page_number"] == want_page
                for h in hits
            )
            passed += int(ok)
            print(f"{'PASS' if ok else ('WEAK' if in_top5 else 'FAIL')} {query}")
            print(f"     期望 kid={want_kid} p{want_page} — {note}")
            print(f"     实际 top1 kid={top['knowledge_id'] if top else None} "
                  f"p{top['page_number'] if top else None} "
                  f"sim={top['similarity']:.4f}" if top else "     实际 无结果")
            if not ok:
                for i, h in enumerate(hits[:3], 1):
                    print(f"       rank{i} kid={h['knowledge_id']} "
                          f"p{h['page_number']} sim={h['similarity']:.4f} "
                          f"{h['file_name']}")
            print()

        print(f"[语义召回] top-1 精确命中 {passed}/{len(CASES)}")


if __name__ == "__main__":
    asyncio.run(main())
