"""Drive v2 PR17 — 文件秒传查重 REST API (2026-07-24, W68 第 14 批 B-1)

端点:
  POST /api/v1/drive/files/check-dedupe  body={file_hash}
    → {exists: bool, file_id?: int, dedupe_count?: int, file_name?: str, file_size?: int}

设计:
- 前端上传前算 sha256 → POST check-dedupe → exists=true 则秒传 (复用 file_id, 跳过 MinIO)
- user_id 隔离: 只查当前用户自己的活跃 drive 文件 (跨用户不秒传, 安全边界)
- 命中时 mark_dedupe_hit (count+1 + first_hit_at) — 审计"秒传省了多少次真实上传"

限流:
- POST: drive_upload tier (50/min, app/core/rate_limit.py — /api/v1/drive/* 写)

锚点范式第 172 守恒.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import get_current_user
from app.models.member import Member
from app.services.drive_dedupe_service import (
    DriveDedupeServiceError,
    check_dedupe,
    mark_dedupe_hit,
)

router = APIRouter(prefix="/drive/files", tags=["网盘文件秒传"])


def _reraise_dedupe_error(e: DriveDedupeServiceError) -> None:
    """DriveDedupeServiceError → 统一异常响应格式"""
    code_map = {
        400: "VALIDATION_ERROR",
        403: "FORBIDDEN",
        404: "RESOURCE_NOT_FOUND",
    }
    raise AppException(
        code=code_map.get(e.status_code, "DRIVE_DEDUPE_ERROR"),
        message=str(e),
        status_code=e.status_code,
    )


class CheckDedupeRequest(BaseModel):
    """POST /drive/files/check-dedupe 请求体"""

    file_hash: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="文件 sha256 hex (64 字符), 前端上传前流式计算",
    )


class CheckDedupeResponse(BaseModel):
    """POST /drive/files/check-dedupe 响应"""

    exists: bool = Field(..., description="是否命中秒传")
    file_id: int | None = Field(None, description="命中时: 已存在的 file_id (前端复用)")
    dedupe_count: int | None = Field(None, description="命中时: 秒传累计次数 (含本次)")
    file_name: str | None = Field(None, description="命中时: 已存在文件名")
    file_size: int | None = Field(None, description="命中时: 文件字节大小")


@router.post("/check-dedupe", response_model=CheckDedupeResponse)
async def check_file_dedupe(
    payload: CheckDedupeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
) -> CheckDedupeResponse:
    """v2 PR17: 文件秒传查重

    上传前调用: 前端算 sha256 → POST → exists=true 则复用 file_id 跳过 MinIO 上传.

    铁律:
    - user_id 隔离: 只查 current_user 自己的活跃 drive 文件 (跨用户不秒传)
    - deleted_at IS NULL: 已软删不秒传
    """
    try:
        hit = await check_dedupe(db, current_user.id, payload.file_hash)
    except DriveDedupeServiceError as e:
        _reraise_dedupe_error(e)
        return CheckDedupeResponse(exists=False)  # pragma: no cover (上面必抛)

    if hit is None:
        return CheckDedupeResponse(exists=False)

    # 命中 — 记录审计 (count+1 + first_hit_at)
    try:
        new_count = await mark_dedupe_hit(db, hit.id)
    except DriveDedupeServiceError as e:
        _reraise_dedupe_error(e)
        return CheckDedupeResponse(exists=False)  # pragma: no cover

    return CheckDedupeResponse(
        exists=True,
        file_id=hit.id,
        dedupe_count=new_count,
        file_name=hit.file_name,
        file_size=hit.file_size,
    )
