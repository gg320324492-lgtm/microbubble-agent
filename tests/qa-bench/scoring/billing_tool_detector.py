"""
billing_tool_detector.py — 计费工具调用检测器 (W73 第 1 批 C-1 商业化检测器 2/6, 锚点范式第 238 守恒)

检测 LLM agent 是否正确调用了计费/订阅相关工具:
  - billing_* 前缀工具
  - commercial_* 前缀工具
  - subscription_* 前缀工具
  - invoice_* 前缀工具

误调用 (无商业化意图却调) → 扣分
漏调用 (有商业化意图却没调) → 一票否决前置
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# 计费/商业化工具前缀
BILLING_TOOL_PREFIXES = (
    "billing_",
    "commercial_",
    "subscription_",
    "invoice_",
    "payment_",
    "pricing_",
    "plan_",
    "tenant_",
    "license_",
)

# 编译正则 (匹配工具名前缀)
_BILLING_TOOL_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(p) for p in BILLING_TOOL_PREFIXES) + r")[a-zA-Z_]+$"
)


def is_billing_tool(tool_name: str) -> bool:
    """判断工具名是否为计费/商业化工具."""
    if not tool_name or not isinstance(tool_name, str):
        return False
    return bool(_BILLING_TOOL_PATTERN.match(tool_name))


def extract_billing_tools(tool_calls: List[str]) -> Set[str]:
    """从工具调用列表中提取所有计费/商业化工具."""
    if not tool_calls:
        return set()
    return {t for t in tool_calls if is_billing_tool(t)}


def detect_billing_tool_usage(
    tool_calls: List[str],
    expected_billing_tools: List[str] = None,
    *,
    allow_extra: bool = True,
) -> Dict[str, Any]:
    """检测计费工具调用合规性.

    Args:
        tool_calls: 实际调用的工具列表
        expected_billing_tools: 期望调用的计费工具列表 (None = 不强制)
        allow_extra: 是否允许额外计费工具调用 (False = 严格匹配)

    Returns:
        {
            "called_billing_tools": List[str],
            "missing_billing_tools": List[str],
            "extra_billing_tools": List[str],
            "is_compliant": bool,
            "compliance_score": float [0, 1]
        }
    """
    called = extract_billing_tools(tool_calls)
    expected_set = set(expected_billing_tools or [])

    missing = list(expected_set - called)
    extra = list(called - expected_set) if not allow_extra else []

    is_compliant = len(missing) == 0 and len(extra) == 0

    # 合规分: precision + recall 加权
    if expected_set:
        precision = len(called & expected_set) / len(called) if called else 0.0
        recall = len(called & expected_set) / len(expected_set) if expected_set else 0.0
        compliance_score = (
            2 * precision * recall / (precision + recall)
            if precision + recall > 0
            else 0.0
        )
    else:
        # 无期望 → 不调用得满分, 误调用扣分
        compliance_score = 1.0 if not called else max(0.3, 1.0 - 0.2 * len(called))

    # 额外工具惩罚
    if extra:
        compliance_score *= max(0.5, 1.0 - 0.15 * len(extra))

    return {
        "called_billing_tools": sorted(called),
        "missing_billing_tools": sorted(missing),
        "extra_billing_tools": sorted(extra),
        "is_compliant": is_compliant,
        "compliance_score": round(compliance_score, 4),
    }