"""
subscription_intent_detector.py — 订阅意图检测器 (W73 第 1 批 C-1 商业化检测器 1/6, 锚点范式第 237 守恒)

检测用户查询中是否包含订阅意图关键词, 用于:
  - intent 子维度评分 (商业化意图识别)
  - 路由分发 (订阅页/订阅查询)
  - 一票否决前置检查 (无订阅意图但调用 billing_* 工具 = 误调用)

支持中英文 + 实验室常用术语 (课题组/团队版/订阅/续费).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# 订阅意图关键词 (中英文 + 课题组常用术语)
SUBSCRIPTION_KEYWORDS_ZH = [
    "订阅", "开通", "开通订阅", "续费", "续订", "套餐", "套餐升级", "套餐降级",
    "团队版", "个人版", "企业版", "免费试用", "试用", "开通会员", "会员",
    "购买", "付费", "订购", "预付费", "按月付费", "按年付费", "包月", "包年",
    "激活", "激活码", "邀请码", "兑换码",
]

SUBSCRIPTION_KEYWORDS_EN = [
    "subscribe", "subscription", "renew", "renewal", "plan", "package",
    "team plan", "personal plan", "enterprise plan", "free trial", "trial",
    "membership", "vip", "premium", "pro", "activate", "activation code",
    "invite code", "redeem", "redeem code", "monthly", "yearly", "annual",
]

# 编译正则 (大小写不敏感)
_SUBSCRIPTION_PATTERN = re.compile(
    "|".join(
        [re.escape(kw) for kw in SUBSCRIPTION_KEYWORDS_ZH]
        + SUBSCRIPTION_KEYWORDS_EN
    ),
    re.IGNORECASE,
)


def detect_subscription_intent(query: str) -> Dict[str, Any]:
    """检测查询中是否包含订阅意图.

    Args:
        query: 用户查询字符串

    Returns:
        {
            "has_subscription_intent": bool,
            "matched_keywords": List[str],
            "confidence": float [0, 1],
            "category": "subscribe" | "renew" | "plan_change" | "trial" | "none"
        }
    """
    if not query or not isinstance(query, str):
        return {
            "has_subscription_intent": False,
            "matched_keywords": [],
            "confidence": 0.0,
            "category": "none",
        }

    # 找出所有匹配的关键词
    matches = _SUBSCRIPTION_PATTERN.findall(query)
    matched_keywords = list(set(matches))

    has_intent = bool(matched_keywords)
    # 置信度: 关键词数量越多置信度越高 (但 cap 在 0.95)
    confidence = min(0.5 + len(matched_keywords) * 0.15, 0.95) if has_intent else 0.0

    # 分类
    category = "none"
    if has_intent:
        query_lower = query.lower()
        if any(kw in query for kw in ["续费", "续订", "renew", "renewal"]):
            category = "renew"
        elif any(kw in query for kw in ["升级", "降级", "切换套餐", "upgrade", "downgrade"]):
            category = "plan_change"
        elif any(kw in query for kw in ["试用", "免费试用", "trial"]):
            category = "trial"
        else:
            category = "subscribe"

    return {
        "has_subscription_intent": has_intent,
        "matched_keywords": matched_keywords,
        "confidence": round(confidence, 2),
        "category": category,
    }


def is_subscription_query(query: str, *, min_confidence: float = 0.5) -> bool:
    """快速判断: 查询是否包含订阅意图 (置信度 >= min_confidence)."""
    result = detect_subscription_intent(query)
    return result["has_subscription_intent"] and result["confidence"] >= min_confidence