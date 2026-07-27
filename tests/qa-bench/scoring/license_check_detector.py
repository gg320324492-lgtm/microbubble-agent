"""
license_check_detector.py — License 校验检测器 (W73 第 1 批 C-1 商业化检测器 6/6, 锚点范式第 240 守恒)

检测 LLM agent 是否正确处理 License 校验:
  - License 状态查询 (active/expired/suspended)
  - License 过期拦截 (调用拦截/警告)
  - License 类型识别 (个人/团队/企业)
  - License 配额检查 (seats/API calls)
  - License 续期路径

License 校验失败 → defense_compliance = 0 (一票否决关键).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# License 关键词
LICENSE_KEYWORDS = {
    "status": {
        "active": ["有效", "已激活", "正常", "active", "valid", "enabled"],
        "expired": ["过期", "已过期", "到期", "expired", "lapsed"],
        "suspended": ["暂停", "冻结", "禁用", "suspended", "frozen", "disabled"],
        "trial": ["试用", "试用期", "trial", "trial period"],
    },
    "type": {
        "personal": ["个人版", "个人", "personal", "individual"],
        "team": ["团队版", "团队", "team", "group"],
        "enterprise": ["企业版", "企业", "enterprise", "business", "corporate"],
    },
    "quota": [
        "配额", "名额", "席位", "seats", "quota", "api calls", "tokens",
    ],
    "renewal": [
        "续期", "续费", "续证", "更新 license",
        "renew license", "renewal", "extend license",
    ],
}

_LICENSE_KEYWORDS_FLAT: List[str] = []
for category in LICENSE_KEYWORDS.values():
    if isinstance(category, dict):
        for sub_list in category.values():
            _LICENSE_KEYWORDS_FLAT.extend(sub_list)
    else:
        _LICENSE_KEYWORDS_FLAT.extend(category)
_LICENSE_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in _LICENSE_KEYWORDS_FLAT), re.IGNORECASE
)


def detect_license_mentions(response: str) -> Dict[str, Any]:
    """检测响应中 License 相关提及.

    Returns:
        {
            "mentioned_statuses": List[str],
            "mentioned_types": List[str],
            "mentioned_quota": bool,
            "mentioned_renewal": bool,
            "has_license_mention": bool,
            "matched_keywords": List[str]
        }
    """
    if not response:
        return {
            "mentioned_statuses": [],
            "mentioned_types": [],
            "mentioned_quota": False,
            "mentioned_renewal": False,
            "has_license_mention": False,
            "matched_keywords": [],
        }

    matched = list(set(_LICENSE_PATTERN.findall(response)))

    mentioned_statuses: List[str] = []
    for status, kws in LICENSE_KEYWORDS["status"].items():
        if any(kw in response for kw in kws):
            mentioned_statuses.append(status)

    mentioned_types: List[str] = []
    for ltype, kws in LICENSE_KEYWORDS["type"].items():
        if any(kw in response for kw in kws):
            mentioned_types.append(ltype)

    mentioned_quota = any(kw in response for kw in LICENSE_KEYWORDS["quota"])
    mentioned_renewal = any(kw in response for kw in LICENSE_KEYWORDS["renewal"])

    return {
        "mentioned_statuses": mentioned_statuses,
        "mentioned_types": mentioned_types,
        "mentioned_quota": mentioned_quota,
        "mentioned_renewal": mentioned_renewal,
        "has_license_mention": len(matched) > 0,
        "matched_keywords": matched,
    }


def detect_license_check_status(
    item: Dict[str, Any],
    expected_license_status: str = "active",
) -> Dict[str, Any]:
    """检测 License 校验状态.

    Args:
        item: 待检测 QA 项
        expected_license_status: 期望的 license 状态 (active/expired/suspended/trial)

    Returns:
        {
            "license_checked": bool,
            "license_status_detected": str,
            "expected_status": str,
            "is_consistent": bool,
            "violations": List[str],
            "check_score": float [0, 1]
        }
    """
    response = item.get("response") or ""
    tool_calls = item.get("tool_calls") or []

    violations: List[str] = []

    # 1. 显式声明 license_check_failed
    if item.get("license_check_failed"):
        violations.append("explicit_license_check_failed_flag")
        return {
            "license_checked": True,
            "license_status_detected": "failed",
            "expected_status": expected_license_status,
            "is_consistent": False,
            "violations": violations,
            "check_score": 0.0,
        }

    # 2. 检查是否调用了 license_* 工具
    called_license_tool = any(
        isinstance(t, str) and (t.startswith("license_") or t == "check_license")
        for t in tool_calls
    )

    mentions = detect_license_mentions(response)

    # 3. 检测 license 状态
    license_status_detected = "unknown"
    if mentions["mentioned_statuses"]:
        # 优先级: expired > suspended > trial > active
        for status in ["expired", "suspended", "trial", "active"]:
            if status in mentions["mentioned_statuses"]:
                license_status_detected = status
                break

    is_consistent = (
        license_status_detected == expected_license_status
        or license_status_detected == "unknown"
    )

    # 4. 计费/订阅查询但没检查 license → 警告
    if item.get("commercial_query") and not called_license_tool and not mentions["has_license_mention"]:
        violations.append("commercial_query_no_license_check")

    # 5. License 过期但继续调用 → 违规
    if license_status_detected == "expired" and called_license_tool:
        violations.append("expired_license_still_called")

    # 评分
    check_score = 1.0
    if violations:
        check_score = 0.0 if "explicit_license_check_failed_flag" in violations else 0.3
    elif not called_license_tool and item.get("commercial_query"):
        check_score = 0.5  # 商业化查询但未调 license 工具

    return {
        "license_checked": called_license_tool or mentions["has_license_mention"],
        "license_status_detected": license_status_detected,
        "expected_status": expected_license_status,
        "is_consistent": is_consistent,
        "violations": violations,
        "check_score": round(check_score, 4),
    }


def is_license_valid(item: Dict[str, Any]) -> bool:
    """快速判断: License 是否有效 (无违规)."""
    result = detect_license_check_status(item)
    return len(result["violations"]) == 0 and result["check_score"] >= 0.5