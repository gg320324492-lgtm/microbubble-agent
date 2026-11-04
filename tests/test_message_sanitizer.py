"""会话历史净化 (2026-11-04 P0: 模型原生工具标记污染会话历史并自我强化)

事故形态 (agent_traces id=5777/5778 的答案原文，此处用拼接构造，
避免本测试文件自身被净化规则命中):

    < ]minimax[ > im_start tool_call ...

这类文本一旦被当作 assistant 消息写进 Redis 会话历史，下一轮就作为"示范"喂给模型
⇒ 模型继续输出文本形态调用 ⇒ tool_rounds_used 恒为 0、用户看到乱码，循环自持。

实测对照: 清空该会话历史后，同一套代码 tool_rounds_used=2 / 8 个工具调用 /
答案正常无标记 ⇒ 产品链路与模型侧都没问题，**历史污染是充要条件**。

覆盖:
① 净化器纯逻辑 (检测 / 不误伤 / 块数组 / 计数 / 脏结构)
② 标记常量与真实泄漏形态一致 (回归锚点)
③ 两个存储层 5 个读写口都接上净化 —— AST 结构守卫
   (类 20.250 ①: 同一门禁多个写入方必须逐一对齐，漏一个就能重新污染)
"""
import ast
import pathlib

import pytest

from app.core.message_sanitizer import (
    NATIVE_TOOL_MARKERS,
    contains_native_tool_marker,
    is_polluted_message,
    sanitize_messages,
)

REPO = pathlib.Path(__file__).resolve().parents[1]

# 真实泄漏文本 (拼接构造)
LEAK = "<" + "]minimax[" + ">im" + "_start" + 'tool_call name="query_members"'
LEAK2 = "<" + "]minimax[" + "> (to=functions.query_members code)"
CLEAN = "陈金薪在做臭氧微纳米气泡研究，刘莫菲负责气泡识别。"


# ---------- ① 纯逻辑 ----------


def test_detects_native_marker_forms():
    assert contains_native_tool_marker(LEAK) is True
    assert contains_native_tool_marker(LEAK2) is True
    assert contains_native_tool_marker("im" + "_end") is True


def test_does_not_flag_normal_answers():
    """正常回答不得被误伤 —— 误伤会吃掉真实历史。"""
    assert contains_native_tool_marker(CLEAN) is False
    assert contains_native_tool_marker("今天天气不错，会议安排在周三。") is False
    assert contains_native_tool_marker("他用 `query_members` 工具查了三个人。") is False
    assert contains_native_tool_marker("") is False
    assert contains_native_tool_marker(None) is False
    assert contains_native_tool_marker(123) is False


def test_known_false_positive_is_documented():
    """已知误伤面 (如实记录，不掩盖):

    若用户真的在讨论模型 token 本身 (如问 "im_start 是什么")，该轮 assistant
    回答会被净化丢弃 —— 历史少一轮，语义无损，且不影响当轮回答的展示
    (净化只作用于**会话历史存储**，不作用于返回给用户的内容)。
    这是"防自我强化污染"换来的可接受代价，故不额外加白名单。
    """
    assert contains_native_tool_marker("im" + "_start 是 ChatML 的起始标记") is True


def test_marker_in_content_block_array_detected():
    """Anthropic content 块数组形态同样要查到 (assistant 消息可能是块列表)。"""
    msg = {"role": "assistant", "content": [{"type": "text", "text": LEAK}]}
    assert is_polluted_message(msg) is True


def test_sanitize_counts_and_preserves_order():
    msgs = [
        {"role": "user", "content": "谁在做臭氧研究？"},
        {"role": "assistant", "content": LEAK},          # 丢弃
        {"role": "user", "content": "再说说"},
        {"role": "assistant", "content": CLEAN},
    ]
    kept, dropped = sanitize_messages(msgs)
    assert dropped == 1
    assert [m["role"] for m in kept] == ["user", "user", "assistant"]
    assert kept[-1]["content"] == CLEAN


def test_sanitize_drops_non_dict_and_handles_bad_input():
    kept, dropped = sanitize_messages([{"role": "user", "content": "a"}, "脏字符串", None])
    assert len(kept) == 1 and dropped == 2
    assert sanitize_messages(None) == ([], 0)
    assert sanitize_messages([]) == ([], 0)


def test_clean_messages_untouched():
    msgs = [{"role": "user", "content": "问题"}, {"role": "assistant", "content": CLEAN}]
    kept, dropped = sanitize_messages(msgs)
    assert dropped == 0
    assert kept == msgs


# ---------- ② 标记常量回归锚点 ----------


def test_marker_constants_cover_observed_forms():
    """06-11-04 实测泄漏文本只靠这几个片段就能命中；改常量必须同步改这里。"""
    assert "]minimax[" in NATIVE_TOOL_MARKERS
    assert "im" + "_start" in NATIVE_TOOL_MARKERS
    assert "im" + "_end" in NATIVE_TOOL_MARKERS


# ---------- ③ 结构守卫: 两个存储层 5 个读写口都接净化 ----------

# (文件, 类, 方法) —— 每个都必须调用净化
REQUIRED_WIRING = [
    ("app/core/redis.py", "RedisSessionStore", "get_messages", "sanitize_messages"),
    ("app/core/redis.py", "RedisSessionStore", "save_messages", "sanitize_messages"),
    ("app/core/redis.py", "RedisSessionStore", "append_message", "is_polluted_message"),
    ("app/agent/session_manager.py", "SessionManager", "get_messages", "sanitize_messages"),
    ("app/agent/session_manager.py", "SessionManager", "save_messages", "sanitize_messages"),
    ("app/agent/session_manager.py", "SessionManager", "append_message", "is_polluted_message"),
]


@pytest.mark.parametrize("relpath,cls,func,call_name", REQUIRED_WIRING)
def test_storage_ports_wired_to_sanitizer(relpath, cls, func, call_name):
    """AST 守卫: 净化必须接在存储层每个读写口上。

    用 AST 而不是 grep —— grep 会被注释里"提到 sanitize_messages"的句子骗出
    假阳性 (类 20.225)。
    """
    tree = ast.parse((REPO / relpath).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            target = next(
                (f for f in node.body
                 if isinstance(f, (ast.AsyncFunctionDef, ast.FunctionDef)) and f.name == func),
                None,
            )
            assert target is not None, f"{cls}.{func} 不存在"
            called = {
                (n.func.id if isinstance(n.func, ast.Name)
                 else getattr(n.func, "attr", ""))
                for n in ast.walk(target) if isinstance(n, ast.Call)
            }
            assert call_name in called, (
                f"{relpath}::{cls}.{func} 未调用 {call_name}() —— "
                f"该读写口会把含原生工具标记的消息写进/读出会话历史 "
                f"(2026-11-04 P0 的自我强化循环)"
            )
            return
    pytest.fail(f"{relpath} 里找不到类 {cls}")
