"""
build_finetune_pairs.py 单元测试 (W-N-F +1)

3 unit test 验证:
1. test_qa_bench_loading: qa-bench questions.jsonl 加载正确
2. test_qa_bench_expansion: must_contain → positive_id 反查正确
3. test_self_loop_filter: 自查循环拦截生效 (类 20.144 实战)

**严禁真跑构造** (派工 brief 严禁), 仅测试 mock 数据流程
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# 添加 scripts/ 到 path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from build_finetune_pairs import (  # noqa: E402
    FinetunePair,
    dedupe_pairs,
    expand_qa_bench_to_pairs,
    filter_self_loop,
    load_qa_bench_questions,
    mock_knowledge_index,
    write_jsonl,
)


class TestQaBenchLoading:
    """测试 1: qa-bench 加载"""

    def test_load_real_qa_bench(self):
        """实测 tests/qa-bench/questions.jsonl 加载"""
        items = load_qa_bench_questions("tests/qa-bench/questions.jsonl")
        # 实测 105 题 (派工 brief 估 1000 偏差据实)
        assert len(items) > 0, "qa-bench 不应为空"
        for item in items:
            assert "question" in item, f"item {item.get('id')} 缺 question"
            assert "id" in item
            assert "category" in item

    def test_load_missing_file(self):
        """文件不存在不报错, 返回空 list"""
        items = load_qa_bench_questions("/nonexistent/questions.jsonl")
        assert items == []


class TestQaBenchExpansion:
    """测试 2: must_contain → positive_id 反查"""

    def test_expand_with_must_contain(self):
        """must_contain 关键词命中 mock knowledge_index"""
        questions = [
            {
                "id": "T1",
                "category": "test",
                "question": "研究饮用水的方向有哪些？",
                "expect": {"must_contain": ["饮用水安全", "微生物消杀"]},
            },
            {
                "id": "T2",
                "category": "test",
                "question": "臭氧纳米气泡应用？",
                "expect": {"must_contain": ["臭氧纳米气泡"]},
            },
        ]
        knowledge_index = mock_knowledge_index()
        pairs = expand_qa_bench_to_pairs(questions, knowledge_index)

        # T1: 饮用水安全=[1,2] + 微生物消杀=[4,5,6] = 5 个 (max=3 截断)
        # T2: 臭氧纳米气泡=[7] = 1 个
        assert len(pairs) >= 4  # 至少 4 个
        assert all(p.source == "qa-bench" for p in pairs)
        assert any(p.query == "研究饮用水的方向有哪些？" for p in pairs)
        assert any(p.query == "臭氧纳米气泡应用？" for p in pairs)

    def test_skip_short_query(self):
        """跳过 < 4 字符 query (按字符数)"""
        questions = [
            {"id": "T3", "category": "test", "question": "啊", "expect": {"must_contain": ["饮用水安全"]}},
            {"id": "T4", "category": "test", "question": "   ", "expect": {"must_contain": ["饮用水安全"]}},  # 3 个空白
            {"id": "T5", "category": "test", "question": "臭氧", "expect": {"must_contain": ["臭氧纳米气泡"]}},  # 2 字符
        ]
        pairs = expand_qa_bench_to_pairs(questions, mock_knowledge_index())
        # "啊" 1 字符, "   " 3 字符, "臭氧" 2 字符 → 全部跳过
        assert len(pairs) == 0

    def test_skip_no_must_contain(self):
        """无 must_contain 跳过"""
        questions = [
            {"id": "T5", "category": "test", "question": "测试问题", "expect": {}},
        ]
        pairs = expand_qa_bench_to_pairs(questions, mock_knowledge_index())
        assert len(pairs) == 0


class TestSelfLoopFilter:
    """测试 3: 自查循环拦截 (类 20.144 实战)"""

    def test_self_loop_skipped(self):
        """query 出现在 positive_text 前 200 字符 → 跳过"""
        pairs = [
            FinetunePair(
                query="饮用水安全",
                positive_id=1,
                positive_text="饮用水安全是研究重要方向, ...",  # self-loop
                source="qa-bench",
            ),
            FinetunePair(
                query="臭氧纳米气泡",
                positive_id=2,
                positive_text="水处理技术应用, ...",  # non-self-loop
                source="qa-bench",
            ),
        ]
        filtered = filter_self_loop(pairs)
        assert len(filtered) == 1
        assert filtered[0].positive_id == 2

    def test_dedupe_same_pair(self):
        """(query, positive_id) 重复 → 去重"""
        pairs = [
            FinetunePair(query="Q", positive_id=1, positive_text="T1", source="qa-bench"),
            FinetunePair(query="Q", positive_id=1, positive_text="T1-dup", source="qa-bench"),
            FinetunePair(query="Q", positive_id=2, positive_text="T2", source="qa-bench"),
        ]
        deduped = dedupe_pairs(pairs)
        assert len(deduped) == 2

    def test_write_jsonl(self):
        """写 jsonl 格式正确"""
        pairs = [
            FinetunePair(query="Q1", positive_id=1, positive_text="T1", source="qa-bench"),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "pairs.jsonl"
            n = write_jsonl(pairs, str(out))
            assert n == 1
            with out.open() as f:
                line = f.readline()
                d = json.loads(line)
                assert d["query"] == "Q1"
                assert d["positive_id"] == 1
                assert d["source"] == "qa-bench"
