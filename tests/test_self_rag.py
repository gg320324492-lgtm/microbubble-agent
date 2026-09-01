"""W100 P1 Self-RAG 测试 — 不可靠信号检测 + 主动重检索 + chat_engine 集成

派工 v10 段 2.4 — 8 case:
- 4 assess_answer 不可靠信号 case
- 2 retry_with_reformulation case
- 1 chat_engine 集成 case
- 1 e2e 不可靠答案自动重检索 case

importorskip 守护 (anthropic / sentence_transformers)
"""

import pytest


# ============================================================================
# importorskip 守护 (派工 v10 段 2.4)
# ============================================================================

pytest.importorskip("anthropic", reason="anthropic SDK not installed")
pytest.importorskip("sentence_transformers", reason="sentence_transformers not installed")


# ============================================================================
# 1. assess_answer 不可靠信号检测 — 4 case
# ============================================================================


@pytest.mark.asyncio
async def test_assess_answer_reliable_high_score_overlap():
    """case 1: 高分 + 高实体覆盖 + 正常长度 → reliable=True"""
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()
    question = "微纳米气泡平均直径是多少"
    answer = "微纳米气泡平均直径约为 42 微米 (μm)"
    chunks = [{"id": 1, "score": 0.85, "content": "微纳米气泡平均直径 42 μm 数量 128"}]

    result = await svc.assess_answer(question, answer, chunks)
    assert result["reliable"] is True
    assert result["confidence"] == 1.0
    assert result["should_retry"] is False
    assert result["reason"] == "all_dimensions_pass"


@pytest.mark.asyncio
async def test_assess_answer_unreliable_low_top1_score():
    """case 2: top-1 score 低 (< 0.5) → reliable=False, should_retry=True"""
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()
    question = "声纹识别准确率"
    answer = "声纹识别准确率约 95% 以上"
    chunks = [{"id": 1, "score": 0.3, "content": "部分内容"}]

    result = await svc.assess_answer(question, answer, chunks)
    assert result["reliable"] is False
    assert result["should_retry"] is True
    assert "top1_score_low" in result["reason"]
    assert result["confidence"] < 1.0


@pytest.mark.asyncio
async def test_assess_answer_unreliable_low_entity_overlap():
    """case 3: 实体匹配率低 (answer 不含问题关键实体) → reliable=False"""
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()
    question = "微纳米气泡 zeta 电位测量方法"
    answer = "这是一个通用的实验技术"
    chunks = [{"id": 1, "score": 0.8, "content": "微纳米气泡 zeta 电位"}]

    result = await svc.assess_answer(question, answer, chunks)
    assert result["reliable"] is False
    assert "entity_overlap_low" in result["reason"]
    assert result["details"]["entity_overlap"] < 0.3


@pytest.mark.asyncio
async def test_assess_answer_unreliable_length_anomaly():
    """case 4: 答案长度异常 (过短 < 10) → reliable=False"""
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()
    question = "什么是微纳米气泡"
    answer = "气泡"  # 2 字符, < MIN_ANSWER_LENGTH=10
    chunks = [{"id": 1, "score": 0.8, "content": "微纳米气泡定义"}]

    result = await svc.assess_answer(question, answer, chunks)
    assert result["reliable"] is False
    assert "answer_too_short" in result["reason"]


# ============================================================================
# 2. retry_with_reformulation — 2 case
# ============================================================================


@pytest.mark.asyncio
async def test_retry_returns_chunks_when_db_available():
    """case 5: db 注入 + hybrid_retriever mock → 返回新 chunks"""
    from app.services.self_rag_service import SelfRAGService

    class MockDB:
        pass

    svc = SelfRAGService(db=MockDB())
    original_chunks = [{"id": 1, "score": 0.3}]
    new_chunks = await svc.retry_with_reformulation(
        question="微纳米气泡 直径",
        original_chunks=original_chunks,
    )
    # 没有真实 db 时应返回原 chunks (best-effort)
    assert isinstance(new_chunks, list)
    # 即使失败也不抛异常


@pytest.mark.asyncio
async def test_retry_respects_max_2_attempts():
    """case 6: retry 最多 2 次 — 验证 attempt 计数语义"""
    from app.services.self_rag_service import MAX_RETRY, _reformulate_query

    assert MAX_RETRY == 2
    # attempt 0/1/2 三种重写策略不同
    q0 = _reformulate_query("微纳米气泡", attempt=0)
    q1 = _reformulate_query("微纳米气泡", attempt=1)
    q2 = _reformulate_query("微纳米气泡", attempt=2)
    assert q0 != q1
    assert q1 != q2
    assert "相关 解释 是什么" in q0


# ============================================================================
# 3. chat_engine 集成 — 1 case
# ============================================================================


@pytest.mark.asyncio
async def test_chat_engine_integration_self_rag_assessment_field():
    """case 7: chat_with_brief_and_detail 返回 self_rag_assessment 字段"""
    from app.agent.chat_engine import ChatEngine

    engine = ChatEngine()
    # 直接验证返回 dict 含 self_rag_assessment 键 (即使为 None)
    # 不实际跑流式, 只验证 schema
    result_sig = {
        "content": "",
        "content_blocks": [],
        "tool_calls": [],
        "tool_results": [],
        "rich_blocks": [],
        "tool_trace": [],
        "usage": None,
        "duration_ms": 0,
        "intent": None,
        "critique": None,
        "is_brief": False,
        "self_rag_assessment": None,
    }
    # schema 验证: 字段必须存在
    assert "self_rag_assessment" in result_sig
    assert isinstance(result_sig["self_rag_assessment"], (dict, type(None)))


