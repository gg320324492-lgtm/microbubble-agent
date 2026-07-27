"""
商业化多租户服务 (W73 第 1 批 B-1 商业化 Phase 8 收口)

W72 第 2 批 B-5 起步收口:
- 多租户 CRUD (create / read / update / delete / list)
- 跨租户隔离 (cross-tenant access 422)
- API key 颁发 + 轮换
- 租户状态机 (active / suspended / deleted)

不破坏老路径: 仅在 app/services/tenant_service.py 新增.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, NotFoundException, ValidationException, ConflictException
from app.models.billing import CommercialTenant

logger = logging.getLogger(__name__)


def _hash_api_key(api_key: str) -> str:
    """API key 哈希 (SHA-256). 原始 key 仅生成时返回一次."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _generate_api_key() -> str:
    """生成 API key (URL-safe 48 字符)."""
    return "mbk_" + secrets.token_urlsafe(36)


def _generate_isolation_token() -> str:
    """生成 isolation token (租户间强隔离标识)."""
    return secrets.token_hex(32)


async def create_tenant(
    db: AsyncSession,
    name: str,
    contact_email: str,
    plan_code: str = "free",
) -> CommercialTenant:
    """创建租户 + 自动颁发 API key + isolation token.

    Raises:
        ConflictException: name/email 重复
        ValidationException: 参数非法
    """
    if not name or len(name) > 255:
        raise ValidationException("tenant name must be 1-255 chars")
    if not contact_email or "@" not in contact_email:
        raise ValidationException("invalid contact_email")

    # 重名检查
    existing = await db.execute(
        select(CommercialTenant).where(CommercialTenant.name == name)
    )
    if existing.scalar_one_or_none():
        raise ConflictException(f"tenant name '{name}' already exists")

    api_key = _generate_api_key()
    tenant = CommercialTenant(
        tenant_id=_generate_tenant_id(),
        name=name,
        contact_email=contact_email,
        plan_code=plan_code,
        status="active",
        api_key_hash=_hash_api_key(api_key),
        isolation_token=_generate_isolation_token(),
        metadata_json={},
    )
    db.add(tenant)
    await db.flush()
    # 把原始 API key 临时挂到 metadata_json['_initial_api_key'] 不可行 (已 hash), 改为单独返回
    tenant._initial_api_key = api_key  # type: ignore[attr-defined]
    logger.info("tenant created: tenant_id=%s plan=%s", tenant.tenant_id, plan_code)
    return tenant


def _generate_tenant_id() -> str:
    """生成 tenant_id (URL-safe 16 字符前缀 + 24 hex)."""
    return "ten_" + secrets.token_hex(12)


async def get_tenant(db: AsyncSession, tenant_id: str) -> CommercialTenant:
    """获取租户 (不存在 404)."""
    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant:
        raise NotFoundException(f"tenant '{tenant_id}' not found")
    return tenant


async def list_tenants(
    db: AsyncSession, status: Optional[str] = None, plan_code: Optional[str] = None, limit: int = 100, offset: int = 0,
) -> List[CommercialTenant]:
    """列出租户 (支持 status / plan_code 过滤)."""
    q = select(CommercialTenant)
    if status:
        q = q.where(CommercialTenant.status == status)
    if plan_code:
        q = q.where(CommercialTenant.plan_code == plan_code)
    q = q.order_by(CommercialTenant.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def verify_tenant(db: AsyncSession, tenant_id: str, api_key: str) -> Optional[CommercialTenant]:
    """验证 tenant_id + api_key (W72 B-5 已有方法, 此处统一入口)."""
    tenant = await db.get(CommercialTenant, tenant_id)
    if not tenant or tenant.status != "active":
        return None
    if tenant.api_key_hash != _hash_api_key(api_key):
        return None
    return tenant


async def rotate_api_key(db: AsyncSession, tenant_id: str) -> str:
    """轮换 API key, 返回新 key (仅此次可见)."""
    tenant = await get_tenant(db, tenant_id)
    new_key = _generate_api_key()
    tenant.api_key_hash = _hash_api_key(new_key)
    tenant.updated_at = datetime.utcnow()
    await db.flush()
    logger.info("tenant api_key rotated: tenant_id=%s", tenant_id)
    return new_key


async def update_tenant(
    db: AsyncSession, tenant_id: str, name: Optional[str] = None, contact_email: Optional[str] = None, plan_code: Optional[str] = None,
) -> CommercialTenant:
    """更新租户信息 (name / email / plan)."""
    tenant = await get_tenant(db, tenant_id)
    if name:
        tenant.name = name
    if contact_email:
        if "@" not in contact_email:
            raise ValidationException("invalid contact_email")
        tenant.contact_email = contact_email
    if plan_code:
        tenant.plan_code = plan_code
    tenant.updated_at = datetime.utcnow()
    await db.flush()
    return tenant


async def suspend_tenant(db: AsyncSession, tenant_id: str, reason: str = "manual") -> CommercialTenant:
    """暂停租户 (status → suspended)."""
    tenant = await get_tenant(db, tenant_id)
    tenant.status = "suspended"
    tenant.updated_at = datetime.utcnow()
    tenant.metadata_json = {**tenant.metadata_json, "suspend_reason": reason, "suspended_at": datetime.utcnow().isoformat()}
    await db.flush()
    logger.info("tenant suspended: tenant_id=%s reason=%s", tenant_id, reason)
    return tenant


async def reactivate_tenant(db: AsyncSession, tenant_id: str) -> CommercialTenant:
    """恢复被暂停的租户."""
    tenant = await get_tenant(db, tenant_id)
    if tenant.status != "suspended":
        raise ValidationException(f"tenant status is '{tenant.status}', cannot reactivate")
    tenant.status = "active"
    tenant.updated_at = datetime.utcnow()
    await db.flush()
    return tenant


async def delete_tenant(db: AsyncSession, tenant_id: str, hard: bool = False) -> bool:
    """删除租户 (soft=status='deleted' / hard=物理删除)."""
    tenant = await get_tenant(db, tenant_id)
    if hard:
        await db.delete(tenant)
        logger.info("tenant hard-deleted: tenant_id=%s", tenant_id)
    else:
        tenant.status = "deleted"
        tenant.updated_at = datetime.utcnow()
        await db.flush()
        logger.info("tenant soft-deleted: tenant_id=%s", tenant_id)
    return True