"""
支付服务 (W74 第 1 批 B-2 真支付接入)

派工 v6 段 5 反馈 #6 实战:
- init: 创建 PaymentIntent (调 billing_gateway)
- confirm: 确认支付 (调 billing_gateway.confirm)
- refund: 退款 (调 billing_gateway.refund)
- get: 查询支付记录

不破坏老路径: 仅在 app/services/billing/payment_service.py 新增.
与 app/services/invoice_service.py 协同: 支付成功 → invoice 标 paid.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException, ConflictException
from app.models.billing import Invoice
from app.services.billing_gateway import (
    PaymentIntent,
    PaymentResult,
    get_billing_gateway,
    list_supported_providers,
)

logger = logging.getLogger(__name__)

# 进程级内存存储 (mock 支付记录, 与 billing_gateway._intents 配套)
_PAYMENT_RECORDS: dict[str, dict] = {}


def _generate_payment_id() -> str:
    return "pay_" + secrets.token_hex(12)


async def init_payment(
    db: AsyncSession,
    invoice_id: str,
    tenant_id: str,
    provider: str = "mock",
) -> dict:
    """初始化支付 (创建 PaymentIntent).

    Returns:
        dict with payment_id, intent_id, client_secret, redirect_url, provider
    """
    if provider not in list_supported_providers():
        raise ValidationException(
            f"unsupported payment provider '{provider}', supported: {list_supported_providers()}"
        )

    inv = await db.get(Invoice, invoice_id)
    if not inv:
        raise NotFoundException(f"invoice '{invoice_id}' not found")
    if inv.tenant_id != tenant_id:
        # 信息隐藏, 不暴露存在性
        raise NotFoundException(f"invoice '{invoice_id}' not found")
    if inv.status != "pending":
        raise ConflictException(f"invoice '{invoice_id}' already {inv.status}")

    gateway = get_billing_gateway(provider)
    intent = await gateway.create_payment(inv.invoice_id, inv.amount_cents, inv.currency)

    # 内存记录 (mock)
    payment_id = _generate_payment_id()
    _PAYMENT_RECORDS[payment_id] = {
        "payment_id": payment_id,
        "invoice_id": invoice_id,
        "tenant_id": tenant_id,
        "intent_id": intent.intent_id,
        "provider": provider,
        "amount_cents": inv.amount_cents,
        "currency": inv.currency,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "payment init: payment_id=%s invoice=%s provider=%s intent=%s",
        payment_id, invoice_id, provider, intent.intent_id,
    )
    return {
        "payment_id": payment_id,
        "intent_id": intent.intent_id,
        "client_secret": intent.client_secret,
        "redirect_url": intent.redirect_url,
        "provider": provider,
        "amount_cents": inv.amount_cents,
        "currency": inv.currency,
    }


async def confirm_payment(
    db: AsyncSession,
    payment_id: str,
    tenant_id: str,
    provider_ref: Optional[str] = None,
) -> dict:
    """确认支付 (mock 默认成功).

    与 invoice_service.pay_invoice 协同: 支付成功 → invoice 标 paid.
    """
    rec = _PAYMENT_RECORDS.get(payment_id)
    if not rec:
        raise NotFoundException(f"payment '{payment_id}' not found")
    if rec["tenant_id"] != tenant_id:
        raise NotFoundException(f"payment '{payment_id}' not found")
    if rec["status"] != "pending":
        raise ConflictException(f"payment '{payment_id}' already {rec['status']}")

    gateway = get_billing_gateway(rec["provider"])
    result: PaymentResult = await gateway.confirm_payment(rec["intent_id"], provider_ref)

    rec["status"] = result.status
    rec["provider_ref"] = result.provider_ref
    rec["error"] = result.error
    rec["completed_at"] = result.completed_at.isoformat() if result.completed_at else None

    # 协同: 支付成功 → invoice 标 paid
    if result.status == "success":
        inv = await db.get(Invoice, rec["invoice_id"])
        if inv and inv.status == "pending":
            inv.status = "paid"
            inv.payment_provider = rec["provider"]
            inv.payment_ref = result.provider_ref
            inv.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()
            logger.info("invoice paid via payment: invoice=%s payment=%s ref=%s",
                        rec["invoice_id"], payment_id, result.provider_ref)

    logger.info("payment confirm: payment_id=%s status=%s provider=%s",
                payment_id, result.status, rec["provider"])
    return {
        "payment_id": payment_id,
        "status": result.status,
        "provider": rec["provider"],
        "provider_ref": result.provider_ref,
        "error": result.error,
        "completed_at": rec["completed_at"],
    }


async def refund_payment(
    db: AsyncSession,
    payment_id: str,
    tenant_id: str,
    amount_cents: Optional[int] = None,
) -> dict:
    """退款 (mock 默认成功)."""
    rec = _PAYMENT_RECORDS.get(payment_id)
    if not rec:
        raise NotFoundException(f"payment '{payment_id}' not found")
    if rec["tenant_id"] != tenant_id:
        raise NotFoundException(f"payment '{payment_id}' not found")
    if rec["status"] != "success":
        raise ConflictException(f"payment '{payment_id}' not success (status={rec['status']}), cannot refund")

    gateway = get_billing_gateway(rec["provider"])
    result = await gateway.refund(rec["intent_id"], amount_cents)

    # 协同: 退款成功 → invoice 标 refunded
    if result.status == "success":
        inv = await db.get(Invoice, rec["invoice_id"])
        if inv and inv.status == "paid":
            inv.status = "refunded"
            await db.flush()
            rec["status"] = "refunded"
            logger.info("invoice refunded via payment: invoice=%s payment=%s",
                        rec["invoice_id"], payment_id)

    return {
        "payment_id": payment_id,
        "status": rec["status"],
        "provider": rec["provider"],
        "provider_ref": result.provider_ref,
    }


async def get_payment(payment_id: str, tenant_id: Optional[str] = None) -> dict:
    """查询支付记录 (可选 tenant_id 校验)."""
    rec = _PAYMENT_RECORDS.get(payment_id)
    if not rec:
        raise NotFoundException(f"payment '{payment_id}' not found")
    if tenant_id and rec["tenant_id"] != tenant_id:
        raise NotFoundException(f"payment '{payment_id}' not found")
    return dict(rec)


async def list_payments_for_invoice(invoice_id: str, tenant_id: str) -> list[dict]:
    """列出指定 invoice 的所有支付记录."""
    return [
        dict(rec) for rec in _PAYMENT_RECORDS.values()
        if rec["invoice_id"] == invoice_id and rec["tenant_id"] == tenant_id
    ]