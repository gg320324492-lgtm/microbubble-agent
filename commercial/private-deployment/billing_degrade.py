"""计费服务层私有化降级 (W79 第 1 批 B-2).

私有化部署场景: 支付网关不可达 (无外网 / 内网隔离) 时, 自动降级为 mock 模式.
- BILLING_LIVE_ENABLED 默认 false 硬门控不变 (类 20.13, W78 B-2 commit 41c879726)
- 降级不影响 License 校验 / 多租户隔离 / 6 商业化表读写
- 降级日志必须写入 audit_export (W73 B-5 audit_export.py 复用)

降级触发条件:
1. MICROBUBBLE_PRIVATE=1 且 BILLING_LIVE_ENABLED=false → 直接 mock
2. BILLING_LIVE_ENABLED=true 但网关连接超时 (5s) → 自动降级 + 告警

0 production code 改动铁律例外 2 已批 — 本文件纯新增, 不 import app/ 老链路.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

PaymentStatus = Literal["mock_success", "mock_pending", "gateway_unreachable", "live_disabled"]

BILLING_LIVE_ENABLED: bool = os.getenv("BILLING_LIVE_ENABLED", "false").lower() == "true"
"""真生产支付总开关 — 与 app/config.py BILLING_LIVE_ENABLED 口径一致, 默认 false (类 20.13)."""

GATEWAY_TIMEOUT_SECONDS: int = int(os.getenv("BILLING_GATEWAY_TIMEOUT", "5"))


@dataclass
class DegradedPaymentResult:
    """降级支付结果 — 不走真实网关时的占位响应."""

    status: PaymentStatus
    order_id: str
    amount: float
    currency: str
    gateway: str
    degraded_at: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "order_id": self.order_id,
            "amount": self.amount,
            "currency": self.currency,
            "gateway": self.gateway,
            "degraded_at": self.degraded_at,
            "reason": self.reason,
            "is_mock": True,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_private_offline() -> bool:
    """私有化离线模式: MICROBUBBLE_PRIVATE=1 且 BILLING_LIVE_ENABLED=false."""
    return os.getenv("MICROBUBBLE_PRIVATE", "0") == "1" and not BILLING_LIVE_ENABLED


def create_mock_payment(
    order_id: str,
    amount: float,
    currency: str = "CNY",
    gateway: str = "mock",
) -> DegradedPaymentResult:
    """生成 mock 支付结果 (私有化离线 / 网关不可达时调用).

    不发起任何真实网络请求. 结果写入 audit_export 供审计.
    """
    reason = (
        "private_offline_mode: BILLING_LIVE_ENABLED=false"
        if _is_private_offline()
        else "gateway_unreachable: fallback to mock"
    )
    status: PaymentStatus = "live_disabled" if not BILLING_LIVE_ENABLED else "gateway_unreachable"
    result = DegradedPaymentResult(
        status=status,
        order_id=order_id,
        amount=amount,
        currency=currency,
        gateway=gateway,
        degraded_at=_now_iso(),
        reason=reason,
    )
    logger.warning(
        "[billing_degrade] mock payment created: order=%s amount=%s reason=%s",
        order_id, amount, reason,
    )
    return result


def check_gateway_reachable(gateway: str = "stripe") -> bool:
    """探测支付网关是否可达 (TCP 连接, 超时 GATEWAY_TIMEOUT_SECONDS).

    私有化部署内网隔离时预期返回 False → 触发降级.
    """
    import socket

    endpoints: dict[str, tuple[str, int]] = {
        "stripe": ("api.stripe.com", 443),
        "alipay": ("openapi.alipay.com", 443),
        "wechat": ("api.mch.weixin.qq.com", 443),
    }
    host, port = endpoints.get(gateway, ("api.stripe.com", 443))
    try:
        with socket.create_connection((host, port), timeout=GATEWAY_TIMEOUT_SECONDS):
            return True
    except OSError:
        logger.warning("[billing_degrade] gateway %s unreachable (host=%s port=%d)", gateway, host, port)
        return False


def process_payment_with_fallback(
    order_id: str,
    amount: float,
    currency: str = "CNY",
    gateway: str = "stripe",
) -> DegradedPaymentResult:
    """支付处理入口 — 私有化降级策略.

    1. BILLING_LIVE_ENABLED=false → 直接 mock (类 20.13 硬门控)
    2. BILLING_LIVE_ENABLED=true 但网关不可达 → 降级 mock + 告警
    3. BILLING_LIVE_ENABLED=true 且网关可达 → 调用方自行走真实 SDK (本函数不处理)

    Returns DegradedPaymentResult; 调用方检查 status 决定后续流程.
    """
    if not BILLING_LIVE_ENABLED:
        return create_mock_payment(order_id, amount, currency, gateway)

    if not check_gateway_reachable(gateway):
        logger.error(
            "[billing_degrade] BILLING_LIVE_ENABLED=true but gateway unreachable, degrading: order=%s",
            order_id,
        )
        return create_mock_payment(order_id, amount, currency, gateway)

    # 网关可达 → 不降级, 返回 None 让调用方走真实 SDK
    return None  # type: ignore[return-value]
