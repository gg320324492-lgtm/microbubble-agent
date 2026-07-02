"""LLM tool_call 协议转换器 (Anthropic ↔ OpenAI)

2026-07-02 实现: 切 mimo OpenAI endpoint 修复 429 限流

设计目标:
- Anthropic SDK messages.create / messages.stream 用 Anthropic protocol (tools 列表 + content blocks)
- OpenAI 兼容 (mimo /v1) 用 OpenAI ChatCompletion API (tools 列表 + tool_calls + tool message)
- 7 个核心函数双向转换, 加上 1 个混合消息转换器

Anthropic protocol:
  tools: [{"name": "x", "description": "y", "input_schema": {...}}]
  content blocks: text / tool_use (assistant) / tool_result (user)

OpenAI ChatCompletion protocol:
  tools: [{"type": "function", "function": {"name": "x", "description": "y", "parameters": {...}}}]
  messages: tool_calls (assistant) / tool (role=tool, content=str) (user)
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.tool_call_converter")


# ============================================================================
# 1. Anthropic tools -> OpenAI tools
# ============================================================================

def anthropic_to_openai_tools(anthropic_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Anthropic tool schema (含 input_schema) -> OpenAI tool schema (含 type=function + parameters)

    兼容 OpenAI 兼容 endpoint (mimo /v1 等)
    """
    if not anthropic_tools:
        return []
    openai_tools = []
    for t in anthropic_tools:
        if not isinstance(t, dict):
            logger.warning(f"跳过非 dict tool: {t!r}")
            continue
        # 跳过空 tool (CLAUDE.md 2026-07-01 v3 教训: mimo 不转发空 tools 列表会返 500)
        if not t.get("name") or not t.get("input_schema"):
            logger.debug(f"跳过空 tool: {t.get('name', '?')}")
            continue
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t["input_schema"],
            },
        })
    return openai_tools


# ============================================================================
# 2. Anthropic messages -> OpenAI messages
# ============================================================================

