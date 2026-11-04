"""工具结果的 OpenAI 协议邻接性 + 异常兜底不掩盖原始错误 (2026-11-04)

## 起因

fast 模式放行工具循环 (commit f563a947e) 后, 真实 /chat 的 data_query
第一次真正跑 Phase 1, 随即 HTTP 500。App 日志两层:

1. 根因: MiniMax 400
   `invalid params, tool call result does not follow tool call (2013)`;
2. 掩盖层: `UnboundLocalError: final_text` —— 异常兜底块引用了在
   **Phase 4 之后**才初始化的变量, 把 400 放大成 500 并盖掉原始错误。

根因机制: `anthropic_messages_to_openai()` 把一条 user 消息里的
text 块先输出成 `role=user`, 再 `extend(tool_results)` ⇒
`assistant(tool_calls) → user(text) → tool(result)`, 中间夹了一条 user。
而 `inject_compressed_to_messages` 恰恰会往同一条 user 里追加 `<compressed>`
文本块 ⇒ 只要工具循环真的跑过, 严格后端必炸。
这条缺陷一直被遮着, 因为 fast 原先 `max_tool_rounds=0` 从不跑工具循环
(类 20.220: 修上游缺陷会暴露下游缺陷)。

⚠️ 仓库里 `tests/unit/test_tool_call_converter.py` 整个文件被
`pytest.skip(allow_module_level=True)` 归档, 对现役链路零保护 ——
所以本文件是**新的活测试**, 不复活旧快照。
"""
import ast
import pathlib

from app.core.tool_call_converter import anthropic_messages_to_openai

REPO = pathlib.Path(__file__).resolve().parents[1]


def _one_round_messages():
    """复刻 Phase 1 一轮结束后的真实形状 (含压缩追加的文本块)。"""
    return [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "tu_1", "name": "query_members",
             "input": {"research_area": "臭氧"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1",
             "content": '{"status":"ok","count":2}'},
            {"type": "text", "text": "<compressed>已筛选 2 条</compressed>"},
        ]},
    ]


def test_tool_message_immediately_follows_tool_calls():
    """核心回归: role=tool 必须**紧挨** assistant(tool_calls), 中间不许夹 user。"""
    out = anthropic_messages_to_openai(_one_round_messages(), "sys")
    roles = [m["role"] for m in out]
    assert roles == ["system", "assistant", "tool", "user"], (
        "工具结果被文本块挤开了: %s" % roles)

    for i, m in enumerate(out):
        if m["role"] == "tool":
            assert i > 0 and out[i - 1]["role"] == "assistant"
            assert out[i - 1].get("tool_calls"), "role=tool 前面不是 tool_calls"
            assert m.get("tool_call_id") == "tu_1"
            assert isinstance(m["content"], str)


def test_context_text_is_preserved_after_tool_results():
    """重排不能把压缩说明文本弄丢 —— 它是给模型看的上下文。"""
    out = anthropic_messages_to_openai(_one_round_messages())
    last = out[-1]
    assert last["role"] == "user"
    text = " ".join(
        p.get("text", "") for p in last["content"]
        if isinstance(p, dict) and p.get("type") == "text"
    ) if isinstance(last["content"], list) else str(last["content"])
    assert "已筛选" in text


def test_multiple_tool_results_all_adjacent():
    """一轮多个工具: 所有 role=tool 必须连续跟在 assistant(tool_calls) 后。"""
    msgs = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "query_members", "input": {}},
            {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "A"},
            {"type": "text", "text": "压缩说明"},
            {"type": "tool_result", "tool_use_id": "t2", "content": "B"},
        ]},
    ]
    out = anthropic_messages_to_openai(msgs)
    first_tool = next(i for i, m in enumerate(out) if m["role"] == "tool")
    assert out[first_tool - 1].get("tool_calls")
    tool_msgs = [m for m in out if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["t1", "t2"]
    # 两个 tool 之间不许夹别的 role
    idxs = [i for i, m in enumerate(out) if m["role"] == "tool"]
    assert idxs == list(range(idxs[0], idxs[0] + len(idxs)))


def test_plain_text_conversation_unchanged():
    """没有工具块的普通对话, 顺序与内容不受重排影响。"""
    msgs = [{"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好呀"}]
    out = anthropic_messages_to_openai(msgs, "sys")
    assert [m["role"] for m in out] == ["system", "user", "assistant"]
    assert out[1]["content"] == "你好"


# ---------------------------------------------------------------- 掩盖层


def test_final_text_initialized_before_synthesis():
    """AST: `final_text = ""` 必须出现在 `_synthesize_stream` 调用**之前**。

    否则 _synthesize_stream 抛异常时, except 兜底块
    (`if rich_blocks and not final_text.strip()`) 引用未绑定变量 ⇒
    UnboundLocalError 把原始 400 盖成 500 (类 20.220 的掩盖层)。
    """
    src = (REPO / "app/agent/agentic_loop.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_run_legacy"
    )

    init_linenos = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "final_text" for t in n.targets)
        and isinstance(n.value, ast.Constant) and n.value.value == ""
    ]
    synth_linenos = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == "_synthesize_stream"
    ]
    assert init_linenos and synth_linenos
    assert min(init_linenos) < min(synth_linenos), (
        "final_text 初始化 (%s) 不早于 synthesis (%s) ⇒ 异常兜底会二次抛错"
        % (init_linenos, synth_linenos))
    assert len(init_linenos) == 1, (
        "有多处 `final_text = \"\"` —— Phase 4 retry 后的正文可能被后面那次清空: %s"
        % init_linenos)
