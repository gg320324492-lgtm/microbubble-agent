"""
商业化计费 ORM 模型 (W72 Phase 8 起步)

4 张表:
- plans: 套餐定义 (free / pro / enterprise)
- subscriptions: 租户订阅
- invoices: 账单
- usage_records: 用量记录
- licenses: License 缓存
- tenants: 租户多租户表 (与 commercial/saas-platform 协同)
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, JSON, ForeignKey, Index, Boolean, Text,
)
from sqlalchemy.orm import relationship

# W73 第 1 批 B-1 收口: 修正 W72 B-5 起步的 import 错误 (Base 在 app.core.database, 不在 app.models.base)
from app.core.database import Base


class Plan(Base):
    """套餐定义."""
    __tablename__ = "commercial_plans"

    plan_code = Column(String(32), primary_key=True)  # free / pro / enterprise
    display_name = Column(String(128), nullable=False)
    monthly_price_cents = Column(Integer, default=0)
    yearly_price_cents = Column(Integer, default=0)
    currency = Column(String(8), default="CNY")
    limits = Column(JSON, default={})  # api_calls / storage_mb / asr_seconds / agent_turns
    features = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommercialTenant(Base):
    """商业化租户 (主索引)."""
    __tablename__ = "commercial_tenants"

    tenant_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    plan_code = Column(String(32), ForeignKey("commercial_plans.plan_code"), default="free")
    status = Column(String(32), default="active")  # active / suspended / deleted
    api_key_hash = Column(String(128))
    isolation_token = Column(String(64))
    metadata_json = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_commercial_tenants_status", "status"),
        Index("ix_commercial_tenants_plan", "plan_code"),
    )


class Subscription(Base):
    """租户订阅."""
    __tablename__ = "commercial_subscriptions"

    subscription_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("commercial_tenants.tenant_id"), nullable=False)
    plan_code = Column(String(32), ForeignKey("commercial_plans.plan_code"), nullable=False)
    period = Column(String(16), nullable=False)  # monthly / yearly
    status = Column(String(32), default="active")  # active / cancelled / expired
    started_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)
    invoice_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_commercial_subs_tenant", "tenant_id"),
        Index("ix_commercial_subs_status", "status"),
    )


class Invoice(Base):
    """账单."""
    __tablename__ = "commercial_invoices"

    invoice_id = Column(String(64), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("commercial_tenants.tenant_id"), nullable=False)
    plan_code = Column(String(32), ForeignKey("commercial_plans.plan_code"), nullable=False)
    period = Column(String(16), nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(8), default="CNY")
    status = Column(String(32), default="pending")  # pending / paid / failed / refunded
    payment_provider = Column(String(32), nullable=True)
    payment_ref = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_commercial_invoices_tenant", "tenant_id"),
        Index("ix_commercial_invoices_status", "status"),
    )


class UsageRecord(Base):
    """用量记录."""
    __tablename__ = "commercial_usage_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(64), ForeignKey("commercial_tenants.tenant_id"), nullable=False)
    metric = Column(String(64), nullable=False)  # api_calls / storage_mb / asr_seconds / agent_turns
    value = Column(Numeric(20, 4), nullable=False)
    record_metadata = Column("metadata", JSON, default={})
    recorded_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_commercial_usage_tenant_metric", "tenant_id", "metric"),
        Index("ix_commercial_usage_recorded_at", "recorded_at"),
    )


class License(Base):
    """License 缓存 (与 docker/commercial/license-check.py 协同)."""
    __tablename__ = "commercial_licenses"

    license_key_hash = Column(String(128), primary_key=True)
    tenant_id = Column(String(64), ForeignKey("commercial_tenants.tenant_id"), nullable=False)
    tier = Column(String(32), nullable=False)
    last_verified_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    __table_args__ = (
        Index("ix_commercial_licenses_tenant", "tenant_id"),
    )