def anthropic_messages_to_openai(
    anthropic_messages: List[Dict[str, Any]],
    system: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Anthropic messages (含 content blocks) -> OpenAI messages (含 role+content/tool_calls)

    处理:
    - user messages with text content blocks -> role=user, content=str
    - user messages with tool_result blocks -> role=tool, content=str(per result)
    - assistant messages with tool_use blocks -> role=assistant, content=None, tool_calls=[...]
    - assistant messages with text blocks -> role=assistant, content=str

    注: OpenAI 严格模式: tool message 必须紧跟 assistant tool_calls, 顺序保持
    """
    openai_messages = []
    if system:
        openai_messages.append({"role": "system", "content": system})

    for msg in anthropic_messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            # Anthropic user content 可能是 str 或 list[block]
            if isinstance(content, str):
                openai_messages.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # 分离 text 和 tool_result
                text_parts = []
                tool_results = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_result":
                        # Anthropic tool_result 块 -> OpenAI tool message
                        tr_content = block.get("content", "")
                        if isinstance(tr_content, list):
                            # 嵌套 list[block] -> 拼 text
                            tr_text = " ".join(
                                b.get("text", "") for b in tr_content
                                if isinstance(b, dict) and b.get("type") == "text"
                            )
                        else:
                            tr_text = str(tr_content)
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id", ""),
                            "content": tr_text,
                        })
                if text_parts:
                    openai_messages.append({
                        "role": "user",
                        "content": "\n".join(text_parts),
                    })
                openai_messages.extend(tool_results)

        elif role == "assistant":
            if isinstance(content, list):
                # 分离 text 和 tool_use
                text_parts = []
                tool_calls = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        inp = block.get("input", {})
                        tool_calls.append({
                            "id": block.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": json.dumps(inp, ensure_ascii=False),
                            },
                        })
                msg = {"role": "assistant", "content": "\n".join(text_parts) or None}
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                openai_messages.append(msg)
            else:
                openai_messages.append({"role": "assistant", "content": str(content) or ""})

    return openai_messages


# ============================================================================
# 3. OpenAI response -> Anthropic-style 响应对象 (兼容 _AnthropicMessageWrapper)
# ============================================================================

def openai_response_to_anthropic_message(
    openai_response: Any,
) -> Dict[str, Any]:
    """OpenAI ChatCompletion response -> Anthropic-style message dict.

    兼容 Pydantic model (ChatCompletion) 和 dict 两种输入.
    LLMClient 调用方代码使用 .content / .stop_reason / .usage.input_tokens 属性访问.

    OpenAI response:
      ChatCompletion(
        id="chatcmpl-xxx",
        choices=[Choice(message=ChoiceMessage(content="...", tool_calls=[...]), finish_reason="stop")],
        usage=Usage(prompt_tokens=N, completion_tokens=N, total_tokens=N)
      )
    """
    # 兼容 Pydantic model + dict 两种输入 (2026-07-02 backend dispatch 修复)
    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    choice = _get(openai_response, "choices", [{}])[0]
    msg = _get(choice, "message", {}) or {}
    raw_msg = msg if isinstance(msg, dict) else (vars(msg) if not isinstance(msg, dict) else msg)
    usage = _get(openai_response, "usage", {}) or {}

    # 拼装 Anthropic-style content blocks
    content_blocks = []
    text_content = raw_msg.get("content") if isinstance(raw_msg, dict) else getattr(raw_msg, "content", "") or ""
    if text_content:
        content_blocks.append({
            "type": "text",
            "text": text_content,
        })

    # OpenAI tool_calls -> Anthropic tool_use blocks
    tool_calls_obj = raw_msg.get("tool_calls") if isinstance(raw_msg, dict) else getattr(raw_msg, "tool_calls", None)
    tool_calls = tool_calls_obj or []
    for tc in tool_calls:
        if isinstance(tc, dict):
            func = tc.get("function", {})
            tc_id = tc.get("id", "")
            func_name = func.get("name", "")
            args_str = func.get("arguments", "{}")
        else:
            func = getattr(tc, "function", None)
            tc_id = getattr(tc, "id", "")
            func_name = getattr(func, "name", "") if func else ""
            args_str = getattr(func, "arguments", "{}") if func else "{}"
        try:
            inp = json.loads(args_str)
        except (json.JSONDecodeError, TypeError):
            inp = {}
        content_blocks.append({
            "type": "tool_use",
            "id": tc_id,
            "name": func_name,
            "input": inp,
        })

    finish_reason = _get(choice, "finish_reason", "stop")
    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "stop_sequence",
    }
    stop_reason = stop_reason_map.get(finish_reason, "end_turn")

    return {
        "id": _get(openai_response, "id", ""),
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "model": _get(openai_response, "model", ""),
        "usage": {
            "input_tokens": _get(usage, "prompt_tokens", 0),
            "output_tokens": _get(usage, "completion_tokens", 0),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


# ============================================================================
# 4. 流式 chunk 累积 (OpenAI delta -> Anthropic event 序列)
# ============================================================================

class OpenAIToolCallAccumulator:
    """累积 OpenAI streaming tool_calls delta (name + arguments 分段发送)

    OpenAI 流式响应中, tool_calls 字段每个 chunk 只包含部分字段:
      chunk 1: {"tool_calls": [{"index": 0, "id": "call_xxx", "function": {"name": "search", "arguments": ""}}]}
      chunk 2: {"tool_calls": [{"index": 0, "function": {"arguments": "{\"query\":"}}]}
      chunk 3: {"tool_calls": [{"index": 0, "function": {"arguments": "\"微纳米气泡\"}"}}]}

    累积后输出完整 tool_call (id, name, arguments)
    """

    def __init__(self):
        # tool_index -> {id, name, arguments_parts}
        self._calls: Dict[int, Dict[str, Any]] = {}

    def add_delta(self, delta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """处理 OpenAI streaming delta 块, 返回完整 tool_call (finalized) 列表"""
        finalized = []
        for tc in delta.get("tool_calls", []) or []:
            idx = tc.get("index", 0)
            if idx not in self._calls:
                self._calls[idx] = {
                    "id": tc.get("id", ""),
                    "name": "",
                    "arguments_parts": [],
                }
            call = self._calls[idx]
            if tc.get("id"):
                call["id"] = tc["id"]
            func = tc.get("function", {})
            if func.get("name"):
                call["name"] = func["name"]
            if func.get("arguments"):
                call["arguments_parts"].append(func["arguments"])
            # finalize 标志: 当前 chunk 含 finish_reason=tool_calls
            if tc.get("finish_reason") == "tool_calls":
                finalized.append(self._finalize(idx))
        return finalized

    def _finalize(self, idx: int) -> Dict[str, Any]:
        call = self._calls[idx]
        try:
            arguments = json.loads("".join(call["arguments_parts"]) or "{}")
        except json.JSONDecodeError:
            arguments = {}
        return {
            "id": call["id"],
            "type": "function",
            "function": {
                "name": call["name"],
                "arguments": json.dumps(arguments, ensure_ascii=False),
            },
        }

    def finalize_all(self) -> List[Dict[str, Any]]:
        return [self._finalize(i) for i in sorted(self._calls.keys())]


# ============================================================================
# 5. 流式 OpenAI delta -> Anthropic streaming event (content_block_delta)
# ============================================================================

def openai_streaming_delta_to_anthropic_events(
    openai_chunk: Dict[str, Any],
    accum_text: str,
    tool_acc: OpenAIToolCallAccumulator,
) -> List[Dict[str, Any]]:
    """OpenAI stream chunk -> Anthropic-style events

    返回事件:
    - {"type": "message_start", "message": {...}}
    - {"type": "content_block_start", "index": N, "content_block": {...}}
    - {"type": "content_block_delta", "index": N, "delta": {"type": "text_delta"|"input_json_delta", "text"|"partial_json": ...}}
    - {"type": "content_block_stop", "index": N}
    - {"type": "message_delta", "delta": {"stop_reason": ...}, "usage": {...}}
    - {"type": "message_stop"}
    """
    events = []
    choice = openai_chunk.get("choices", [{}])[0]
    delta = choice.get("delta", {})

    # 文本增量
    if delta.get("content"):
        # 简化为单 text block
        events.append({
            "type": "content_block_delta",
            "index": 0,
            "delta": {
                "type": "text_delta",
                "text": delta["content"],
            },
        })

    # tool_calls 增量
    finalized = tool_acc.add_delta({
        "tool_calls": delta.get("tool_calls", []) or [],
    })
    for fc in finalized:
        events.append({
            "type": "content_block_start",
            "index": len(finalized),  # 简化: 假设 tool_use 总是 block index 1+
            "content_block": {
                "type": "tool_use",
                "id": fc["id"],
                "name": fc["function"]["name"],
                "input": {},  # 完整 input 在 message_delta 后给出
            },
        })
        events.append({
            "type": "content_block_delta",
            "index": len(finalized),
            "delta": {
                "type": "input_json_delta",
                "partial_json": fc["function"]["arguments"],
            },
        })
        events.append({
            "type": "content_block_stop",
            "index": len(finalized),
        })

    # finish_reason -> message_delta + message_stop
    if choice.get("finish_reason"):
        finish_reason = choice["finish_reason"]
        stop_reason_map = {
            "stop": "end_turn",
            "length": "max_tokens",
            "tool_calls": "tool_use",
            "content_filter": "stop_sequence",
        }
        usage = openai_chunk.get("usage", {})
        events.append({
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason_map.get(finish_reason, "end_turn")},
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        })
        events.append({"type": "message_stop"})

    return events


# ============================================================================
# 6. 镜像 round-trip 检查 (Anthropic <-> OpenAI 协议一致)
# ============================================================================

def anthropic_tools_match_openai(
    anthropic_tools: List[Dict[str, Any]],
    openai_tools: List[Dict[str, Any]],
) -> bool:
    """检查 Anthropic -> OpenAI 转换后是否 round-trip 一致 (用于测试)"""
    openai_result = anthropic_to_openai_tools(anthropic_tools)
    if len(openai_result) != len(openai_tools):
        return False
    for a, o in zip(anthropic_tools, openai_result):
        if o["function"]["name"] != a["name"]:
            return False
        if o["function"]["description"] != a.get("description", ""):
            return False
        if o["function"]["parameters"] != a.get("input_schema"):
            return False
    return True