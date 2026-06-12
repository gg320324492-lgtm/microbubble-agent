"""Admin 路由 — Agent Trace 监控 + 未来其他 admin 功能

权限：所有端点需 Depends(get_current_admin) — 普通用户 403
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.agent_trace import AgentTrace
from app.models.member import Member

logger = logging.getLogger("microbubble.admin")
router = APIRouter()


async def get_current_admin(current_user: Member = Depends(get_current_user)) -> Member:
    """仅 admin/leader 可访问"""
    if current_user.role not in ("admin", "leader"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


@router.get("/admin/agent-traces")
async def list_agent_traces(
    user_id: Optional[int] = Query(None, description="按 user_id 过滤"),
    date_from: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    current_user: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """列出 agent_traces（按时间倒序）"""
    q = select(AgentTrace).order_by(AgentTrace.created_at.desc()).limit(limit)
    if user_id:
        q = q.where(AgentTrace.user_id == user_id)
    if date_from:
        try:
            df = datetime.strptime(date_from, "%Y-%m-%d")
            q = q.where(AgentTrace.created_at >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, "%Y-%m-%d")
            # +1 天包含当天
            from datetime import timedelta
            q = q.where(AgentTrace.created_at < dt + timedelta(days=1))
        except ValueError:
            pass
    result = await db.execute(q)
    traces = result.scalars().all()
    return {
        "traces": [t.to_dict() for t in traces],
        "total": len(traces),
        "filters": {"user_id": user_id, "date_from": date_from, "date_to": date_to},
    }


@router.get("/admin/agent-traces/{trace_id}")
async def get_agent_trace(
    trace_id: int,
    current_user: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """获取单个 trace 详情"""
    result = await db.execute(select(AgentTrace).where(AgentTrace.id == trace_id))
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} 不存在")
    d = trace.to_dict()
    # 详情包含完整 tool_calls 和 rich_blocks
    d["tool_calls"] = trace.tool_calls or []
    d["rich_blocks"] = trace.rich_blocks or []
    d["brief"] = trace.brief
    d["detail"] = trace.detail
    return d
