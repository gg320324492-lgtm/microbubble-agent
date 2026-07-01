"""分片上传 REST API (PR2.8)

基于 PR2.3 简化版 service, 暴露 3 端点:
  POST /api/v1/upload/multipart/init
    body: {filename, content_type, total_size, folder_path?, storage_mode?, visibility?, title?, folder_id?}
    resp: {upload_id, object_name, part_size, total_size}
  POST /api/v1/upload/multipart/{upload_id}/complete
    body: binary file content (FastAPI UploadFile)
    resp: {object_name, size, etag, knowledge_id}
  POST /api/v1/upload/multipart/abort
    body: {upload_id}
    resp: 204

设计简化 (PR2.3 决策):
  - upload_id = object_name (init 唯一产物, 不真用 S3 CreateMultipartUpload)
  - 后端单端点接收全部 bytes, minio put_object 自管分片
  - 简化前端: 不用管 part 编号 / etag 收集
  - 失败回滚: complete 失败时调 abort
  - abort 用 body 传 upload_id 而非 path 段 (PR2.8 e2e 验证 405 路径冲突)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.drive_service import (
    DriveService,
    DriveServiceError,
    MAX_DRIVE_FILE_SIZE_BYTES,
    MAX_DRIVE_FILE_SIZE_MB,
)
from app.services.folder_service import FolderService
from app.services.generic_chunked_upload_service import (
    ChunkedUploadError,
    generic_chunked_upload_service,
)

logger = logging.getLogger("microbubble.upload_multipart")
router = APIRouter(prefix="/upload/multipart", tags=["分片上传"])


# === Schemas ===

class MultipartInitRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content_type: str = "application/octet-stream"
    total_size: int = Field(..., gt=0, le=MAX_DRIVE_FILE_SIZE_BYTES)
    folder_path: Optional[str] = None  # 父 folder 物化 path, e.g. "1/4/"
    storage_mode: str = "drive"        # 仅支持 drive (kb 走现有 /upload)
    visibility: str = "team"           # private | team | public
    title: Optional[str] = None         # 知识库 title
    folder_id: Optional[int] = None     # Knowledge.folder_id


class MultipartInitResponse(BaseModel):
    upload_id: str
    object_name: str
    part_size: int
    total_size: int


class MultipartCompleteResponse(BaseModel):
    object_name: str
    size: int
    etag: str
    knowledge_id: int  # 同步落 Knowledge 元数据后的 id


# === 端点 ===

@router.post("/init", response_model=MultipartInitResponse)
async def init_multipart(
    payload: MultipartInitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """初始化分片上传 (实际不调 S3 CreateMultipartUpload, 仅校验 + 算 object_name)

    上传完成后调 complete 端点接收 bytes + 落 Knowledge 元数据.
    """
    if payload.storage_mode != "drive":
        raise HTTPException(
            status_code=400,
            detail=f"multipart 仅支持 drive 模式, 当前 {payload.storage_mode}",
        )
    if payload.visibility not in ("private", "team", "public"):
        raise HTTPException(
            status_code=400,
            detail=f"非法 visibility: {payload.visibility}",
        )
    # folder_id 越权校验
    if payload.folder_id is not None:
        folder_svc = FolderService(db)
        folder = await folder_svc.get_folder(payload.folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail=f"folder {payload.folder_id} 不存在")
        if folder.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权在该 folder 中上传")

    try:
        init_resp = await generic_chunked_upload_service.init_upload(
            filename=payload.filename,
            content_type=payload.content_type,
            total_size=payload.total_size,
            folder_path=payload.folder_path,
            storage_mode=payload.storage_mode,
            user_id=current_user.id,
        )
    except ChunkedUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return MultipartInitResponse(**init_resp)


@router.post("/complete", response_model=MultipartCompleteResponse)
async def complete_multipart(
    file: UploadFile = File(..., description="完整文件 bytes"),
    upload_id: str = Form(..., description="init 返回的 upload_id (= object_name)"),
    content_type: Optional[str] = Form(None),
    visibility: str = Form("team"),
    title: Optional[str] = Form(None),
    folder_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """完成分片上传: 接收 bytes 写 MinIO + 落 Knowledge 元数据

    upload_id 走 Form 而非 path 段 (因 upload_id 含 '/', FastAPI path param 不允许 '/').
    失败回滚: put_object 失败或 create_file 失败时, 调 abort 清 MinIO.
    """
    if visibility not in ("private", "team", "public"):
        raise HTTPException(status_code=400, detail=f"非法 visibility: {visibility}")

    # folder_id 越权校验
    if folder_id is not None:
        folder_svc = FolderService(db)
        folder = await folder_svc.get_folder(folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail=f"folder {folder_id} 不存在")
        if folder.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权在该 folder 中上传")

    # 1) 读 file bytes
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传内容为空")
    if len(data) > MAX_DRIVE_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件 {len(data)} bytes 超过 {MAX_DRIVE_FILE_SIZE_MB}MB",
        )
    real_ct = content_type or file.content_type or "application/octet-stream"

    # 2) 写 MinIO
    try:
        complete_resp = await generic_chunked_upload_service.complete_upload(
            upload_id=upload_id,
            data=data,
            content_type=real_ct,
        )
    except ChunkedUploadError as e:
        # 失败回滚
        await generic_chunked_upload_service.abort_upload(upload_id=upload_id)
        raise HTTPException(status_code=e.status_code, detail=str(e))

    # 3) 落 Knowledge 元数据
    real_filename = file.filename or upload_id.split("/")[-1]
    ext = "." + real_filename.rsplit(".", 1)[-1] if "." in real_filename else ""
    drive_svc = DriveService(db)
    try:
        knowledge = await drive_svc.create_file(
            title=title or real_filename,
            file_path=complete_resp["object_name"],
            file_name=real_filename,
            file_type=ext,
            file_size=complete_resp["size"] or len(data),
            owner_id=current_user.id,
            storage_mode="drive",
            visibility=visibility,
            folder_id=folder_id,
            created_by=current_user.id,
            source_type="drive",
        )
    except DriveServiceError as e:
        # 失败回滚: 清 MinIO
        await generic_chunked_upload_service.abort_upload(upload_id=upload_id)
        raise HTTPException(status_code=e.status_code, detail=str(e))

    logger.info(
        f"[multipart.complete] upload_id={upload_id} knowledge_id={knowledge.id} "
        f"file_name={real_filename} size={complete_resp['size']}"
    )
    return MultipartCompleteResponse(
        object_name=complete_resp["object_name"],
        size=complete_resp["size"] or 0,
        etag=complete_resp["etag"],
        knowledge_id=knowledge.id,
    )


class AbortRequest(BaseModel):
    upload_id: str = Field(..., min_length=1)


@router.post("/abort", status_code=204)
async def abort_multipart(payload: AbortRequest):
    """取消上传, 清可能已写入的 MinIO 对象

    body: {"upload_id": "drive/abc.txt"}
    """
    ok = await generic_chunked_upload_service.abort_upload(upload_id=payload.upload_id)
    if not ok:
        raise HTTPException(status_code=500, detail="abort 失败")
    return
