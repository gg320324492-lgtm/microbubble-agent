"""
发票服务 (W73 第 1 批 B-1)

W72 第 2 批 B-5 起步收口:
- 发票 CRUD (create / list / pay / refund)
- 与计费网关集成 (BillingGateway)
- 多租户隔离 (tenant_id 强制)

不破坏老路径: 仅在 app/services/invoice_service.py 新增.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException, ConflictException
from app.models.billing import Invoice, CommercialTenant
from app.services.billing_gateway import get_billing_gateway

logger = logging.getLogger(__name__)


def _generate_invoice_id() -> str:
    return "inv_" + secrets.token_hex(12)


async def create_invoice(
    db: AsyncSession,
    tenant_id: str,
    plan_code: str,
    period: str,
    amount_cents: int,
    currency: str = "CNY",
) -> Invoice:
    """创建发票 (pending 状态)."""
    if amount_cents <= 0:
        raise ValidationException("amount_cents must be > 0")
    if period not in ("monthly", "yearly"):
        raise ValidationException("period must be 'monthly' or 'yearly'")

    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        raise NotFoundException(f"tenant '{tenant_id}' not found")

    inv = Invoice(
        invoice_id=_generate_invoice_id(),
        tenant_id=tenant_id,
        plan_code=plan_code,
        period=period,
        amount_cents=amount_cents,
        currency=currency,
        status="pending",
    )
    db.add(inv)
    await db.flush()
    logger.info("invoice created: id=%s tenant=%s amount=%d", inv.invoice_id, tenant_id, amount_cents)
    return inv


async def list_invoices(
    db: AsyncSession, tenant_id: str, status: Optional[str] = None, limit: int = 50, offset: int = 0,
) -> List[Invoice]:
    """列出发票 (强制 tenant_id 过滤)."""
    q = select(Invoice).where(Invoice.tenant_id == tenant_id)
    if status:
        q = q.where(Invoice.status == status)
    q = q.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_invoice(db: AsyncSession, invoice_id: str, tenant_id: Optional[str] = None) -> Invoice:
    """获取发票 (可选 tenant_id 校验)."""
    inv = await db.get(Invoice, invoice_id)
    if not inv:
        raise NotFoundException(f"invoice '{invoice_id}' not found")
    if tenant_id and inv.tenant_id != tenant_id:
        raise NotFoundException(f"invoice '{invoice_id}' not found")  # 信息隐藏
    return inv


async def pay_invoice(
    db: AsyncSession, invoice_id: str, tenant_id: str, provider: str = "mock",
) -> dict:
    """支付发票 (调计费网关)."""
    inv = await get_invoice(db, invoice_id, tenant_id=tenant_id)
    if inv.status == "paid":
        raise ConflictException(f"invoice '{invoice_id}' already paid")
    if inv.status == "refunded":
        raise ConflictException(f"invoice '{invoice_id}' already refunded")

    gateway = get_billing_gateway(provider)
    intent = await gateway.create_payment(inv.invoice_id, inv.amount_cents, inv.currency)
    result = await gateway.confirm_payment(intent.intent_id)

    if result.status == "success":
        inv.status = "paid"
        inv.payment_provider = provider
        inv.payment_ref = result.provider_ref
        inv.paid_at = datetime.utcnow()
        await db.flush()
        logger.info("invoice paid: id=%s provider=%s ref=%s", invoice_id, provider, result.provider_ref)
    else:
        inv.status = "failed"
        await db.flush()
        logger.warning("invoice payment failed: id=%s err=%s", invoice_id, result.error)
    return {
        "invoice_id": inv.invoice_id,
        "status": inv.status,
        "intent_id": intent.intent_id,
        "provider": provider,
        "provider_ref": result.provider_ref,
    }


async def refund_invoice(db: AsyncSession, invoice_id: str, tenant_id: str, provider: str = "mock") -> dict:
    """退款."""
    inv = await get_invoice(db, invoice_id, tenant_id=tenant_id)
    if inv.status != "paid":
        raise ConflictException(f"invoice '{invoice_id}' not paid, cannot refund")

    gateway = get_billing_gateway(provider)
    result = await gateway.refund(inv.invoice_id or invoice_id)

    if result.status == "success":
        inv.status = "refunded"
        await db.flush()
        logger.info("invoice refunded: id=%s", invoice_id)
    return {
        "invoice_id": invoice_id,
        "status": inv.status,
        "provider": provider,
        "provider_ref": result.provider_ref,
    }