"""半自动标注辅助脚本 — 给 eval_queries.jsonl 补 relevant_ids

流程：
1. 跑 hybrid_retriever.retrieve() 拿每问 top-10 候选
2. 输出到控制台让人工标记哪些是相关
3. 把标记结果合并到 data/eval_queries.jsonl

跑法：
    cd /opt/microbubble-agent
    python scripts/build_eval_ground_truth.py
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.database import async_session
from app.services.hybrid_retriever import get_hybrid_retriever

EVAL_FILE = ROOT / "data" / "eval_queries.jsonl"
GT_FILE = ROOT / "data" / "ground_truth_template.jsonl"


def load_eval_set():
    with open(EVAL_FILE, encoding="utf-8") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]


async def main():
    cases = load_eval_set()
    print(f"📋 {len(cases)} 问，开始 retrieve() 检索 top-10 候选...\n")

    async with async_session() as db:
        retriever = get_hybrid_retriever(db)
        template = []
        for case in cases:
            print(f"━━━ [{case['id']}] {case['query']} ━━━")
            results = await retriever.retrieve(case["query"], top_k=10)
            if not results:
                print("    ⚠️ 检索无结果（可能数据库无知识条目）")
                template.append({**case, "candidates": []})
                continue
            for i, r in enumerate(results, 1):
                snippet = (r.get("content", "") or "")[:80].replace("\n", " ")
                print(f"    {i:2d}. [id={r.get('id')}] {r.get('title', '?')[:50]}  | {snippet}...")
            relevant = input(f"    → relevant_ids (逗号分隔, 0=跳过): ").strip()
            if relevant and relevant != "0":
                ids = [int(x) for x in relevant.split(",") if x.strip().isdigit()]
                template.append({**case, "relevant_ids": ids})
            else:
                template.append({**case, "relevant_ids": []})
            print()

        with open(GT_FILE, "w", encoding="utf-8") as f:
            for entry in template:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"\n✅ 模板已生成: {GT_FILE}")
        print(f"   人工筛选完后，cp {GT_FILE.name} {EVAL_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())
