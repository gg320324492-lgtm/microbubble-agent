"""
detectors/stream_interrupt.py — SSE 流中断检测器 (P0)

检测 SSE 事件流是否异常中断：
1. 连接断开前没收到 done 事件
2. 收到 error 事件但没后续 done
3. 收到 aborted 事件（用户主动中断时 expected，其他场景是 bug）
4. 工具调用过程中连接突然断开

按 v0.0.1 plan：
- 适用于 P5 abort 专项测试
- 也可作为通用流稳定性指标
"""
from typing import Any, Dict, List


def detect_stream_interrupt(events: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """检测 SSE 流是否异常中断

    Returns: issue dict 列表，每个包含 type/severity/expected/context
    """
    issues = []

    if not events:
        issues.append({
            "type": "stream_empty",
            "severity": "fail",
            "expected": "non-empty",
            "actual": "0 events",
            "context": "SSE 事件流为空（连接立即断开或服务端未发任何事件）",
        })
        return issues

    # 1. 检查是否有 done 事件
    has_done = any(e.get("type") == "done" for e in events)
    if not has_done:
        issues.append({
            "type": "stream_no_done",
            "severity": "fail",
            "expected": "done event",
            "actual": "no done event in stream",
            "context": f"共 {len(events)} 个事件，最后一个事件类型: {events[-1].get('type', 'unknown')}",
        })

    # 2. 检查 error 事件
    error_events = [e for e in events if e.get("type") == "error"]
    if error_events:
        for e in error_events:
            err_msg = e.get("error", e.get("message", "unknown"))
            issues.append({
                "type": "stream_error_event",
                "severity": "fail",
                "expected": "no error event",
                "actual": f"error: {err_msg}",
                "context": "SSE 流中出现 error 事件（应用错误传播到客户端）",
            })

    # 3. 检查 aborted 事件
    aborted_events = [e for e in events if e.get("type") == "aborted"]
    if aborted_events:
        # aborted 是用户主动中断的合法事件，不一定是 bug
        # 但如果是 non-P5 测试中出现了，说明是异常中断
        issues.append({
            "type": "stream_aborted",
            "severity": "warn",
            "expected": "no aborted (unless P5 test)",
            "actual": f"{len(aborted_events)} aborted events",
            "context": "流被主动中断（用户 stop / 连接断开）",
        })

    # 4. 检查 text_delta 之后是否立即 done（没有 synthesis_start）
    # 仅当 text_delta 数量 > 5（说明有真正综合阶段）才检查
    text_count = sum(1 for e in events if e.get("type") == "text_delta")
    has_synthesis = any(e.get("type") == "synthesis_start" for e in events)
    if text_count > 5 and not has_synthesis:
        issues.append({
            "type": "stream_text_without_synthesis",
            "severity": "warn",
            "expected": "synthesis_start before many text_delta",
            "actual": f"{text_count} text_delta but no synthesis_start",
            "context": f"text_delta 出现 {text_count} 次但缺少 synthesis_start 阶段标记（短回复可豁免）",
        })

    return issues


# 测试代码（仅在直接运行此文件时执行）
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        ("正常 done 流", [
            {"type": "intent_detected"}, {"type": "text_delta", "delta": "你好"},
            {"type": "done", "duration_ms": 1234}
        ]),
        ("缺 done 流", [
            {"type": "intent_detected"}, {"type": "text_delta", "delta": "你好"}
        ]),
        ("error 事件", [
            {"type": "intent_detected"}, {"type": "error", "error": "Claude API 500"},
        ]),
        ("空流", []),
        ("aborted 流", [
            {"type": "text_delta", "delta": "你好"}, {"type": "aborted"}
        ]),
    ]

    for name, events in test_cases:
        print(f"\n=== {name} ===")
        issues = detect_stream_interrupt(events)
        if not issues:
            print("  ✓ 通过")
        else:
            for issue in issues:
                print(f"  [{issue['severity']}] {issue['type']}: {issue['context']}")
