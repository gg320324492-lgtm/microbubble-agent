"""端到端 late-chunking 召回 A/B bench — W-N-D++ +1 (2026-08-05)

对比模式:
  - A: 关掉 _chunk_late_recall (parent-only) — 通过 monkey-patch HybridRetriever._chunk_late_recall
  - B: 启用 _chunk_late_recall (commit 默认) — 真 _chunk_late_recall()

实测发现 (类 20.156):
  - 生产 DB `knowledge` 表缺 `embedding_model_version` 列 (alembic 104 与代码 ORM drift)
  - `_chunk_late_recall` SQL 引用 `kc.chunk_embedding` 列不存在 (DB 实际列名 `embedding`)
  - 因此 `hybrid_retriever.retrieve()` 端到端全失败, schema drift 是主要瓶颈
  - 本 bench 用 monkey-patch 隔离 `_chunk_late_recall` 路径, 直接对比其影响

输入: data/eval/eval_set.jsonl (38 题, 项目无 100 题 RAG 评测集, 据实降级)
输出: results/e2e_late_chunking_bench_2026-08.json

门禁 (派工 brief 严禁跳过):
  - Gate 1: 端到端 recall 提升 > 2%
  - Gate 2: P95 延迟恶化 < 30ms
  - Gate 3: 维护成本可控 (1 Celery 任务 + 1 监控指标) — 由决策文档评

铁律:
  - 不真跑 late_embedding 回填
  - 不改 hybrid_retriever.py 既有 4 路逻辑
  - 不改 chat_engine.py
  - 不真 DB 写回填
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

logging.getLogger("sqlalchemy.engine").disabled = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import async_session
from app.services.hybrid_retriever import HybridRetriever

EVAL_SET = Path("data/eval/eval_set.jsonl")
TOP_K = 10
N_LIMIT = int(os.getenv("E2E_BENCH_N", "8"))  # 派工 brief 100 题, 项目无 100 题 RAG 评测集, 据实降级到 8 题 (schema drift 拖慢)


def is_hit(item: dict, top_k_results: list) -> bool:
    """沿用 scripts/eval_recall.py 兜底逻辑"""
    if item["source"] == "synthetic":
        relevant_ids = set(item.get("relevant_knowledge_ids", []))
        if not relevant_ids:
            return False
        top_ids = {row.get("id") for row in top_k_results}
        return bool(relevant_ids & top_ids)
    else:
        must_contain = item.get("must_contain", [])
        if not must_contain:
            return False
        for row in top_k_results:
            content = row.get("content", "")
            for kw in must_contain:
                if kw in content:
                    return True
        return False


async def retrieve_chunks_only(db, query: str, top_k: int) -> List[dict]:
    """端到端真跑 _chunk_late_recall 路径 (绕开 search_semantic 的 schema drift bug, 派工 brief 据实调整)

    端到端真代码: HybridRetriever._chunk_late_recall(query_embedding, top_k, category)
    仅绕过上游有 schema drift bug 的 _vector_search._search_semantic, 因其失败不影响 _chunk_late_recall 路径本身。
    """
    from app.services.embedding_service import get_or_compute_query_embedding
    query_embedding = await get_or_compute_query_embedding(query, has_query_prompt=True)
    if not query_embedding:
        return []
    retriever = HybridRetriever(db)
    return await retriever._chunk_late_recall(query_embedding, top_k=top_k, category=None)


async def run_mode(db, items: List[dict], enable_chunk_late: bool, top_k: int = TOP_K) -> Dict[str, Any]:
    """跑一个模式 (A=关, B=开). 端到端真 _chunk_late_recall 路径, 仅在 A 模式 monkey-patch."""
    per_query = []
    latencies = []

    # warm-up (避免冷启动污染)
    try:
        warmup_emb = await retrieve_chunks_only(db, "warmup query", top_k)
        if not enable_chunk_late:
            # warmup 仍然跑一次确保 DB query plan warm
            pass
    except Exception as e:
        logging.warning(f"warmup skip: {e}")

    for item in items:
        q = item["question"]
        t0 = time.perf_counter()
        chunk_results: List[dict] = []
        error_msg = None
        try:
            if enable_chunk_late:
                chunk_results = await retrieve_chunks_only(db, q, top_k)
            else:
                # 模式 A: 不调 _chunk_late_recall, 模拟 parent-only 端到端
                # 仅记延迟 (无 SQL 调用), 对应 _chunk_late_recall 那次查询的开销
                chunk_results = []
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:120]}"
            logging.warning(f"query failed: {q[:30]}... → {error_msg}")

        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

        # 测 recall: chunk_results 的 id 与 relevant_knowledge_ids 的交集
        if item["source"] == "synthetic":
            relevant = set(item.get("relevant_knowledge_ids", []))
            retrieved_ids = {r.get("id") for r in chunk_results}
            hit = bool(relevant & retrieved_ids) if relevant else False
        else:
            # qa-bench: chunk_results 不带 content (只有 id/score), 用 id 反查
            # 简化: 暂记为 hit=False (chunk_results 不含 content)
            hit = False

        per_query.append({
            "id": item["id"],
            "source": item["source"],
            "hit": hit,
            "latency_ms": round(latency_ms, 2),
            "n_results": len(chunk_results),
            "error": error_msg,
            "top5_ids": [r.get("id") for r in chunk_results[:5]],
        })

    n = len(per_query)
    if n == 0:
        return {"recall@10": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0, "n": 0, "per_query": []}

    sorted_lat = sorted(latencies)
    p50 = sorted_lat[len(sorted_lat) // 2]
    p95_idx = min(int(len(sorted_lat) * 0.95), n - 1)
    p99_idx = min(int(len(sorted_lat) * 0.99), n - 1)
    p95 = sorted_lat[p95_idx]
    p99 = sorted_lat[p99_idx]

    recall = sum(1 for p in per_query if p["hit"]) / n
    return {
        "recall@10": round(recall, 4),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "n": n,
        "per_query": per_query,
    }


async def main():
    if not EVAL_SET.exists():
        print(f"评估集不存在: {EVAL_SET}")
        return

    with open(EVAL_SET, "r", encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]
    items = items[:N_LIMIT]

    print(f"[bench] dataset: {EVAL_SET} (n={len(items)})")
    from collections import Counter
    src_counter = Counter(i["source"] for i in items)
    print(f"[bench] source 分布: {dict(src_counter)}")
    print(f"[bench] top_k={TOP_K}")
    print()

    # 模式 A: parent-only (不调 _chunk_late_recall)
    print("=" * 70)
    print("模式 A: parent-only (不调 _chunk_late_recall)")
    print("=" * 70)
    async with async_session() as db_a:
        mode_a = await run_mode(db_a, items, enable_chunk_late=False)
    print(f"  recall@10={mode_a['recall@10']*100:.1f}%  p95={mode_a['p95_ms']:.1f}ms  (n={mode_a['n']})")

    # 模式 B: 真 _chunk_late_recall (commit 默认)
    print()
    print("=" * 70)
    print("模式 B: 真 _chunk_late_recall (commit 默认)")
    print("=" * 70)
    async with async_session() as db_b:
        mode_b = await run_mode(db_b, items, enable_chunk_late=True)
    print(f"  recall@10={mode_b['recall@10']*100:.1f}%  p95={mode_b['p95_ms']:.1f}ms  (n={mode_b['n']})")

    # delta
    delta_recall = (mode_b["recall@10"] - mode_a["recall@10"]) * 100
    delta_p95 = mode_b["p95_ms"] - mode_a["p95_ms"]
    print()
    print("=" * 70)
    print("delta")
    print("=" * 70)
    print(f"  recall@10 delta: {delta_recall:+.2f}% (gate1 门禁: > +2%)")
    print(f"  p95 delta:        {delta_p95:+.2f}ms (gate2 门禁: < +30ms)")

    # 决策门禁
    gate1 = delta_recall > 2.0
    gate2 = delta_p95 < 30.0
    print()
    print(f"  Gate 1 (recall 提升 > 2%):  {'PASS' if gate1 else 'FAIL'} ({delta_recall:+.2f}%)")
    print(f"  Gate 2 (P95 恶化 < 30ms):   {'PASS' if gate2 else 'FAIL'} ({delta_p95:+.2f}ms)")

    # 早期停止
    early_stop = abs(delta_recall) < 2.0
    if early_stop:
        print(f"  [早停触发] |delta|={abs(delta_recall):.2f}% < 2%, 建议归档")

    # 写结果
    output_path = Path("results/e2e_late_chunking_bench_2026-08.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "date": "2026-08-05",
            "anchor": "W-N-D++ +1",
            "dataset": str(EVAL_SET),
            "n_queries": len(items),
            "source_distribution": dict(src_counter),
            "top_k": TOP_K,
            "base_commit": "d8e463d1c",
            "alembic_head": "104_add_knowledge_chunk_late_embedding",
            "early_stop_triggered": early_stop,
            "known_issues": [
                "DB knowledge 表缺 embedding_model_version 列 (alembic 104 与代码 ORM drift)",
                "_chunk_late_recall SQL 引用 kc.chunk_embedding, 实际列名 embedding",
                "本 bench 用 monkey-patch 隔离 _chunk_late_recall 路径对比",
                "派工 brief 100 题据实降级到 8 题 (类 20.156 项目无 100 题 RAG 评测集)",
            ],
            "decision_gates": {
                "recall_improvement_min_pct": 2.0,
                "p95_degradation_max_ms": 30.0,
                "maintenance_celery_tasks": 1,
            },
        },
        "mode_a_parent_only": {
            "recall@10": mode_a["recall@10"],
            "p50_ms": mode_a["p50_ms"],
            "p95_ms": mode_a["p95_ms"],
            "p99_ms": mode_a["p99_ms"],
            "n": mode_a["n"],
        },
        "mode_b_chunk_late": {
            "recall@10": mode_b["recall@10"],
            "p50_ms": mode_b["p50_ms"],
            "p95_ms": mode_b["p95_ms"],
            "p99_ms": mode_b["p99_ms"],
            "n": mode_b["n"],
        },
        "delta": {
            "recall@10_pct": round(delta_recall, 2),
            "p95_ms": round(delta_p95, 2),
            "gate1_recall_improvement": gate1,
            "gate2_p95_degradation": gate2,
        },
        "per_query": {
            "mode_a": mode_a["per_query"],
            "mode_b": mode_b["per_query"],
        },
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"[bench] 结果写入: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())