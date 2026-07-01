"""admin/audit REST API (PR7)

端点:
  GET    /api/v1/admin/audit            审计日志查询 (admin only)
  GET    /api/v1/admin/audit/summary    审计统计摘要 (按 action 聚合)

权限:
  仅 admin/leader 可访问 (Depends(get_current_admin))
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.knowledge import AuditLog
from app.api.v1.admin import get_current_admin
from app.models.member import Member
from app.services.audit_service import audit_service

logger = logging.getLogger("microbubble.admin_audit")
router = APIRouter(prefix="/admin/audit", tags=["审计"])


@router.get("")
async def list_audit(
    user_id: Optional[int] = Query(None, description="按用户过滤"),
    action: Optional[str] = Query(None, description="按 action 过滤"),
    ip_address: Optional[str] = Query(None, description="按 IP 过滤"),
    path_prefix: Optional[str] = Query(None, description="按路径前缀过滤"),
    from_dt: Optional[datetime] = Query(None, description="起始时间 (UTC)"),
    to_dt: Optional[datetime] = Query(None, description="截止时间 (UTC)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(get_current_admin),
):
    """审计日志查询 (admin only)"""
    result = await audit_service.query(
        db,
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        path_prefix=path_prefix,
        from_dt=from_dt,
        to_dt=to_dt,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/summary")
async def audit_summary(
    from_dt: Optional[datetime] = Query(None, description="起始时间 (UTC)"),
    to_dt: Optional[datetime] = Query(None, description="截止时间 (UTC)"),
    limit_per_action: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(get_current_admin),
):
    """审计统计: 按 action 聚合最近 N 条 (用于 dashboard 热力图)

    Returns:
        {
          "total": N,
          "by_action": {"login": N, "file_request_submit": N, ...},
          "by_status": {200: N, 404: N, 500: N, ...}
        }
    """
    base_q = select(AuditLog)
    if from_dt:
        base_q = base_q.where(AuditLog.created_at >= from_dt)
    if to_dt:
        base_q = base_q.where(AuditLog.created_at <= to_dt)

    # total
    total = (await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )).scalar() or 0

    # by_action
    action_rows = (await db.execute(
        select(AuditLog.action, func.count().label("n"))
        .select_from(base_q.subquery())
        .group_by(AuditLog.action)
        .order_by(desc("n"))
        .limit(50)
    )).all()
    by_action = {row[0]: row[1] for row in action_rows}

    # by_status
    status_rows = (await db.execute(
        select(AuditLog.status_code, func.count().label("n"))
        .select_from(base_q.subquery())
        .where(AuditLog.status_code.isnot(None))
        .group_by(AuditLog.status_code)
        .order_by(desc("n"))
    )).all()
    by_status = {row[0]: row[1] for row in status_rows}

    return {
        "total": total,
        "by_action": by_action,
        "by_status": by_status,
    }
