"""上下文窗口按 token 预算裁剪 (2026-11-04 B 档)

替代原先「存 30 条 = 送 30 条」的按条数硬截断。实测依据:
- MiniMax /v1 中文增量斜率 ≈ 0.47 token/字符 (850字→602, 1700字→1002)，
  本模块按 0.6 估算，**必须保守** (宁可提前裁，不能超预算)；
- 单轮实测 prompt_tokens=7034 (system 11251 字符 + 32 个工具 schema)；
- 多轮工具调用实测最高 72847 —— 条数限制对这种量级完全无感。

关键回归: 窗口起点必须是「不含 tool_result 的 user 消息」。Anthropic 协议里
tool_result 装在 user 消息内，只判 role 挡不住孤儿 —— 产生它的 assistant
tool_use 被裁掉后，严格后端会直接 400 (2026-10-14 同型故障)。
"""
import ast
import pathlib

import pytest

from app.agent.context_budget import (
    REQUEST_OVERHEAD_TOKENS,
    TOOLS_SCHEMA_TOKENS,
    _has_tool_result,
    estimate_message_tokens,
    estimate_request_tokens,
    trim_to_budget,
)

REPO = pathlib.Path(__file__).resolve().parents[1]


def _turn(n: int, chars: int = 200):
    """造 n 轮 user/assistant 对话，每条约 chars 字符。"""
    out = []
    for i in range(n):
        out.append({"role": "user", "content": "问题%d：" % i + "纳米气泡" * (chars // 4)})
        out.append({"role": "assistant", "content": "回答%d：" % i + "微纳米气泡" * (chars // 5)})
    return out


# ---------- 估算 ----------


def test_estimate_is_conservative_vs_measurement():
    """估算值必须**不低于**实测 prompt_tokens —— 否则预算会溢出。

    实测锚点: system 11251 字符 + 单条 user + 32 个工具 = 7034 tokens (2026-11-04)。
    """
    est = estimate_request_tokens(
        [{"role": "user", "content": "我们组谁在做臭氧微纳米气泡研究？"}],
        system_chars=11251,
        with_tools=True,
    )
    assert est >= 7034, "估算 %d 低于实测 7034, 系数不够保守" % est


def test_estimate_without_tools_drops_schema_cost():
    with_t = estimate_request_tokens([{"role": "user", "content": "a"}], 0, True)
    no_t = estimate_request_tokens([{"role": "user", "content": "a"}], 0, False)
    assert with_t - no_t == TOOLS_SCHEMA_TOKENS


def test_estimate_counts_blocks_and_tool_calls():
    blocks = {"role": "assistant", "content": [
        {"type": "text", "text": "甲" * 100},
        {"type": "tool_use", "id": "tu_1", "name": "query_members",
         "input": {"research_area": "臭氧"}},
    ]}
    plain = {"role": "assistant", "content": "甲" * 100}
    assert estimate_message_tokens(blocks) > estimate_message_tokens(plain)

    tc = {"role": "assistant", "content": "x", "tool_calls": [{"id": "1", "name": "n"}]}
    assert estimate_message_tokens(tc) > estimate_message_tokens(
        {"role": "assistant", "content": "x"})


def test_estimate_tolerates_junk():
    assert estimate_message_tokens(None) == 0
    assert estimate_message_tokens("不是dict") == 0
    assert estimate_message_tokens({"role": "user"}) == pytest.approx(8, abs=1)


# ---------- 裁剪 ----------


def test_under_budget_returns_untouched():
    msgs = _turn(3)
    kept, dropped, _ = trim_to_budget(msgs, budget_tokens=60000, system_chars=1000)
    assert dropped == 0
    assert kept == msgs


def test_over_budget_keeps_newest_and_drops_oldest():
    msgs = _turn(40, chars=400)
    kept, dropped, est = trim_to_budget(msgs, budget_tokens=20000, system_chars=1000)
    assert dropped > 0
    assert kept[-1] == msgs[-1], "最新一条必须保留"
    assert len(kept) == len(msgs) - dropped
    assert est <= 25000, "裁剪后仍远超预算: %d" % est


def test_tiny_budget_still_keeps_current_turn():
    """预算再小也不能把用户当前这问丢掉 (min_keep 保证)。"""
    msgs = _turn(10)
    kept, dropped, _ = trim_to_budget(msgs, budget_tokens=10, system_chars=0)
    assert len(kept) >= 1
    assert kept[-1] == msgs[-1]


def test_empty_messages_safe():
    kept, dropped, est = trim_to_budget([], budget_tokens=60000)
    assert kept == [] and dropped == 0
    assert est == REQUEST_OVERHEAD_TOKENS + TOOLS_SCHEMA_TOKENS


def test_orphan_tool_result_never_becomes_window_start():
    """核心回归: 起点若是「带 tool_result 的 user 消息」必须继续往后挪。"""
    msgs = [
        {"role": "user", "content": "老问题"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_9", "name": "query_meetings", "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_9", "content": "会议数据..."}]},
        {"role": "assistant", "content": "基于工具结果的回答"},
        {"role": "user", "content": "新问题"},
    ]
    kept, dropped, _ = trim_to_budget(msgs, budget_tokens=120, system_chars=0, min_keep=2)
    assert kept, "不能裁空"
    assert not _has_tool_result(kept[0]), "窗口起点是孤儿 tool_result: %s" % kept[0]
    assert kept[0]["role"] == "user"


def test_leading_assistant_is_not_a_valid_start():
    msgs = [
        {"role": "user", "content": "甲" * 500},
        {"role": "assistant", "content": "乙" * 500},
        {"role": "user", "content": "丙"},
        {"role": "assistant", "content": "丁"},
    ]
    kept, _, _ = trim_to_budget(msgs, budget_tokens=700, system_chars=0, min_keep=1)
    assert kept[0]["role"] == "user"


def test_validity_beats_exact_budget():
    """切点对齐会**向前扩展**，因此结果可能略超预算 —— 这是有意的取舍。

    宁可多带几条，也不能交出一个起点是 assistant / 孤儿 tool_result 的请求
    (那种请求严格后端直接 400，省下的 token 换不来一次失败)。

    结构: 两个完整轮次, 每轮都是 user → assistant(tool_use) → user(tool_result)
    → assistant。预算只够最后一两条 ⇒ 朴素裁剪会落在 assistant 或 tool_result 上，
    正确行为是回扩到第二轮的 user 起点 (index 4)，既裁掉第一轮又保证合法。
    """
    msgs = [
        {"role": "user", "content": "第一轮问题" + "甲" * 2000},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "query_meetings", "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "乙" * 2000}]},
        {"role": "assistant", "content": "第一轮回答" + "丙" * 2000},
        {"role": "user", "content": "第二轮问题" + "丁" * 2000},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t2", "name": "query_members", "input": {}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t2", "content": "戊" * 2000}]},
        {"role": "assistant", "content": "第二轮回答" + "己" * 2000},
    ]
    kept, dropped, est = trim_to_budget(msgs, budget_tokens=3000, system_chars=0, min_keep=1)

    assert kept[0]["role"] == "user" and not _has_tool_result(kept[0]), (
        "窗口起点必须是干净的轮次边界: %s" % kept[0])
    assert dropped > 0, "应当裁掉第一轮的一部分, 否则没体现裁剪"
    assert kept[0] is msgs[4], "应回扩到第二轮的 user 起点 (index 4)"
    assert est > 3000, "本用例应体现扩展导致超预算 (合法性优先)"


def test_only_safe_start_at_index_zero_keeps_everything():
    """整段历史只有一个干净起点 (index 0) 时, 宁可全保留也不交出不合法请求。"""
    msgs = [
        {"role": "user", "content": "甲" * 2000},
        {"role": "assistant", "content": "乙" * 2000},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "丙" * 2000}]},
        {"role": "assistant", "content": "丁" * 2000},
    ]
    kept, dropped, _ = trim_to_budget(msgs, budget_tokens=1500, system_chars=0, min_keep=1)
    assert kept == msgs and dropped == 0


def test_align_lookback_is_bounded():
    """整段都是工具块、找不到干净起点时，不能无限向前扩展。"""
    msgs = [{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "t%d" % i, "content": "数据" * 50}]}
        for i in range(40)]
    kept, dropped, _ = trim_to_budget(
        msgs, budget_tokens=100, system_chars=0, min_keep=1)
    # 回看上限 8 条 ⇒ 最多扩到 start = 32-8 = 24 附近，不会把 40 条全捞回来
    assert len(kept) <= 1 + 8 + 2, "扩展超出回看上限: %d" % len(kept)


