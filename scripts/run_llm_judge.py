"""LLM-as-judge 评估脚本

跑 data/eval_queries.jsonl 标注集：
1. 对每问调 hybrid_retriever.retrieve() 拿 context
2. 调 agent.chat() 拿 answer
3. 调 rag_evaluator.evaluate() 评分（faithfulness / relevancy / precision / recall）
4. 聚合报告 → data/quality_report.json

跑法：
    cd /opt/microbubble-agent
    python scripts/run_llm_judge.py
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.database import async_session
from app.services.rag_evaluator import get_rag_evaluator
from app.services.hybrid_retriever import get_hybrid_retriever
from app.agent.micro_bubble_agent import agent as v2_agent

EVAL_FILE = ROOT / "data" / "eval_queries.jsonl"
REPORT_FILE = ROOT / "data" / "quality_report.json"
BASELINE_FILE = ROOT / "data" / "quality_report_baseline.json"


def load_eval_set() -> list:
    cases = []
    with open(EVAL_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


async def main():
    cases = load_eval_set()
    print(f"📋 加载 {len(cases)} 条评估问句")

    async with async_session() as db:
        evaluator = get_rag_evaluator()
        retriever = get_hybrid_retriever(db)

        per_query = []
        for case in cases:
            print(f"  ⏳ [{case['id']}/{len(cases)}] {case['query'][:30]}...")
            # 1. 检索 context
            ctx_results = await retriever.retrieve(case["query"], top_k=5)
            context_text = "\n".join(r.get("content", "") for r in ctx_results)
            # 2. 生成答案
            answer = await v2_agent.chat(
                message=case["query"],
                session_id=f"eval_{case['id']}",
                db=db,
                user_id=1,  # admin
            )
            # 3. LLM-as-judge 评分
            try:
                metrics = await evaluator.evaluate(
                    query=case["query"],
                    answer=answer.get("content", ""),
                    context=context_text,
                    reference=case.get("reference_answer"),
                )
            except Exception as e:
                print(f"    ⚠️ 评分失败: {e}")
                metrics = {"faithfulness": 0, "answer_relevancy": 0, "context_precision": 0, "context_recall": 0, "overall": 0}

            per_query.append({
                "id": case["id"],
                "query": case["query"],
                **metrics,
            })

        # 聚合
        n = len(per_query)
        report = {
            "n_questions": n,
            "avg_faithfulness": sum(p["faithfulness"] for p in per_query) / n,
            "avg_answer_relevancy": sum(p["answer_relevancy"] for p in per_query) / n,
            "avg_context_precision": sum(p["context_precision"] for p in per_query) / n,
            "avg_context_recall": sum(p["context_recall"] for p in per_query) / n,
            "avg_overall": sum(p["overall"] for p in per_query) / n,
            "details": per_query,
        }
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        # 首次跑同步到 baseline
        if not BASELINE_FILE.exists():
            with open(BASELINE_FILE, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"📌 已生成 baseline: {BASELINE_FILE}")

    print("\n" + "=" * 60)
    print(f"✅ 评估完成 ({n} 问)")
    print(f"   avg_faithfulness:    {report['avg_faithfulness']:.3f}")
    print(f"   avg_answer_relevancy:{report['avg_answer_relevancy']:.3f}")
    print(f"   avg_context_precision:{report['avg_context_precision']:.3f}")
    print(f"   avg_context_recall:  {report['avg_context_recall']:.3f}")
    print(f"   avg_overall:         {report['avg_overall']:.3f}")
    print(f"\n📄 报告: {REPORT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