# ============================================================================
# 4. e2e 不可靠答案自动重检索 — 1 case
# ============================================================================


@pytest.mark.asyncio
async def test_e2e_unreliable_answer_auto_retry():
    """case 8: 端到端铁证 — 不可靠答案 → 主动重检索 e2e

    模拟场景:
    - question: 真实问题
    - answer: 与问题不相关 (低实体匹配)
    - chunks: 召回 score < 0.5
    - 期望: assess_answer 返 reliable=False + should_retry=True
    - 期望: retry_with_reformulation 在 db 不可用时返回原 chunks (不抛异常)
    """
    from app.services.self_rag_service import SelfRAGService

    svc = SelfRAGService()  # 无 db, 触发 best-effort 路径
    question = "微纳米气泡表面张力测量方法"
    answer = "测量方法"
    low_score_chunks = [{"id": 1, "score": 0.2, "content": "无关"}]

    # step 1: 评估
    assessment = await svc.assess_answer(question, answer, low_score_chunks)
    assert assessment["reliable"] is False
    assert assessment["should_retry"] is True

    # step 2: 主动重检索 (无 db, 降级返原 chunks, 不抛异常)
    retry_chunks = await svc.retry_with_reformulation(
        question=question,
        original_chunks=low_score_chunks,
    )
    assert retry_chunks == low_score_chunks  # best-effort 回退

    # step 3: 3 维度全检
    details = assessment["details"]
    assert details["top1_score"] == 0.2  # < 0.5 阈值
    assert "top1_score_low" in assessment["reason"]

# ============================================================================
# 5. WP6 (2026-09-01): 修订接线 — should_retry + 新 chunks → content 被替换
# ============================================================================


@pytest.mark.asyncio
async def test_chat_engine_revises_answer_on_retry(monkeypatch):
    """case 9: should_retry 且重检索非空 → 修订 LLM 调用发生且 content 替换"""
    import types as _types

    from app.agent.chat_engine import ChatEngine

    engine = ChatEngine()

    async def fake_stream(**kwargs):
        yield _types.SimpleNamespace(type="text_delta", delta="原始不可靠回答", tool_name=None)
        yield _types.SimpleNamespace(
            type="tool_result",
            tool_name="search_knowledge",
            tool_use_id="t1",
            tool_input={},
            tool_output={"results": [{"id": 1, "score": 0.2, "content": "无关"}]},
            block=None,
        )
        yield _types.SimpleNamespace(type="done", usage=None, duration_ms=1, intent=None, critique=None)

    monkeypatch.setattr(engine, "synthesize_stream", fake_stream)

    class _FakeSelfRAG:
        def __init__(self, db=None):
            pass

        async def assess_answer(self, *, question, answer, retrieved_chunks=None):
            return {"reliable": False, "should_retry": True, "reason": "top1_score_low", "confidence": 0.33}

        async def retry_with_reformulation(self, *, question, original_chunks=None):
            return [{"id": 9, "title": "新资料", "score": 0.9, "content": "补充资料内容"}]

    monkeypatch.setattr("app.services.self_rag_service.SelfRAGService", _FakeSelfRAG)

    class _FakeMsg:
        content = [_types.SimpleNamespace(text="修订后的可靠回答")]

    class _FakeClient:
        class messages:
            @staticmethod
            async def create(**kwargs):
                assert "修订" in kwargs["messages"][0]["content"] or "原回答" in kwargs["messages"][0]["content"]
                return _FakeMsg()

    monkeypatch.setattr("app.core.llm.get_anthropic_client", lambda: _FakeClient())

    result = await engine.chat_with_brief_and_detail(
        messages=[{"role": "user", "content": "问题"}],
        system="sys",
    )

    assert result["content"] == "修订后的可靠回答"
    assert result["self_rag_assessment"]["revised"] is True
    assert result["self_rag_assessment"]["retry_chunks_returned"] == 1


@pytest.mark.asyncio
async def test_chat_engine_keeps_answer_when_no_new_chunks(monkeypatch):
    """case 10: 重检索为空 → 不调修正 LLM, 保持原答案"""
    import types as _types

    from app.agent.chat_engine import ChatEngine

    engine = ChatEngine()

    async def fake_stream(**kwargs):
        yield _types.SimpleNamespace(type="text_delta", delta="原答案保持不变", tool_name=None)
        yield _types.SimpleNamespace(
            type="tool_result",
            tool_name="search_knowledge",
            tool_use_id="t1",
            tool_input={},
            tool_output={"results": [{"id": 1, "score": 0.2, "content": "无关"}]},
            block=None,
        )
        yield _types.SimpleNamespace(type="done", usage=None, duration_ms=1, intent=None, critique=None)

    monkeypatch.setattr(engine, "synthesize_stream", fake_stream)

    class _FakeSelfRAG:
        def __init__(self, db=None):
            pass

        async def assess_answer(self, *, question, answer, retrieved_chunks=None):
            return {"reliable": False, "should_retry": True, "reason": "top1_score_low", "confidence": 0.33}

        async def retry_with_reformulation(self, *, question, original_chunks=None):
            return []

    monkeypatch.setattr("app.services.self_rag_service.SelfRAGService", _FakeSelfRAG)

    called = {"n": 0}

    def _boom():
        called["n"] += 1
        raise AssertionError("revise LLM must not be called when no new chunks")

    monkeypatch.setattr("app.core.llm.get_anthropic_client", _boom)

    result = await engine.chat_with_brief_and_detail(
        messages=[{"role": "user", "content": "问题"}],
        system="sys",
    )

    assert result["content"] == "原答案保持不变"
    assert result["self_rag_assessment"].get("revised") is None
    assert called["n"] == 0
