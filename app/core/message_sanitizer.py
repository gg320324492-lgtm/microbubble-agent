"""会话消息净化 —— 拦截模型原生工具调用标记污染会话历史（2026-11-04 P0）。

## 事故链（会议 265 之后的对话验证中发现）

1. 某轮请求里模型没有走结构化 `tool_calls`，而是把工具调用写成**正文文本**
   （形态是 `<` + `]minimax[` + `>` + `im_start` 这类 MiniMax 原生标记）；
2. 这段文本作为 assistant 消息被**原样写入会话历史**（Redis）；
3. 下一轮请求把这段"文本形态的工具调用"当**示范**喂给模型 ⇒ 模型继续模仿
   ⇒ 工具永不执行（`tool_rounds_used=0`）、用户看到乱码标记，且**自我强化**；
4. 实测对照：同一套代码 + 同一模型，清空历史后 `tool_rounds_used=2`、
   8 个工具调用、答案正常无标记 ⇒ 产品链路与模型侧都没问题，
   历史污染是充要条件。

## 本模块做两件事（主指挥 2026-11-04 拍板：存前净化 + 读时过滤）

- `sanitize_messages()`：写库前过滤，堵住**新增**污染；
- 读历史时同样过滤：让**已带污染**的老会话自动恢复，不必人工清 Redis。

## 为什么整条丢弃而不是剥掉标记

这类消息的内容本身就是"未执行的工具调用"，剥掉标记后只剩半截自然语言
（例如 "你不能搞这大个这个一个评估的事儿。我可以这样，就是把这个PPT..."），
给模型的示范更糟。整条丢弃后历史只是少一轮，语义无损。

## 为什么放在存储层而不是调用方

会话读写有 4 个入口（SessionManager.get/save、RedisSessionStore.get/save/append），
在存储层收口可一处覆盖全部，避免漏掉某个调用方（类 20.250 ①：同一门禁多个写入方
必须逐键对齐）。
"""
from typing import Any, Dict, List, Tuple

# 标记片段用拼接构造：既避免本文件被自己的检测规则命中，也让字面量来源清晰。
_MARKER_MINIMAX = "]" + "minimax" + "["
_MARKER_IM_START = "im" + "_start"
_MARKER_IM_END = "im" + "_end"

NATIVE_TOOL_MARKERS: Tuple[str, ...] = (
    _MARKER_MINIMAX,
    _MARKER_IM_START,
    _MARKER_IM_END,
)


def contains_native_tool_marker(text: Any) -> bool:
    """判断文本里是否含模型原生工具调用标记。

    只检查字符串；content 为块数组（Anthropic 风格）时由调用方先取文本。
    """
    if not isinstance(text, str) or not text:
        return False
    return any(m in text for m in NATIVE_TOOL_MARKERS)


def _content_text(content: Any) -> str:
    """取消息的可读文本（兼容 str 与 Anthropic content 块数组）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                parts.append(str(blk.get("text") or blk.get("content") or ""))
        return " ".join(parts)
    return ""


def is_polluted_message(msg: Any) -> bool:
    """整条消息是否被原生工具标记污染（role 与 tool 结果都查）。"""
    if not isinstance(msg, dict):
        return False
    if contains_native_tool_marker(_content_text(msg.get("content"))):
        return True
    # tool_result 块里也可能带标记（工具输出被模型当正文回显的情形）
    return contains_native_tool_marker(str(msg.get("name") or ""))


def sanitize_messages(
    messages: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    """过滤掉含原生工具标记的消息，返回 (干净列表, 丢弃条数)。

    非 dict 元素一并丢弃（历史里出现脏结构时不应再喂给模型）。
    """
    if not isinstance(messages, list):
        return [], 0
    kept: List[Dict[str, Any]] = []
    dropped = 0
    for m in messages:
        if not isinstance(m, dict) or is_polluted_message(m):
            dropped += 1
            continue
        kept.append(m)
    return kept, dropped


__all__ = [
    "NATIVE_TOOL_MARKERS",
    "contains_native_tool_marker",
    "is_polluted_message",
    "sanitize_messages",
]
