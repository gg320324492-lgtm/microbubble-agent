"""构造 A/B 评估集 (qa-bench + 合成 query)

逻辑:
  1. 读 tests/qa-bench/questions.jsonl + questions_500.jsonl
  2. 过滤 search/knowledge 类问题 (必须有 must_contain 关键词)
  3. 补充: 从 knowledge 表抽取合成 query (用标题 + content 截短, ground truth = knowledge.id)
  4. 输出 eval_set.jsonl: [{question, relevant_knowledge_ids, must_contain, ...}, ...]

评估指标:
  - recall@K: must_contain 关键词 (或 relevant_knowledge_ids) 在 top-K 检索结果中出现的比例
  - MRR: 第一个相关文档的排名倒数均值
"""
import json
import os
import random
from pathlib import Path

QA_BENCH_DIR = Path("tests/qa-bench")
OUT = Path("data/eval/eval_set.jsonl")


def collect_search_questions():
    """从 qa-bench 收集 search/knowledge 类问题"""
    eval_items = []
    seen_questions = set()

    for fname in ["questions.jsonl", "questions_500.jsonl"]:
        fpath = QA_BENCH_DIR / fname
        if not fpath.exists():
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    q = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # 只保留 search/knowledge 类
                category = q.get("category", "")
                intent = q.get("expect", {}).get("intent", "")
                must_contain = q.get("expect", {}).get("must_contain", [])

                # 筛选: category=knowledge 或 intent 包含 search
                is_relevant = (
                    category == "knowledge"
                    or "search" in intent.lower()
                )
                if not is_relevant or not must_contain:
                    continue

                question = q.get("question", "").strip()
                if not question or question in seen_questions:
                    continue
                seen_questions.add(question)

                eval_items.append({
                    "source": "qa-bench",
                    "id": q.get("id", ""),
                    "category": category,
                    "intent": intent,
                    "question": question,
                    "must_contain": must_contain,
                    "relevant_knowledge_ids": [],  # qa-bench 没标具体 ID
                })

    return eval_items


def collect_synthetic_queries():
    """从 knowledge 表构造合成 query (供 A/B 评估)

    策略:
      - 对每条 knowledge, 从 title 或 content 截短造一个 query
      - ground truth: 该 knowledge 的 ID (relevant_knowledge_ids = [id])
      - 抽 25-30 条 (随机种子固定, 可复现)
    """
    import asyncio
    import sys
    sys.path.insert(0, "/app")

    # 直接通过 docker exec 调用? 不行, 要在 app 容器内跑
    # 改用环境变量查询 PG
    async def _run():
        from app.core.database import async_session
        from sqlalchemy import select, text
        from app.models.knowledge import Knowledge

        async with async_session() as db:
            # 抽 30 条有 title 的 knowledge
            result = await db.execute(
                select(Knowledge.id, Knowledge.title, Knowledge.summary, Knowledge.category)
                .where(Knowledge.title.isnot(None))
                .where(Knowledge.embedding.isnot(None))  # 只用已嵌入的
                .order_by(Knowledge.id)
                .limit(200)
            )
            rows = result.fetchall()
        return rows

    # 直接调用 (脚本在容器内被 docker exec 跑)
    rows = asyncio.run(_run())

    # 随机抽 30 条 (固定种子)
    random.seed(42)
    sample = random.sample(rows, min(30, len(rows)))

    items = []
    for kid, title, summary, category in sample:
        # query 策略: 用 title 作为 query (短, 检索性强)
        # 如果 title 太短, 用 summary 前 30 字
        if title and len(title.strip()) >= 6:
            query = title.strip()
        elif summary:
            query = summary.strip()[:30]
        else:
            continue

        # must_contain: 从 title 提取 2-3 个关键词
        # 简化: 把 title 拆词后取名词
        import re
        # 中文按字符长度拆分 (每 2-4 字一组)
        words = re.findall(r"[一-鿿]+|[A-Za-z]+", title or "")
        keywords = [w for w in words if 2 <= len(w) <= 10][:3]
        if not keywords and summary:
            words = re.findall(r"[一-鿿]+|[A-Za-z]+", summary[:50])
            keywords = [w for w in words if 2 <= len(w) <= 10][:3]
        if not keywords:
            continue

        items.append({
            "source": "synthetic",
            "id": f"S{kid}",
            "category": category or "knowledge",
            "intent": "search_info",
            "question": query,
            "must_contain": keywords,
            "relevant_knowledge_ids": [kid],
        })

    return items


def main():
    items = []
    items.extend(collect_search_questions())
    items.extend(collect_synthetic_queries())

    print(f"qabench: {sum(1 for x in items if x['source'] == 'qa-bench')} 条")
    print(f"合成: {sum(1 for x in items if x['source'] == 'synthetic')} 条")
    print(f"总计: {len(items)} 条")
    print()

    # 按 category 分类统计
    from collections import Counter
    cats = Counter(item["category"] for item in items)
    print("分类统计:")
    for cat, cnt in cats.most_common():
        print(f"  {cat}: {cnt}")
    print()

    # 写输出
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"评估集写入: {OUT}")
    print()

    # 打印前 10 条样本
    print("=" * 60)
    print("样本 (前 10 条):")
    print("=" * 60)
    for item in items[:10]:
        print(f"\n[{item['id']}] source={item['source']} [{item['category']}]")
        print(f"  Q: {item['question']}")
        print(f"  must_contain: {item['must_contain']}")
        if item.get("relevant_knowledge_ids"):
            print(f"  relevant_ids: {item['relevant_knowledge_ids']}")


if __name__ == "__main__":
    main()
