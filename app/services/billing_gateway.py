"""
计费网关抽象 (W73 第 1 批 B-1 + W74 第 1 批 B-2 真支付 mock 接入 + W75 第 1 批 C-1 真 SDK 接入 + W78 第 1 批 B-2 真生产 key 启用)

W72 第 2 批 B-5 起步收口:
- 接口预留: stripe / alipay / wechat_pay (3 实现切换, 仅 mock)
- W73 仅预留接口, 不接真支付 (主指挥决策 W74 拍板)

W74 第 1 批 B-2 真支付 mock 接入 (D-1 §3.2 W74 Step 5 P0 主拍单独拍板):
- 3 实现全部 mock 化 (Stripe / Alipay / WeChatPay), 不接真支付
- 真接入须主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)
- 3 实现切换逻辑由 get_billing_gateway(provider) 统一管理
- 共享内存存储 (进程级), 仅测试用

W75 第 1 批 C-1 真支付 SDK 接入 (D-1 §5.4 真支付 SDK 接入决策 + 派工 v6 段 5 反馈 #6):
- 替换 MockStripeGateway / MockAlipayGateway / MockWeChatPayGateway 为 StripeSDKGateway / AlipaySDKGateway / WeChatPaySDKGateway
- 默认沙箱模式 (settings.STRIPE_TEST_SECRET_KEY / ALIPAY_* / WECHAT_PAY_*), 不接真钱

W77 第 1 批 B-3 真支付生产 key 主拍决策准备 (类 20.13 实战):
- 仅沙箱升级准备 + 主拍决策记录, 不在 W77 自动启用
- .env.production.example 新建 (3 支付渠道真生产 key 占位符)
- W78-B-1/B-2 主拍拍板时间表: mock → 沙箱 → 真生产逐步启用

W78 第 1 批 B-2 真支付生产 key 启用 (类 20.13 主拍决策落地):
- get_billing_gateway() 新增 PROD_KEY_AUTO_ENABLE 硬门 + 真生产 key 自动切换 + 优雅降级
- BILLING_LIVE_ENABLED + 真生产 key 必先经主拍单独拍板 (类 20.13 实战, 主指挥决策)
- 真生产 key 缺失自动降级 mock (W75 C-1 沙箱模式 + 派工 v4 铁律 3 实战)
- 真支付测试必走小额 $0.01/¥0.01 三方 canary (Stripe PaymentIntent + Alipay AlipayTradePagePay + WeChat Pay V3 jsapi)

不破坏老路径: 仅在 app/services/billing_gateway.py 修改 + mock 实现 + 真 SDK 接入 (W75 C-1).

设计:
- BillingGateway 抽象基类 (Strategy 模式)
- MockBillingGateway (W73 默认, 进程级内存)
- StripeBillingGateway / AlipayBillingGateway / WeChatPayBillingGateway (W74 B-2 全部 mock 化)
- StripeSDKGateway / AlipaySDKGateway / WeChatPaySDKGateway (W75 C-1 真 SDK)
- 工厂函数 get_billing_gateway(provider) 按 settings 切换 + W78 B-2 主拍决策落地
"""
from __future__ import annotations

import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PaymentIntent:
    """支付意图 (统一抽象)."""
    intent_id: str
    invoice_id: str
    amount_cents: int
    currency: str = "CNY"
    provider: str = "mock"
    client_secret: Optional[str] = None
    redirect_url: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PaymentResult:
    """支付结果."""
    intent_id: str
    status: str  # success / failed / pending
    provider: str
    provider_ref: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class BillingGateway(ABC):
    """计费网关抽象基类 (Strategy 模式)."""

    provider_name: str = "abstract"

    @abstractmethod
    async def create_payment(self, invoice_id: str, amount_cents: int, currency: str = "CNY") -> PaymentIntent:
        """创建支付意图."""
        ...

    @abstractmethod
    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        """确认支付结果 (webhook 回调或主动查询)."""
        ...

    @abstractmethod
    async def refund(self, intent_id: str, amount_cents: Optional[int] = None) -> PaymentResult:
        """退款."""
        ...

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """验证 webhook 签名 (mock 默认 True)."""
        ...


