"""
商业化计费 Pydantic Schema (W72 Phase 8 起步)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class PlanOut(BaseModel):
    """套餐响应."""
    model_config = ConfigDict(from_attributes=True)

    plan_code: str
    display_name: str
    monthly_price_cents: int
    yearly_price_cents: int
    currency: str
    limits: dict
    features: list[str]
    is_active: bool


class TenantCreate(BaseModel):
    """创建租户请求."""
    name: str = Field(..., min_length=1, max_length=255)
    contact_email: str = Field(..., max_length=255)
    plan_code: str = "free"


class TenantCreated(BaseModel):
    """创建租户响应 (含一次性 API key)."""
    tenant_id: str
    name: str
    contact_email: str
    plan_code: str
    api_key: str  # 一次性, 仅创建时返回
    isolation_token: str
    created_at: datetime


class TenantOut(BaseModel):
    """租户信息响应 (不含 api_key)."""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    name: str
    contact_email: str
    plan_code: str
    status: str
    created_at: datetime


class SubscriptionOut(BaseModel):
    """订阅响应."""
    model_config = ConfigDict(from_attributes=True)

    subscription_id: str
    tenant_id: str
    plan_code: str
    period: str
    status: str
    started_at: datetime
    expires_at: datetime
    invoice_id: Optional[str]


class InvoiceCreate(BaseModel):
    """创建账单请求."""
    plan_code: str
    period: str = Field(..., pattern="^(monthly|yearly)$")
    payment_provider: str = "mock"


class InvoiceOut(BaseModel):
    """账单响应."""
    model_config = ConfigDict(from_attributes=True)

    invoice_id: str
    tenant_id: str
    plan_code: str
    period: str
    amount_cents: int
    currency: str
    status: str
    payment_provider: Optional[str]
    payment_ref: Optional[str]
    created_at: datetime
    paid_at: Optional[datetime]


class InvoicePayRequest(BaseModel):
    """账单支付请求 (mock)."""
    payment_ref: Optional[str] = None


class UsageRecordIn(BaseModel):
    """上报用量."""
    metric: str
    value: float
    metadata: dict = {}


class UsageSummary(BaseModel):
    """用量汇总."""
    tenant_id: str
    summary: dict[str, float]
