"""
pricing_accuracy_detector.py — 价格准确性检测器 (W73 第 1 批 C-1 商业化检测器 4/6, 锚点范式第 240 守恒)

检测 LLM agent 返回的价格/计费信息是否准确:
  - 价格金额格式 (¥/$/€ + 数字)
  - 币种标识 (RMB/USD/EUR)
  - 价格区间 (range vs point)
  - 计费单位 (月/年/次)
  - 价格变动 (历史/当前)

商业化计算准确性核心: content_billing_calc 子维度评分依据.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# 价格格式正则 (支持 ¥/$/€ + 数字 + 可选小数)
_PRICE_PATTERN = re.compile(
    r"(?:¥|￥|\$|€|￥|RMB|USD|EUR)\s*(\d+(?:[,]\d{3})*(?:\.\d{1,2})?)"
    r"|(\d+(?:[,]\d{3})*(?:\.\d{1,2})?)\s*(?:元|RMB|USD|EUR)",
    re.IGNORECASE,
)

# 纯数字 + 单位模式 (如 99 元, 99/月)
_PRICE_UNIT_PATTERN = re.compile(
    r"(\d+(?:[,]\d{3})*(?:\.\d{1,2})?)\s*(元|块|RMB|美元|USD|EUR)(?:/(月|年|次|天))?",
    re.IGNORECASE,
)

# 计费单位关键词
_BILLING_UNIT_KEYWORDS = [
    "月", "年", "次", "天", "周", "季度",
    "monthly", "yearly", "annual", "per month", "per year",
]


def extract_prices(text: str) -> List[Dict[str, Any]]:
    """从文本中提取所有价格信息.

    Returns:
        List[{amount, currency, unit, raw_match}]
    """
    if not text:
        return []

    prices = []

    # 货币符号 → ISO 代码映射
    currency_map = {
        "¥": "CNY",
        "￥": "CNY",
        "$": "USD",
        "€": "EUR",
        "元": "CNY",
        "块": "CNY",
        "RMB": "CNY",
        "USD": "USD",
        "EUR": "EUR",
    }

    # 标准格式 (¥/$/€ + 数字, 可选 /月 /年 /次 /天)
    standard_pattern = re.compile(
        r"(¥|￥|\$|€)\s*(\d+(?:[,]\d{3})*(?:\.\d{1,2})?)"
        r"(?:\s*/\s*(月|年|次|天|周|季度))?"
    )
    for match in standard_pattern.finditer(text):
        currency_symbol = match.group(1)
        amount_str = match.group(2)
        unit = match.group(3) or "unknown"
        amount = float(amount_str.replace(",", ""))
        prices.append({
            "amount": amount,
            "currency": currency_map.get(currency_symbol, currency_symbol),
            "unit": unit,
            "raw_match": match.group(0),
        })

    # 数字 + 元/USD 等格式 (99 元, 99 RMB, 99 USD/月)
    for match in _PRICE_UNIT_PATTERN.finditer(text):
        amount = float(match.group(1).replace(",", ""))
        currency_text = match.group(2)
        unit = match.group(3) or "unknown"
        currency = currency_map.get(currency_text.upper(), currency_text.upper())
        prices.append({
            "amount": amount,
            "currency": currency,
            "unit": unit,
            "raw_match": match.group(0),
        })

    return prices


def detect_pricing_accuracy(
    response: str,
    expected_prices: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """检测价格准确性.

    Args:
        response: LLM agent 的回复
        expected_prices: 期望价格列表 [{amount, currency, unit}, ...]

    Returns:
        {
            "found_prices": List[Dict],
            "expected_prices": List[Dict],
            "matched_prices": List[Dict],
            "missing_prices": List[Dict],
            "format_compliant": bool,
            "format_issues": List[str],
            "accuracy_score": float [0, 1]
        }
    """
    found = extract_prices(response)
    expected = expected_prices or []

    # 格式合规检查
    format_issues: List[str] = []
    if response and any(kw in response for kw in ["价格", "费用", "收费", "订阅费", "price"]):
        # 提到了价格/费用但没找到任何价格 → 格式问题
        if not found:
            format_issues.append("mentioned_price_but_no_amount_found")

    # 金额格式必须 ≥ 1 种合理格式
    has_currency = any(p["currency"] != "unknown" for p in found)
    has_number = any(p["amount"] > 0 for p in found)
    if found and not (has_currency and has_number):
        format_issues.append("incomplete_price_format")

    format_compliant = len(format_issues) == 0

    # 价格匹配检查
    matched: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []

    if expected:
        for exp in expected:
            matched_flag = False
            for f in found:
                if (
                    abs(f["amount"] - exp["amount"]) < 0.01
                    and f["currency"] == exp.get("currency", "CNY")
                ):
                    matched.append({"expected": exp, "found": f})
                    matched_flag = True
                    break
            if not matched_flag:
                missing.append(exp)

        # accuracy_score = matched / expected
        if expected:
            accuracy_score = len(matched) / len(expected)
        else:
            accuracy_score = 1.0 if not found else 0.5
    else:
        # 无期望价格 → 只看格式合规
        accuracy_score = 1.0 if format_compliant else 0.5

    # 格式不合规扣分
    if not format_compliant:
        accuracy_score *= 0.7

    return {
        "found_prices": found,
        "expected_prices": expected,
        "matched_prices": matched,
        "missing_prices": missing,
        "format_compliant": format_compliant,
        "format_issues": format_issues,
        "accuracy_score": round(accuracy_score, 4),
    }