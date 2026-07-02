"""tool_call_converter 单元测试

2026-07-02 实现: 12 cases 覆盖 7 个核心函数
"""
import json
import sys
from pathlib import Path

# 让 Python 找到 app/ 模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.tool_call_converter import (
    anthropic_to_openai_tools,
    anthropic_messages_to_openai,
    openai_response_to_anthropic_message,
    OpenAIToolCallAccumulator,
    openai_streaming_delta_to_anthropic_events,
    anthropic_tools_match_openai,
)


# ============================================================================
# Case 1: anthropic_to_openai_tools 正向
# ============================================================================
def test_anthropic_to_openai_tools_basic():
    """Anthropic tool schema -> OpenAI tool schema"""
    ant = [{
        "name": "search_knowledge",
        "description": "search KB",
        "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
    }]
    oai = anthropic_to_openai_tools(ant)
    assert len(oai) == 1
    assert oai[0]["type"] == "function"
    assert oai[0]["function"]["name"] == "search_knowledge"
    assert oai[0]["function"]["description"] == "search KB"
    assert oai[0]["function"]["parameters"] == {"type": "object", "properties": {"q": {"type": "string"}}}
    print("✅ Case 1: anthropic_to_openai_tools 正向")


# ============================================================================
# Case 2: anthropic_to_openai_tools 跳过空 tool (mimo 不转发空 tools)
# ============================================================================
def test_anthropic_to_openai_tools_skip_empty():
    """空 name 或空 input_schema 的 tool 必须跳过 (否则 mimo 报 500)"""
    ant = [
        {"name": "good_tool", "input_schema": {"type": "object"}},  # OK
        {"name": "", "input_schema": {"type": "object"}},  # 空 name
        {"name": "no_schema"},  # 空 input_schema
    ]
    oai = anthropic_to_openai_tools(ant)
    assert len(oai) == 1
    assert oai[0]["function"]["name"] == "good_tool"
    print("✅ Case 2: 跳过空 tool")


