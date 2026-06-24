"""A/B embedding 评估 - 跑检索 + 计算 recall@K / MRR

输入: data/eval/eval_set.jsonl
输出: 打印平均 recall@1 / recall@5 / recall@10 / MRR

评估模式:
  - qa-bench (must_contain): top-K 文档 content 任一关键词出现 = 命中
  - synthetic (relevant_knowledge_ids): top-K IDs 含 ground truth ID = 命中
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.getLogger("sqlalchemy.engine").disabled = True
sys.path.insert(0, "/app")

from app.core.database import async_session
from app.services.embedding_service import _get_model, generate_embedding, generate_embeddings
from sqlalchemy import select, text

EVAL_SET = Path("data/eval/eval_set.jsonl")
TOP_K = 10
MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "?")


async def search_knowledge(query: str, top_k: int = TOP_K) -> list:
    """检索 knowledge 表, 返回 top_k 个 (id, title, content_preview)"""
    qvec = await generate_embedding(query, for_query=True)
    if not qvec:
        return []
    qvec_str = "[" + ",".join(f"{x:.6f}" for x in qvec) + "]"
    sql = (
        f"SELECT id, title, LEFT(content, 200) AS preview "
        f"FROM knowledge "
        f"WHERE embedding IS NOT NULL "
        f"ORDER BY embedding <=> '{qvec_str}'::vector "
        f"LIMIT {top_k}"
    )
    async with async_session() as db:
        result = await db.execute(text(sql))
        return [(row[0], row[1] or "", row[2] or "") for row in result.fetchall()]


def is_hit(item: dict, top_k_results: list) -> bool:
    """判断 top_k_results 是否"命中"该 query 的 ground truth

    qa-bench (source=qa-bench): 必须 content 包含任一 must_contain 关键词
    synthetic (source=synthetic): top-K IDs 必须含 relevant_knowledge_ids
    """
    if item["source"] == "synthetic":
        relevant_ids = set(item.get("relevant_knowledge_ids", []))
        if not relevant_ids:
            return False
        top_ids = {row[0] for row in top_k_results}
        return bool(relevant_ids & top_ids)
    else:
        # qa-bench: content 关键词匹配
        must_contain = item.get("must_contain", [])
        if not must_contain:
            return False
        for row in top_k_results:
            content = row[2]  # preview
            for kw in must_contain:
                if kw in content:
                    return True
        return False


def reciprocal_rank(item: dict, top_k_results: list) -> float:
    """MRR: 第一个相关文档排名的倒数, 没命中 = 0

    qa-bench: 第一个含 must_contain 关键词的文档排名
    synthetic: 第一个 relevant_knowledge_ids 文档排名
    """
    if item["source"] == "synthetic":
        relevant_ids = set(item.get("relevant_knowledge_ids", []))
        if not relevant_ids:
            return 0.0
        for rank, row in enumerate(top_k_results, 1):
            if row[0] in relevant_ids:
                return 1.0 / rank
        return 0.0
    else:
        must_contain = item.get("must_contain", [])
        if not must_contain:
            return 0.0
        for rank, row in enumerate(top_k_results, 1):
            content = row[2]
            for kw in must_contain:
                if kw in content:
                    return 1.0 / rank
        return 0.0


async def main():
    if not EVAL_SET.exists():
        print(f"评估集不存在: {EVAL_SET} (先跑 scripts/build_eval_set.py)")
        return

    items = []
    with open(EVAL_SET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))

    print(f"评估集: {len(items)} 条")
    print(f"模型: {MODEL_NAME}")
    print(f"Top-K: {TOP_K}")
    print()

    # warm-up (触发 Qwen3 加载 + 首次推理)
    print("热身 (warm-up)...")
    await generate_embedding("warmup")
    print()

    # 跑每条 query
    recall_at = {1: 0, 5: 0, 10: 0}
    rr_sum = 0.0
    hits_by_source = {"qa-bench": 0, "synthetic": 0}
    total_by_source = {"qa-bench": 0, "synthetic": 0}

    print("=" * 70)
    for i, item in enumerate(items, 1):
        q = item["question"]
        top_k_results = await search_knowledge(q)
        # 计算 hit @ K
        hit_10 = is_hit(item, top_k_results)
        hit_5 = is_hit(item, top_k_results[:5]) if len(top_k_results) >= 5 else hit_10
        hit_1 = is_hit(item, top_k_results[:1]) if len(top_k_results) >= 1 else False
        rr = reciprocal_rank(item, top_k_results)

        if hit_10:
            recall_at[10] += 1
        if hit_5:
            recall_at[5] += 1
        if hit_1:
            recall_at[1] += 1
        rr_sum += rr

        src = item["source"]
        total_by_source[src] += 1
        if hit_10:
            hits_by_source[src] += 1

        # 显示前 5 条详情
        if i <= 5:
            top1_id = top_k_results[0][0] if top_k_results else None
            mark = "✅" if hit_10 else "❌"
            print(f"  {mark} [{item['id']}] {src}")
            print(f"      Q: {q[:60]}")
            print(f"      top1: id={top1_id}  rr={rr:.2f}")
            if src == "synthetic":
                print(f"      relevant_ids: {item.get('relevant_knowledge_ids', [])}")
            else:
                print(f"      must_contain: {item.get('must_contain', [])[:3]}")

    print("=" * 70)
    n = len(items)

    # 输出汇总
    print()
    print("=" * 70)
    print(f"评估结果 (模型: {MODEL_NAME})")
    print("=" * 70)
    print(f"  总查询数: {n}")
    print()
    print(f"  Recall@1:  {recall_at[1]}/{n} = {recall_at[1]/n*100:.1f}%")
    print(f"  Recall@5:  {recall_at[5]}/{n} = {recall_at[5]/n*100:.1f}%")
    print(f"  Recall@10: {recall_at[10]}/{n} = {recall_at[10]/n*100:.1f}%")
    print(f"  MRR:       {rr_sum/n:.4f}")
    print()
    print(f"  按数据源细分 Recall@10:")
    for src in ["qa-bench", "synthetic"]:
        h = hits_by_source[src]
        t = total_by_source[src]
        if t > 0:
            print(f"    {src}: {h}/{t} = {h/t*100:.1f}%")

    print()
    print("=" * 70)
    print("✅ 评估完成")


if __name__ == "__main__":
    asyncio.run(main())
