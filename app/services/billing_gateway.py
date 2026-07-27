"""
计费网关抽象 (W73 第 1 批 B-1)

W72 第 2 批 B-5 起步收口:
- 接口预留: stripe / alipay / wechat_pay (3 实现切换, 仅 mock)
- W73 仅预留接口, 不接真支付 (主指挥决策 W74 拍板)
- 不破坏老路径: 仅在 app/services/billing_gateway.py 新增

设计:
- BillingGateway 抽象基类
- MockBillingGateway (W73 默认, mock 实现)
- StripeBillingGateway / AlipayBillingGateway / WeChatPayBillingGateway (接口骨架, 抛 NotImplementedError)
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


class MockBillingGateway(BillingGateway):
    """Mock 计费网关 (W73 默认)."""

    provider_name = "mock"

    def __init__(self):
        # 内存存储 (进程级), 仅测试用
        self._intents: dict = {}

    async def create_payment(self, invoice_id: str, amount_cents: int, currency: str = "CNY") -> PaymentIntent:
        intent_id = "mock_pi_" + secrets.token_hex(12)
        intent = PaymentIntent(
            intent_id=intent_id,
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            currency=currency,
            provider=self.provider_name,
            client_secret="mock_secret_" + secrets.token_hex(8),
            redirect_url=f"https://mock.billing.local/confirm/{intent_id}",
        )
        self._intents[intent_id] = intent
        logger.info("mock payment intent created: id=%s invoice=%s amount=%d", intent_id, invoice_id, amount_cents)
        return intent

    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        intent = self._intents.get(intent_id)
        if not intent:
            return PaymentResult(
                intent_id=intent_id, status="failed", provider=self.provider_name,
                error="intent not found",
            )
        # mock 直接成功
        return PaymentResult(
            intent_id=intent_id,
            status="success",
            provider=self.provider_name,
            provider_ref=provider_ref or ("mock_ref_" + secrets.token_hex(8)),
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
            provider_ref="mock_refund_" + secrets.token_hex(8),
            completed_at=datetime.now(timezone.utc),
        )


class StripeBillingGateway(BillingGateway):
    """Stripe 网关骨架 (W76+ 实物接入).

    W73 派工预设: 仅留接口, 不接真支付.
    """

    provider_name = "stripe"

    async def create_payment(self, invoice_id: str, amount_cents: int, currency: str = "CNY") -> PaymentIntent:
        raise NotImplementedError("Stripe gateway reserved for W76+ rollout")

    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        raise NotImplementedError("Stripe gateway reserved for W76+ rollout")

    async def refund(self, intent_id: str, amount_cents: Optional[int] = None) -> PaymentResult:
        raise NotImplementedError("Stripe gateway reserved for W76+ rollout")


class AlipayBillingGateway(BillingGateway):
    """支付宝网关骨架 (W76+ 实物接入)."""

    provider_name = "alipay"

    async def create_payment(self, invoice_id: str, amount_cents: int, currency: str = "CNY") -> PaymentIntent:
        raise NotImplementedError("Alipay gateway reserved for W76+ rollout")

    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        raise NotImplementedError("Alipay gateway reserved for W76+ rollout")

    async def refund(self, intent_id: str, amount_cents: Optional[int] = None) -> PaymentResult:
        raise NotImplementedError("Alipay gateway reserved for W76+ rollout")


class WeChatPayBillingGateway(BillingGateway):
    """微信支付网关骨架 (W76+ 实物接入)."""

    provider_name = "wechat_pay"

    async def create_payment(self, invoice_id: str, amount_cents: int, currency: str = "CNY") -> PaymentIntent:
        raise NotImplementedError("WeChat Pay gateway reserved for W76+ rollout")

    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        raise NotImplementedError("WeChat Pay gateway reserved for W76+ rollout")

    async def refund(self, intent_id: str, amount_cents: Optional[int] = None) -> PaymentResult:
        raise NotImplementedError("WeChat Pay gateway reserved for W76+ rollout")


# ----- 工厂 -----

_GATEWAYS = {
    "mock": MockBillingGateway,
    "stripe": StripeBillingGateway,
    "alipay": AlipayBillingGateway,
    "wechat_pay": WeChatPayBillingGateway,
}


def get_billing_gateway(provider: str = "mock") -> BillingGateway:
    """工厂函数: 按 provider 名获取网关实例."""
    cls = _GATEWAYS.get(provider)
    if not cls:
        raise ValueError(f"unknown billing provider '{provider}', supported: {list(_GATEWAYS.keys())}")
    return cls()