"""
订阅服务 (W74 第 1 批 B-2 真支付接入)

派工 v6 段 5 反馈 #6 实战:
- 订阅生命周期管理 (active / cancelled / expired / renewed)
- 与 payment_service / invoice_service 协同
- 升级 / 降级 plan
- 自动续费占位 (主拍单独拍板真接入)

不破坏老路径: 仅在 app/services/billing/subscription_service.py 新增.
与 app/services/billing_service.py 协同.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException, ConflictException
from app.models.billing import (
    Subscription, CommercialTenant, Plan, Invoice,
)
from app.schemas.billing import SubscriptionOut

logger = logging.getLogger(__name__)


def _generate_subscription_id() -> str:
    return "sub_" + secrets.token_hex(8)


async def get_active_subscription(db: AsyncSession, tenant_id: str) -> Optional[SubscriptionOut]:
    """获取 tenant 当前活跃订阅."""
    stmt = (
        select(Subscription)
        .where(
            and_(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
            )
        )
        .order_by(Subscription.started_at.desc())
    )
    result = await db.execute(stmt)
    sub = result.scalars().first()
    if not sub:
        return None
    return SubscriptionOut.model_validate(sub)


async def list_subscriptions(db: AsyncSession, tenant_id: str, limit: int = 50, offset: int = 0) -> list[Subscription]:
    """列出 tenant 全部订阅 (历史)."""
    stmt = (
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def cancel_subscription(
    db: AsyncSession, subscription_id: str, tenant_id: str,
) -> dict:
    """取消订阅 (立即生效或到期生效二选一, mock 立即)."""
    sub = await db.get(Subscription, subscription_id)
    if not sub:
        raise NotFoundException(f"subscription '{subscription_id}' not found")
    if sub.tenant_id != tenant_id:
        raise NotFoundException(f"subscription '{subscription_id}' not found")
    if sub.status != "active":
        raise ConflictException(f"subscription '{subscription_id}' already {sub.status}")

    sub.status = "cancelled"
    sub.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    logger.info("subscription cancelled: id=%s tenant=%s", subscription_id, tenant_id)
    return {
        "subscription_id": subscription_id,
        "status": sub.status,
        "cancelled_at": sub.cancelled_at.isoformat() if sub.cancelled_at else None,
    }


async def renew_subscription(
    db: AsyncSession, tenant_id: str, plan_code: str, period: str,
    invoice_id: Optional[str] = None,
) -> Subscription:
    """续费 / 升级订阅 (mock 直接生效)."""
    if period not in ("monthly", "yearly"):
        raise ValidationException("period must be 'monthly' or 'yearly'")

    plan = await db.get(Plan, plan_code)
    if not plan:
        raise NotFoundException(f"plan '{plan_code}' not found")

    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        raise NotFoundException(f"tenant '{tenant_id}' not found")

    days = 30 if period == "monthly" else 365
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sub = Subscription(
        subscription_id=_generate_subscription_id(),
        tenant_id=tenant_id,
        plan_code=plan_code,
        period=period,
        status="active",
        started_at=now,
        expires_at=now + timedelta(days=days),
        invoice_id=invoice_id,
    )
    db.add(sub)

    # 同步更新 tenant plan
    tenant.plan_code = plan_code

    await db.flush()
    logger.info(
        "subscription renewed: id=%s tenant=%s plan=%s period=%s expires=%s",
        sub.subscription_id, tenant_id, plan_code, period, sub.expires_at,
    )
    return sub


async def change_plan(
    db: AsyncSession, tenant_id: str, new_plan_code: str, period: str = "monthly",
) -> Subscription:
    """变更 plan (升级 / 降级). 取消老订阅 + 创建新订阅."""
    if period not in ("monthly", "yearly"):
        raise ValidationException("period must be 'monthly' or 'yearly'")

    # 取消老订阅 (如有)
    active_sub = await get_active_subscription(db, tenant_id)
    if active_sub:
        sub = await db.get(Subscription, active_sub.subscription_id)
        if sub:
            sub.status = "cancelled"
            sub.cancelled_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()

    # 创建新订阅
    new_sub = await renew_subscription(db, tenant_id, new_plan_code, period)
    logger.info(
        "plan changed: tenant=%s old=%s → new=%s",
        tenant_id, active_sub.plan_code if active_sub else "free", new_plan_code,
    )
    return new_sub


async def expire_overdue_subscriptions(db: AsyncSession) -> int:
    """清理过期订阅 (Celery beat 调用)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    stmt = select(Subscription).where(
        and_(
            Subscription.status == "active",
            Subscription.expires_at <= now,
        )
    )
    result = await db.execute(stmt)
    overdue = list(result.scalars().all())
    for sub in overdue:
        sub.status = "expired"
    await db.flush()
    if overdue:
        logger.info("expired %d overdue subscriptions", len(overdue))
    return len(overdue)


def is_auto_renew_enabled() -> bool:
    """自动续费开关 (mock 默认 False, 真接入主拍拍板)."""
    return False