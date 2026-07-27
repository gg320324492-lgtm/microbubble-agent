"""
License 校验服务 (W73 第 1 批 B-1 商业化 Phase 8 收口)

W72 第 2 批 B-5 Dockerfile.commercial + license-check.py 起步收口:
- License 服务端校验 (在线)
- 离线 7 天宽限 (最后一次在线校验后 7 天内继续可用)
- License 过期 → read-only 模式
- License 表缓存 + 在线校验结果落表

不破坏老路径: 仅在 app/services/license_service.py 新增.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.models.billing import License, CommercialTenant

logger = logging.getLogger(__name__)

# 离线宽限期 (天)
OFFLINE_GRACE_DAYS = 7


def _hash_license_key(license_key: str) -> str:
    """License key 哈希."""
    return hashlib.sha256(license_key.encode("utf-8")).hexdigest()


async def verify_license(
    db: AsyncSession,
    license_key: str,
    tenant_id: str,
    online: bool = True,
) -> dict:
    """验证 License 有效性.

    Returns:
        dict: {"valid": bool, "tier": str, "mode": "online"|"offline_grace"|"read_only"|"expired", "expires_at": datetime, "days_until_expiry": int}

    Logic:
    - online=True 时:
      1. license_key_hash 命中 → 检查 expires_at
      2. 过期 → mode="read_only"
      3. 未过期 → mode="online", 落库 last_verified_at
    - online=False 时 (离线宽限):
      1. last_verified_at + 7 天 > now → mode="offline_grace"
      2. 超 7 天 → mode="read_only"
    """
    if not license_key:
        raise ValidationException("license_key required")

    lk_hash = _hash_license_key(license_key)
    lic = await db.execute(select(License).where(License.license_key_hash == lk_hash))
    lic = lic.scalar_one_or_none()
    if not lic:
        return {"valid": False, "mode": "unknown", "reason": "license_key not found"}

    if lic.tenant_id != tenant_id:
        logger.warning("license tenant mismatch: lic.tenant=%s requester=%s", lic.tenant_id, tenant_id)
        return {"valid": False, "mode": "unknown", "reason": "license does not belong to tenant"}

    now = datetime.utcnow()
    expires = lic.expires_at
    days_until = (expires - now).days if expires else -1
    expired = expires is not None and expires < now

    if expired:
        lic.is_active = False
        await db.flush()
        return {
            "valid": False, "tier": lic.tier, "mode": "read_only",
            "expires_at": expires, "days_until_expiry": days_until,
            "reason": "license expired",
        }

    if online:
        # 在线校验 — 更新 last_verified_at
        lic.last_verified_at = now
        lic.is_active = True
        await db.flush()
        return {
            "valid": True, "tier": lic.tier, "mode": "online",
            "expires_at": expires, "days_until_expiry": days_until,
        }

    # 离线宽限校验
    last = lic.last_verified_at or (now - timedelta(days=OFFLINE_GRACE_DAYS + 1))
    days_since_last = (now - last).days
    if days_since_last > OFFLINE_GRACE_DAYS:
        return {
            "valid": False, "tier": lic.tier, "mode": "read_only",
            "expires_at": expires, "days_until_expiry": days_until,
            "reason": f"offline grace {OFFLINE_GRACE_DAYS}d exceeded (last_verified {days_since_last}d ago)",
        }
    return {
        "valid": True, "tier": lic.tier, "mode": "offline_grace",
        "expires_at": expires, "days_until_expiry": days_until,
        "grace_days_remaining": OFFLINE_GRACE_DAYS - days_since_last,
    }


async def register_license(
    db: AsyncSession,
    license_key: str,
    tenant_id: str,
    tier: str,
    expires_at: Optional[datetime] = None,
) -> License:
    """注册 License (新装/换 key)."""
    if not tier or len(tier) > 32:
        raise ValidationException("tier required (max 32 chars)")
    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        raise NotFoundException(f"tenant '{tenant_id}' not found")
    lk_hash = _hash_license_key(license_key)
    lic = License(
        license_key_hash=lk_hash,
        tenant_id=tenant_id,
        tier=tier,
        last_verified_at=datetime.utcnow(),
        expires_at=expires_at,
        is_active=True,
    )
    db.add(lic)
    await db.flush()
    logger.info("license registered: tenant=%s tier=%s", tenant_id, tier)
    return lic


async def revoke_license(db: AsyncSession, license_key: str) -> bool:
    """吊销 License."""
    lk_hash = _hash_license_key(license_key)
    lic = await db.execute(select(License).where(License.license_key_hash == lk_hash))
    lic = lic.scalar_one_or_none()
    if not lic:
        return False
    lic.is_active = False
    await db.flush()
    logger.info("license revoked: tenant=%s", lic.tenant_id)
    return True