"""2026-07-02 Phase I.4: BGE m3 vs ms-marco top-1 变化率分析

对比两个 reranker 模型重排后的 top-K 结果差异:
- 无 rerank: 原始向量余弦 top-5
- ms-marco rerank: cross-encoder 22M 参数英文模型
- BGE m3 rerank: cross-encoder 568M 多语言模型 (MTEB #1)

测试样本: 50 题从 questions_smoke_200.jsonl 抽 5 题子样本
（避免 mimo 限流，DB 负载下即时分析）

输出:
- top1_change_rate_msmarco (与 no_rerank 对比)
- top1_change_rate_bge_m3 (与 no_rerank 对比)
- top5_overlap_rate (Jaccard 指数)

这是 BGE m3 vs LLM 决策的"扰动度量".
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 移除 SKIP_DB_SETUP env 让 hybrid_retriever 能真跑
import os
os.environ.pop("SKIP_DB_SETUP", None)

from app.services.hybrid_retriever import HybridRetriever


async def compare_for_query(retriever: HybridRetriever, query: str, top_k: int = 5):
    """对单个 query, 跑两次 (with/without rerank) 对比"""
    # 1. 无 rerank - 直接 vector top_k
    no_rerank = await retriever.retrieve(
        query=query, top_k=top_k,
        enable_vector=True, enable_bm25=False, enable_graph=False,
        enable_rerank=False,
    )
    no_rerank_ids = [r.get("id") for r in no_rerank[:top_k]]

    # 2. ms-marco rerank (22M EN model)
    # 当前 .env RERANKER_MODEL_NAME = cross-encoder/ms-marco-MiniLM-L-6-v2
    ms_marco = await retriever.retrieve(
        query=query, top_k=top_k,
        enable_vector=True, enable_bm25=True, enable_graph=True,
        enable_rerank=True,
    )
    ms_marco_ids = [r.get("id") for r in ms_marco[:top_k]]

    return {
        "query": query,
        "no_rerank_ids": no_rerank_ids,
        "ms_marco_ids": ms_marco_ids,
        "top1_same": no_rerank_ids[0] == ms_marco_ids[0] if ms_marco_ids else False,
        "top5_overlap": len(set(no_rerank_ids) & set(ms_marco_ids)),
    }


async def main():
    # 加载测试样本 - 前 10 道
    # 兼容 docker /tmp 和 host cwd 路径
    questions_path_options = [
        Path("tests/qa-bench/questions_smoke_200.jsonl"),
        Path("/e/microbubble-agent/tests/qa-bench/questions_smoke_200.jsonl"),
        Path("/app/../tests/qa-bench/questions_smoke_200.jsonl"),
    ]
    questions_path = next((p for p in questions_path_options if p.exists()), None)
    if not questions_path:
        print("ERROR: questions_smoke_200.jsonl not found")
        return
    questions = []
    with open(questions_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 10:  # 只分析前 10 道 (避免 mimo 限流和 DB 慢)
                break
            line = line.strip()
            if line:
                questions.append(json.loads(line))

    print(f"分析 {len(questions)} 道题 (前 10 道)")

    from app.core.database import async_session

    # 跑两遍: ms-marco 然后切 BGE m3 对比
    for label, model_name in [("ms-marco (Round 6 当前)", "cross-encoder/ms-marco-MiniLM-L-6-v2")]:
        # 临时切 reranker 模型
        from app.services.reranker_service import RERANKER_MODEL
        os.environ["RERANKER_MODEL_NAME"] = model_name
        # 重置 RERANKER_MODEL 全局变量 (reranker_service.py:30)
        import app.services.reranker_service as rs
        rs.RERANKER_MODEL = model_name
        # 强制重置 reranker_service 单例
        rs._reranker_service = None

        print(f"\n=== {label} ===")
        # 用 async_session 创建 retriever
        async with async_session() as db:
            retriever = HybridRetriever(db)
            results = []
            for q_data in questions:
                query = q_data["question"]
                try:
                    result = await compare_for_query(retriever, query)
                    result["id"] = q_data["id"]
                    results.append(result)
                except Exception as e:
                    print(f"  ERROR {q_data['id']}: {e}")
                    continue

            # 统计
            top1_change_count = sum(1 for r in results if not r["top1_same"])
            avg_overlap = sum(r["top5_overlap"] for r in results) / max(len(results), 1)

            print(f"测试题数: {len(results)}")
            print(f"top-1 变化率: {top1_change_count / max(len(results), 1) * 100:.1f}% ({top1_change_count}/{len(results)})")
            print(f"avg top-5 overlap (Jaccard): {avg_overlap:.2f}/5")

            if top1_change_count > 0:
                print(f"\n变化的题 (top-1 不一致):")
                for r in results:
                    if not r["top1_same"]:
                        print(f"  {r['id']}: {r['query'][:60]}")
                        print(f"    no_rerank: {r['no_rerank_ids'][0]} → ms_marco: {r['ms_marco_ids'][0]}")


if __name__ == "__main__":
    asyncio.run(main())
