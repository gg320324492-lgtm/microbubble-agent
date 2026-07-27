"""
计费网关抽象 (W73 第 1 批 B-1 + W74 第 1 批 B-2 真支付 mock 接入)

W72 第 2 批 B-5 起步收口:
- 接口预留: stripe / alipay / wechat_pay (3 实现切换, 仅 mock)
- W73 仅预留接口, 不接真支付 (主指挥决策 W74 拍板)

W74 第 1 批 B-2 真支付 mock 接入 (D-1 §3.2 W74 Step 5 P0 主拍单独拍板):
- 3 实现全部 mock 化 (Stripe / Alipay / WeChatPay), 不接真支付
- 真接入须主拍单独拍板 (派工 v6 段 5 反馈 #6 实战)
- 3 实现切换逻辑由 get_billing_gateway(provider) 统一管理
- 共享内存存储 (进程级), 仅测试用

不破坏老路径: 仅在 app/services/billing_gateway.py 修改 + mock 实现.

设计:
- BillingGateway 抽象基类 (Strategy 模式)
- MockBillingGateway (W73 默认, 进程级内存)
- StripeBillingGateway / AlipayBillingGateway / WeChatPayBillingGateway (W74 B-2 全部 mock 化)
- 工厂函数 get_billing_gateway(provider) 按 settings 切换
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
}


def get_billing_gateway(provider: str = "mock") -> BillingGateway:
    """工厂函数: 按 provider 名获取网关实例.

    默认 'mock' (派工 v4 铁律 3 真验证 — settings 不覆盖则默认 mock).
    真支付须主拍单独拍板.
    """
    cls = _GATEWAYS.get(provider)
    if not cls:
        raise ValueError(f"unknown billing provider '{provider}', supported: {list(_GATEWAYS.keys())}")
    return cls()


def list_supported_providers() -> list[str]:
    """列出所有支持的支付 provider."""
    return list(_GATEWAYS.keys())