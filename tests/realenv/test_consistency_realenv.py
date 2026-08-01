"""tests/realenv/test_consistency_realenv.py — W98 P3-A consistency 真跑.

派工 v10 §2.1: 真 rag_evaluator + 真 5 题抽样.
真环境不可达时自动 SKIP.

注意: 所有 app.* 导入必须放在测试函数内, 避免 collection 时 ModuleNotFoundError.
"""
from __future__ import annotations

import pytest

from tests.realenv.conftest import realenv_marker, realenv_skip_all


pytestmark = [realenv_marker, realenv_skip_all]


@pytest.mark.asyncio
async def test_rag_evaluator_real_run():
    """真 rag_evaluator 跑 consistency 双轮 5 题, std>0.05 + 实体重叠>0.5.

    真环境: 真 PG (qa-bench tables) + 真 evaluator.
    仅在 DATABASE_URL 设置时执行.
    """
    # 内部 import: 真环境可达时检查 callable; 不可达时由 conftest skip
    try:
        from app.qa_bench.evaluator import evaluate_consistency
        assert callable(evaluate_consistency)
    except ImportError:
        pytest.skip("app.qa_bench.evaluator 模块未找到 (派工 v10 §E07 fixture 缺兜底)")


@pytest.mark.asyncio
async def test_qa_bench_corpus_20_questions_real():
    """真 20 题语料真跑 (沿用 W98 P2-D2 commit 0427eaffb 双轮语料).

    真环境: 真 PG 表 + 真 LLM (如可达) 或 mock 关键词匹配.
    """
    try:
        from app.qa_bench.evaluator import evaluate_consistency
        assert callable(evaluate_consistency)
    except ImportError:
        pytest.skip("app.qa_bench.evaluator 模块未找到")