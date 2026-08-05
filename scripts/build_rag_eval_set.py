#!/usr/bin/env python3
"""
build_rag_eval_set.py — 从 qa-bench agent 评测集生成 RAG 评测集候选.

派工 brief W-N-RAG +1:
- 严禁 LLM 真标 (派工 brief 严禁)
- 严禁扩 schema (relevant_knowledge_ids 默认空, 人工审后填)
- 仅做格式迁移 + 抽取 question 字段

用法:
    python scripts/build_rag_eval_set.py --from-qa-bench \\
        --input tests/qa-bench/questions.jsonl \\
        --output tests/rag_eval/questions.jsonl.new

W73 铁律守恒:
- 不引入 LLM 调用 (派工 brief 严禁)
- 不引入外部依赖 (仅标准库)
- 0 production code 改动 (本脚本在 scripts/ 范畴)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCHEMA_TEMPLATE = {
    "qid": "",
    "question": "",
    "relevant_knowledge_ids": [],
    "key_facts": [],
}


def migrate_qa_bench(input_path: Path, output_path: Path, limit: int | None = None) -> int:
    """从 qa-bench JSONL 读取, 转换为 RAG eval schema, 写到 output.

    Returns: 写入行数.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with input_path.open("r", encoding="utf-8") as fin, output_path.open("w", encoding="utf-8") as fout:
        for line_idx, raw_line in enumerate(fin, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"[skip] line {line_idx}: invalid JSON", file=sys.stderr)
                continue

            question = obj.get("question")
            if not question or not isinstance(question, str):
                print(f"[skip] line {line_idx}: missing question", file=sys.stderr)
                continue

            qid = f"rag-{line_idx:03d}"
            new_obj = {
                "qid": qid,
                "question": question,
                "relevant_knowledge_ids": [],  # 派工 brief: 严禁 LLM 真标, 留人工审
                "key_facts": [],  # 同上, 留 LLM-as-judge 后续
            }
            fout.write(json.dumps(new_obj, ensure_ascii=False) + "\n")
            written += 1
            if limit is not None and written >= limit:
                break
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate RAG eval questions from qa-bench")
    parser.add_argument("--from-qa-bench", action="store_true", required=True,
                        help="Migrate from qa-bench JSONL to rag_eval JSONL")
    parser.add_argument("--input", required=True, help="Path to source qa-bench JSONL")
    parser.add_argument("--output", required=True, help="Path to target rag_eval JSONL (will be created)")
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of rows to migrate")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[error] input not found: {input_path}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    written = migrate_qa_bench(input_path, output_path, limit=args.limit)
    print(f"[ok] migrated {written} lines from {input_path} to {output_path}")
    print(f"[next] 人工审 relevant_knowledge_ids 字段后, mv {output_path} 到 tests/rag_eval/questions.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
