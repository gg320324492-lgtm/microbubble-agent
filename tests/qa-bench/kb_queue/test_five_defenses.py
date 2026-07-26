from __future__ import annotations

import random

from . import save_to_kb
from .five_defenses import (
    defense_dedup,
    defense_human_review,
    defense_length,
    defense_sensitive_words,
    defense_llm_reject,
)

TEXT = (
    "这是一段足够长的安全知识内容，用于验证知识库自动入库防线的正常通过路径。"
    "内容包含完整背景、实验现象、分析过程和可复核结论，因此适合进入候选知识队列。"
)


def test_scenario_1_dedup_pass():
    passed, reason = defense_dedup("x", [1.0, 0.0], existing_embeddings=[[0.0, 1.0]])
    assert passed is True and reason is None


def test_scenario_2_dedup_reject():
    passed, reason = defense_dedup("x", [1.0, 0.0], existing_embeddings=[[1.0, 0.0]])
    assert passed is False and "重复" in reason


def test_scenario_3_length_too_short_reject():
    passed, reason = defense_length("短" * 10)
    assert passed is False and "超限" in reason


def test_scenario_4_length_too_long_reject():
    passed, reason = defense_length("长" * 4001)
    assert passed is False and "超限" in reason


def test_scenario_5_llm_judge_pass():
    passed, reason = defense_llm_reject(TEXT, lambda _: 0.9)
    assert passed is True and reason is None


def test_scenario_6_llm_judge_reject():
    passed, reason = defense_llm_reject(TEXT, lambda _: 0.2)
    assert passed is False and "score" in reason

    saved: list[str] = []
    result = save_to_kb(
        TEXT + " 我不知道",
        llm_judge_fn=lambda _: 1.0,
        saver=saved.append,
    )
    assert result["saved"] is False and result["defense"] == "llm_reject"
    assert saved == []


def test_scenario_7_sensitive_word_reject():
    passed, reason = defense_sensitive_words(TEXT + " TODO")
    assert passed is False and "TODO" in reason


def test_scenario_8_sensitive_word_pass():
    passed, reason = defense_sensitive_words(TEXT, blacklist=["绝不匹配"])
    assert passed is True and reason is None


def test_scenario_9_human_review_trigger():
    reviewed: list[str] = []
    passed, reason = defense_human_review(
        TEXT, sample_rate=1.0, rng=random.Random(1), review_sink=reviewed.append
    )
    assert passed is True and "抽检" in reason and reviewed == [TEXT]


def test_scenario_10_human_review_no_trigger():
    reviewed: list[str] = []
    passed, reason = defense_human_review(
        TEXT, sample_rate=0.0, rng=random.Random(1), review_sink=reviewed.append
    )
    assert passed is True and reason is None and reviewed == []
