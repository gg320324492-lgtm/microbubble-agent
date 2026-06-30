"""
detectors/tool_error_propagated.py — 工具错误传播检测器 (P0)

检测工具（@tool）错误是否被"原样"传播到用户响应里。
CLAUDE.md 2026-06-15 教训: LLM hallucinate 借口（"系统故障"/"数据同步中"等）
检测的是工具出错后，LLM 是否"撒谎"把错误归因于系统/技术问题。

检测规则：
1. 工具返回 status="error" 或 exception 字段，但 LLM 回答里出现借口话术
2. 工具返回字段含 traceback / stack trace 直接暴露给用户
3. 工具返回内含数据库错误码（如 'duplicate key', 'foreign key constraint'）
"""
import re
from typing import Any, Dict, List


# LLM 常见"借口"话术（与 placeholder_text 不同 — 这里是"出错时的归因谎言"）
LLM_EXCUSE_PATTERNS = [
    re.compile(r"系统.{0,5}(故障|维护|升级|异常)", re.IGNORECASE),
    re.compile(r"数据库.{0,5}(故障|连接|异常|同步中)", re.IGNORECASE),
    re.compile(r"技术(问题|故障|原因)", re.IGNORECASE),
    re.compile(r"数据(同步|加载|获取)中", re.IGNORECASE),
    re.compile(r"请(联系管理员|稍后再试|稍后重试)", re.IGNORECASE),
    re.compile(r"暂时无法.{0,10}(查询|访问|处理)", re.IGNORECASE),
    re.compile(r"(网络|服务)异常", re.IGNORECASE),
    re.compile(r"(技术原因|技术问题)导致", re.IGNORECASE),
    re.compile(r"API.{0,5}(超时|限流|失败)", re.IGNORECASE),
    re.compile(r"工单|工单系统|工单处理", re.IGNORECASE),
]

# 技术细节泄露模式（应被 LLM 兜底过滤）
TECHNICAL_LEAK_PATTERNS = [
    re.compile(r"Traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r"asyncpg\.exceptions\.", re.IGNORECASE),
    re.compile(r"sqlalchemy\.exc\.", re.IGNORECASE),
    re.compile(r"KeyError: |AttributeError: |TypeError: |ValueError: ", re.IGNORECASE),
    re.compile(r"duplicate key value violates unique constraint", re.IGNORECASE),
    re.compile(r"foreign key constraint", re.IGNORECASE),
    re.compile(r"null value in column .* violates not-null constraint", re.IGNORECASE),
    re.compile(r"AttributeError: 'NoneType' object has no attribute", re.IGNORECASE),
    re.compile(r"Internal Server Error \(500\)", re.IGNORECASE),
    re.compile(r"connection refused|timed out|ECONNREFUSED", re.IGNORECASE),
]


def detect_tool_error_propagated(
    content: str,
    tool_results: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """检测工具错误是否被 LLM 撒谎/泄露给用户

    Args:
        content: LLM 完整回复文本
        tool_results: 工具调用结果列表 (从 SSE 事件解析)

    Returns: issue dict 列表
    """
    issues = []

    # 1. 找工具错误（status=error 或 exception 字段）
    error_tools = []
    for tr in tool_results:
        result = tr.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("status") == "error" or "exception" in result:
            error_tools.append(tr.get("name", "unknown_tool"))

    if not error_tools:
        # 工具没出错，但 LLM 仍编借口 → LLM hallucinate
        for pat in LLM_EXCUSE_PATTERNS:
            m = pat.search(content)
            if m:
                issues.append({
                    "type": "llm_excuse_no_tool_error",
                    "severity": "fail",
                    "expected": "no excuse when tool succeeded",
                    "actual": f"LLM 编造借口: '{m.group(0)}'",
                    "context": "工具调用成功但 LLM 仍借口系统故障（典型 LLM hallucinate）",
                })
                break  # 一次只报一个
    else:
        # 工具真出错时，检测借口话术（合理但不能太具体）
        for pat in LLM_EXCUSE_PATTERNS:
            m = pat.search(content)
            if m:
                issues.append({
                    "type": "tool_error_with_excuse",
                    "severity": "warn",
                    "expected": "honest error message",
                    "actual": f"LLM 使用借口话术: '{m.group(0)}'",
                    "context": f"工具 ({', '.join(error_tools)}) 真出错，LLM 用借口话术（应诚实说明）",
                })
                break

    # 2. 任何场景下都不能泄露技术细节
    for pat in TECHNICAL_LEAK_PATTERNS:
        m = pat.search(content)
        if m:
            issues.append({
                "type": "technical_leak",
                "severity": "fail",
                "expected": "no technical error exposed to user",
                "actual": f"技术细节泄露: '{m.group(0)}'",
                "context": "工具错误的技术细节（traceback / DB error / 库异常）暴露给用户",
            })
            break

    return issues


# 测试代码
if __name__ == "__main__":
    test_cases = [
        ("工具成功 + LLM 借口", "抱歉系统故障了，请稍后再试。", [
            {"name": "query_members", "result": {"members": [{"name": "杨慈"}]}}
        ]),
        ("工具失败 + LLM 借口", "系统异常无法查询。", [
            {"name": "query_members", "result": {"status": "error", "exception": "DB timeout"}}
        ]),
        ("技术细节泄露", "Traceback (most recent call last): ...", []),
        ("正常回答", "杨慈是博一学生。", [
            {"name": "query_members", "result": {"members": [{"name": "杨慈"}]}}
        ]),
    ]

    for name, content, tool_results in test_cases:
        print(f"\n=== {name} ===")
        issues = detect_tool_error_propagated(content, tool_results)
        if not issues:
            print("  ✓ 通过")
        else:
            for issue in issues:
                print(f"  [{issue['severity']}] {issue['type']}: {issue['context']}")
