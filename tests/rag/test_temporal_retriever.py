"""W100-RAG-6 Temporal Retriever 单测 (15 cases)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.base import utcnow
from app.services.temporal_retriever import TemporalRetriever


def _t():
    return TemporalRetriever()


def test_module_loads():
    """模块可加载 + 类可访问"""
    from app.services import temporal_retriever
    assert hasattr(temporal_retriever, "TemporalRetriever")
    assert hasattr(TemporalRetriever, "compute_temporal_weight")


def test_age_zero_boosts():
    """age=0 (刚刚) → boost 路径, weight ≈ 1.0 + 0.2 = 1.2"""
    now = utcnow()
    w = _t().compute_temporal_weight(now, now=now)
    assert 1.19 <= w <= 1.21


def test_age_one_year_neutral():
    """age=1y → 中间区, ≈ 1.0 (无 boost 无 decay)"""
    now = utcnow()
    w = _t().compute_temporal_weight(now - timedelta(days=365), now=now)
    assert 0.99 <= w <= 1.01


def test_age_two_years_in_transition():
    """age=2y → 边界 (boost_years=2), 应仍在 boost 区 (≤ boost)
    实测公式: base = 0.5 + 0.5 * exp(-2/2) = 0.5 + 0.5 * 0.368 = 0.684, + 0.2 = 0.884
    """
    now = utcnow()
    w = _t().compute_temporal_weight(now - timedelta(days=730), now=now)
    # age=1.9986 < boost_years=2 → boost 路径: base + boost_factor ≈ 0.884
    assert 0.87 <= w <= 0.90


def test_age_five_years_decay_path():
    """age=5y → decay 边界 (5 >= 5), base ≈ 0.5 + 0.5 * exp(-2.5) = 0.541
    × (1 - 0.3) = 0.379
    注意: 精确 5y 因为闰年累计 ≈ 4.999, 走中间区. 5.001y 才走 decay.
    """
    now = utcnow()
    w = _t().compute_temporal_weight(now - timedelta(days=int(365.25 * 5.5)), now=now)
    assert 0.36 <= w <= 0.42


def test_age_ten_years_old():
    """age=10y → 严重衰减, base ≈ 0.5 + 0.5 * exp(-5) = 0.503
    × (1 - 0.3) = 0.352
    """
    now = utcnow()
    w = _t().compute_temporal_weight(now - timedelta(days=int(365.25 * 10)), now=now)
    assert 0.34 <= w <= 0.38


def test_future_time_clamped_to_zero():
    """未来时间 (created_at > now) → 视为 age=0, 走 boost 路径"""
    now = utcnow()
    future = now + timedelta(days=30)
    w = _t().compute_temporal_weight(future, now=now)
    # age=0 → boost → ≈ 1.2
    assert 1.19 <= w <= 1.21


def test_none_created_at_returns_one():
    """None created_at → 中性权重 1.0 (不影响排序)"""
    now = utcnow()
    w = _t().compute_temporal_weight(None, now=now)  # type: ignore[arg-type]
    assert w == 1.0


def test_tz_aware_normalized_to_naive():
    """tz-aware datetime 归一化到 naive UTC (与 app.models.base.utcnow 一致)"""
    t = _t()
    naive_now = utcnow()
    aware_now = naive_now.replace(tzinfo=timezone.utc)
    aware_created = naive_now.replace(tzinfo=timezone.utc)
    w_naive = t.compute_temporal_weight(naive_now, now=naive_now)
    w_aware = t.compute_temporal_weight(aware_created, now=aware_now)
    assert abs(w_naive - w_aware) < 0.001


def test_apply_to_score_multiplies():
    """apply_to_score: score * weight"""
    t = _t()
    now = utcnow()
    s_old = 1.0
    s_new = 1.0
    w_old = t.apply_to_score(s_old, now - timedelta(days=365 * 7), now=now)
    w_new = t.apply_to_score(s_new, now, now=now)
    assert w_new > w_old
    assert abs(w_new - 1.2) < 0.01
    assert abs(w_old - 0.7 * (0.5 + 0.5 * 2.718 ** (-7 / 2))) < 0.05


def test_extreme_age_capped():
    """极端 age (1000y) → exp 趋 0, base → 0.5, 不会爆炸
    实测: base ≈ 0.5, × 0.7 = 0.35
    """
    t = _t()
    now = utcnow()
    ancient = now - timedelta(days=365 * 1000)
    w = t.compute_temporal_weight(ancient, now=now)
    assert 0.0 <= w <= 1.0
    assert 0.30 <= w <= 0.40


def test_boost_factor_zero_no_boost():
    """boost_factor=0 → 新资料不加权"""
    t = _t()
    now = utcnow()
    w_normal = t.compute_temporal_weight(now, now=now)
    w_zero_boost = t.compute_temporal_weight(now, now=now, boost_factor=0.0)
    # w_normal ≈ 1.2, w_zero_boost ≈ 1.0
    assert w_normal > w_zero_boost
    assert abs(w_zero_boost - 1.0) < 0.01


def test_decay_factor_one_kills_old():
    """decay_factor=1.0 → 老资料 weight → 0 (完全压扁)"""
    t = _t()
    now = utcnow()
    w = t.compute_temporal_weight(now - timedelta(days=365 * 10), now=now, decay_factor=1.0)
    # base ≈ 0.35, × (1 - 1.0) = 0
    assert w == 0.0


def test_boost_years_threshold():
    """boost_years=10 → age=5y 进入 boost 区 (≤ 10)"""
    t = _t()
    now = utcnow()
    age_5y = now - timedelta(days=365 * 5)
    w_default = t.compute_temporal_weight(age_5y, now=now)
    w_big_boost = t.compute_temporal_weight(age_5y, now=now, boost_years=10)
    # default 走 decay (5y >= 5y), big_boost 走 boost (5y < 10y)
    assert w_big_boost > w_default


def test_signature_has_default_args():
    """compute_temporal_weight 签名: now/boost_years/... 全 Optional 默认"""
    import inspect
    sig = inspect.signature(TemporalRetriever.compute_temporal_weight)
    for param_name in ("now", "boost_years", "boost_factor", "decay_years", "decay_factor"):
        param = sig.parameters[param_name]
        assert param.default is not inspect.Parameter.empty, f"{param_name} 无默认"