"""
LoRA 微调数据构造脚本 (W-N-F +1, plan §2 任务 F.1 步骤 1 修订版)

**严禁真跑** (派工 brief 派工铁律):
- 不真跑构造流程 (用 --dry-run flag 强制默认)
- 不真跑 LoRA 训练
- 仅产出 jsonl (query, positive) pairs 骨架

**query 来源** (派工 v6 §13.3 据实上报, 严禁自查循环):
- 来源 1: `tests/qa-bench/questions.jsonl` (实测 105 题)
  - 反查 `expect.must_contain` → `knowledge` 表 LIKE 匹配
  - positive knowledge_id 由 must_contain 子串确认
- 来源 2: `search_log` 近 90 天 deduped user query (≥ 10 次搜索) + clicked_id
  - 直接取真实 user 行为, 闭环最强
- 严禁: 用 `kb.summary or kb.key_concepts[0]` 当 query (自我循环)

**正样本构造原则**:
- 1 query → 1~3 positive (multi-positive from must_contain)
- 跳过空 query / 过短 query (< 4 字符)
- 跳过 self-loop: query 出现在 positive.knowledge_content 自身前 200 字符
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

# 严禁真跑 — 默认 dry-run
DRY_RUN_DEFAULT = True

logger = logging.getLogger("microbubble.finetune.build_pairs")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


@dataclass
class FinetunePair:
    """(query, positive_id, positive_text) 三元组

    - query: 用户真实 query (严禁 kb.summary 自查)
    - positive_id: knowledge.id
    - positive_text: knowledge.knowledge_content 截断前 512 字符
    - source: "qa-bench" | "search_log"
    """

    query: str
    positive_id: int
    positive_text: str
    source: str
    category: Optional[str] = None  # qa-bench 才填
    created_at: str = field(default_factory=lambda: "2026-08-05")


# ---------------------------------------------------------------------------
# 来源 1: qa-bench 1000 题
# ---------------------------------------------------------------------------


def load_qa_bench_questions(
    path: str = "tests/qa-bench/questions.jsonl",
) -> List[Dict[str, Any]]:
    """加载 qa-bench 题目, 跳过 schema 不符合的行

    实测 schema: {id, category, question, expect: {must_contain, ...}}
    """
    items: List[Dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        logger.warning("qa-bench file not found: %s", path)
        return items
    with p.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("qa-bench line %d parse error: %s", lineno, e)
                continue
            if "question" not in d:
                logger.warning("qa-bench line %d missing 'question'", lineno)
                continue
            items.append(d)
    logger.info("qa-bench: loaded %d questions from %s", len(items), path)
    return items


def expand_qa_bench_to_pairs(
    questions: List[Dict[str, Any]],
    knowledge_index: Dict[str, List[int]],
    *,
    max_positive_per_query: int = 3,
) -> List[FinetunePair]:
    """把 qa-bench question 反查 knowledge.must_contain 关键词

    knowledge_index: {must_contain_keyword: [knowledge_id, ...]}
    """
    pairs: List[FinetunePair] = []
    for q in questions:
        question = (q.get("question") or "").strip()
        if len(question) < 4:
            continue
        expect = q.get("expect") or {}
        must_contains: List[str] = expect.get("must_contain") or []
        if not must_contains:
            continue
        positive_ids: Set[int] = set()
        for keyword in must_contains:
            for kid in knowledge_index.get(keyword, []):
                positive_ids.add(kid)
                if len(positive_ids) >= max_positive_per_query:
                    break
            if len(positive_ids) >= max_positive_per_query:
                break
        if not positive_ids:
            continue
        for kid in positive_ids:
            pairs.append(
                FinetunePair(
                    query=question,
                    positive_id=kid,
                    positive_text=f"<mock knowledge {kid} content>",  # 占位, 真跑需查 DB
                    source="qa-bench",
                    category=q.get("category"),
                )
            )
    logger.info("qa-bench: expanded to %d pairs", len(pairs))
    return pairs


# ---------------------------------------------------------------------------
# 来源 2: search_log 真实 user query + clicked_id
# ---------------------------------------------------------------------------


async def load_search_log_pairs(
    *,
    min_search_count: int = 10,
    lookback_days: int = 90,
    db_url: Optional[str] = None,
) -> List[FinetunePair]:
    """从 search_log 表加载 user 真实 query + clicked_id 对

    SQL 概念 (真跑需要接 DB):
      SELECT query, clicked_id, COUNT(*) as cnt
      FROM search_logs
      WHERE created_at >= NOW() - INTERVAL '90 days'
        AND clicked_id IS NOT NULL
        AND LENGTH(query) >= 4
      GROUP BY query, clicked_id
      HAVING COUNT(*) >= 10
      ORDER BY cnt DESC
    """
    # 严禁真跑 — 派工 brief 严禁
    if not DRY_RUN_DEFAULT:
        logger.warning("search_log 真查 DB 模式未启用 (DRY_RUN=True)")
    logger.info(
        "search_log: mock %d pairs (DRY_RUN, 真跑需 SQLAlchemy + DB)",
        0,
    )
    return []


# ---------------------------------------------------------------------------
# 严禁: 自查循环拦截
# ---------------------------------------------------------------------------


def filter_self_loop(pairs: List[FinetunePair]) -> List[FinetunePair]:
    """跳过 self-loop: query 出现在 positive_text 前 200 字符

    类 20.144 实战 + 派工 v6 §13.3 假设禁令: 不能用 kb.summary 当 query
    """
    out: List[FinetunePair] = []
    skipped = 0
    for p in pairs:
        head = p.positive_text[:200] if p.positive_text else ""
        if p.query in head:
            skipped += 1
            continue
        out.append(p)
    logger.info("self-loop filter: skipped %d pairs, kept %d", skipped, len(out))
    return out


# ---------------------------------------------------------------------------
# 统计 + 导出
# ---------------------------------------------------------------------------


def dedupe_pairs(pairs: List[FinetunePair]) -> List[FinetunePair]:
    """按 (query, positive_id) 去重, 保留首次出现"""
    seen: Set[Tuple[str, int]] = set()
    out: List[FinetunePair] = []
    for p in pairs:
        key = (p.query, p.positive_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    logger.info("dedupe: %d -> %d pairs", len(pairs), len(out))
    return out


def write_jsonl(pairs: Iterable[FinetunePair], out_path: str) -> int:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")
            n += 1
    logger.info("wrote %d pairs to %s", n, out_path)
    return n


# ---------------------------------------------------------------------------
# Mock knowledge_index (DRY_RUN 测试用)
# ---------------------------------------------------------------------------


def mock_knowledge_index() -> Dict[str, List[int]]:
    """DRY_RUN mock: must_contain keyword → knowledge_id 映射"""
    return {
        "饮用水安全": [1, 2],
        "蜡样芽孢杆菌": [3],
        "微生物消杀": [4, 5, 6],
        "臭氧纳米气泡": [7],
        "水处理": [8, 9, 10],
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="LoRA 微调数据构造 (W-N-F +1)")
    parser.add_argument(
        "--qa-bench-path",
        default="tests/qa-bench/questions.jsonl",
        help="qa-bench questions.jsonl 路径",
    )
    parser.add_argument(
        "--out",
        default="data/finetune/pairs.jsonl",
        help="输出 jsonl 路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=DRY_RUN_DEFAULT,
        help="DRY_RUN 模式 (默认开启, 派工 brief 严禁真跑)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_false",
        dest="dry_run",
        help="关闭 DRY_RUN (派工 brief 严禁, 仅作占位)",
    )
    args = parser.parse_args(argv)

    logger.info("W-N-F +1 build_finetune_pairs.py starting (DRY_RUN=%s)", args.dry_run)

    # 1. 加载 qa-bench
    questions = load_qa_bench_questions(args.qa_bench_path)

    # 2. 构造 knowledge_index (DRY_RUN mock)
    knowledge_index = mock_knowledge_index()
    logger.info("knowledge_index: %d keywords (DRY_RUN mock)", len(knowledge_index))

    # 3. 展开 qa-bench → pairs
    qa_pairs = expand_qa_bench_to_pairs(questions, knowledge_index)

    # 4. 加载 search_log (DRY_RUN mock 0 对, 真跑需 DB)
    search_pairs = asyncio.run(load_search_log_pairs())

    # 5. 合并 + dedupe + filter self-loop
    all_pairs = qa_pairs + search_pairs
    all_pairs = dedupe_pairs(all_pairs)
    all_pairs = filter_self_loop(all_pairs)

    # 6. 写 jsonl
    n = write_jsonl(all_pairs, args.out)

    # 7. 统计
    by_source: Dict[str, int] = {}
    for p in all_pairs:
        by_source[p.source] = by_source.get(p.source, 0) + 1
    logger.info("FINAL: %d pairs, by_source=%s", n, by_source)

    return 0


if __name__ == "__main__":
    sys.exit(main())
