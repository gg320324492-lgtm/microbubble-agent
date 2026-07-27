"""
commercial_compliance_detector.py — 商业化合规检测器 (W73 第 1 批 C-1 商业化检测器 5/6, 锚点范式第 240 守恒)

检测 LLM agent 是否违反商业化合规规则:
  - 退款政策 (refund policy) 错误承诺
  - 价格透明度 (价格未明示币种/单位)
  - 服务条款引用 (ToS 必含)
  - 自动续费告知 (auto-renewal disclosure)
  - 隐私政策链接 (privacy policy)
  - 取消订阅路径 (cancellation path)

商业化合规核心: defense_compliance + rich_billing_field 联合评分依据.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# 合规关键词
COMPLIANCE_KEYWORDS = {
    "refund_policy": ["退款", "退订", "7天无理由", "退款政策", "refund", "money-back"],
    "auto_renewal": [
        "自动续费", "自动续订", "到期自动", "取消自动续费",
        "auto-renew", "auto renewal", "cancel auto-renew",
    ],
    "privacy_policy": ["隐私政策", "隐私声明", "隐私", "privacy policy", "privacy"],
    "cancellation": [
        "取消订阅", "取消订购", "退订", "如何取消", "关闭订阅",
        "cancel subscription", "unsubscribe", "cancel plan",
    ],
    "terms_of_service": [
        "服务条款", "用户协议", "terms of service", "user agreement",
        "terms and conditions",
    ],
    "billing_cycle": [
        "计费周期", "账单周期", "扣款日", "出账日",
        "billing cycle", "billing date", "charged on",
    ],
}

# 编译所有关键词为单一正则
_ALL_KEYWORDS: List[str] = []
for keyword_list in COMPLIANCE_KEYWORDS.values():
    _ALL_KEYWORDS.extend(keyword_list)
_COMPLIANCE_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _ALL_KEYWORDS), re.IGNORECASE
)


def detect_compliance_mentions(response: str) -> Dict[str, Any]:
    """检测响应中提到了哪些合规要素.

    Returns:
        {
            "mentioned_categories": Set[str],
            "missing_categories": Set[str],
            "compliance_coverage": float [0, 1],
            "matched_keywords": List[str]
        }
    """
    if not response:
        return {
            "mentioned_categories": set(),
            "missing_categories": set(COMPLIANCE_KEYWORDS.keys()),
            "compliance_coverage": 0.0,
            "matched_keywords": [],
        }

    matched_keywords = list(set(_COMPLIANCE_PATTERN.findall(response)))

    mentioned: Set[str] = set()
    for category, kws in COMPLIANCE_KEYWORDS.items():
        if any(kw in response for kw in kws):
            mentioned.add(category)

    missing = set(COMPLIANCE_KEYWORDS.keys()) - mentioned
    coverage = len(mentioned) / len(COMPLIANCE_KEYWORDS)

    return {
        "mentioned_categories": mentioned,
        "missing_categories": missing,
        "compliance_coverage": round(coverage, 4),
        "matched_keywords": matched_keywords,
    }


def detect_compliance_violation(
    response: str,
    *,
    required_categories: List[str] = None,
    commercial_query: bool = False,
) -> Dict[str, Any]:
    """检测商业化合规违规.

    Args:
        response: LLM agent 的回复
        required_categories: 商业化场景必含的合规类别 (默认 refund_policy + auto_renewal)
        commercial_query: 是否为商业化查询

    Returns:
        {
            "is_violated": bool,
            "violations": List[str],
            "coverage": float [0, 1],
            "required_coverage_met": bool
        }
    """
    required = required_categories or ["refund_policy"]
    mentions = detect_compliance_mentions(response)
    coverage = mentions["compliance_coverage"]

    violations: List[str] = []

    # 1. 商业化查询必含 refund_policy
    if commercial_query:
        missing_required = [c for c in required if c not in mentions["mentioned_categories"]]
        if missing_required:
            violations.append(
                f"commercial_missing_required_disclosure: {missing_required}"
            )

    # 2. 自动续费未告知 (subscription/plan 类查询必含)
    if commercial_query and "auto_renewal" in required:
        if "auto_renewal" not in mentions["mentioned_categories"]:
            if any(kw in response for kw in ["订阅", "续费", "自动", "subscribe", "renew"]):
                violations.append("auto_renewal_disclosure_missing")

    # 3. 隐私政策链接缺失 (合规底线)
    if commercial_query and "privacy_policy" in required:
        if "privacy_policy" not in mentions["mentioned_categories"]:
            violations.append("privacy_policy_disclosure_missing")

    is_violated = len(violations) > 0
    required_coverage_met = all(
        c in mentions["mentioned_categories"] for c in required
    )

    return {
        "is_violated": is_violated,
        "violations": violations,
        "coverage": coverage,
        "required_coverage_met": required_coverage_met,
    }


def is_compliant_response(
    response: str,
    *,
    commercial_query: bool = True,
    required_categories: List[str] = None,
) -> bool:
    """快速判断: 响应是否合规."""
    result = detect_compliance_violation(
        response,
        required_categories=required_categories,
        commercial_query=commercial_query,
    )
    return not result["is_violated"]