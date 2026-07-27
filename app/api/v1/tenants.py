"""
租户管理 REST API (W73 第 1 批 B-1)

多租户 CRUD + API key 轮换 + 状态切换 (active/suspended/deleted).

不破坏老路径: 仅在 app/api/v1/tenants.py 新增.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import tenant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commercial/tenants", tags=["commercial-tenants"])


# ----- Schemas -----


class TenantCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    plan_code: str = Field("free", pattern=r"^(free|pro|enterprise)$")


class TenantUpdateIn(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    contact_email: Optional[EmailStr] = None
    plan_code: Optional[str] = Field(None, pattern=r"^(free|pro|enterprise)$")


class TenantOut(BaseModel):
    tenant_id: str
    name: str
    contact_email: str
    plan_code: str
    status: str
    isolation_token: str
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, t) -> "TenantOut":
        return cls(
            tenant_id=t.tenant_id,
            name=t.name,
            contact_email=t.contact_email,
            plan_code=t.plan_code,
            status=t.status,
            isolation_token=t.isolation_token or "",
            created_at=t.created_at.isoformat() if t.created_at else "",
            updated_at=t.updated_at.isoformat() if t.updated_at else "",
        )


class TenantCreatedOut(TenantOut):
    api_key: str  # 仅创建/轮换时返回一次


# ----- Routes -----


@router.post("", response_model=TenantCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreateIn, db: AsyncSession = Depends(get_db)):
    """创建租户 + 颁发 API key."""
    tenant = await tenant_service.create_tenant(
        db, name=payload.name, contact_email=payload.contact_email, plan_code=payload.plan_code,
    )
    await db.commit()
    out = TenantCreatedOut.from_orm(tenant)
    out.api_key = getattr(tenant, "_initial_api_key", "")
    return out


@router.get("", response_model=List[TenantOut])
async def list_tenants(
    status_filter: Optional[str] = Query(None, alias="status"),
    plan_code: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """列出租户 (支持 status / plan 过滤)."""
    tenants = await tenant_service.list_tenants(
        db, status=status_filter, plan_code=plan_code, limit=limit, offset=offset,
    )
    return [TenantOut.from_orm(t) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """获取租户详情."""
    t = await tenant_service.get_tenant(db, tenant_id)
    return TenantOut.from_orm(t)


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(tenant_id: str, payload: TenantUpdateIn, db: AsyncSession = Depends(get_db)):
    """更新租户信息 (name / email / plan)."""
    t = await tenant_service.update_tenant(
        db, tenant_id, name=payload.name, contact_email=payload.contact_email, plan_code=payload.plan_code,
    )
    await db.commit()
    return TenantOut.from_orm(t)


@router.post("/{tenant_id}/rotate-key", response_model=TenantCreatedOut)
async def rotate_api_key(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """轮换 API key (返回新 key, 仅此次可见)."""
    new_key = await tenant_service.rotate_api_key(db, tenant_id)
    await db.commit()
    t = await tenant_service.get_tenant(db, tenant_id)
    out = TenantCreatedOut.from_orm(t)
    out.api_key = new_key
    return out


@router.post("/{tenant_id}/suspend", response_model=TenantOut)
async def suspend_tenant(tenant_id: str, reason: str = Query("manual"), db: AsyncSession = Depends(get_db)):
    """暂停租户."""
    t = await tenant_service.suspend_tenant(db, tenant_id, reason=reason)
    await db.commit()
    return TenantOut.from_orm(t)


@router.post("/{tenant_id}/reactivate", response_model=TenantOut)
async def reactivate_tenant(tenant_id: str, db: AsyncSession = Depends(get_db)):
    """恢复被暂停的租户."""
    t = await tenant_service.reactivate_tenant(db, tenant_id)
    await db.commit()
    return TenantOut.from_orm(t)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: str, hard: bool = Query(False), db: AsyncSession = Depends(get_db)):
    """删除租户 (默认软删 status=deleted, hard=true 物理删除)."""
    await tenant_service.delete_tenant(db, tenant_id, hard=hard)
    await db.commit()
    return None