# ============================================================================
# Case 3: anthropic_messages_to_openai 正向 (user+assistant+tool_result 序列)
# ============================================================================
def test_anthropic_messages_to_openai_sequence():
    """user -> assistant(tool_use) -> user(tool_result) -> assistant"""
    ant_msgs = [
        {"role": "user", "content": [{"type": "text", "text": "微纳米气泡是什么"}]},
        {"role": "assistant", "content": [
            {"type": "text", "text": "让我查一下"},
            {"type": "tool_use", "id": "call_001", "name": "search_knowledge", "input": {"q": "微纳米气泡"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_001", "content": "微纳米气泡是..."},
        ]},
        {"role": "assistant", "content": [{"type": "text", "text": "微纳米气泡是 XXX"}]},
    ]
    oai = anthropic_messages_to_openai(ant_msgs)
    # 期望 4 个 msg: user, assistant(带 tool_calls), tool, assistant
    assert len(oai) == 4
    assert oai[0]["role"] == "user"
    assert "微纳米气泡是什么" in oai[0]["content"]
    assert oai[1]["role"] == "assistant"
    assert oai[1]["content"] == "让我查一下"
    assert "tool_calls" in oai[1]
    assert oai[1]["tool_calls"][0]["id"] == "call_001"
    assert oai[1]["tool_calls"][0]["function"]["name"] == "search_knowledge"
    assert json.loads(oai[1]["tool_calls"][0]["function"]["arguments"]) == {"q": "微纳米气泡"}
    assert oai[2]["role"] == "tool"
    assert oai[2]["tool_call_id"] == "call_001"
    assert oai[2]["content"] == "微纳米气泡是..."
    assert oai[3]["role"] == "assistant"
    print("✅ Case 3: messages 序列完整转换")


# ============================================================================
# Case 4: anthropic_messages_to_openai 带 system
# ============================================================================
def test_anthropic_messages_to_openai_with_system():
    """system prompt 作为第一个 system role message"""
    oai = anthropic_messages_to_openai(
        [{"role": "user", "content": [{"type": "text", "text": "你好"}]}],
        system="你是小气助手",
    )
    assert oai[0]["role"] == "system"
    assert oai[0]["content"] == "你是小气助手"
    assert oai[1]["role"] == "user"
    print("✅ Case 4: system 消息")


# ============================================================================
# Case 5: openai_response_to_anthropic_message 正向
# ============================================================================
def test_openai_response_to_anthropic_message_basic():
    """OpenAI ChatCompletion response -> Anthropic-style message"""
    oai_resp = {
        "id": "chatcmpl-xxx",
        "model": "mimo-v2.5",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "微纳米气泡是...",
                "tool_calls": [],
            },
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    ant_msg = openai_response_to_anthropic_message(oai_resp)
    assert ant_msg["role"] == "assistant"
    assert ant_msg["stop_reason"] == "end_turn"
    assert ant_msg["content"][0]["type"] == "text"
    assert ant_msg["content"][0]["text"] == "微纳米气泡是..."
    assert ant_msg["usage"]["input_tokens"] == 100
    assert ant_msg["usage"]["output_tokens"] == 50
    print("✅ Case 5: OpenAI response -> Anthropic message")


# ============================================================================
# Case 6: openai_response_to_anthropic_message with tool_calls
# ============================================================================
def test_openai_response_to_anthropic_message_with_tool_calls():
    """OpenAI tool_calls 转换 -> Anthropic tool_use blocks"""
    oai_resp = {
        "id": "chatcmpl-xxx",
        "model": "mimo-v2.5",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "id": "call_001",
                    "type": "function",
                    "function": {
                        "name": "search_knowledge",
                        "arguments": json.dumps({"q": "微纳米气泡"}, ensure_ascii=False),
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30},
    }
    ant_msg = openai_response_to_anthropic_message(oai_resp)
    assert ant_msg["stop_reason"] == "tool_use"
    # 应该有 1 个 tool_use block
    tu_blocks = [b for b in ant_msg["content"] if b.get("type") == "tool_use"]
    assert len(tu_blocks) == 1
    assert tu_blocks[0]["id"] == "call_001"
    assert tu_blocks[0]["name"] == "search_knowledge"
    assert tu_blocks[0]["input"] == {"q": "微纳米气泡"}
    print("✅ Case 6: OpenAI tool_calls -> Anthropic tool_use")


# ============================================================================
# Case 7: OpenAIToolCallAccumulator 流式累积
# ============================================================================
def test_openai_tool_call_accumulator():
    """OpenAI streaming tool_calls delta 分段累积"""
    acc = OpenAIToolCallAccumulator()

    # Chunk 1: 只有 id + name
    d1 = {"tool_calls": [{"index": 0, "id": "call_001", "function": {"name": "search", "arguments": ""}}]}
    f1 = acc.add_delta(d1)
    assert len(f1) == 0  # 未完成

    # Chunk 2: arguments 第 1 段
    d2 = {"tool_calls": [{"index": 0, "function": {"arguments": '{"q":'}}]}
    f2 = acc.add_delta(d2)
    assert len(f2) == 0

    # Chunk 3: arguments 第 2 段
    d3 = {"tool_calls": [{"index": 0, "function": {"arguments": '"微纳米气泡"}'}}]}
    f3 = acc.add_delta(d3)
    assert len(f3) == 0

    # 手动 finalize
    all_calls = acc.finalize_all()
    assert len(all_calls) == 1
    assert all_calls[0]["id"] == "call_001"
    assert all_calls[0]["function"]["name"] == "search"
    assert json.loads(all_calls[0]["function"]["arguments"]) == {"q": "微纳米气泡"}
    print("✅ Case 7: 流式 tool_calls 累积")


# ============================================================================
# Case 8: openai_streaming_delta_to_anthropic_events
# ============================================================================
def test_openai_streaming_delta_to_anthropic_events():
    """OpenAI stream chunk -> Anthropic-style events"""
    acc = OpenAIToolCallAccumulator()

    # 文本 chunk
    chunk1 = {"choices": [{"delta": {"content": "你好"}, "finish_reason": None}]}
    ev1 = openai_streaming_delta_to_anthropic_events(chunk1, "", acc)
    assert any(e["type"] == "content_block_delta" and e["delta"]["text"] == "你好" for e in ev1)

    # 结束 chunk
    chunk2 = {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    ev2 = openai_streaming_delta_to_anthropic_events(chunk2, "", acc)
    assert any(e["type"] == "message_delta" and e["delta"]["stop_reason"] == "end_turn" for e in ev2)
    assert any(e["type"] == "message_stop" for e in ev2)
    print("✅ Case 8: streaming chunk -> Anthropic events")


# ============================================================================
# Case 9: round-trip 一致性 (anthropic_tools_match_openai)
# ============================================================================
def test_round_trip_consistency():
    """anthropic -> openai -> 比较 一致性"""
    ant = [
        {"name": "tool_a", "description": "desc_a", "input_schema": {"type": "object"}},
        {"name": "tool_b", "description": "desc_b", "input_schema": {"type": "object", "properties": {}}},
    ]
    oai = anthropic_to_openai_tools(ant)
    assert anthropic_tools_match_openai(ant, oai) is True
    print("✅ Case 9: round-trip 一致性")


# ============================================================================
# Case 10: tool_call ID round-trip
# ============================================================================
def test_tool_call_id_preservation():
    """Anthropic tool_use id 必须保留到 OpenAI tool_calls id"""
    ant = [
        {"role": "user", "content": [{"type": "text", "text": "查询"}]},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_test_001", "name": "search_knowledge", "input": {"q": "x"}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_test_001", "content": "result"},
        ]},
    ]
    oai = anthropic_messages_to_openai(ant)
    # 找到 tool_call 和 tool message
    tool_call = next((m for m in oai if m.get("role") == "assistant" and "tool_calls" in m), None)
    tool_msg = next((m for m in oai if m.get("role") == "tool"), None)
    assert tool_call["tool_calls"][0]["id"] == "toolu_test_001"
    assert tool_msg["tool_call_id"] == "toolu_test_001"
    print("✅ Case 10: tool_call ID 保留")