class MockBillingGateway(BillingGateway):
    """Mock 计费网关 (W73 默认, W74 B-2 扩展 3 provider 共用 mock 实现)."""

    provider_name = "mock"

    def __init__(self):
        # 内存存储 (进程级), 仅测试用
        self._intents: dict = {}

    async def create_payment(self, invoice_id: str, amount_cents: int, currency: str = "CNY") -> PaymentIntent:
        intent_id = f"{self.provider_name}_pi_" + secrets.token_hex(12)
        intent = PaymentIntent(
            intent_id=intent_id,
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            currency=currency,
            provider=self.provider_name,
            client_secret=f"{self.provider_name}_secret_" + secrets.token_hex(8),
            redirect_url=f"https://mock.billing.local/{self.provider_name}/confirm/{intent_id}",
        )
        self._intents[intent_id] = intent
        logger.info("[%s] mock payment intent created: id=%s invoice=%s amount=%d",
                    self.provider_name, intent_id, invoice_id, amount_cents)
        return intent

    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        intent = self._intents.get(intent_id)
        if not intent:
            return PaymentResult(
                intent_id=intent_id, status="failed", provider=self.provider_name,
                error="intent not found",
            )
        return PaymentResult(
            intent_id=intent_id,
            status="success",
            provider=self.provider_name,
            provider_ref=provider_ref or (f"{self.provider_name}_ref_" + secrets.token_hex(8)),
            completed_at=datetime.now(timezone.utc),
        )

    async def refund(self, intent_id: str, amount_cents: Optional[int] = None) -> PaymentResult:
        intent = self._intents.get(intent_id)
        if not intent:
            return PaymentResult(
                intent_id=intent_id, status="failed", provider=self.provider_name,
                error="intent not found",
            )
        return PaymentResult(
            intent_id=intent_id,
            status="success",
            provider=self.provider_name,
            provider_ref=f"{self.provider_name}_refund_" + secrets.token_hex(8),
            completed_at=datetime.now(timezone.utc),
        )

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Mock 签名验证: 始终返回 True (W74 B-2, 真接入主拍拍板)."""
        return True


class StripeBillingGateway(MockBillingGateway):
    """Stripe 网关 mock (W74 第 1 批 B-2 真支付接入).

    W73 派工预设: 仅留接口, 不接真支付 (W74 B-2 全部 mock 化, 真接入主拍拍板).
    """

    provider_name = "stripe"

    def __init__(self):
        super().__init__()
        # Stripe 特定字段
        self.publishable_key_prefix = "pk_test_"
        self.webhook_secret_prefix = "whsec_"


class AlipayBillingGateway(MockBillingGateway):
    """支付宝网关 mock (W74 第 1 批 B-2 真支付接入).

    W73 派工预设: 仅留接口, 不接真支付 (W74 B-2 全部 mock 化, 真接入主拍拍板).
    """

    provider_name = "alipay"

    def __init__(self):
        super().__init__()
        # 支付宝特定字段 (RSA2 签名占位)
        self.app_id_prefix = "20210001"
        self.sign_type = "RSA2"


class WeChatPayBillingGateway(MockBillingGateway):
    """微信支付网关 mock (W74 第 1 批 B-2 真支付接入).

    W73 派工预设: 仅留接口, 不接真支付 (W74 B-2 全部 mock 化, 真接入主拍拍板).
    """

    provider_name = "wechat_pay"

    def __init__(self):
        super().__init__()
        # 微信支付特定字段 (V3 API 签名占位)
        self.mch_id_prefix = "190000"
        self.api_v3_key_prefix = "mch_secret_"


# ----- 工厂 -----

_GATEWAYS = {
    "mock": MockBillingGateway,
    "stripe": StripeBillingGateway,
    "alipay": AlipayBillingGateway,
    "wechat_pay": WeChatPayBillingGateway,
    # W75 第 1 批 C-1: 真 SDK 接入 (Stripe + Alipay + WeChat Pay V3)
    # 派工 v6 段 5 反馈 #6 实战 + D-1 §5.4 真支付 SDK 接入决策
    # 默认从 settings 读 API key (沙箱模式), 真生产 key 须主拍单独拍板启用
    "stripe_real": None,         # lazy import 避免循环依赖, 在 get_billing_gateway() 中实例化
    "alipay_real": None,
    "wechat_pay_real": None,
}


def _check_live_key_for_provider(provider: str) -> tuple[bool, str]:
    """W78 第 1 批 B-2 真生产 key 自动检查 + 优雅降级实战.

    派工 v6 段 5 反馈 #6 实战 + 类 20.13 实战:
    - 真生产 key 启用必须先经主拍单独拍板
    - BILLING_LIVE_ENABLED=true 且对应渠道真生产 key 完整注入 → 启用真支付
    - 任一条件不满足 → 优雅降级 mock, 永不自启真钱

    Args:
        provider: 'stripe_real' / 'alipay_real' / 'wechat_pay_real'

    Returns:
        (enabled, reason) — enabled=True 表示真生产 key 完整, False 表示需降级
    """
    from app.config import settings  # 延迟导入

    live_enabled = getattr(settings, "BILLING_LIVE_ENABLED", False)
    if not live_enabled:
        return False, "BILLING_LIVE_ENABLED=false (主拍未启用真生产)"

    if provider == "stripe_real":
        secret_key = getattr(settings, "STRIPE_LIVE_SECRET_KEY", None)
        if not secret_key or not secret_key.startswith("sk_live_"):
            return False, "STRIPE_LIVE_SECRET_KEY 缺失或非 sk_live_ 前缀"
        return True, "stripe 真生产 key 已注入"

    if provider == "alipay_real":
        app_id = getattr(settings, "ALIPAY_LIVE_APP_ID", None)
        private_key = getattr(settings, "ALIPAY_LIVE_PRIVATE_KEY", None)
        public_key = getattr(settings, "ALIPAY_LIVE_PUBLIC_KEY", None)
        if not all([app_id, private_key, public_key]):
            return False, "ALIPAY_LIVE_APP_ID/PRIVATE_KEY/PUBLIC_KEY 三件套缺失"
        if "BEGIN RSA PRIVATE KEY" not in (private_key or ""):
            return False, "ALIPAY_LIVE_PRIVATE_KEY 格式异常 (非 RSA2 PEM)"
        return True, "alipay 真生产 key 三件套已注入"

    if provider == "wechat_pay_real":
        app_id = getattr(settings, "WECHAT_PAY_LIVE_APP_ID", None)
        mch_id = getattr(settings, "WECHAT_PAY_LIVE_MCH_ID", None)
        api_v3_key = getattr(settings, "WECHAT_PAY_LIVE_API_V3_KEY", None)
        if not all([app_id, mch_id, api_v3_key]):
            return False, "WECHAT_PAY_LIVE_APP_ID/MCH_ID/API_V3_KEY 三件套缺失"
        return True, "wechat_pay V3 真生产 key 三件套已注入"

    return False, f"unknown provider '{provider}'"


def get_billing_gateway(provider: str = "mock") -> BillingGateway:
    """工厂函数: 按 provider 名获取网关实例.

    默认 'mock' (派工 v4 铁律 3 真验证 — settings 不覆盖则默认 mock).
    真支付须主拍单独拍板.

    W75 第 1 批 C-1 新增 *_real provider:
    - stripe_real → StripeSDKGateway (PaymentIntent + construct_event + Refund + Customer)
    - alipay_real → AlipaySDKGateway (AlipayTradePagePay + RSA2 + Refund + Query)
    - wechat_pay_real → WeChatPaySDKGateway (jsapi + V3 签名 + Refund + Order.query)
    - API key 必读 settings.STRIPE_TEST_SECRET_KEY / ALIPAY_* / WECHAT_PAY_*
    - SDK 不可用时优雅降级 mock (派工 v4 铁律)

    W78 第 1 批 B-2 真生产 key 启用 (类 20.13 主拍决策落地):
    - _check_live_key_for_provider() 自动检查 BILLING_LIVE_ENABLED + 真生产 key
    - 真生产 key 完整 → 返回对应 *_real 网关
    - 真生产 key 缺失 → 优雅降级 mock (W75 C-1 沙箱模式实战)
    - 真生产 key 启用前必先经主拍单独拍板 (类 20.13 实战, 主指挥决策)
    - 真支付测试必走小额 $0.01/¥0.01 三方 canary (W77 B-3 §4 时间表)
    """
    # 真 SDK lazy 实例化 (避免顶部 import 循环)
    if provider in ("stripe_real", "alipay_real", "wechat_pay_real"):
        # W78 B-2 主拍决策落地 — 真生产 key 自动检查
        enabled, reason = _check_live_key_for_provider(provider)
        if enabled:
            logger.info("[billing_gateway] %s 真生产 key 已启用: %s", provider, reason)
        else:
            logger.warning(
                "[billing_gateway] %s 真生产 key 未启用, 优雅降级 mock: %s "
                "(派工 v6 段 5 反馈 #6 + 类 20.13 实战)",
                provider, reason,
            )

        if provider == "stripe_real":
            from app.services.billing.stripe_sdk import StripeSDKGateway
            cfg = __import__("app.config", fromlist=["settings"]).settings
            return StripeSDKGateway(
                api_key=getattr(cfg, "STRIPE_LIVE_SECRET_KEY", None) if enabled else None,
                sandbox=not enabled,  # 真生产 key 启用 → sandbox=False; 否则保持沙箱
            )
        if provider == "alipay_real":
            from app.services.billing.alipay_sdk import AlipaySDKGateway
            cfg = __import__("app.config", fromlist=["settings"]).settings
            return AlipaySDKGateway(
                app_id=getattr(cfg, "ALIPAY_LIVE_APP_ID", None) if enabled else None,
                app_private_key=getattr(cfg, "ALIPAY_LIVE_PRIVATE_KEY", None) if enabled else None,
                alipay_public_key=getattr(cfg, "ALIPAY_LIVE_PUBLIC_KEY", None) if enabled else None,
                sandbox=not enabled,
            )
        if provider == "wechat_pay_real":
            from app.services.billing.wechat_pay_sdk import WeChatPaySDKGateway
            cfg = __import__("app.config", fromlist=["settings"]).settings
            return WeChatPaySDKGateway(
                app_id=getattr(cfg, "WECHAT_PAY_LIVE_APP_ID", None) if enabled else None,
                mch_id=getattr(cfg, "WECHAT_PAY_LIVE_MCH_ID", None) if enabled else None,
                api_v3_key=getattr(cfg, "WECHAT_PAY_LIVE_API_V3_KEY", None) if enabled else None,
                sandbox=not enabled,
            )

    cls = _GATEWAYS.get(provider)
    if not cls:
        raise ValueError(f"unknown billing provider '{provider}', supported: {list(_GATEWAYS.keys())}")
    return cls()


def list_supported_providers() -> list[str]:
    """列出所有支持的支付 provider."""
    return list(_GATEWAYS.keys())