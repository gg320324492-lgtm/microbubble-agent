"""RAG 召回率评估脚本

跑 data/eval_queries.jsonl 标注集：
1. 对每问调 hybrid_retriever.retrieve() 拿 top-5
2. 计算 recall@5 / precision@5 / MRR
3. 跑消融（vector only / bm25 only / 四路全开对比）
4. 报告 → data/rag_recall_report.json

跑法：
    cd /opt/microbubble-agent
    python scripts/run_rag_eval.py
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
REPORT_FILE = ROOT / "data" / "rag_recall_report.json"


def load_eval_set():
    with open(EVAL_FILE, encoding="utf-8") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]


async def main():
    eval_set = load_eval_set()
    print(f"📋 加载 {len(eval_set)} 条评估问句")

    # 过滤有 relevant_ids 标注的（无标注 skip）
    annotated = [c for c in eval_set if c.get("relevant_ids")]
    if not annotated:
        print("⚠️ 当前标注集无 relevant_ids，跳过召回率评估")
        print("   （待人工补充 relevant_ids 标注后重跑）")
        # 输出空报告
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "n_questions": 0,
                "skipped": "无 relevant_ids 标注",
                "ablations": {},
            }, f, ensure_ascii=False, indent=2)
        return

    async with async_session() as db:
        retriever = get_hybrid_retriever(db)
        # 消融对比
        ablations = {
            "all_paths": {},  # 默认全开
            "vector_only": {"enable_bm25": False, "enable_graph": False, "enable_rerank": False},
            "bm25_only": {"enable_vector": False, "enable_graph": False, "enable_rerank": False},
            "no_graph": {"enable_graph": False},
            "no_rerank": {"enable_rerank": False},
        }
        report = await retriever.evaluate(annotated, top_k=5, ablations=ablations)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✅ RAG 评估完成 ({report['n_questions']} 问)")
    print(f"   recall@5:    {report['recall@5']:.3f}")
    print(f"   precision@5: {report['precision@5']:.3f}")
    print(f"   mrr:         {report['mrr']:.3f}")
    if "ablations" in report:
        print("\n   消融对比:")
        for name, abl in report["ablations"].items():
            print(f"     {name:20s} recall={abl['recall@5']:.3f}  mrr={abl['mrr']:.3f}")
    print(f"\n📄 报告: {REPORT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
