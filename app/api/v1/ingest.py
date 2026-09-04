"""W100 +73 admin ingest 触发端点

派工 brief: 可选 admin 触发 (admin 上传文件后立刻走 ingestion 流水线)

实现要点:
- POST /api/v1/admin/ingest/run  → 同步调用 ``auto_ingest_pending`` Celery task
  .delay() 走异步, 立刻返回一个 ``{task_id}`` 让前端可轮询状态
- GET  /api/v1/admin/ingest/status  → 返回 pending/ingesting/done/failed 计数
  + 最近失败的 meta 列表 (admin triage)

admin 鉴权复用 ``require_admin`` (派工 v6 §13 既有模式)
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.rag_auto_ingest_service import (
    DEFAULT_LIMIT,
    STATE_DONE,
    STATE_FAILED,
    STATE_INGESTING,
    STATE_PENDING,
)

logger = logging.getLogger("microbubble.api.ingest")

router = APIRouter(
    prefix="/admin/ingest",
    tags=["admin-ingest"],
)


async def get_current_admin(current_user: Member = Depends(get_current_user)) -> Member:
    """原 admin/leader-only guard — 2026-09-05 角色扁平化：所有登录成员等权"""
    return current_user


# ============================================================
# Pydantic Schemas
# ============================================================


class IngestRunRequest(BaseModel):
    """POST /admin/ingest/run request body."""

    limit: int = DEFAULT_LIMIT


class IngestRunResponse(BaseModel):
    """POST /admin/ingest/run response — kicks off async Celery batch."""

    ok: bool = True
    task_id: str


class FailureEntry(BaseModel):
    """Single failed-ingest row summary."""

    id: int
    title: str
    error: str


class IngestStatusResponse(BaseModel):
    """GET /admin/ingest/status — queue depth + recent failures."""

    pending: int
    ingesting: int
    done: int
    failed: int
    recent_failures: List[FailureEntry] = []


# ============================================================
# Endpoints
# ============================================================


@router.post(
    "/run",
    response_model=IngestRunResponse,
    summary="触发一次 RAG auto-ingest Celery 批 (admin)",
    dependencies=[Depends(get_current_admin)],
)
async def run_ingest(payload: IngestRunRequest) -> IngestRunResponse:
    """Kick off a single Celery batch. Idempotent — re-runs are safe."""
    # Import here to avoid Celery import cost when endpoint unused
    from app.services.rag_auto_ingest_service import auto_ingest_pending_files_task

    async_result = auto_ingest_pending_files_task.delay(limit=payload.limit)
    return IngestRunResponse(task_id=str(async_result.id))


@router.get(
    "/status",
    response_model=IngestStatusResponse,
    summary="RAG auto-ingest 队列状态 (admin)",
    dependencies=[Depends(get_current_admin)],
)
async def get_ingest_status(db: AsyncSession = Depends(get_db)) -> IngestStatusResponse:
    """Return ingest queue depth and up to 10 most-recent failed rows."""

    async def _count(state: str) -> int:
        res = await db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.analysis_status == state
            )
        )
        return int(res.scalar_one() or 0)

    pending = await _count(STATE_PENDING)
    ingesting = await _count(STATE_INGESTING)
    done = await _count(STATE_DONE)
    failed = await _count(STATE_FAILED)

    recent_res = await db.execute(
        select(Knowledge)
        .where(Knowledge.analysis_status == STATE_FAILED)
        .order_by(Knowledge.id.desc())
        .limit(10)
    )
    recent_rows = list(recent_res.scalars().all())
    recent_failures = [
        FailureEntry(
            id=row.id,
            title=row.title or "",
            error=(row.meta or {}).get("ingest_last_error", "") if row.meta else "",
        )
        for row in recent_rows
    ]

    return IngestStatusResponse(
        pending=pending,
        ingesting=ingesting,
        done=done,
        failed=failed,
        recent_failures=recent_failures,
    )
