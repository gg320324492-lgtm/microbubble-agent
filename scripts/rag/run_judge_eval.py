"""P1 评测三件套基线运行器 (2026-11-04, 类 20.229: 判据必须可执行)。

固定评测集: 从 search_logs 真实查询采样 50 条 (seed 固定, 集合入库 results/,
后续任何 RAG 改动跑同一集合 => 数字可横比)。

流程 (每条): knowledge_qa.answer_question(auto_research=False) 全链路答案
  → sources 拼上下文 (title + content 节选)
  → RAGEvaluator.evaluate (judge = 本机 M3.1-Flash, 三指标)
  → 汇总 JSON + 控制台摘要。

用法 (容器内):
  python /app/run_judge_eval.py --build-set          # 一次性建固定集合
  python /app/run_judge_eval.py --run --limit 3      # 冒烟
  python /app/run_judge_eval.py --run                # 全量 50 条
"""
import argparse
import asyncio
import json
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/app")

EVAL_SET = "/app/results/rag-judge-eval-set-2026-11-04.json"
SEED = 20261104
SAMPLE_N = 50


async def build_set():
    """从 search_logs 采样 50 条真实查询, 固化为评测集。"""
    from sqlalchemy import text
    from app.core.celery_db import create_celery_engine_and_session
    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        rows = (await db.execute(text(
            "SELECT query, count(*) AS hits FROM search_logs "
            "WHERE length(query) BETWEEN 6 AND 120 "
            "GROUP BY query ORDER BY hits DESC LIMIT 400"))).fetchall()
    await engine.dispose()
    pool = [r[0] for r in rows]
    rnd = random.Random(SEED)
    rnd.shuffle(pool)
    picked = pool[:SAMPLE_N]
    payload = {
        "seed": SEED, "created": datetime.now(timezone.utc).isoformat(),
        "source": "search_logs distinct queries (pool=%d)" % len(pool),
        "queries": picked,
    }
    with open(EVAL_SET, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print("[eval-set] 已写 %d 条 -> %s" % (len(picked), EVAL_SET), flush=True)


async def run(limit, tag=""):
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.knowledge import Knowledge
    from app.services.knowledge_qa_service import KnowledgeQAService
    from app.services.rag_evaluator import RAGEvaluator

    with open(EVAL_SET, encoding="utf-8") as fh:
        queries = json.load(fh)["queries"]
    if limit:
        queries = queries[:limit]

    engine, Session = create_celery_engine_and_session()
    evaluator = RAGEvaluator()
    out, t_all = [], time.time()
    async with Session() as db:
        qa = KnowledgeQAService(db)
        # 类 20.226 ⑦: 评测必须复刻生产路径 —— 用 spy 捕获 _llm_synthesize 收到的
        # 真实上下文 (检索器产出的精确片段), 而不是用 sources 拼近似上下文。
        captured = {}
        orig_synth = KnowledgeQAService._llm_synthesize

        async def _spy(self, question, context_str):
            captured["context"] = context_str
            return await orig_synth(self, question, context_str)

        KnowledgeQAService._llm_synthesize = _spy
        try:
            for i, q in enumerate(queries):
                t0 = time.time()
                try:
                    res = await qa.answer_question(q, top_k=8, auto_research=False)
                    answer = res.get("answer", "")
                    srcs = res.get("sources", [])[:5]
                    context = captured.get("context", "")
                    metrics = await evaluator.evaluate(q, answer, context)
                    out.append({"query": q, "answer_head": answer[:160],
                                "n_sources": len(srcs), "latency_s": round(time.time() - t0, 1),
                                **metrics})
                    print("[%d/%d] %.1fs F=%.2f R=%.2f P=%.2f | %s" % (
                        i + 1, len(queries), time.time() - t0,
                        metrics["faithfulness"], metrics["answer_relevancy"],
                        metrics["context_precision"], q[:36]), flush=True)
                except Exception as e:
                    out.append({"query": q, "error": "%s: %s" % (type(e).__name__, str(e)[:160])})
                    print("[%d/%d] ERROR %s" % (i + 1, len(queries), str(e)[:80]), flush=True)
        finally:
            KnowledgeQAService._llm_synthesize = orig_synth

    ok = [r for r in out if "error" not in r]
    summary = {
        "n": len(out), "n_ok": len(ok),
        "mean_faithfulness": round(sum(r["faithfulness"] for r in ok) / max(1, len(ok)), 4),
        "mean_answer_relevancy": round(sum(r["answer_relevancy"] for r in ok) / max(1, len(ok)), 4),
        "mean_context_precision": round(sum(r["context_precision"] for r in ok) / max(1, len(ok)), 4),
        "overall": round(sum(r["overall"] for r in ok) / max(1, len(ok)), 4),
        "wall_s": round(time.time() - t_all, 1),
        "judge": "MiniMax-M3.1-Flash", "detail": out,
    }
    # --tag 让复测结果另存: 判「改好还是改坏」必须把修前/修后两份都留着,
    # 覆盖掉基线就等于失去参照 (类 20.252: 跨轮比较先确认参照集没变)。
    path = "/app/results/rag-judge-baseline-2026-11-04%s%s.json" % (
        "-smoke" if limit else "", ("-" + tag) if tag else "")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)
    print("\n== 汇总 ==\n%s" % json.dumps(
        {k: v for k, v in summary.items() if k != "detail"}, ensure_ascii=False), flush=True)
    print("已写", path, flush=True)
    await engine.dispose()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-set", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="", help="复测标签, 结果另存不覆盖修前基线")
    args = ap.parse_args()

    if args.build_set:
        asyncio.run(build_set())
    elif args.run:
        asyncio.run(run(args.limit, args.tag))


if __name__ == "__main__":
    main()
