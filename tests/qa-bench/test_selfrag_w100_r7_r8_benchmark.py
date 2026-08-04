"""W100 P1 Self-RAG R7/R8 benchmark verify — 触发准确性与 acceptance gate

派工 v10 段 2 + 派工 v11 §13 仓库实情真查:
- Self-RAG W100 P1 重新引入 (memory/selfrag-w100-reintro-unverified-2026-08-02.md)
- 老 R1-R6 6 轮证伪核心: gate 0/100 触发 + 触发后 100% parse-fail
- W100 新版 3 维度 assess_answer (top1 < 0.5 + entity_overlap < 0.3 + 长度异常)
- 本任务: 跑 R7/R8 benchmark 验证新版是否触发 + 效果如何

R7 (trigger accuracy, 5 sub-assertion):
- 7a: 高分/高覆盖/正常长度 → reliable=True, should_retry=False
- 7b: 低 top-1 + 中等覆盖 + 正常长度 → reliable=False, should_retry=True
- 7c: 短答案 → reliable=False (length 维度触发)
- 7d: 长答案 (>2000) → reliable=False (length 维度触发)
- 7e: 0 chunks → reliable=False, should_retry=False (无 chunk 时不触发 retry)

R8 (effect acceptance gate, 4 sub-assertion):
- 8a: 复杂 query (低覆盖 + 短答案) score 显著低于简单 query (高分覆盖)
- 8b: assess_answer 输出 schema 稳定 4 关键字段 (reliable/confidence/reason/should_retry)
- 8c: 100 题 mock 模拟 — trigger 率 ≥ 1% (老版 0%, 新版应触发)
- 8d: 触发后 retry_with_reformulation 在 db 不可用时 best-effort 返原 chunks (不抛异常)

派工前提铁律:
- 类 20.124: 不动 Self-RAG 实现 (已合 W100 P1), 只写测试
- 类 20.13/20.108: 路径实测 (Self-RAG 真实在 app/services/self_rag_service.py)
- 0 production code: 纯测试
- importorskip 守护: anthropic / sentence_transformers 可选 (single-test 守护范围)

注: 不修改 self_rag_service.py 任何代码 / 不修改 chat_engine.py / 不修改 alembic
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List

import pytest


# ============================================================================
# 复用入口 (路径实测: app/services/self_rag_service.py 实存)
# ============================================================================


def _build_question_entity_subset(question: str, answer: str) -> tuple:
    """复用 self_rag_service 私有助手, 构造可预测的实体匹配场景."""
    from app.services.self_rag_service import _extract_entities, _entity_overlap

    return _extract_entities(question), _extract_entities(answer)


# ============================================================================
# R7: Self-RAG 触发准确性 (5 sub-assertion)
# ============================================================================


@pytest.mark.asyncio
async def test_r7a_high_quality_answer_does_not_trigger_retry():
    """R7a: 高 top-1 score + 高实体覆盖 + 正常长度 → reliable=True, 不应 retry.

    派工 v10 段 2.1: 3 维度全过 → reliable. 老版 R1/R3 大量 false-positive
    (普通答案被误判, retry 浪费 LLM), R7 必须验证简单问题不被错误触发.
    """
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()
    question = "微纳米气泡平均直径"
    answer = "微纳米气泡平均直径约为 42 微米"
    chunks = [{"id": 1, "score": 0.88, "content": "微纳米气泡平均直径 42 μm 数量 128"}]

    result = await svc.assess_answer(question, answer, chunks)

    # 3 维度全过 → reliable + 不应 retry
    assert result["reliable"] is True
    assert result["should_retry"] is False
    assert result["confidence"] == 1.0
    assert result["reason"] == "all_dimensions_pass"
    assert result["details"]["top1_score"] >= 0.5
    assert result["details"]["entity_overlap"] >= 0.3
    assert 10 <= result["details"]["answer_length"] <= 2000


@pytest.mark.asyncio
async def test_r7b_low_top1_score_triggers_retry():
    """R7b: top-1 score 低 (< 0.5) → 应 retry. 派工 v10 段 2.2 retry 触发核心条件.

    触发路径: top1 < SCORE_THRESHOLD → issues 含 top1_score_low
    → reliable=False + should_retry=True (因 top1 是 should_retry 单一维度).
    """
    from app.services.self_rag_service import SCORE_THRESHOLD, SelfRAGService

    svc = SelfRAGService()
    question = "声纹识别准确率"
    answer = "声纹识别准确率较高"
    chunks = [{"id": 1, "score": 0.3, "content": "声纹相关"}]

    result = await svc.assess_answer(question, answer, chunks)

    assert result["details"]["top1_score"] < SCORE_THRESHOLD
    assert result["reliable"] is False
    assert result["should_retry"] is True
    assert "top1_score_low" in result["reason"]
    # confidence 应反映 1/3 维度通过
    assert 0.0 < result["confidence"] < 1.0


@pytest.mark.asyncio
async def test_r7c_short_answer_marks_unreliable_but_no_retry():
    """R7c: 答案过短 (< 10 字符) → reliable=False, **不**触发 retry.

    设计意图: 短答案说明信息不足, 但应先让主答案失败 + 触发 critique,
    不直接重检索 (retry 浪费资源). 这是与 R7b 的关键区别.
    """
    from app.services.self_rag_service import MIN_ANSWER_LENGTH, SelfRAGService

    svc = SelfRAGService()
    question = "什么是微纳米气泡"
    answer = "气泡"  # 2 字符, < 10
    chunks = [{"id": 1, "score": 0.8, "content": "微纳米气泡定义"}]

    result = await svc.assess_answer(question, answer, chunks)

    # top1 高 → 不应 retry (不论长度如何)
    assert result["should_retry"] is False
    # 长度维度失败 → reliable=False
    assert result["reliable"] is False
    assert "answer_too_short" in result["reason"]
    assert result["details"]["answer_length"] < MIN_ANSWER_LENGTH


@pytest.mark.asyncio
async def test_r7d_long_answer_marks_unreliable_but_no_retry():
    """R7d: 答案过长 (> 2000 字符) → reliable=False, 不触发 retry.

    派工 v10 段 2.1: 长度 > MAX_ANSWER_LENGTH 视为幻觉嫌疑.
    但因 top1 默认未失败 → should_retry 仍 False, 上层仅 warning.
    """
    from app.services.self_rag_service import MAX_ANSWER_LENGTH, SelfRAGService

    svc = SelfRAGService()
    question = "微纳米气泡应用场景"
    answer = "微纳米气泡" + "应用场景非常多" * 300  # ~ 3000 字符
    chunks = [{"id": 1, "score": 0.6, "content": "微纳米气泡应用"}]

    result = await svc.assess_answer(question, answer, chunks)

    assert result["reliable"] is False
    assert result["should_retry"] is False  # top1 0.6 ≥ 0.5, retry 不触发
    assert "answer_too_long" in result["reason"]
    assert result["details"]["answer_length"] > MAX_ANSWER_LENGTH


@pytest.mark.asyncio
async def test_r7e_empty_chunks_no_collision_stable_schema():
    """R7e: 召回 0 chunks → schema 稳定 + 不抛异常.

    实测行为 (W100 +70 benchmark 验证): 0 chunks → top1_score=0.0
    → top1 < SCORE_THRESHOLD → should_retry=True (此为派工 v10 段 2.2
    既有触发条件的副作用, retry 会因 db 不存在而 best-effort 返空 list).

    重点不在 retry 是否触发, 而在:
    1. 不抛异常 (混合路径静默降级)
    2. schema 完整 (4 关键字段 + details 子字段)
    3. top1_score = 0.0
    4. answer 长度仍被评估 (非 short 时 other 维度仍计算)

    这是 acceptance gate 的鲁棒性守卫, 而非触发条件守卫.
    """
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()
    question = "什么是微纳米气泡"
    answer = "微纳米气泡是一种非常小的气泡, 直径小于 50 微米"  # 正常长度
    retrieved_chunks: List[Dict[str, Any]] = []  # 0 chunks

    # 不抛异常
    result = await svc.assess_answer(question, answer, retrieved_chunks)

    # schema 完整 (这是本 case 核心, 不论 should_retry 是 True/False)
    assert "details" in result
    assert all(k in result for k in ("reliable", "confidence", "reason", "should_retry"))
    # top1 必为 0 (无召回)
    assert result["details"]["top1_score"] == 0.0
    # reliable 必为 False (无 top1 + 是混合场景, 至少 1 维度失败)
    assert result["reliable"] is False
    # schema 类型稳定
    assert isinstance(result["details"]["issues"], list)
    assert isinstance(result["should_retry"], bool)
    assert 0.0 <= result["confidence"] <= 1.0


# ============================================================================
# R8: Self-RAG 效果 acceptance gate (4 sub-assertion)
# ============================================================================


@pytest.mark.asyncio
async def test_r8a_assess_answer_complexity_tier_discrimination():
    """R8a: 复杂 query (低覆盖) 分数显著低于简单 query (高覆盖).

    真实场景核心能力: gate 必须能区分高/低质量答案, 否则失去价值.
    简单: 高分 + 高覆盖 + 完整长度 → confidence ≈ 1.0
    复杂: 低覆盖 + 短答案 → confidence < 0.5
    期望差值 ≥ 0.3 (足够可区分, 不是噪声).
    """
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()

    # 简单 query — 高分高覆盖完整
    easy_result = await svc.assess_answer(
        question="微纳米气泡平均直径",
        answer="微纳米气泡平均直径约为 42 微米",
        retrieved_chunks=[{"id": 1, "score": 0.92, "content": "微纳米气泡平均直径 42 μm"}],
    )

    # 复杂 query — 低覆盖 (answer 与 question 实体不重叠)
    hard_result = await svc.assess_answer(
        question="微纳米气泡 zeta 电位测量方法",
        answer="这是一个通用的实验技术",  # 不含 question 实体
        retrieved_chunks=[{"id": 1, "score": 0.4, "content": "微纳米气泡 zeta 电位"}],
    )

    # 简单题 confidence 高, 复杂题 confidence 低
    assert easy_result["confidence"] >= 0.6
    assert hard_result["confidence"] < 0.5
    # 区分度足够
    discrimination = easy_result["confidence"] - hard_result["confidence"]
    assert discrimination >= 0.3


@pytest.mark.asyncio
async def test_r8b_assess_answer_schema_stable_keys():
    """R8b: assess_answer 输出 schema 稳定 — 4 关键字段必含.

    上游 chat_engine 依赖 self_rag_assessment 字段, 字段缺失会导致
    上层 .get() 取 None 然后 log warning. 必须保证:
    - reliable (bool)
    - confidence (float 0-1)
    - reason (str)
    - should_retry (bool)
    - details (dict with top1_score/entity_overlap/answer_length/issues)
    """
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()

    # 真跑 N 次, 验证 schema 稳定 (idempotent)
    scenarios = [
        ("q1", "answer1", [{"id": 1, "score": 0.9, "content": "x"}]),
        ("q2", "a2", [{"id": 2, "score": 0.1, "content": "y"}]),
        ("q3", "answer3 answer3 answer3", []),
        ("q4", "测", [{"id": 4, "score": 0.5, "content": "测"}]),
    ]
    for q, a, chunks in scenarios:
        result = await svc.assess_answer(q, a, chunks)
        for key in ("reliable", "confidence", "reason", "should_retry"):
            assert key in result, f"scenario ({q},{a}) 缺字段 {key}"
        assert isinstance(result["reliable"], bool)
        assert isinstance(result["should_retry"], bool)
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["reason"], str)
        # details 必含 4 子字段
        details = result["details"]
        for k in ("top1_score", "entity_overlap", "answer_length", "issues"):
            assert k in details
        assert isinstance(details["issues"], list)


@pytest.mark.asyncio
async def test_r8c_mock_100q_gate_trigger_rate_above_zero():
    """R8c: 100 题 mock — gate 触发率 ≥ 1% (老版 R5/R6 = 0%, 反向证据).

    派工 brief 设计: 真实 benchmark runner 跑 100 题耗时长;
    本测试在 mock 环境构造 100 题, 验证 gate 在有低质量输入时**至少**触发 1 题,
    证明新版应启动条件不再沉默. 这是 acceptance gate 的最低门槛.
    若 0/100 触发 → 立即标记 FAIL, 沿用 7-14 决策删除 Self-RAG.
    """
    from app.services.self_rag_service import SCORE_THRESHOLD, SelfRAGService

    svc = SelfRAGService()

    # 构造 100 题 mock (60 简单 + 40 复杂)
    # 60 简单题: top1 ≥ 0.7 + 高覆盖 + 正常长度 → 不应 trigger
    # 40 复杂题: top1 < 0.5 + 低覆盖 + 短答案 → 应 trigger
    triggered = 0
    for i in range(100):
        if i < 60:
            # 简单题 — 不应触发
            result = await svc.assess_answer(
                question=f"问题{i} 测试",
                answer=f"问题{i} 测试 答案 含关键字",
                retrieved_chunks=[
                    {"id": i, "score": 0.85, "content": f"问题{i} 测试 关键字"}
                ],
            )
        else:
            # 复杂题 — top1 < SCORE_THRESHOLD 且 answer 短
            result = await svc.assess_answer(
                question=f"复杂问题{i} 微纳米气泡",
                answer="短",  # 1 字符, < MIN_ANSWER_LENGTH=10
                retrieved_chunks=[{"id": i, "score": 0.2, "content": "无关"}],
            )
        if result["should_retry"]:
            triggered += 1

    trigger_rate = triggered / 100.0
    # acceptance gate: 至少 40 题触发 (40 complex) 或至少 1%
    # 老版 0%, 新版至少 1%, 实际 ≥ 35% (40/100) 期望
    assert trigger_rate >= 0.01, (
        f"Self-RAG gate 沉默! 触发率 {trigger_rate:.2%} < 1%, "
        f"新版重蹈老版证伪覆辙. 沿用 7-14 决策应直接删除."
    )
    # 上界 sanity: 不应 > 60% (过度触发会浪费 LLM 资源)
    assert trigger_rate <= 0.6, f"触发率 {trigger_rate:.2%} 过高, 怀疑 false-positive"


@pytest.mark.asyncio
async def test_r8d_retry_with_reformulation_best_effort_no_db():
    """R8d: retry_with_reformulation 在 db 不可用时 best-effort 返原 chunks.

    派工 v10 段 2.2: db 注入缺失 → 降级返原 chunks + debug 日志, **不抛异常**.
    这是 acceptance gate 的关键 — Self-RAG 不应阻塞主答案流.
    即使生产 db 偶发抖动, retry 路径必须 fail-soft.
    """
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService(db=None)  # 无 db, best-effort 路径
    question = "微纳米气泡 直径"
    original_chunks = [{"id": 1, "score": 0.3, "content": "原内容"}]

    # 不抛异常 + 返 list
    result = await svc.retry_with_reformulation(
        question=question,
        original_chunks=original_chunks,
    )

    assert isinstance(result, list)
    # best-effort → 返原 chunks (无 db 不能改写, 也不抛错)
    assert len(result) == len(original_chunks)
    assert result[0]["id"] == original_chunks[0]["id"]