# ============================================================================
# Case 11: OpenAI tool message content 必须是 str (per protocol)
# ============================================================================
def test_openai_tool_message_content_is_str():
    """Anthropic tool_result content 是 str (per OpenAI protocol)"""
    ant = [{"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "call_001", "content": "string result"},
    ]}]
    oai = anthropic_messages_to_openai(ant)
    assert oai[0]["role"] == "tool"
    assert isinstance(oai[0]["content"], str)
    assert oai[0]["content"] == "string result"
    print("✅ Case 11: tool message content 必为 str")


# ============================================================================
# Case 12: 异常 path (空 messages, None content)
# ============================================================================
def test_edge_cases():
    """空 messages + None content 不崩"""
    # 空 list
    assert anthropic_to_openai_tools([]) == []
    assert anthropic_messages_to_openai([]) == []
    # None content
    msgs = [
        {"role": "assistant", "content": None},  # None
    ]
    oai = anthropic_messages_to_openai(msgs)
    # 至少不应崩
    assert isinstance(oai, list)
    print("✅ Case 12: 异常路径不崩")


# ============================================================================
# Run all
# ============================================================================
if __name__ == "__main__":
    test_anthropic_to_openai_tools_basic()
    test_anthropic_to_openai_tools_skip_empty()
    test_anthropic_messages_to_openai_sequence()
    test_anthropic_messages_to_openai_with_system()
    test_openai_response_to_anthropic_message_basic()
    test_openai_response_to_anthropic_message_with_tool_calls()
    test_openai_tool_call_accumulator()
    test_openai_streaming_delta_to_anthropic_events()
    test_round_trip_consistency()
    test_tool_call_id_preservation()
    test_openai_tool_message_content_is_str()
    test_edge_cases()
    print()
    print("=" * 50)
    print("All 12 cases PASSED ✅")
    print("=" * 50)