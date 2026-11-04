"""上下文窗口按 token 预算裁剪（2026-11-04 B 档，替代 SESSION_WINDOW_SIZE=30 的按条数硬截断）

## 为什么要换掉「30 条」

按条数截断在两个方向上都失控：

- 30 条里若有一次工具返回上万字，条数限制**挡不住**溢出（实测多轮工具调用
  `input_tokens` 可达 72847）；
- 30 条若都是「嗯」「好的」这类短应答，又装不下多少信息，白白丢轮次。

实测标定（MiniMax /v1，2026-11-04）：

| 输入字符数 | prompt_tokens |
|---|---|
| 850 | 602 |
| 1700 | 1002 |

⇒ 增量斜率 ≈ **0.47 token/字符**（1 token ≈ 2.1 个中文字符），另有约 200 token
的模板固定开销；32 个工具的 schema 约 1600 token（从单轮实测 7034 反推）。
本模块按 **0.6 token/字符** 估算（比实测高 28%，宁可提前裁剪也不超预算）。

## 关键约束：切点必须落在 user 消息上

从中间截断会留下**孤儿 tool_result**（有 tool_result 却没有产生它的 assistant
tool_use），严格后端会直接 400 —— 这正是 2026-10-14 那次
「tool result's tool id not found」故障的形态。所以裁剪后要把开头的非 user 消息
一并丢掉，保证窗口起点总是一轮的开始。

## 与净化器的关系

`core/message_sanitizer.py` 负责「不污染」，本模块负责「不超预算」，两者都在
会话层收口，互不重叠。
"""
from typing import Any, Dict, List, Tuple

# 估算系数: 实测 0.47 token/字符, 取 0.6 留安全边际 (宁可早裁)
TOKENS_PER_CHAR = 0.6
# 模板固定开销 (messages 外壳 + role 标记)
REQUEST_OVERHEAD_TOKENS = 200
# 工具 schema 的固定开销 (32 个工具实测约 1600 token, 按上取整留余量)
TOOLS_SCHEMA_TOKENS = 1800
# 切点对齐时最多向前回看几条 (防止整段都是工具块时无限扩展)
MAX_ALIGN_LOOKBACK = 8


def estimate_message_tokens(msg: Any) -> int:
    """估算单条消息的 token 数（含 role 与结构开销的粗略上界）。"""
    if not isinstance(msg, dict):
        return 0
    content = msg.get("content")
    if isinstance(content, str):
        chars = len(content)
    elif isinstance(content, list):
        chars = 0
        for blk in content:
            if isinstance(blk, dict):
                for key in ("text", "content", "input", "partial_json"):
                    v = blk.get(key)
                    if v is None:
                        continue
                    chars += len(v) if isinstance(v, str) else len(str(v))
        chars += 60 * len(content)  # 块结构本身的开销
    else:
        chars = len(str(content or ""))
    # tool_calls 也占上下文
    for tc in (msg.get("tool_calls") or []):
        chars += len(str(tc))
    return int(chars * TOKENS_PER_CHAR) + 8


def estimate_request_tokens(
    messages: List[Dict[str, Any]],
    system_chars: int = 0,
    with_tools: bool = True,
) -> int:
    """估算整个请求的 prompt_tokens 上界。"""
    total = REQUEST_OVERHEAD_TOKENS
    if with_tools:
        total += TOOLS_SCHEMA_TOKENS
    total += int(system_chars * TOKENS_PER_CHAR)
    for m in messages:
        total += estimate_message_tokens(m)
    return total


def _has_tool_result(msg: Any) -> bool:
    """消息里是否含 tool_result 块。

    ⚠️ Anthropic 协议里 tool_result 装在 **user** 消息内 —— 所以"窗口起点必须是
    user"这一条**不足以**排除孤儿: 起点可能正是一条带着 tool_result 的 user 消息,
    而产生它的 assistant tool_use 已被裁掉 ⇒ 严格后端会直接 400
    (2026-10-14「tool result's tool id not found」同型故障)。
    """
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        return any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content
        )
    return False


def trim_to_budget(
    messages: List[Dict[str, Any]],
    budget_tokens: int,
    system_chars: int = 0,
    min_keep: int = 2,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """从最新往回累加，裁到预算内。

    返回 (裁剪后的消息, 丢弃条数, 估算 token 数)。

    不变量:
    - 结果**非空**时，首条必须是 user（否则孤儿 tool_result 会让严格后端 400）；
    - 至少保留 `min_keep` 条（预算再小也不能把当前问题丢掉）；
    - 预算充足时原样返回，不做无谓拷贝。
    """
    if not messages:
        return [], 0, estimate_request_tokens([], system_chars)

    fixed = REQUEST_OVERHEAD_TOKENS + TOOLS_SCHEMA_TOKENS + int(
        system_chars * TOKENS_PER_CHAR)
    per_msg = [estimate_message_tokens(m) for m in messages]

    # 从最新往回收: 超预算就停, 但**至少收 min_keep 条** —— 预算再小也不能把
    # 用户当前这问丢掉 (否则模型收到空上下文)。
    total = fixed
    start = len(messages) - 1
    n_kept = 0
    for i in range(len(messages) - 1, -1, -1):
        over_budget = total + per_msg[i] > budget_tokens
        if over_budget and n_kept >= min_keep:
            break
        total += per_msg[i]
        start = i
        n_kept += 1

    # 切点对齐: 窗口起点必须是一条 **不含 tool_result 的 user 消息**。
    #
    # 为什么是「向前扩展」而不是「向后收缩」:
    #   - 只判 role 不够 —— tool_result 就装在 user 消息里, 产生它的 assistant
    #     tool_use 若被裁掉就成了孤儿, 严格后端直接 400 (2026-10-14 同型故障);
    #   - 收缩到只剩一条 assistant 开头 (甚至只剩 tool_result) 的请求**本身不合法**,
    #     省下的那点 token 不值得换一次 400。
    # 所以宁可多带几条、轻微超预算, 也要把起点落到真正的轮次边界上。
    def _is_safe_start(m: Any) -> bool:
        return (
            isinstance(m, dict)
            and m.get("role") == "user"
            and not _has_tool_result(m)
        )

    extended = 0
    while start > 0 and not _is_safe_start(messages[start]):
        start -= 1
        total += per_msg[start]
        extended += 1
        if extended > MAX_ALIGN_LOOKBACK:
            # 历史里找不到干净的轮次边界 (整段都是工具块) —— 保持现状, 不再无限扩展
            break

    result = list(messages[start:])
    return result, len(messages) - len(result), total


__all__ = [
    "TOKENS_PER_CHAR",
    "REQUEST_OVERHEAD_TOKENS",
    "TOOLS_SCHEMA_TOKENS",
    "estimate_message_tokens",
    "estimate_request_tokens",
    "trim_to_budget",
    "_has_tool_result",
]
