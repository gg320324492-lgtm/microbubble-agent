"""
twelve_dim_v4.py — qa-bench 12 子维度商业化评分 (W73 第 1 批 C-1 核心交付物, 锚点范式 W72 第 2 批 235 → W73 第 1 批 C-1 241 守恒 +1)

12 子维度 = 7 维主框架拆 6 维各 2 子维度:
  1. intent (8%)          — 意图识别 (基础意图稳定, 不拆)
  2. tool_choice (12%)    — 工具选择子维度 (基础工具 F1)
  3. tool_billing_semantic (6%) — 商业化工具语义 (billing_*/commercial_* 工具调用是否合规)
  4. content_factual (20%) — 内容事实准确性 (基础)
  5. content_billing_calc (10%) — 商业化计算准确性 (价格/计费术语)
  6. rich_basic (6%)      — Rich Block 基础合规
  7. rich_billing_field (4%) — Rich Block 商业化字段 (套餐卡片/计费 chip)
  8. defense_basic (10%)  — 防御性基础 (安全/权限/越权)
  9. defense_compliance (8%) — 商业化合规 (租户隔离/license 校验)
  10. perf_latency (6%)   — 延迟 SLA
  11. perf_billing_sync (4%) — 计费网关同步 SLA
  12. consistency (6%)    — 多轮上下文一致 (跨场景稳定, 不拆)

权重和约束:
  - 12 个子维度权重和 = 1.00 (强制, sum=1.00 校验, 偏差 > 1e-9 即拒)
  - 关键维度 fail 一票否决 (commercial critical-dimension): 计费/订阅/多租户
  - veto_thresholds:
    - content_factual < 0.5 → FAIL (内容核心)
    - defense_compliance < 0.7 → FAIL (商业化合规: 计费/订阅/多租户)
    - content_billing_calc < 0.6 → FAIL (商业化计算)

A-F 分级 (基于 weighted_total × 100):
  A 90-100 / B 75-89 / C 60-74 / D 40-59 / F <40

输入约定:
  item:    dict (e2e response + tool_calls + rich_blocks + billing_context 等)
  weights: dict[str, float] — 12 子维度权重 (sum=1.0)
  benchmark: dict (expected_intent + expected_tools + content_keywords + billing_keywords + max_latency_ms + billing_sla_ms)

输出:
  result: dict 含 grade, total_score, scores (12 子维度), veto 字段

向后兼容:
  score_12d_item() 接受 v3 7 维 dict, 自动迁移 (子维度 = 父维度 × 父权重, 商业化部分由 benchmark 推断)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

# 12 子维度固定顺序 (决定 weights_v4.json 加权时的遍历顺序)
TWELVE_DIMENSIONS: Tuple[str, ...] = (
    "intent",                  # 8%
    "tool_choice",             # 12%
    "tool_billing_semantic",   # 6%
    "content_factual",         # 20%
    "content_billing_calc",    # 10%
    "rich_basic",              # 6%
    "rich_billing_field",      # 4%
    "defense_basic",           # 10%
    "defense_compliance",      # 8%
    "perf_latency",            # 6%
    "perf_billing_sync",       # 4%
    "consistency",             # 6%
)

# 默认权重 (与 weights_v4.json 对齐, 可被外部 override)
DEFAULT_WEIGHTS_V4: Dict[str, float] = {
    "intent": 0.08,
    "tool_choice": 0.12,
    "tool_billing_semantic": 0.06,
    "content_factual": 0.20,
    "content_billing_calc": 0.10,
    "rich_basic": 0.06,
    "rich_billing_field": 0.04,
    "defense_basic": 0.10,
    "defense_compliance": 0.08,
    "perf_latency": 0.06,
    "perf_billing_sync": 0.04,
    "consistency": 0.06,
}

# 一票否决阈值 (commercial critical-dimension)
DEFAULT_VETO_THRESHOLDS_V4: Dict[str, float] = {
    "content_factual": 0.5,         # 内容核心
    "defense_compliance": 0.7,      # 商业化合规 (计费/订阅/多租户)
    "content_billing_calc": 0.6,    # 商业化计算
}

# A-F 分级阈值
DEFAULT_GRADE_THRESHOLDS_V4: Dict[str, float] = {
    "A": 90.0,
    "B": 75.0,
    "C": 60.0,
    "D": 40.0,
}


def load_weights_v4(path: str | Path = None) -> Dict[str, Any]:
    """从 weights_v4.json 加载完整配置 (含 weights + veto_thresholds + grade_thresholds).

    默认路径: tests/qa-bench/scoring/weights_v4.json
    返回 dict 含 'weights', 'veto_thresholds', 'grade_thresholds', 'version' 四个字段.
    """
    if path is None:
        path = Path(__file__).resolve().parent / "weights_v4.json"
    else:
        path = Path(path)

    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)

    weights = cfg.get("weights", DEFAULT_WEIGHTS_V4)
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > 1e-9:
        raise ValueError(
            f"weights_v4.json 权重和 = {weight_sum}, 必须 = 1.0 (±1e-9). "
            f"请检查 {path}"
        )

    missing = set(TWELVE_DIMENSIONS) - set(weights.keys())
    if missing:
        raise ValueError(
            f"weights_v4.json 缺少子维度: {sorted(missing)}, 必须含 {TWELVE_DIMENSIONS}"
        )

    return {
        "version": cfg.get("version", "4.0"),
        "weights": dict(weights),
        "veto_thresholds": dict(cfg.get("veto_thresholds", DEFAULT_VETO_THRESHOLDS_V4)),
        "grade_thresholds": dict(cfg.get("grade_thresholds", DEFAULT_GRADE_THRESHOLDS_V4)),
    }


def check_veto_v4(scores: Mapping[str, float],
                  veto_thresholds: Mapping[str, float] = None) -> Dict[str, Any] | None:
    """关键子维度 fail 一票否决.

    Returns:
        None if pass (no veto)
        {"triggered": True, "dimension": "<sub_dim>", "score": <x>, "threshold": <y>,
         "reason": "<sub_dim>_below_threshold", "category": "commercial_critical"}
        if veto triggered
    """
    veto_thresholds = veto_thresholds or DEFAULT_VETO_THRESHOLDS_V4
    for dim, threshold in veto_thresholds.items():
        score = scores.get(dim, 0.0)
        if score < threshold:
            # 商业化 critical-dimension 分类
            category = "commercial_critical" if dim in (
                "defense_compliance", "content_billing_calc"
            ) else "core_content"
            return {
                "triggered": True,
                "dimension": dim,
                "score": round(score, 4),
                "threshold": threshold,
                "reason": f"{dim}_below_threshold",
                "category": category,
            }
    return None


def grade_v4(total_score: float,
             grade_thresholds: Mapping[str, float] = None) -> str:
    """A-F 分级 (total_score ∈ [0, 100])."""
    grade_thresholds = grade_thresholds or DEFAULT_GRADE_THRESHOLDS_V4
    if total_score >= grade_thresholds["A"]:
        return "A"
    if total_score >= grade_thresholds["B"]:
        return "B"
    if total_score >= grade_thresholds["C"]:
        return "C"
    if total_score >= grade_thresholds["D"]:
        return "D"
    return "F"


# === 12 子维度打分函数 (各 ∈ [0, 1]) ===

def _score_intent_v4(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """Intent 子维度: 用户意图分类是否命中 + 商业化意图识别 (订阅/计费/多租户)."""
    expected = item.get("expected_intent") or benchmark.get("expected_intent")
    predicted = item.get("predicted_intent")
    if expected is None or predicted is None:
        return 0.0
    return 1.0 if expected == predicted else 0.0


def _score_tool_choice(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """tool_choice 子维度: 工具选择 F1 (排除 billing_*/commercial_* 工具)."""
    expected_tools = set(benchmark.get("expected_tools", []))
    # 过滤 billing_*/commercial_* (由 tool_billing_semantic 子维度评估)
    expected_core = {t for t in expected_tools if not (
        t.startswith("billing_") or t.startswith("commercial_")
    )}
    actual_tools = set(item.get("tool_calls", []))
    actual_core = {t for t in actual_tools if not (
        t.startswith("billing_") or t.startswith("commercial_")
    )}
    if not expected_core:
        return 1.0 if not actual_core else 0.5
    if not actual_core:
        return 0.0
    tp = len(expected_core & actual_core)
    precision = tp / len(actual_core) if actual_core else 0.0
    recall = tp / len(expected_core) if expected_core else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _score_tool_billing_semantic(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """tool_billing_semantic 子维度: 商业化工具调用合规 (billing_*/commercial_*)."""
    expected_billing = set(benchmark.get("expected_billing_tools", []))
    actual_tools = set(item.get("tool_calls", []))
    actual_billing = {t for t in actual_tools if (
        t.startswith("billing_") or t.startswith("commercial_")
    )}
    if not expected_billing:
        # 无期望商业化工具: 不调用得满分, 误调用扣分
        return 1.0 if not actual_billing else 0.3
    if not actual_billing:
        return 0.0
    tp = len(expected_billing & actual_billing)
    precision = tp / len(actual_billing) if actual_billing else 0.0
    recall = tp / len(expected_billing) if expected_billing else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _score_content_factual(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """content_factual 子维度: 内容事实准确性 (排除价格/计费术语)."""
    keywords = benchmark.get("content_keywords", [])
    # 排除计费术语 (由 content_billing_calc 评估)
    billing_terms = set(benchmark.get("billing_keywords", []))
    factual_keywords = [kw for kw in keywords if kw not in billing_terms]
    if not factual_keywords:
        return 1.0
    response = (item.get("response") or "").lower()
    hits = sum(1 for kw in factual_keywords if kw.lower() in response)
    return hits / len(factual_keywords)


def _score_content_billing_calc(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """content_billing_calc 子维度: 价格/计费术语准确性 (商业化关键)."""
    billing_keywords = benchmark.get("billing_keywords", [])
    if not billing_keywords:
        return 1.0
    response = (item.get("response") or "").lower()
    hits = sum(1 for kw in billing_keywords if kw.lower() in response)
    base_score = hits / len(billing_keywords)

    # 额外校验: 计费金额格式必须 ≥ 1 种合理格式 (¥/$/元 + 数字)
    # 如果 item.billing_response 字段存在, 校验格式
    billing_resp = item.get("billing_response")
    if billing_resp and isinstance(billing_resp, str):
        import re
        has_currency = bool(re.search(r'[¥$€￥]|元|RMB|USD', billing_resp))
        has_number = bool(re.search(r'\d+(?:\.\d+)?', billing_resp))
        if not (has_currency and has_number):
            base_score *= 0.5  # 计费格式不规范扣半

    return base_score


def _score_rich_basic(item: Mapping[str, Any]) -> float:
    """rich_basic 子维度: Rich Block 基础合规."""
    known_types = {
        "meeting", "task_list", "knowledge_ref", "member",
        "formula", "hypothesis", "project", "transcript", "chart",
        "file", "audio", "image",
    }
    blocks = item.get("rich_blocks", [])
    if not blocks:
        return 1.0
    valid = 0
    for b in blocks:
        btype = b.get("type") if isinstance(b, dict) else None
        if btype in known_types:
            valid += 1
    return valid / len(blocks)


def _score_rich_billing_field(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """rich_billing_field 子维度: 商业化字段渲染 (套餐卡片/计费 chip)."""
    blocks = item.get("rich_blocks", [])
    if not blocks:
        # 商业化场景期望有套餐卡片但缺失 → 0
        if benchmark.get("expected_billing_blocks"):
            return 0.0
        return 1.0

    expected_billing_types = set(benchmark.get("expected_billing_blocks", [
        "billing_card", "subscription_plan", "invoice_chip", "pricing_table"
    ]))
    actual_billing_types = set()
    for b in blocks:
        if isinstance(b, dict):
            btype = b.get("type", "")
            if btype in expected_billing_types:
                actual_billing_types.add(btype)
            # 检查必需字段 (发票号/税额/金额)
            if btype == "invoice_chip":
                if b.get("invoice_number") and b.get("amount") and b.get("tax"):
                    actual_billing_types.add("invoice_complete")

    if not expected_billing_types:
        return 1.0

    return len(actual_billing_types) / len(expected_billing_types)


def _score_defense_basic(item: Mapping[str, Any]) -> float:
    """defense_basic 子维度: 基础防御 (安全/权限/越权)."""
    if item.get("permission_violation") or item.get("pii_leak"):
        return 0.0
    if item.get("forbidden_tool_called"):
        return 0.0
    return 1.0


def _score_defense_compliance(item: Mapping[str, Any]) -> float:
    """defense_compliance 子维度: 商业化合规 (租户隔离/license 校验) — 关键维度.

    一票否决域: 计费/订阅/多租户 (commercial critical-dimension).
    """
    # 多租户越权 → 直接 0
    if item.get("tenant_violation"):
        return 0.0
    # License 校验失败 → 0
    if item.get("license_check_failed"):
        return 0.0
    # 跨租户调用 → 0
    if item.get("cross_tenant_call"):
        return 0.0

    # 商业化合规字段缺失扣分
    if item.get("commercial_query") and not item.get("compliance_checked"):
        return 0.3

    return 1.0


def _score_perf_latency(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """perf_latency 子维度: 延迟 SLA."""
    latency_ms = item.get("latency_ms")
    max_latency_ms = item.get("max_latency_ms") or benchmark.get("max_latency_ms", 3000)
    if latency_ms is None:
        return 1.0
    if latency_ms <= max_latency_ms:
        return 1.0
    return max(max_latency_ms / latency_ms, 0.0)


def _score_perf_billing_sync(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """perf_billing_sync 子维度: 计费网关同步 SLA (商业化关键).

    计费查询 SLA 默认 1s, 订阅页 SLA 默认 500ms.
    """
    billing_latency_ms = item.get("billing_latency_ms")
    if billing_latency_ms is None:
        return 1.0
    max_billing_ms = benchmark.get("billing_sla_ms", 1000)
    if billing_latency_ms <= max_billing_ms:
        return 1.0
    return max(max_billing_ms / billing_latency_ms, 0.0)


def _score_consistency_v4(item: Mapping[str, Any], benchmark: Mapping[str, Any]) -> float:
    """consistency 子维度: 多轮上下文一致."""
    expected_consistent = benchmark.get("consistent_keywords", [])
    if not expected_consistent:
        return 1.0
    response = (item.get("response") or "").lower()
    hits = sum(1 for kw in expected_consistent if kw.lower() in response)
    return hits / len(expected_consistent)


def score_12d_item(item: Mapping[str, Any],
                   weights: Mapping[str, float] = None,
                   benchmark: Mapping[str, Any] = None,
                   veto_thresholds: Mapping[str, float] = None,
                   grade_thresholds: Mapping[str, float] = None) -> Dict[str, Any]:
    """对单条 QA 结果跑 12 子维度评分 + 一票否决 + A-F 分级.

    Args:
        item: 待评分 QA 项
        weights: 12 子维度权重, 默认使用 DEFAULT_WEIGHTS_V4 (sum=1.0)
        benchmark: 期望 / 参考
        veto_thresholds: 一票否决阈值, 默认 DEFAULT_VETO_THRESHOLDS_V4
        grade_thresholds: A-F 分级阈值, 默认 DEFAULT_GRADE_THRESHOLDS_V4

    Returns:
        {
            "grade": "A"-"F",
            "total_score": float [0, 100],
            "scores": {sub_dim: float [0, 1], ...}  (12 子维度)
            "veto": {triggered, dimension, score, threshold, reason, category} or None,
            "version": "4.0"
        }
    """
    weights = weights or DEFAULT_WEIGHTS_V4
    benchmark = benchmark or {}
    veto_thresholds = veto_thresholds or DEFAULT_VETO_THRESHOLDS_V4
    grade_thresholds = grade_thresholds or DEFAULT_GRADE_THRESHOLDS_V4

    # === Step 1: 12 子维度独立打分 (各 ∈ [0, 1]) ===
    scores: Dict[str, float] = {
        "intent": _score_intent_v4(item, benchmark),
        "tool_choice": _score_tool_choice(item, benchmark),
        "tool_billing_semantic": _score_tool_billing_semantic(item, benchmark),
        "content_factual": _score_content_factual(item, benchmark),
        "content_billing_calc": _score_content_billing_calc(item, benchmark),
        "rich_basic": _score_rich_basic(item),
        "rich_billing_field": _score_rich_billing_field(item, benchmark),
        "defense_basic": _score_defense_basic(item),
        "defense_compliance": _score_defense_compliance(item),
        "perf_latency": _score_perf_latency(item, benchmark),
        "perf_billing_sync": _score_perf_billing_sync(item, benchmark),
        "consistency": _score_consistency_v4(item, benchmark),
    }

    # === Step 2: 一票否决检查 (commercial critical-dimension) ===
    veto = check_veto_v4(scores, veto_thresholds)
    if veto is not None:
        return {
            "grade": "F",
            "total_score": 0.0,
            "scores": {dim: round(scores[dim], 4) for dim in TWELVE_DIMENSIONS},
            "veto": veto,
            "version": "4.0",
        }

    # === Step 3: 加权总分 (sum(score × weight) × 100 ∈ [0, 100]) ===
    total = sum(scores[dim] * weights[dim] for dim in TWELVE_DIMENSIONS) * 100.0

    # === Step 4: A-F 分级 ===
    final_grade = grade_v4(total, grade_thresholds)

    return {
        "grade": final_grade,
        "total_score": round(total, 2),
        "scores": {dim: round(scores[dim], 4) for dim in TWELVE_DIMENSIONS},
        "veto": None,
        "version": "4.0",
    }


def score_12d_batch(items: list,
                    weights: Mapping[str, float] = None,
                    benchmarks: list = None,
                    veto_thresholds: Mapping[str, float] = None,
                    grade_thresholds: Mapping[str, float] = None) -> list:
    """批量 12 子维度评分. 返回 list[dict] 同 score_12d_item 结构."""
    if benchmarks is None:
        benchmarks = [{}] * len(items)
    assert len(items) == len(benchmarks), \
        f"items ({len(items)}) 与 benchmarks ({len(benchmarks)}) 长度必须一致"
    return [
        score_12d_item(item, weights, bench, veto_thresholds, grade_thresholds)
        for item, bench in zip(items, benchmarks)
    ]


def migrate_v3_to_v4_aggregate(scores_v3: Mapping[str, float]) -> Dict[str, float]:
    """v3 7 维 → v4 12 子维度: 父维度分数 × 父权重均分到子维度.

    Args:
        scores_v3: 7 维分数 dict {intent/tool/content/rich_block/defense/perf/consistency}

    Returns:
        12 子维度分数 dict (子维度 = 父维度分数, 因为权重迁移由 weights_v4.json 接管)
    """
    # v4 拆解映射
    return {
        "intent": scores_v3.get("intent", 0.0),
        "tool_choice": scores_v3.get("tool", 0.0),
        "tool_billing_semantic": scores_v3.get("tool", 0.0),  # 默认 fallback
        "content_factual": scores_v3.get("content", 0.0),
        "content_billing_calc": scores_v3.get("content", 0.0),
        "rich_basic": scores_v3.get("rich_block", 0.0),
        "rich_billing_field": scores_v3.get("rich_block", 0.0),
        "defense_basic": scores_v3.get("defense", 0.0),
        "defense_compliance": scores_v3.get("defense", 0.0),
        "perf_latency": scores_v3.get("perf", 0.0),
        "perf_billing_sync": scores_v3.get("perf", 0.0),
        "consistency": scores_v3.get("consistency", 0.0),
    }