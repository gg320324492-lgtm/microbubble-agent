"""W78 第 1 批 B-2 商业化真支付生产 key 启用 e2e.

W77 第 1 批 B-3 commit c7b8466df 真支付生产 key 主拍决策准备 (类 20.13 实战);
W78 第 1 批 B-2 主拍决策落地 — 真生产 key 启用 4 case:

  test_01_real_key_enable_accepts_main_decision: 真生产 key 启用 accept (主拍拍板后)
  test_02_real_key_enable_rejects_when_key_missing: 真生产 key 缺失 → 优雅降级 mock
  test_03_replay_protection_blocks_resends: 重放保护实战 (timestamp 5min + nonce)
  test_04_real_payment_mock_three_channels: 真支付 mock 测试 (Stripe + Alipay + WeChat Pay V3)

测试前置 (SKIP_DB_SETUP=1 mock 测试, 不发起真钱):
  - 默认 BILLING_LIVE_ENABLED=false → 优雅降级 mock
  - 测试 01 用 mock 注入真生产 key 必含字段 → 验证 accept
  - 测试 02 验证缺失字段 → reject
  - 测试 03 复用 W75 C-1 webhook_signature_real.check_replay_protection
  - 测试 04 验证 3 渠道 *_real provider 都能实例化 + 走 mock 路径 (无真 key 时)

不破坏老路径: 仅在 tests/test_billing_real_key_enable_e2e.py 新增.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

# 测试模式: SKIP_DB_SETUP=1 时跳过真实 DB
os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest

from app.services import billing_gateway
from app.services.billing_gateway import (
    _check_live_key_for_provider,
    get_billing_gateway,
    list_supported_providers,
)
from app.services.billing.webhook_signature_real import (
    check_replay_protection,
    clear_replay_cache,
    get_replay_cache_size,
)


# ---------- Case 01: 真生产 key 启用 accept (主拍拍板后) ----------

def test_01_real_key_enable_accepts_main_decision(monkeypatch):
    """真生产 key 启用 accept (主拍拍板后 BILLING_LIVE_ENABLED=true + 真生产 key 完整注入).

    W78 B-2 主拍决策落地实战: 主拍单独拍板 → secrets manager 注入真生产 key → BILLING_LIVE_ENABLED=true.
    """
    from app.config import settings

    # Mock settings 真生产 key 注入 (主拍拍板实战)
    monkeypatch.setattr(settings, "BILLING_LIVE_ENABLED", True, raising=False)
    monkeypatch.setattr(settings, "STRIPE_LIVE_SECRET_KEY", "sk_live_test_main_decision_2026_07_28",
                        raising=False)
    monkeypatch.setattr(settings, "ALIPAY_LIVE_APP_ID", "2026000000000001", raising=False)
    monkeypatch.setattr(settings, "ALIPAY_LIVE_PRIVATE_KEY",
                        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEAtest\n-----END RSA PRIVATE KEY-----",
                        raising=False)
    monkeypatch.setattr(settings, "ALIPAY_LIVE_PUBLIC_KEY", "alipay_pub_test", raising=False)
    monkeypatch.setattr(settings, "WECHAT_PAY_LIVE_APP_ID", "wx_test_appid", raising=False)
    monkeypatch.setattr(settings, "WECHAT_PAY_LIVE_MCH_ID", "1900000001", raising=False)
    monkeypatch.setattr(settings, "WECHAT_PAY_LIVE_API_V3_KEY", "test_v3_key_32_chars_abcdef123456",
                        raising=False)

    # 3 渠道 *_real 都应 accept (主拍决策落地)
    assert _check_live_key_for_provider("stripe_real")[0] is True
    assert _check_live_key_for_provider("alipay_real")[0] is True
    assert _check_live_key_for_provider("wechat_pay_real")[0] is True

    # get_billing_gateway() 返回 *_real 网关 (真生产 key 已注入, sandbox=False)
    stripe_gw = get_billing_gateway("stripe_real")
    assert stripe_gw.provider_name == "stripe_real"
    # sandbox=False 表示真生产模式 (主拍决策落地实战)


# ---------- Case 02: 真生产 key 缺失 → 优雅降级 mock ----------

def test_02_real_key_enable_rejects_when_key_missing(monkeypatch):
    """真生产 key 缺失 → 优雅降级 mock (W75 C-1 沙箱模式 + 派工 v4 铁律 3 实战).

    W78 B-2 主拍决策落地: BILLING_LIVE_ENABLED=true 但真生产 key 缺失 → 优雅降级 mock, 永不自启真钱.
    """
    from app.config import settings

    # 主拍开启 live, 但任一渠道真生产 key 缺失
    monkeypatch.setattr(settings, "BILLING_LIVE_ENABLED", True, raising=False)
    # 故意只注入 stripe key, 不注入 alipay + wechat_pay
    monkeypatch.setattr(settings, "STRIPE_LIVE_SECRET_KEY", "sk_live_test_partial", raising=False)
    monkeypatch.setattr(settings, "ALIPAY_LIVE_APP_ID", None, raising=False)
    monkeypatch.setattr(settings, "ALIPAY_LIVE_PRIVATE_KEY", None, raising=False)
    monkeypatch.setattr(settings, "ALIPAY_LIVE_PUBLIC_KEY", None, raising=False)
    monkeypatch.setattr(settings, "WECHAT_PAY_LIVE_APP_ID", None, raising=False)
    monkeypatch.setattr(settings, "WECHAT_PAY_LIVE_MCH_ID", None, raising=False)
    monkeypatch.setattr(settings, "WECHAT_PAY_LIVE_API_V3_KEY", None, raising=False)

    # alipay/wechat_pay 应 reject (真生产 key 缺失)
    alipay_enabled, alipay_reason = _check_live_key_for_provider("alipay_real")
    assert alipay_enabled is False
    assert "三件套缺失" in alipay_reason

    wechat_enabled, wechat_reason = _check_live_key_for_provider("wechat_pay_real")
    assert wechat_enabled is False
    assert "三件套缺失" in wechat_reason

    # stripe prefix 异常也应 reject
    monkeypatch.setattr(settings, "STRIPE_LIVE_SECRET_KEY", "pk_live_wrong_prefix", raising=False)
    stripe_enabled, stripe_reason = _check_live_key_for_provider("stripe_real")
    assert stripe_enabled is False
    assert "sk_live_ 前缀" in stripe_reason

    # BILLING_LIVE_ENABLED=false → 全部 reject
    monkeypatch.setattr(settings, "BILLING_LIVE_ENABLED", False, raising=False)
    for provider in ("stripe_real", "alipay_real", "wechat_pay_real"):
        enabled, reason = _check_live_key_for_provider(provider)
        assert enabled is False, f"{provider} 应 reject"
        assert "BILLING_LIVE_ENABLED=false" in reason


# ---------- Case 03: 重放保护实战 (timestamp 5min + nonce) ----------

def test_03_replay_protection_blocks_resends():
    """重放保护实战 (W75 C-1 16/16 + W76 E-1 PASS verify 实战).

    W78 B-2 主拍决策落地: 真生产启用 → 必含重放保护 gate (timestamp 5min + nonce).
    """
    clear_replay_cache()
    assert get_replay_cache_size() == 0

    # 1. 合法 timestamp → pass
    now_ts = str(int(time.time()))
    assert check_replay_protection(now_ts, window_seconds=300) is True

    # 2. 同 timestamp 重放 → block (nonce 去重)
    assert check_replay_protection(now_ts, window_seconds=300) is False

    # 3. 过期 timestamp (6 分钟前) → block
    expired_ts = str(int(time.time()) - 360)
    assert check_replay_protection(expired_ts, window_seconds=300) is False

    # 4. ISO 8601 格式也兼容 (但要清 cache 避免与 unix timestamp 同秒碰撞 nonce key)
    clear_replay_cache()
    from datetime import datetime, timezone
    iso_ts = datetime.now(timezone.utc).isoformat()
    assert check_replay_protection(iso_ts, window_seconds=300) is True

    # 5. 异常格式 → block (保守拒绝)
    assert check_replay_protection("not_a_timestamp", window_seconds=300) is False

    clear_replay_cache()


# ---------- Case 04: 真支付 mock 测试 (Stripe + Alipay + WeChat Pay V3) ----------

@pytest.mark.asyncio
async def test_04_real_payment_mock_three_channels(monkeypatch):
    """真支付 mock 测试 (Stripe + Alipay + WeChat Pay V3 三方 canary).

    W78 B-2 主拍决策落地: 真生产 key 缺失 → *_real 网关优雅降级 mock, 真支付 mock 仍可走完 3 渠道 canary 流程.
    类 20.13 实战 + 派工 v6 段 5 反馈 #6 实战 + W77 B-3 §4 时间表.
    """
    from app.config import settings

    # 模拟主拍决策: BILLING_LIVE_ENABLED=true 但真生产 key 缺失 → 全部降级 mock
    monkeypatch.setattr(settings, "BILLING_LIVE_ENABLED", True, raising=False)
    for attr in ("STRIPE_LIVE_SECRET_KEY", "ALIPAY_LIVE_APP_ID", "ALIPAY_LIVE_PRIVATE_KEY",
                 "ALIPAY_LIVE_PUBLIC_KEY", "WECHAT_PAY_LIVE_APP_ID", "WECHAT_PAY_LIVE_MCH_ID",
                 "WECHAT_PAY_LIVE_API_V3_KEY"):
        monkeypatch.setattr(settings, attr, None, raising=False)

    # 3 渠道 *_real 都应能实例化 (降级 mock, 永不抛异常)
    for provider in ("stripe_real", "alipay_real", "wechat_pay_real"):
        gw = get_billing_gateway(provider)
        assert gw is not None
        assert gw.provider_name == provider

        # 真支付 mock 测试 (小额 ¥0.01 = 1 cent)
        intent = await gw.create_payment(
            invoice_id=f"inv_w78b2_test_{provider}",
            amount_cents=1,  # $0.01 / ¥0.01
            currency="USD" if "stripe" in provider else "CNY",
        )
        # *_real 网关降级 mock → intent_id 含 provider name (W75 C-1 沙箱模式实战)
        assert intent.intent_id  # 非空
        assert intent.amount_cents == 1
        assert intent.provider == provider

        # confirm_payment mock
        result = await gw.confirm_payment(intent.intent_id)
        assert result.status in ("success", "pending")

        # refund mock
        refund_result = await gw.refund(intent.intent_id, amount_cents=1)
        assert refund_result.status in ("success", "failed", "pending")


# ---------- 辅助验证 ----------

def test_supported_providers_include_real_variants():
    """list_supported_providers 必须包含 *_real provider (W75 C-1 + W78 B-2 主拍决策)."""
    providers = list_supported_providers()
    assert "mock" in providers
    assert "stripe" in providers
    assert "alipay" in providers
    assert "wechat_pay" in providers
    assert "stripe_real" in providers
    assert "alipay_real" in providers
    assert "wechat_pay_real" in providers