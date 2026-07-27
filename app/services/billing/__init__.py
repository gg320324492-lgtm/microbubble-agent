"""
计费子包 (W74 第 1 批 B-2 真支付接入)

5 大件:
- stripe_gateway / alipay_gateway / wechat_pay_gateway: 3 支付网关 (mock)
- payment_service: 支付流程编排 (init/confirm/refund)
- subscription_service: 订阅管理
- webhook_handler: webhook 异步处理

锚点范式: W73 第 1 批 B-1 235 → W74 第 1 批 B-2 247 守恒 (+12)
派工 v6 段 5 反馈 #6 实战: 3 支付网关仅 mock, 真接入主拍拍板
"""
from app.services.billing_gateway import (
    BillingGateway,
    MockBillingGateway,
    StripeBillingGateway,
    AlipayBillingGateway,
    WeChatPayBillingGateway,
    PaymentIntent,
    PaymentResult,
    get_billing_gateway,
    list_supported_providers,
)

__all__ = [
    "BillingGateway",
    "MockBillingGateway",
    "StripeBillingGateway",
    "AlipayBillingGateway",
    "WeChatPayBillingGateway",
    "PaymentIntent",
    "PaymentResult",
    "get_billing_gateway",
    "list_supported_providers",
]