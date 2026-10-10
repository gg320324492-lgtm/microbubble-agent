"""agent44 验收探针 — 找「只存在于整页视觉转写、任何既有索引里都没有」的词。

验收标准 (brief 要求 5): 用几个只有页面转写里才有、文件名和正文里都没有的词,
验证真的能检索命中。

这里的「既有索引」取最宽口径 —— 检索池里所有可被文本路命中的正文:
  * knowledge.content / formatted_content
  * knowledge_chunks.content
  * knowledge_images.ocr_text
  * 文件名 (file_name / title)
探针词必须在这四类里**一个都不出现**, 才算「只有页面转写里才有」。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter

sys.path.insert(0, "/app")

import logging as _logging
_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from sqlalchemy import text as sqlt
from app.core.database import async_session

# 中英混合词: 拉丁串 (>=3) 或中文串 (>=3)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}|[一-鿿]{3,}")

# 明显无信息量 / 到处都有的词, 排除
_STOP = {
    "the", "and", "for", "with", "this", "that", "from", "are", "was", "were",
    "com", "www", "http", "https", "pdf", "pptx", "png", "jpg", "jpeg", "gif",
    "lab", "univ", "university", "tianjin", "天津大学", "环境学院",
    "研究", "结果", "方法", "系统", "实验", "分析", "模型", "数据",
}


async def main() -> None:
    async with async_session() as db:
        # 探针候选: 只从 page_transcripts 正文取
        rows = (await db.execute(sqlt("""
            SELECT p.content, p.knowledge_id, p.page_number, p.file_name
            FROM knowledge_page_transcripts p
            WHERE p.blocked = FALSE AND p.content IS NOT NULL
        """))).all()

        corpus_counts: Counter = Counter()
        for r in rows:
            corpus_counts.update({t.lower() for t in _TOKEN.findall(r.content or "")})

        # 既有索引全文 (最大口径)
        existing = (await db.execute(sqlt("""
            SELECT string_agg(txt, ' ') FROM (
                SELECT coalesce(content,'') || ' ' || coalesce(formatted_content,'') AS txt
                FROM knowledge WHERE deleted_at IS NULL
                UNION ALL SELECT coalesce(content,'') FROM knowledge_chunks
                UNION ALL SELECT coalesce(ocr_text,'') FROM knowledge_images
                UNION ALL SELECT coalesce(file_name,'') || ' ' || coalesce(title,'')
                          FROM knowledge
            ) s
        """))).scalar_one()
        existing_l = (existing or "").lower()

    # 打分: 越罕见越像探针; 再要求在既有全文里彻底不出现
    cands = [
        (cnt, tok) for tok, cnt in corpus_counts.items()
        if tok not in _STOP and len(tok) >= 3 and tok not in existing_l
    ]
    cands.sort()

    print(f"[probe] page_transcript 词表 {len(corpus_counts)} 个, "
          f"既有全文 {len(existing_l)} 字符")
    print(f"[probe] 既有索引中**完全不出现**的候选 = {len(cands)}")
    print("\n[probe] 罕见度 top 60 (只出现在整页视觉转写里):")
    out = []
    for cnt, tok in cands[:60]:
        print(f"   {tok:<34} 出现 {cnt} 次")
        out.append({"term": tok, "count": cnt})
    json.dump(out, open("/tmp/a44/_probes.json", "w"), ensure_ascii=False, indent=1)
    print("\n[probe] -> /tmp/a44/_probes.json")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