def test_has_tool_result_helper():
    assert _has_tool_result({"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "x"}]}) is True
    assert _has_tool_result({"role": "user", "content": [
        {"type": "text", "text": "hi"}]}) is False
    assert _has_tool_result({"role": "user", "content": "hi"}) is False
    assert _has_tool_result(None) is False


# ---------- 结构守卫: 两条对话路径都接了预算门禁 ----------


def test_both_chat_paths_apply_token_budget():
    """chat() 与 chat_stream() 都必须走 _trim_messages_to_budget。

    同一道门禁的多个写入方必须逐一对齐，漏一条就行为不一致 (类 20.250 ①)。
    用 AST 而非 grep —— grep 会被注释里"提到该函数"的句子骗出假阳性 (类 20.225)。
    """
    src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    agent_cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "MicroBubbleAgent"
    )
    covered = set()
    for fn in agent_cls.body:
        if not isinstance(fn, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        if fn.name not in ("chat", "chat_stream"):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
                if name == "_trim_messages_to_budget":
                    covered.add(fn.name)
    assert covered == {"chat", "chat_stream"}, "只接了 %s" % covered


def test_storage_decoupled_from_send_budget():
    """存 200 条、送按 token 裁 —— 存储不得再用旧的 30 条常量。"""
    src = (REPO / "app/agent/micro_bubble_agent.py").read_text(encoding="utf-8")
    assert "SESSION_STORE_MAX_MESSAGES" in src
    assert "settings.SESSION_WINDOW_SIZE" not in src, (
        "存储截断仍用 SESSION_WINDOW_SIZE —— 会把长会话的历史永久丢掉"
    )
