"""
租户数据隔离拦截器 (W73 第 1 批 B-1)

W72 第 2 批 B-5 起步收口:
- 跨租户数据访问 422 (TenantIsolationViolation)
- 共享资源白名单 (plans 表 / 公共 endpoint)
- 隔离 token 校验 (防御 IDOR)

不破坏老路径: 仅在 app/services/tenant_data_isolation.py 新增,
与 billing_service.verify_tenant() 协同 (头部 X-Tenant-ID + X-API-Key).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.exceptions import AppException
from app.services.tenant_service import verify_tenant
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TenantIsolationViolation(AppException):
    """跨租户访问拦截 (HTTP 422)."""

    code = "TENANT_ISOLATION_VIOLATION"
    message = "Cross-tenant data access forbidden"
    status_code = 422

    def __init__(self, resource: str, owner_tenant: str, requester_tenant: str):
        super().__init__(
            message=f"resource '{resource}' owned by tenant '{owner_tenant}', requester='{requester_tenant}'",
            details={"resource": resource, "owner_tenant": owner_tenant, "requester_tenant": requester_tenant},
        )


# 共享资源白名单 — 无 tenant_id 字段, 不参与隔离
SHARED_RESOURCES = frozenset({"commercial_plans"})


async def check_cross_tenant(
    db: AsyncSession,
    requester_tenant_id: str,
    requester_api_key: str,
    target_tenant_id: str,
    resource: str,
) -> None:
    """跨租户访问拦截 (有 owner_tenant 时校验).

    Args:
        requester_tenant_id: 调用方 tenant_id (从 X-Tenant-ID 头读出)
        requester_api_key: 调用方 api_key
        target_tenant_id: 资源归属 tenant_id (None = 公共资源放行)
        resource: 资源名 (用于日志/异常)

    Raises:
        TenantIsolationViolation: requester_tenant_id != target_tenant_id
    """
    if resource in SHARED_RESOURCES or target_tenant_id is None:
        return  # 公共资源放行
    if requester_tenant_id != target_tenant_id:
        logger.warning(
            "cross-tenant access blocked: requester=%s target=%s resource=%s",
            requester_tenant_id, target_tenant_id, resource,
        )
        raise TenantIsolationViolation(resource, target_tenant_id, requester_tenant_id)
    # 同租户则校验 api_key
    tenant = await verify_tenant(db, requester_tenant_id, requester_api_key)
    if not tenant:
        raise AppException(code="INVALID_API_KEY", message="api_key invalid", status_code=401)


def extract_tenant_from_obj(obj: Any) -> Optional[str]:
    """从 ORM 对象取 tenant_id 字段 (None 表示公共资源)."""
    return getattr(obj, "tenant_id", None)


def assert_tenant_match(obj: Any, requester_tenant_id: str, resource: str = "resource") -> None:
    """同步版断言 (对象已加载). 不查 DB, 仅校验 ID 匹配."""
    owner = extract_tenant_from_obj(obj)
    if owner is None or owner in SHARED_RESOURCES:
        return
    if owner != requester_tenant_id:
        raise TenantIsolationViolation(resource, owner, requester_tenant_id)