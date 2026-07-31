"""Drive → KB 入库 API (W98)

端点:
  POST   /api/v1/drive/{file_id}/to-kb          → 单文件入库 (drive → kb)
  POST   /api/v1/drive/folders/{folder_id}/to-kb → 文件夹批量入库
  GET    /api/v1/drive/ingestable                → 列出可入库文件 (未转化)

统一错误 envelope: 全部走 raise_app_error (AppException), 与 _drive_error_helper
铁律一致 (新 endpoint 禁止 raise HTTPException)。
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._drive_error_helper import (
    ERR_FILE_NOT_FOUND,
    raise_app_error,
)
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.drive_service import DriveService
from app.services.drive_to_kb_service import DriveToKBError, DriveToKBService

logger = logging.getLogger("microbubble.drive_to_kb_api")
router = APIRouter(prefix="/drive", tags=["网盘入库 RAG"])


# === Schemas ===


class IngestResult(BaseModel):
    """单文件入库结果"""

    knowledge_id: int
    already_ingested: bool = False
    title: Optional[str] = None
    content_length: int = 0
    source_file_id: int


class IngestBatchResult(BaseModel):
    """批量入库结果"""

    dry_run: bool = False
    total: int = 0
    ingested: int = 0
    already_ingested: int = 0
    failed: int = 0
    errors: List[dict] = []
    knowledge_ids: List[int] = []


class IngestableItem(BaseModel):
    """可入库文件清单项"""

    file_id: int
    title: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    visibility: Optional[str] = None
    folder_id: Optional[int] = None
    ingestable: bool = True


async def _get_visible_drive_file(
    svc: DriveService, file_id: int, user_id: int
) -> object:
    """查 drive 文件 + 权限校验 (owner 或 visibility != private), 失败 raise_app_error"""
    f = await svc.get_file(file_id, current_user_id=user_id)
    if f is None:
        raise_app_error(404, ERR_FILE_NOT_FOUND, "file 不存在或非 owner", file_id=file_id)
    return f


# === Endpoints ===


@router.post("/{file_id}/to-kb", response_model=IngestResult)
async def drive_file_to_kb(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """单文件入库: drive 文件 → kb 条目 (完整 RAG 管线)

    幂等: 同 file_id 重复调用返回既有 kb 行 (already_ingested=true)。
    原 drive 行保留 (文件管理仍走 drive 域)。
    """
    drive_svc = DriveService(db)
    await _get_visible_drive_file(drive_svc, file_id, current_user.id)

    svc = DriveToKBService(db)
    try:
        result = await svc.ingest_drive_file(file_id)
    except DriveToKBError as e:
        # 404 → FILE_NOT_FOUND; 其他 (400/403/422/502) → 保持 DriveToKBError 语义
        code = ERR_FILE_NOT_FOUND if e.status_code == 404 else "DRIVE_TO_KB_ERROR"
        raise_app_error(
            e.status_code,
            code,
            e.message,
            file_id=file_id,
        )
    return result


@router.post("/folders/{folder_id}/to-kb", response_model=IngestBatchResult)
async def drive_folder_to_kb(
    folder_id: int,
    dry_run: bool = Query(False, description="仅统计不真正入库"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """文件夹批量入库: 该文件夹下所有未转化 drive 文件"""
    svc = DriveToKBService(db)
    try:
        return await svc.ingest_folder(folder_id, dry_run=dry_run)
    except DriveToKBError as e:
        code = ERR_FILE_NOT_FOUND if e.status_code == 404 else "DRIVE_TO_KB_ERROR"
        raise_app_error(e.status_code, code, e.message, folder_id=folder_id)


@router.get("/ingestable", response_model=List[IngestableItem])
async def drive_ingestable(
    folder_id: Optional[int] = Query(None, description="限定文件夹 (默认团队可见全部)"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列出可入库的 drive 文件 (未转化 + 解析器支持)"""
    svc = DriveToKBService(db)
    try:
        items = await svc.list_ingestable(folder_id=folder_id)
    except DriveToKBError as e:
        code = ERR_FILE_NOT_FOUND if e.status_code == 404 else "DRIVE_TO_KB_ERROR"
        raise_app_error(e.status_code, code, e.message, folder_id=folder_id)
    return items
