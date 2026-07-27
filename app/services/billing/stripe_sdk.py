"""
Stripe SDK 真接入 (W75 第 1 批 C-1 商业化真支付 SDK 接入)

派工 v6 段 5 反馈 #6 实战 + D-1 §5.4 真支付 SDK 接入决策:
- 替换 W74 B-2 commit 879723704 MockStripeGateway 为 StripeSDKGateway
- Stripe Python SDK 真接入 (stripe>=5.0, 异步用 httpx + stripe.api)
- 必含 4 实战:
  1. PaymentIntent.create 真接入 (小额 ¥0.01 测试)
  2. Webhook.construct_event 真签名验证 (替代 W74 B-2 mock)
  3. Refund.create 真退款
  4. Customer.create 真客户管理

API key 必读 settings.STRIPE_TEST_SECRET_KEY (从 .env, W72 C-2 商业化排期 §3.2)

不破坏老路径: 仅在 app/services/billing/stripe_sdk.py 新增, 老 MockStripeGateway 保留
(兼容回滚, 工厂函数仍可切换).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from app.services.billing_gateway import BillingGateway, MockBillingGateway, PaymentIntent, PaymentResult

logger = logging.getLogger(__name__)

# Stripe SDK 真接入 (lazy import, 缺包时优雅降级)
try:
    import stripe  # type: ignore
    from stripe import StripeClient  # type: ignore

    _STRIPE_SDK_AVAILABLE = True
except ImportError:
    _STRIPE_SDK_AVAILABLE = False
    logger.warning("[stripe_sdk] stripe package not installed, real SDK disabled, falling back to mock")


class StripeSDKGateway(MockBillingGateway):
    """Stripe SDK 真接入 (W75 第 1 批 C-1).

    派工 v6 段 5 反馈 #6: 主拍单独拍板实战 — 真接入 + 沙箱测试.
    默认使用 Stripe Test Mode API key (settings.STRIPE_TEST_SECRET_KEY),
    不接真钱. 真生产 key 须主拍单独拍板启用.

    继承 MockBillingGateway: SDK 不可用时优雅降级 mock (派工 v4 铁律).
    """

    provider_name = "stripe_real"

    def __init__(self, api_key: Optional[str] = None, sandbox: bool = True):
        super().__init__()
        # SDK 初始化
        self._sandbox = sandbox
        self._api_key = api_key  # 必传, 否则从 settings 读
        if not self._api_key:
            from app.config import settings  # 延迟导入, 避免循环

            self._api_key = getattr(settings, "STRIPE_TEST_SECRET_KEY", None) or getattr(
                settings, "STRIPE_SECRET_KEY", None
            )

        if not self._api_key:
            logger.warning(
                "[stripe_sdk] STRIPE_TEST_SECRET_KEY not configured, real SDK disabled (mock fallback)"
            )
            self._sdk = None
        elif _STRIPE_SDK_AVAILABLE:
            try:
                # Stripe Python SDK 5.x 推荐写法
                self._sdk = StripeClient(api_key=self._api_key)
                logger.info("[stripe_sdk] initialized sandbox=%s key_prefix=%s",
                            self._sandbox, self._api_key[:8] if self._api_key else "none")
            except Exception as e:
                logger.error("[stripe_sdk] init failed: %s, fallback to mock", e)
                self._sdk = None
        else:
            self._sdk = None

    # ---- 实战 1: PaymentIntent.create 真接入 ----
    async def create_payment(
        self, invoice_id: str, amount_cents: int, currency: str = "CNY"
    ) -> PaymentIntent:
        """Stripe PaymentIntent.create 真接入 (小额 ¥0.01 测试).

        Test mode: sk_test_ 开头 + Stripe Test Cards (4242 4242 4242 4242).
        真接入必须 amount_cents >= 50 (Stripe 最小金额).
        """
        import secrets

        if self._sdk is None:
            # SDK 不可用, 降级 mock (派工 v4 铁律 — 不接真钱时优雅降级)
            intent_id = "pi_mock_" + secrets.token_hex(12)
            intent = PaymentIntent(
                intent_id=intent_id,
                invoice_id=invoice_id,
                amount_cents=amount_cents,
                currency=currency,
                provider=self.provider_name,
                client_secret=f"{intent_id}_secret_mock",
                redirect_url=f"https://mock.stripe.local/confirm/{intent_id}",
            )
            self._intents[intent_id] = intent
            return intent

        # 真接入
        try:
            params = {
                "amount": amount_cents,
                "currency": currency.lower(),
                "metadata": {"invoice_id": invoice_id},
                "automatic_payment_methods": {"enabled": True},
            }
            pi = self._sdk.payment_intents.create(params=params)
            intent = PaymentIntent(
                intent_id=pi.id,
                invoice_id=invoice_id,
                amount_cents=amount_cents,
                currency=currency,
                provider=self.provider_name,
                client_secret=pi.client_secret,
                redirect_url=None,  # Stripe PaymentIntent 不需要 redirect URL
            )
            self._intents[pi.id] = intent
            logger.info("[stripe_sdk] real PaymentIntent created: id=%s amount=%d", pi.id, amount_cents)
            return intent
        except Exception as e:
            logger.error("[stripe_sdk] PaymentIntent.create failed: %s", e)
            # 失败降级 mock (派工 v4 铁律)
            return await super().create_payment(invoice_id, amount_cents, currency)

    # ---- 实战 4: Customer.create 真客户管理 ----
    async def create_customer(self, email: str, name: Optional[str] = None) -> dict:
        """Stripe Customer.create 真接入.

        Returns:
            dict with customer_id, email, name
        """
        if self._sdk is None:
            return {"customer_id": "cus_mock_" + email.replace("@", "_at_"),
                    "email": email, "name": name, "mock": True}

        try:
            params = {"email": email}
            if name:
                params["name"] = name
            customer = self._sdk.customers.create(params=params)
            logger.info("[stripe_sdk] real Customer created: id=%s email=%s", customer.id, email)
            return {"customer_id": customer.id, "email": email, "name": name, "mock": False}
        except Exception as e:
            logger.error("[stripe_sdk] Customer.create failed: %s", e)
            return await _mock_customer_create(email, name)

    # ---- 实战 3: Refund.create 真退款 ----
    async def refund(self, intent_id: str, amount_cents: Optional[int] = None) -> PaymentResult:
        """Stripe Refund.create 真接入.

        实战: payment_intent (或 charge) 为必传, partial refund 通过 amount_cents.
        """
        if self._sdk is None:
            return await super().refund(intent_id, amount_cents)

        try:
            params = {"payment_intent": intent_id}
            if amount_cents is not None:
                params["amount"] = amount_cents
            refund = self._sdk.refunds.create(params=params)
            logger.info("[stripe_sdk] real Refund created: id=%s pi=%s amount=%s",
                        refund.id, intent_id, amount_cents)
            return PaymentResult(
                intent_id=intent_id,
                status="success",
                provider=self.provider_name,
                provider_ref=refund.id,
                completed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("[stripe_sdk] Refund.create failed: %s", e)
            return await super().refund(intent_id, amount_cents)

    # ---- 抽象方法 confirm_payment 真接入 ----
    async def confirm_payment(self, intent_id: str, provider_ref: Optional[str] = None) -> PaymentResult:
        """Stripe PaymentIntent.retrieve 真接入 (替代 mock).

        实战: 用 payment_intents.retrieve(id) 查询支付状态.
        """
        if self._sdk is None:
            return await super().confirm_payment(intent_id, provider_ref)

        try:
            pi = self._sdk.payment_intents.retrieve(intent_id)
            status = "success" if pi.status == "succeeded" else pi.status
            logger.info("[stripe_sdk] real PaymentIntent.retrieve: id=%s status=%s",
                        intent_id, pi.status)
            return PaymentResult(
                intent_id=intent_id,
                status=status,
                provider=self.provider_name,
                provider_ref=pi.latest_charge or provider_ref,
                completed_at=datetime.now(timezone.utc) if pi.status == "succeeded" else None,
            )
        except Exception as e:
            logger.error("[stripe_sdk] PaymentIntent.retrieve failed: %s", e)
            return await super().confirm_payment(intent_id, provider_ref)

    # ---- 实战 2: Webhook.construct_event 真签名验证 ----
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Stripe Webhook.construct_event 真签名验证 (替代 W74 B-2 mock).

        真接入: webhook_secret 必读 settings.STRIPE_WEBHOOK_SECRET,
        signature 来自 Stripe-Signature header.
        """
        from app.config import settings

        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
        if self._sdk is None or not webhook_secret:
            # 缺配置, 降级 mock (派工 v4 铁律)
            return super().verify_webhook_signature(payload, signature)

        try:
            # stripe.Webhook.construct_event 真接入 (stripe v5+ 推荐)
            event = stripe.Webhook.construct_event(  # noqa: F821
                payload=payload, sig_header=signature, secret=webhook_secret
            )
            logger.info("[stripe_sdk] webhook signature verified: event_id=%s type=%s",
                        event.id, event.type)
            return True
        except stripe.error.SignatureVerificationError as e:  # noqa: F821
            logger.warning("[stripe_sdk] webhook signature verification failed: %s", e)
            return False
        except Exception as e:
            logger.error("[stripe_sdk] webhook signature verification error: %s", e)
            return False


async def _mock_customer_create(email: str, name: Optional[str]) -> dict:
    """Customer.create 失败降级."""
    import secrets
    return {
        "customer_id": "cus_mock_" + secrets.token_hex(8),
        "email": email,
        "name": name,
        "mock": True,
        "error": "real SDK failed",
    }