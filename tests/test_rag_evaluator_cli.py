"""test_rag_evaluator_cli.py — CHAT-P0-D W98 +0 评估框架激活测试

覆盖 (D1 CLI + 抽样钩子):
1. get_eval_sample_rate: env 解析 (默认 0 / 合法值 / 非法值归 0)
2. _eval_sample_hit: rate<=0 恒 False, rate>=1 恒 True, 概率命中走 monkeypatch
3. maybe_evaluate_async: 不命中 no-op (不触碰 DB / LLM)
4. maybe_evaluate_async: 命中 → 读消息 → 4 指标 → save_evaluation 落库
   (monkeypatch async_session + evaluator, 不真连 DB / 不真调 LLM)
5. _build_context_from_tool_trace: tool_trace → context 文本 (tool_use 输入 + 结果)
6. _cli_main 参数解析: --skip-llm 短路 (只汇总不调 LLM)
7. _cli_collect_targets: 按 session 收集 assistant 回答 (mock db)

运行: SKIP_DB_SETUP=1 pytest tests/test_rag_evaluator_cli.py -q
"""
import asyncio
import os

import pytest

from app.services import rag_evaluator as re_mod


# === 1. get_eval_sample_rate ===

@pytest.mark.parametrize("env_value,expected", [
    ("", 0.0),          # 缺省
    ("0", 0.0),         # 显式关闭
    ("0.05", 0.05),     # 5% 抽样
    ("1", 1.0),         # 全量
    ("abc", 0.0),       # 非法 → 归 0
    ("-1", 0.0),        # 负值 → 归 0
    ("1.5", 0.0),       # 超上限 → 归 0
])
def test_get_eval_sample_rate(env_value, expected, monkeypatch):
    re_mod._EVAL_SAMPLE_RATE = None
    monkeypatch.setenv("EVAL_SAMPLE_RATE", env_value)
    assert re_mod.get_eval_sample_rate() == expected
    re_mod._EVAL_SAMPLE_RATE = None


# === 2. _eval_sample_hit ===

def test_eval_sample_hit_off_and_full(monkeypatch):
    monkeypatch.setattr(re_mod, "_EVAL_SAMPLE_RATE", 0.0)
    assert re_mod._eval_sample_hit() is False   # rate<=0 恒不命中
    monkeypatch.setattr(re_mod, "_EVAL_SAMPLE_RATE", 1.0)
    assert re_mod._eval_sample_hit() is True    # rate>=1 恒命中


def test_eval_sample_hit_probabilistic(monkeypatch):
    monkeypatch.setattr(re_mod, "_EVAL_SAMPLE_RATE", 0.5)
    monkeypatch.setattr(re_mod, "random", __import__("random"))
    # monkeypatch random.random 固定返回值 → 命中判定确定
    calls = []

    class FakeRandom:
        def random(self):
            calls.append(1)
            return 0.4  # < 0.5 → 命中

    monkeypatch.setattr(re_mod, "random", FakeRandom())
    assert re_mod._eval_sample_hit() is True
    assert len(calls) == 1


# === 3. maybe_evaluate_async 不命中 = no-op (0 DB 访问) ===

@pytest.mark.asyncio
async def test_maybe_evaluate_async_miss_is_noop(monkeypatch):
    monkeypatch.setattr(re_mod, "_EVAL_SAMPLE_RATE", 0.0)
    touched = []

    async def _boom(*a, **k):
        touched.append(1)
        raise AssertionError("不命中时不得触碰任何 IO")

    monkeypatch.setattr(re_mod, "async_session", _boom)
    await re_mod.maybe_evaluate_async(user_id=1, session_id="s1", message_id=2)
    assert touched == [], "rate=0 时 maybe_evaluate_async 必须纯 no-op"


# === 4. maybe_evaluate_async 命中 → 评估链路 (mock session + evaluator) ===

