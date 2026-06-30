"""
detectors/first_token_latency.py — 首字延迟 (TTFT) 检测器 (P1)

检测从 SSE 连接建立到收到第一个 text_delta 事件的延迟（Time To First Token）。
TTFT 反映 streaming 体感"卡不卡"，业界标准：
- <1s: 优秀（用户感觉"瞬间"响应）
- 1-3s: 良好（可接受）
- 3-8s: warn（用户开始焦虑）
- >8s: fail（用户以为卡死）

注：TTFT 与总 duration 区分。Total duration 包括工具调用 + 综合生成全程。
TTFT 只反映"从用户发问到看到第一段文字"的时间。
"""
from typing import Any, Dict, List, Optional


# 阈值（秒）
TTFT_WARN_S = 3.0
TTFT_FAIL_S = 8.0


def calculate_ttft(
    events: List[Dict[str, Any]],
    request_start_ts: Optional[float] = None,
) -> Optional[float]:
    """计算首字延迟（秒）

    Args:
        events: SSE 事件列表
        request_start_ts: 请求开始时间戳（time.time()），如果为 None 则用第一个事件的时间戳

    Returns: TTFT 秒数，找不到 text_delta 返 None
    """
    if not events:
        return None

    first_text_event = None
    for evt in events:
        if evt.get("type") == "text_delta":
            first_text_event = evt
            break

    if not first_text_event:
        return None

    # 尝试从事件本身取时间戳，否则用 request_start_ts
    event_ts = first_text_event.get("timestamp") or first_text_event.get("ts")
    if event_ts is None:
        return None
    if request_start_ts is None:
        # 没有基准时间，不能计算
        return None

    return event_ts - request_start_ts


def detect_first_token_latency(
    events: List[Dict[str, Any]],
    request_start_ts: Optional[float] = None,
) -> List[Dict[str, str]]:
    """检测首字延迟是否超阈值

    Args:
        events: SSE 事件列表（必须含 timestamp 字段）
        request_start_ts: 请求开始时间戳

    Returns: issue dict 列表
    """
    issues = []

    ttft = calculate_ttft(events, request_start_ts)
    if ttft is None:
        # 没拿到时间戳 — 静默跳过（不报错，避免 false positive）
        return issues

    if ttft > TTFT_FAIL_S:
        issues.append({
            "type": "ttft_too_slow",
            "severity": "fail",
            "expected": f"<= {TTFT_FAIL_S}s",
            "actual": f"{ttft:.2f}s",
            "context": f"首字延迟 {ttft:.2f}s 超过 fail 阈值 {TTFT_FAIL_S}s（用户感觉卡死）",
        })
    elif ttft > TTFT_WARN_S:
        issues.append({
            "type": "ttft_slow",
            "severity": "warn",
            "expected": f"<= {TTFT_WARN_S}s",
            "actual": f"{ttft:.2f}s",
            "context": f"首字延迟 {ttft:.2f}s 超过 warn 阈值 {TTFT_WARN_S}s（用户开始焦虑）",
        })

    return issues


# 测试代码
if __name__ == "__main__":
    import time

    # 模拟事件
    base_ts = time.time()

    test_cases = [
        ("快速 (0.5s)", [
            {"type": "intent_detected", "timestamp": base_ts},
            {"type": "text_delta", "delta": "你好", "timestamp": base_ts + 0.5},
            {"type": "done", "timestamp": base_ts + 2.0},
        ]),
        ("良好 (2s)", [
            {"type": "text_delta", "delta": "你好", "timestamp": base_ts + 2.0},
        ]),
        ("慢 (5s)", [
            {"type": "text_delta", "delta": "你好", "timestamp": base_ts + 5.0},
        ]),
        ("超慢 (10s)", [
            {"type": "text_delta", "delta": "你好", "timestamp": base_ts + 10.0},
        ]),
        ("无 text_delta", [
            {"type": "intent_detected", "timestamp": base_ts},
        ]),
    ]

    for name, events in test_cases:
        print(f"\n=== {name} ===")
        issues = detect_first_token_latency(events, request_start_ts=base_ts)
        if not issues:
            print("  ✓ 通过")
        else:
            for issue in issues:
                print(f"  [{issue['severity']}] {issue['type']}: {issue['context']}")
