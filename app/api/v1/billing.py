"""
商业化计费 REST API (W72 Phase 8 起步)

不破坏老路径: 仅在 app/api/v1/billing.py 新增, 业务路径不动.
"""
from __future__ import annotations

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.billing import (
    PlanOut, TenantCreate, TenantCreated, TenantOut,
    SubscriptionOut, InvoiceCreate, InvoiceOut, InvoicePayRequest,
    UsageRecordIn, UsageSummary,
)
from app.services import billing_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commercial/billing", tags=["commercial-billing"])


async def get_current_tenant(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> str:
    """多租户隔离: 强制 tenant_id + api_key 校验."""
    tenant = await billing_service.verify_tenant(db, x_tenant_id, x_api_key)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid tenant_id or api_key",
        )
    return tenant.tenant_id


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[PlanOut]:
    """列出所有套餐."""
    return await billing_service.list_plans(db)


@router.post("/tenants", response_model=TenantCreated, status_code=201)
async def create_tenant(
    req: TenantCreate,
    db: AsyncSession = Depends(get_db),
) -> TenantCreated:
    """注册新租户 (返回一次性 API key)."""
    try:
        return await billing_service.create_tenant(db, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tenants/me", response_model=TenantOut)
async def get_me(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    """查询当前 tenant (X-Tenant-ID + X-API-Key 校验)."""
    tenant = await billing_service.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="tenant not found")
    return tenant


@router.get("/subscriptions/me", response_model=SubscriptionOut)
async def get_my_subscription(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionOut:
    """查询当前 tenant 订阅."""
    sub = await billing_service.get_subscription(db, tenant_id)
    if not sub:
        raise HTTPException(status_code=404, detail="no active subscription")
    return sub


@router.post("/invoices", response_model=InvoiceOut, status_code=201)
async def create_invoice(
    req: InvoiceCreate,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    """创建账单."""
    try:
        return await billing_service.create_invoice(db, tenant_id, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceOut)
async def pay_invoice(
    invoice_id: str,
    req: InvoicePayRequest,
    db: AsyncSession = Depends(get_db),
) -> InvoiceOut:
    """Mock 支付 (Phase 8 起步, 后续 W76 接真实支付)."""
    try:
        return await billing_service.pay_invoice(db, invoice_id, req.payment_ref)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/usage", status_code=204)
async def record_usage(
    req: UsageRecordIn,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """上报用量."""
    await billing_service.record_usage(db, tenant_id, req)


@router.get("/usage/summary", response_model=UsageSummary)
async def get_usage_summary(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    """查询当前 tenant 用量汇总."""
    return await billing_service.get_usage_summary(db, tenant_id)