@pytest.mark.asyncio
async def test_maybe_evaluate_async_hit_runs_evaluation(monkeypatch):
    monkeypatch.setattr(re_mod, "_EVAL_SAMPLE_RATE", 1.0)  # 恒命中

    saved = []
    metrics = {
        "faithfulness": 0.9, "answer_relevancy": 0.8,
        "context_precision": 0.7, "context_recall": 0.6, "overall": 0.75,
    }

    class FakeMsg:
        def __init__(self, mid, role, content, tool_trace, deleted=False):
            self.id = mid
            self.role = role
            self.content = content
            self.tool_trace = tool_trace
            self.is_deleted = deleted

    class FakeSession:
        def __init__(self, msgs):
            self.msgs = msgs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    async def fake_list_messages(db, user_id, session_id, **kw):
        return FakeSession  # 占位 (不调用)

    original_run_single_eval = re_mod._run_single_eval

    async def fake_run(db, user_id, session_id, message_id):
        saved.append((user_id, session_id, message_id))

        async def fake_list_messages_inner(db, user_id, session_id, **kw):
            return (
                [
                    FakeMsg(1, "user", "杨慈是研究什么的？", {}),
                    FakeMsg(2, "assistant", "杨慈研究方向为饮用水安全与微纳米气泡。", {}),
                ],
                False,
            )
        from app.services import chat_history_service as chat_svc
        monkeypatch.setattr(chat_svc, "list_messages", fake_list_messages_inner)

        class Eval:
            async def evaluate(self, query, answer, context):
                assert query == "杨慈是研究什么的？"
                assert answer == "杨慈研究方向为饮用水安全与微纳米气泡。"
                assert "杨慈" in context or context == query  # 无工具上下文 → query 兜底
                return metrics

            async def save_evaluation(self, db, query, answer, context, metrics):
                assert metrics == metrics
                saved.append("saved")

        monkeypatch.setattr(re_mod, "get_rag_evaluator", lambda: Eval())
        await original_run_single_eval(db, user_id, session_id, message_id)

    # async_session 是 _SessionFactoryProxy, __call__ 同步返回 async 上下文管理器
    def fake_async_session():
        return FakeSession([])

    # 注入 async_session 上下文管理器 + _run_single_eval 的真实现
    # 这里直接驱动 _run_single_eval (内部自建 session 的路径由 fake_async_session 覆盖)
    monkeypatch.setattr(re_mod, "async_session", fake_async_session)
    monkeypatch.setattr(re_mod, "_run_single_eval", fake_run)

    await re_mod.maybe_evaluate_async(user_id=7, session_id="s1", message_id=2)
    assert saved == [(7, "s1", 2), "saved"], f"评估链路必须完整执行: {saved}"


# === 4b. _run_single_eval 真实路径 (mock chat_svc.list_messages + evaluator) ===

@pytest.mark.asyncio
async def test_run_single_eval_full_path(monkeypatch):
    from app.services import chat_history_service as chat_svc

    class FakeMsg:
        def __init__(self, mid, role, content, tool_trace, deleted=False):
            self.id = mid
            self.role = role
            self.content = content
            self.tool_trace = tool_trace
            self.is_deleted = deleted

    msgs = [
        FakeMsg(1, "user", "什么是 zeta 电位？", {}),
        FakeMsg(2, "assistant", "zeta 电位是胶体表面的电位差。", {
            "trace": [
                {"type": "tool_use", "name": "search_knowledge", "input": {"query": "zeta 电位"}},
                {"type": "tool_result", "name": "search_knowledge", "result": {"hits": ["zeta 电位定义"]}},
            ],
        }),
    ]

    async def fake_list_messages(db, user_id, session_id, **kw):
        return msgs, False

    monkeypatch.setattr(chat_svc, "list_messages", fake_list_messages)

    saved = []
    metrics = {"faithfulness": 0.9, "answer_relevancy": 0.8,
               "context_precision": 0.7, "context_recall": 0.6}

    class Eval:
        async def evaluate(self, query, answer, context):
            assert query == "什么是 zeta 电位？"
            assert "zeta 电位" in context and "search_knowledge" in context
            return metrics

        async def save_evaluation(self, db, query, answer, context, metrics):
            saved.append((query, metrics))

    monkeypatch.setattr(re_mod, "get_rag_evaluator", lambda: Eval())

    await re_mod._run_single_eval(db=object(), user_id=1, session_id="s1", message_id=2)
    assert len(saved) == 1 and saved[0][0] == "什么是 zeta 电位？"


# === 4c. _run_single_eval 目标消息不存在 → 跳过 (不调 evaluator) ===

@pytest.mark.asyncio
async def test_run_single_eval_target_missing_skips(monkeypatch):
    from app.services import chat_history_service as chat_svc

    class FakeMsg:
        def __init__(self, mid, role, content):
            self.id = mid
            self.role = role
            self.content = content
            self.tool_trace = None
            self.is_deleted = False

    async def fake_list_messages(db, user_id, session_id, **kw):
        return [FakeMsg(1, "user", "hi"), FakeMsg(2, "assistant", "hello")], False

    monkeypatch.setattr(chat_svc, "list_messages", fake_list_messages)
    touched = []

    class Eval:
        async def evaluate(self, *a, **k):
            touched.append(1)
            return {}

    monkeypatch.setattr(re_mod, "get_rag_evaluator", lambda: Eval())

    await re_mod._run_single_eval(db=object(), user_id=1, session_id="s1", message_id=999)
    assert touched == [], "目标消息不存在必须跳过, 不调 LLM"


# === 5. _build_context_from_tool_trace ===

def test_build_context_from_tool_trace():
    trace = {
        "trace": [
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "微纳米气泡"}},
            {"type": "tool_result", "name": "search_knowledge",
             "result": {"hits": ["微纳米气泡尺寸检测方法"]}},
        ],
    }
    ctx = re_mod._build_context_from_tool_trace(trace)
    assert "search_knowledge" in ctx
    assert "微纳米气泡" in ctx
    assert re_mod._build_context_from_tool_trace(None) == ""
    assert re_mod._build_context_from_tool_trace({}) == ""
    assert re_mod._build_context_from_tool_trace({"trace": "not-a-list"}) == ""


