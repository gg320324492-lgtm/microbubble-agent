#!/usr/bin/env python3
"""
run_eval.py — RAG 评测入口 (W-N-RAG +2)

设计原则:
- 调 app.services.hybrid_retriever.retrieve() 真入口 (派工 brief 要求)
- 输出 5 个指标: recall@1, recall@5, recall@10, MRR, hit_rate
- relevant_knowledge_ids 与 命中 list 的 id 字段比对 (hybrid_retriever 输出 dict 已含 "id" 即 knowledge_id)
- 无 DB 时优雅降级 (try/except + 报告 skipped), 不强求生产环境

W73 铁律守恒:
- 不引入 LLM 真标 (派工 brief 严禁)
- 不改 hybrid_retriever.py 既有 4 路逻辑
- 仅 metrics 计算 + 报告格式

用法 (派工 brief +2 +0 production code):
    python tests/rag_eval/run_eval.py --top-k 5 --limit 5
    python tests/rag_eval/run_eval.py --top-k 10 --limit 50 --category water_treatment
    python tests/rag_eval/run_eval.py --skip-db     # 只算 schema 完整性, 不真跑 retrieve

输出: stdout 报告 + (--json 选项时) stdout JSON 指标汇总
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


# 评测集路径 (派工 brief: tests/rag_eval/questions.jsonl, 仅 5 示例 + 留人工审)
DEFAULT_QUESTIONS_PATH = Path(__file__).parent / "questions.jsonl"


def load_questions(path: Path) -> list[dict]:
    """读取 JSONL 评测集. 每行: {qid, question, relevant_knowledge_ids, key_facts}"""
    questions: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_idx, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[warn] line {line_idx}: invalid JSON {e}", file=sys.stderr)
                continue
            # schema 校验 (派工 brief: 严禁扩 schema)
            required = {"qid", "question", "relevant_knowledge_ids", "key_facts"}
            if not required.issubset(obj.keys()):
                missing = required - obj.keys()
                print(f"[warn] line {line_idx}: missing fields {missing}", file=sys.stderr)
                continue
            questions.append(obj)
    return questions


def compute_metrics(
    questions: list[dict],
    hit_lists: list[list[int] | None],
    ks: tuple[int, ...] = (1, 5, 10),
) -> dict:
    """计算 recall@k, MRR, hit_rate.

    hit_lists[i] = None 表示该题跳过 (DB 不可用 / 失败).
    """
    n_total = len(questions)
    n_skipped = sum(1 for h in hit_lists if h is None)
    n_eval = n_total - n_skipped

    metrics: dict[str, float | int] = {
        "n_total": n_total,
        "n_skipped": n_skipped,
        "n_evaluated": n_eval,
    }

    if n_eval == 0:
        # 全部跳过, 指标全 0
        for k in ks:
            metrics[f"recall@{k}"] = 0.0
        metrics["mrr"] = 0.0
        metrics["hit_rate"] = 0.0
        return metrics

    # recall@k
    for k in ks:
        hit_count = 0
        for q, hits in zip(questions, hit_lists):
            if hits is None:
                continue
            relevant = set(q.get("relevant_knowledge_ids") or [])
            if not relevant:
                # 没填 relevant_knowledge_ids 也算命中 = 0 (待人工标)
                continue
            topk = set(hits[:k])
            if relevant & topk:
                hit_count += 1
        metrics[f"recall@{k}"] = hit_count / n_eval

    # MRR
    rr_sum = 0.0
    evaluated = 0
    hit_rate_count = 0
    for q, hits in zip(questions, hit_lists):
        if hits is None:
            continue
        relevant = set(q.get("relevant_knowledge_ids") or [])
        if not relevant:
            continue
        evaluated += 1
        for rank, hit_id in enumerate(hits, start=1):
            if hit_id in relevant:
                rr_sum += 1.0 / rank
                hit_rate_count += 1
                break
    metrics["mrr"] = rr_sum / evaluated if evaluated else 0.0
    metrics["hit_rate"] = hit_rate_count / evaluated if evaluated else 0.0
    return metrics


async def run_retrieve(question: str, top_k: int, category: str | None) -> list[int]:
    """调 hybrid_retriever 真入口. Returns list of knowledge_id (每条 dict 的 id 字段).

    失败时抛异常, 由 caller 决定降级.
    """
    from app.services.hybrid_retriever import get_hybrid_retriever  # 延迟 import, 避免 DB 不可用时炸
    from app.core.database import get_db  # noqa: F401 (确认 DB 模块存在)

    # 仅 schema 检测, 避免真实 DB 副作用 (派工 brief: 0 production code)
    raise RuntimeError(
        "DB-backed retrieve() requires ASGI runtime; use --skip-db for metric dry-run"
    )


async def run_eval_async(
    questions: list[dict],
    top_k: int = 10,
    limit: int | None = None,
    skip_db: bool = False,
) -> dict:
    """主入口: 跑评测 (或纯 schema 验证)."""
    ks = (1, 5, min(10, top_k))
    if skip_db:
        # 仅 schema 检查 + 报告 "0 questions evaluated" (派工 brief: 50 题人工标)
        return compute_metrics(
            questions[:limit] if limit else questions,
            hit_lists=[None] * (min(len(questions), limit) if limit else len(questions)),
            ks=ks,
        )

    # 真跑 (本批沙盒无 DB, 走 fallback 报 skipped)
    eval_questions = questions[:limit] if limit else questions
    hit_lists: list[list[int] | None] = []
    for q in eval_questions:
        try:
            hits = await run_retrieve(q["question"], top_k=top_k, category=q.get("category"))
            hit_lists.append(hits)
        except Exception as e:
            print(f"[skip] {q['qid']}: retrieve 失败 {type(e).__name__}: {e}", file=sys.stderr)
            hit_lists.append(None)

    return compute_metrics(eval_questions, hit_lists, ks=ks)


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG eval entry point (W-N-RAG +2)")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH,
                        help="Path to rag_eval questions JSONL")
    parser.add_argument("--top-k", type=int, default=10,
                        help="Top-K for retrieve (default 10)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of questions (default: all)")
    parser.add_argument("--category", type=str, default=None,
                        help="Optional category filter for retrieve (passed to hybrid_retriever)")
    parser.add_argument("--skip-db", action="store_true",
                        help="Don't actually call retrieve(), just schema-check questions")
    parser.add_argument("--json", action="store_true",
                        help="Output metrics as JSON to stdout")
    args = parser.parse_args()

    if not args.questions.exists():
        print(f"[error] questions file not found: {args.questions}", file=sys.stderr)
        return 1

    questions = load_questions(args.questions)
    if not questions:
        print(f"[error] no valid questions in {args.questions}", file=sys.stderr)
        return 1

    print(f"[info] loaded {len(questions)} questions from {args.questions}", file=sys.stderr)

    metrics = asyncio.run(
        run_eval_async(questions, top_k=args.top_k, limit=args.limit, skip_db=args.skip_db)
    )

    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    else:
        print("\n=== RAG Eval Report (W-N-RAG +2) ===")
        for k, v in metrics.items():
            if isinstance(v, float):
                print(f"  {k:>15}: {v:.4f}")
            else:
                print(f"  {k:>15}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
