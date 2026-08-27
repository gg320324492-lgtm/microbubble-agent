"""Health Check — Phase 8 liveness/readiness probe.

[类 20.198] 2026-08-28 添加 /api/v1/health:
- 返回 200 + { status: ok, db: ok/fail, alembic_head: <hash>, env: <env>, version: <ver>, timestamp }
- 给负载均衡 / k8s readiness probe 用 (之前 /health 只到 nginx SPA fallback, 不验 app 进程)
- 不需鉴权 (public endpoint, 仅返回 status 不返回敏感数据)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings  # noqa: PLC0415
from app.core.database import get_db  # noqa: PLC0415


router = APIRouter(prefix="/api/v1", tags=["健康检查"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    """Liveness + DB ping + alembic head."""
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    alembic_head = "unknown"
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        row = result.first()
        if row is not None:
            alembic_head = row[0]
    except Exception:
        pass  # alembic_version 表可能不存在 (没跑过 migration)

    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "fail",
        "alembic_head": alembic_head,
        "env": settings.APP_ENV,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