# === 6. CLI: --skip-llm 短路 (只汇总, 不调 evaluator) ===

@pytest.mark.asyncio
async def test_cli_main_skip_llm_short_circuit(monkeypatch):
    class FakeRow:
        def __init__(self, **kw):
            self.faithfulness = kw["faithfulness"]
            self.answer_relevancy = kw["answer_relevancy"]
            self.context_precision = kw["context_precision"]
            self.context_recall = kw["context_recall"]

    class FakeResult:
        def __init__(self):
            self.value = FakeRow(faithfulness=0.8, answer_relevancy=0.7,
                                 context_precision=0.6, context_recall=0.5)
            self.scalar = lambda: 42  # 模拟 Result.scalar() 调用

        def one(self):
            return self.value

    class FakeDB:
        async def execute(self, stmt):
            return FakeResult()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    # async_session 是 _SessionFactoryProxy, __call__ 同步返回 async 上下文管理器
    def fake_async_session():
        return FakeDB()

    monkeypatch.setattr(re_mod, "async_session", fake_async_session)
    monkeypatch.setattr(re_mod, "get_rag_evaluator",
                        lambda: (_ for _ in ()).throw(AssertionError("skip-llm 不得调 evaluator")))
    rc = await re_mod._cli_main(["--skip-llm"])
    assert rc == 0


# === 7. _cli_collect_targets (mock db) ===

@pytest.mark.asyncio
async def test_cli_collect_targets_mock_db(monkeypatch):
    from sqlalchemy import select

    class FakeMsg:
        def __init__(self, mid, role, content, tool_trace, partial=False, deleted=False):
            self.id = mid
            self.role = role
            self.content = content
            self.tool_trace = tool_trace
            self.is_partial = partial
            self.is_deleted = deleted

    class FakeSessionRow:
        id = "s1"
        user_id = 3
        last_message_at = None

    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalar_one_or_none(self):
            return self._rows[0] if self._rows else None

        def scalars(self):
            return self

        def all(self):
            return self._rows

    msgs = [
        FakeMsg(1, "user", "q1", {}),
        FakeMsg(2, "assistant", "a1", None),
        FakeMsg(3, "assistant", "a2(partial)", None, partial=True),
        FakeMsg(4, "user", "q2", {}),
        FakeMsg(5, "assistant", "a2", {"trace": [{"type": "tool_result", "name": "t", "result": "r"}]}),
    ]

    class FakeDB:
        async def execute(self, stmt):
            stmt_str = str(stmt)
            if "chat_messages" in stmt_str:
                return FakeResult(msgs)
            return FakeResult([FakeSessionRow()])

    rows = await re_mod._cli_collect_targets(FakeDB(), type("Args", (), {
        "session_id": "s1", "limit": 20, "user_id": None,
    })())
    # 期望: 2 条 assistant (跳过 partial), 各自配最近 user 消息
    assert len(rows) == 2, f"期望 2 条, 实际 {len(rows)}"
    assert rows[0][2] == 2 and rows[0][3] == "q1"
    assert rows[1][2] == 5 and rows[1][3] == "q2"
    assert "r" in rows[1][5]  # tool_trace 构造 context


# === 8. 全量 import 冒烟 (0 errors) ===

def test_module_imports_smoke():
    import app.agent.micro_bubble_agent  # noqa: F401 — 钩子 import 必须可用
    assert callable(re_mod.maybe_evaluate_async)
    assert callable(re_mod.main)
    assert hasattr(re_mod, "__main__") or re_mod.__name__ == "app.services.rag_evaluator"


# === 9. P2-D2 W98 +7: consistency 双轮新接口 ===

def test_consistency_double_round_import():
    """新增 (P2-D2 W98 +7): RAGEvaluator 新增 evaluate_consistency_double_round 方法."""
    from app.services.rag_evaluator import RAGEvaluator
    assert hasattr(RAGEvaluator, "evaluate_consistency_double_round"), \
        "派工 v10 §2: 必须新增 evaluate_consistency_double_round 方法"
    # 静态方法 _compute_entity_overlap 也必新增
    assert hasattr(RAGEvaluator, "_compute_entity_overlap"), \
        "派工 v10 §2: 必须新增 _compute_entity_overlap 静态方法"


def test_consistency_runner_module_importable():
    """新增 (P2-D2 W98 +7): consistency_runner.py 可 import."""
    import sys
    from pathlib import Path
    qa_bench_dir = Path(__file__).parent / "qa-bench"
    if str(qa_bench_dir) not in sys.path:
        sys.path.insert(0, str(qa_bench_dir))
    import consistency_runner  # noqa: E402 — sys.path 注入
    assert callable(consistency_runner.run_consistency_double_round)
    assert callable(consistency_runner.load_corpus)
    assert hasattr(consistency_runner, "_MockEvaluator")
