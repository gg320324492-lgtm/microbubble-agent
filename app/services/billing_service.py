"""
商业化计费服务 (W72 Phase 8 起步)

不破坏老路径: 仅在 app/services/billing_service.py 新增, 业务路径不动.
Phase 8 起步: 套餐列表 + 租户创建 + invoice 模拟 + 用量上报.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import get_request_id, get_task_id
from app.models.billing import (
    Plan, CommercialTenant, Subscription, Invoice, UsageRecord,
)
from app.schemas.billing import (
    PlanOut, TenantCreate, TenantCreated, TenantOut,
    SubscriptionOut, InvoiceCreate, InvoiceOut, UsageRecordIn, UsageSummary,
)

logger = logging.getLogger(__name__)

PLAN_PRICING = {
    "free": {"monthly": 0, "yearly": 0, "limits": {"api_calls": 1000, "storage_mb": 100}},
    "pro": {"monthly": 299, "yearly": 2988, "limits": {"api_calls": 50000, "storage_mb": 10240}},
    "enterprise": {"monthly": 1999, "yearly": 19988, "limits": {"api_calls": 500000, "storage_mb": 102400}},
}


def _hash_key(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


async def seed_plans(db: AsyncSession) -> None:
    """启动时 seed 3 个 plan (幂等)."""
    for code, pricing in PLAN_PRICING.items():
        existing = await db.get(Plan, code)
        if existing:
            continue
        plan = Plan(
            plan_code=code,
            display_name=code.title(),
            monthly_price_cents=pricing["monthly"] * 100,
            yearly_price_cents=pricing["yearly"] * 100,
            currency="CNY",
            limits=pricing["limits"],
            features=[],
            is_active=True,
        )
        db.add(plan)
    await db.commit()


async def list_plans(db: AsyncSession) -> list[PlanOut]:
    """列出所有生效套餐."""
    stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.monthly_price_cents)  # noqa: E712
    result = await db.execute(stmt)
    return [PlanOut.model_validate(p) for p in result.scalars().all()]


async def create_tenant(db: AsyncSession, req: TenantCreate) -> TenantCreated:
    """创建租户 (返回一次性 API key)."""
    if req.plan_code not in PLAN_PRICING:
        raise ValueError(f"unknown plan: {req.plan_code}")

    tenant_id = "tenant_" + secrets.token_hex(4)
    api_key = "mbk_" + secrets.token_urlsafe(32)
    isolation_token = secrets.token_urlsafe(16)

    tenant = CommercialTenant(
        tenant_id=tenant_id,
        name=req.name,
        contact_email=req.contact_email,
        plan_code=req.plan_code,
        status="active",
        api_key_hash=_hash_key(api_key),
        isolation_token=isolation_token,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    logger.info(f"[req={get_request_id() or '-'} task={get_task_id() or '-'}] created tenant {tenant_id} ({req.plan_code})")
    return TenantCreated(
        tenant_id=tenant.tenant_id,
        name=tenant.name,
        contact_email=tenant.contact_email,
        plan_code=tenant.plan_code,
        api_key=api_key,
        isolation_token=tenant.isolation_token,
        created_at=tenant.created_at,
    )


async def get_tenant(db: AsyncSession, tenant_id: str) -> Optional[TenantOut]:
    """按 tenant_id 查询."""
    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        return None
    return TenantOut.model_validate(tenant)


async def verify_tenant(db: AsyncSession, tenant_id: str, api_key: str) -> Optional[CommercialTenant]:
    """验证 tenant_id + api_key (隔离底线)."""
    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        return None
    if tenant.status != "active":
        return None
    if tenant.api_key_hash != _hash_key(api_key):
        return None
    return tenant


async def create_invoice(db: AsyncSession, tenant_id: str, req: InvoiceCreate) -> InvoiceOut:
    """创建账单."""
    if req.plan_code not in PLAN_PRICING:
        raise ValueError(f"unknown plan: {req.plan_code}")
    if req.period not in ("monthly", "yearly"):
        raise ValueError(f"unknown period: {req.period}")

    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        raise ValueError(f"tenant {tenant_id} not found")

    pricing = PLAN_PRICING[req.plan_code]
    amount_cents = pricing[req.period] * 100

    invoice_id = "inv_" + secrets.token_hex(6)
    invoice = Invoice(
        invoice_id=invoice_id,
        tenant_id=tenant_id,
        plan_code=req.plan_code,
        period=req.period,
        amount_cents=amount_cents,
        currency="CNY",
        status="pending",
        payment_provider=req.payment_provider,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return InvoiceOut.model_validate(invoice)


async def pay_invoice(db: AsyncSession, invoice_id: str, payment_ref: Optional[str] = None) -> InvoiceOut:
    """Mock 支付成功, 同步创建 subscription."""
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError(f"invoice {invoice_id} not found")
    if invoice.status != "pending":
        raise ValueError(f"invoice {invoice_id} already {invoice.status}")

    invoice.status = "paid"
    invoice.paid_at = datetime.utcnow()
    invoice.payment_ref = payment_ref or f"mock_{secrets.token_hex(8)}"

    days = 30 if invoice.period == "monthly" else 365
    subscription = Subscription(
        subscription_id="sub_" + secrets.token_hex(6),
        tenant_id=invoice.tenant_id,
        plan_code=invoice.plan_code,
        period=invoice.period,
        status="active",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=days),
        invoice_id=invoice_id,
    )
    db.add(subscription)

    # 同步更新 tenant plan
    tenant = await db.get(CommercialTenant, invoice.tenant_id)
    if tenant:
        tenant.plan_code = invoice.plan_code

    await db.commit()
    await db.refresh(invoice)
    return InvoiceOut.model_validate(invoice)


async def get_subscription(db: AsyncSession, tenant_id: str) -> Optional[SubscriptionOut]:
    stmt = select(Subscription).where(
        Subscription.tenant_id == tenant_id,
        Subscription.status == "active",
    ).order_by(Subscription.started_at.desc())
    result = await db.execute(stmt)
    sub = result.scalars().first()
    if not sub:
        return None
    return SubscriptionOut.model_validate(sub)


async def record_usage(db: AsyncSession, tenant_id: str, req: UsageRecordIn) -> None:
    """记录一次用量."""
    rec = UsageRecord(
        tenant_id=tenant_id,
        metric=req.metric,
        value=req.value,
        record_metadata=req.metadata,
    )
    db.add(rec)
    await db.commit()


async def get_usage_summary(db: AsyncSession, tenant_id: str, since: Optional[datetime] = None) -> UsageSummary:
    """汇总 tenant 用量."""
    stmt = select(UsageRecord.metric, func.sum(UsageRecord.value)).where(
        UsageRecord.tenant_id == tenant_id,
    )
    if since is not None:
        stmt = stmt.where(UsageRecord.recorded_at >= since)
    stmt = stmt.group_by(UsageRecord.metric)
    result = await db.execute(stmt)
    summary = {metric: float(total) for metric, total in result.all()}
    return UsageSummary(tenant_id=tenant_id, summary=summary)
