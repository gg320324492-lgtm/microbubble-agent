"""Drive Files REST API (PR2.5)

端点:
  POST   /api/v1/drive/files          → 创建文件元数据 (multipart 完成后调)
  GET    /api/v1/drive/files          → 列 drive 文件 (含分页/filter)
  GET    /api/v1/drive/files/{id}     → 详情
  PUT    /api/v1/drive/files/{id}     → 改名/移动/改 visibility
  DELETE /api/v1/drive/files/{id}     → 软删
  POST   /api/v1/drive/files/{id}/restore → 恢复 (3 天保留期内)
  POST   /api/v1/drive/files/{id}/extract-to-kb → 升级到公共知识库
  GET    /api/v1/drive/storage-stats  → 容量统计 (per member)

Multipart 简化 (PR2.3): 单端点流式接收 + minio 自管分片
  POST   /api/v1/drive/files/upload   → multipart 接收 (单端点, content-type: multipart/form-data)
                                          form: {file, filename, content_type, total_size,
                                                 folder_id?, visibility?, storage_mode?}
"""
import io
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_service import (
    DriveService,
    DriveServiceError,
    MAX_DRIVE_FILE_SIZE_BYTES,
    MAX_DRIVE_FILE_SIZE_MB,
)
from app.services.file_service import file_service
from app.services.generic_chunked_upload_service import (
    ChunkedUploadError,
    generic_chunked_upload_service,
)
from app.services.folder_service import FolderService

logger = logging.getLogger("microbubble.drive_api")
router = APIRouter(prefix="/drive", tags=["网盘文件"])


# === Schemas ===

class DriveFileItem(BaseModel):
    id: int
    title: str
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    storage_mode: str
    visibility: str
    folder_id: Optional[int] = None
    created_by: Optional[int] = None
    source_type: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted_at: Optional[str] = None

    class Config:
        from_attributes = True


class DriveFileListResponse(BaseModel):
    items: List[DriveFileItem]
    total: int
    page: int
    page_size: int


class DriveFileUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    visibility: Optional[str] = None  # private | team | public
    folder_id: Optional[int] = None  # 0 = move to root


class ExtractToKBRequest(BaseModel):
    target_visibility: str = "team"  # team | public (不能 private)


class StorageStatsResponse(BaseModel):
    file_count: int
    by_visibility: dict
    active: bool = True


def _to_item(k: Knowledge) -> DriveFileItem:
    return DriveFileItem(
        id=k.id,
        title=k.title,
        file_path=k.file_path or "",
        file_name=k.file_name or "",
        file_type=k.file_type or "",
        file_size=0,  # PR2 暂未在 Knowledge 模型加 file_size 列
        storage_mode=k.storage_mode,
        visibility=k.visibility,
        folder_id=k.folder_id,
        created_by=k.created_by,
        source_type=k.source_type,
        created_at=str(k.created_at) if k.created_at else None,
        updated_at=str(k.updated_at) if k.updated_at else None,
        deleted_at=str(k.deleted_at) if k.deleted_at else None,
    )


# === 单端点 multipart 上传 (PR2.3 简化版) ===

@router.post("/files/upload", response_model=DriveFileItem, status_code=201)
async def upload_drive_file(
    file: UploadFile = File(..., description="文件二进制"),
    filename: Optional[str] = Form(None, description="原始文件名 (默认 file.filename)"),
    content_type: Optional[str] = Form(None, description="MIME (默认 file.content_type)"),
    folder_id: Optional[int] = Form(None, description="目标 folder id (None=顶级)"),
    visibility: str = Form("team", description="private|team|public"),
    title: Optional[str] = Form(None, description="文件标题 (默认 = filename)"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """单端点 drive 文件上传 (FastAPI 接收 multipart, minio 自管分片)

    不超过 2GB (MAX_DRIVE_FILE_SIZE_BYTES); 走 init/complete pattern 简化为单端点.
    """
    real_filename = filename or file.filename or "unnamed"
    real_ct = content_type or file.content_type or "application/octet-stream"

    # 校验 visibility
    if visibility not in ("private", "team", "public"):
        raise HTTPException(status_code=400, detail=f"非法 visibility: {visibility}")

    # 校验 folder_id (跨用户检查)
    if folder_id is not None:
        folder_svc = FolderService(db)
        folder = await folder_svc.get_folder(folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail=f"folder {folder_id} 不存在")
        if folder.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权在该 folder 中创建文件")

    # 读取 body
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="上传文件为空")
    if len(data) > MAX_DRIVE_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"文件超过 {MAX_DRIVE_FILE_SIZE_MB}MB")

    # 算 folder_path (e.g. "1/4/") from folder_id
    folder_path = None
    if folder_id is not None:
        folder_svc = FolderService(db)
        folder = await folder_svc.get_folder(folder_id)
        if folder is not None:
            folder_path = folder.path

    # 1) init
    try:
        init_resp = await generic_chunked_upload_service.init_upload(
            filename=real_filename,
            content_type=real_ct,
            total_size=len(data),
            folder_path=folder_path,
            storage_mode="drive",
            user_id=current_user.id,
        )
    except ChunkedUploadError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    # 2) complete (写 MinIO)
    try:
        complete_resp = await generic_chunked_upload_service.complete_upload(
            upload_id=init_resp["upload_id"],
            data=data,
            content_type=real_ct,
        )
    except ChunkedUploadError as e:
        # 失败回滚 init (清空)
        await generic_chunked_upload_service.abort_upload(
            upload_id=init_resp["upload_id"],
        )
        raise HTTPException(status_code=e.status_code, detail=str(e))

    # 3) 落 Knowledge 元数据
    drive_svc = DriveService(db)
    try:
        knowledge = await drive_svc.create_file(
            title=title or real_filename,
            file_path=complete_resp["object_name"],
            file_name=real_filename,
            file_type="." + real_filename.rsplit(".", 1)[-1] if "." in real_filename else "",
            file_size=complete_resp["size"] or len(data),
            owner_id=current_user.id,
            storage_mode="drive",
            visibility=visibility,
            folder_id=folder_id,
            created_by=current_user.id,
            source_type="drive",
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    logger.info(
        f"[drive.upload] id={knowledge.id} file_name={real_filename} "
        f"size={complete_resp['size']} visibility={visibility} folder_id={folder_id}"
    )
    return _to_item(knowledge)


# === CRUD ===

@router.get("/files", response_model=DriveFileListResponse)
async def list_drive_files(
    folder_id: Optional[int] = Query(None, description="父 folder id"),
    visibility: Optional[str] = Query(None, description="private|team|public"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列 drive 文件 (含越权过滤: private 仅 owner 可见)"""
    svc = DriveService(db)
    items, total = await svc.list_files(
        current_user_id=current_user.id,
        folder_id=folder_id,
        visibility_filter=visibility,
        storage_mode="drive",
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    return DriveFileListResponse(
        items=[_to_item(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/files/{file_id}", response_model=DriveFileItem)
async def get_drive_file(
    file_id: int,
    include_deleted: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """drive 文件详情 + 越权检查"""
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(
            status_code=404,
            detail="file 不存在或无权访问",
        )
    return _to_item(f)


@router.put("/files/{file_id}", response_model=DriveFileItem)
async def update_drive_file(
    file_id: int,
    payload: DriveFileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """更新 drive 文件 (rename / move / change visibility)"""
    svc = DriveService(db)
    try:
        f = await svc.update_file(
            file_id,
            current_user_id=current_user.id,
            title=payload.title,
            visibility=payload.visibility,
            folder_id=payload.folder_id,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或非 owner")
    return _to_item(f)


@router.delete("/files/{file_id}", status_code=204)
async def delete_drive_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """软删 drive 文件 (owner only)"""
    svc = DriveService(db)
    ok = await svc.soft_delete_file(file_id, current_user_id=current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="file 不存在或非 owner")
    return


@router.post("/files/{file_id}/restore", response_model=DriveFileItem)
async def restore_drive_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """恢复软删 drive 文件 (3 天保留期内, owner only)"""
    svc = DriveService(db)
    f = await svc.restore_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或非 owner")
    return _to_item(f)


@router.post("/files/{file_id}/extract-to-kb", response_model=DriveFileItem)
async def extract_to_kb(
    file_id: int,
    payload: ExtractToKBRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """drive 文件升级到公共知识库 (storage_mode: drive → kb, source_type: drive → drive_extracted)

    后续 PR3 会触发 LLM 提取 + embedding 异步任务
    """
    svc = DriveService(db)
    try:
        f = await svc.extract_to_kb(
            file_id,
            current_user_id=current_user.id,
            target_visibility=payload.target_visibility,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或非 owner")
    return _to_item(f)


# === 容量统计 ===

@router.get("/storage-stats", response_model=StorageStatsResponse)
async def get_storage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """当前用户的 drive 存储统计 (file_count + by_visibility)"""
    svc = DriveService(db)
    stats = await svc.storage_stats(current_user_id=current_user.id)
    return StorageStatsResponse(**stats)


# ==========================================================================
# 下载 (PR2.6)
# ==========================================================================
import zipfile
import re
from urllib.parse import quote

from fastapi.responses import StreamingResponse
from starlette.requests import Request


def _check_download_visibility(file_knowledge, current_user_id: int) -> None:
    """下载/预览前校验: private 必须是 owner"""
    if file_knowledge.visibility == "private" and file_knowledge.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="无权限下载该私有文件")


@router.get("/files/{file_id}/download")
async def download_drive_file(
    file_id: int,
    request: Request,
    disposition: str = Query("attachment", pattern="^(attachment|inline)$"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """单文件下载 (支持 Range 断点续传 + 中文文件名 URL 编码)"""
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或无权访问")
    _check_download_visibility(f, current_user.id)

    if not f.file_path:
        raise HTTPException(status_code=404, detail="file 无 MinIO 对象")

    # 文件元信息
    content_type = f.file_type or "application/octet-stream"
    if content_type and not content_type.startswith("video/") and not content_type.startswith("image/") and disposition == "inline":
        # text 类保持原 mime, 其他 inline 也按 octet-stream
        pass
    filename = f.file_name or f.title or f"file_{f.id}"

    # Range 头解析
    range_header = request.headers.get("Range")
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            start = int(m.group(1))
            end_str = m.group(2)
            # 读 total size
            file_size = await _get_object_size(f.file_path)
            if file_size is None:
                # 没拿到 size, 走完整下载
                start = None
            else:
                if end_str:
                    end = min(int(end_str), file_size - 1)
                else:
                    end = file_size - 1
                length = end - start + 1

                async def _range_stream():
                    chunk = await _download_range(f.file_path, start, length)
                    yield chunk

                encoded = quote(filename)
                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                    "Content-Disposition": f"{disposition}; filename=\"{filename}\"; filename*=UTF-8''{encoded}",
                }
                return StreamingResponse(
                    _range_stream(),
                    status_code=206,
                    media_type=content_type,
                    headers=headers,
                )

    # 完整下载
    file_size = await _get_object_size(f.file_path)
    encoded = quote(filename)
    headers = {
        "Content-Disposition": f"{disposition}; filename=\"{filename}\"; filename*=UTF-8''{encoded}",
    }
    if file_size is not None:
        headers["Content-Length"] = str(file_size)
    headers["Accept-Ranges"] = "bytes"

    async def _full_stream():
        data = await file_service.download_file(f.file_path)
        yield data

    return StreamingResponse(
        _full_stream(),
        media_type=content_type,
        headers=headers,
    )


async def _get_object_size(object_name: str) -> Optional[int]:
    """读 MinIO 对象 size (用 stat_object 同步)"""
    import asyncio
    try:
        def _sync_stat():
            return file_service.client.stat_object(file_service.bucket, object_name)
        obj = await asyncio.to_thread(_sync_stat)
        return obj.size
    except Exception:
        return None


async def _download_range(object_name: str, start: int, length: int) -> bytes:
    """下载 MinIO 对象指定字节范围 (minio get_object 支持 offset+length)"""
    import asyncio
    def _sync_range():
        response = file_service.client.get_object(
            file_service.bucket, object_name, offset=start, length=length,
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
    return await asyncio.to_thread(_sync_range)


# === 批量 ZIP 下载 ===

class BatchDownloadRequest(BaseModel):
    ids: Optional[List[int]] = Field(None, description="文件 id 列表")
    folder_id: Optional[int] = Field(None, description="递归下载整个 folder")


@router.post("/files/batch-download")
async def batch_download_drive_files(
    payload: BatchDownloadRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """批量 ZIP 下载 (流式生成, 不落盘)

    body: {"ids": [1,2,3]} OR {"folder_id": 4}
    无权限文件跳过, ZIP 根目录生成 _skipped.txt
    """
    if not payload.ids and not payload.folder_id:
        raise HTTPException(status_code=400, detail="ids 或 folder_id 必填其一")

    svc = DriveService(db)

    # 1) 收集 file 列表
    file_records = []
    skipped = []
    if payload.ids:
        for fid in payload.ids:
            f = await svc.get_file(fid, current_user_id=current_user.id)
            if f is None:
                skipped.append(f"id={fid} 无权访问")
                continue
            _check_download_visibility(f, current_user.id)
            if not f.file_path:
                skipped.append(f"id={fid} 无 MinIO 对象")
                continue
            file_records.append(f)
    elif payload.folder_id:
        # 递归收集 folder 下的所有文件 (含子 folder)
        file_records, skipped = await _collect_folder_files(
            db, svc, payload.folder_id, current_user.id, skipped
        )

    if not file_records and not skipped:
        raise HTTPException(status_code=404, detail="无可下载文件")

    # 2) 流式生成 ZIP
    timestamp = _dt_now.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"drive_{current_user.username}_{timestamp}.zip"

    async def _zip_stream():
        # BytesIO 缓冲区 zip stream
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in file_records:
                try:
                    data = await file_service.download_file(f.file_path)
                    # ZIP 内路径: file_name (避免重复)
                    arcname = f.file_name or f"file_{f.id}"
                    # 防路径冲突 (同名)
                    existing = [n for n in zf.namelist() if n == arcname]
                    if existing:
                        arcname = f"{f.id}_{arcname}"
                    zf.writestr(arcname, data)
                except Exception as e:
                    logger.warning(f"批量下载跳过 file_id={f.id}: {e}")
                    continue
            # skipped list 写 _skipped.txt
            if skipped:
                skipped_content = "\n".join(skipped)
                zf.writestr("_skipped.txt", skipped_content)
        # yield 一次完整 buffer (PR3 优化: chunked write)
        buffer.seek(0)
        yield buffer.read()

    encoded = quote(zip_filename)
    return StreamingResponse(
        _zip_stream(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=\"{zip_filename}\"; filename*=UTF-8''{encoded}",
        },
    )


async def _collect_folder_files(
    db: AsyncSession,
    drive_svc: DriveService,
    folder_id: int,
    current_user_id: int,
    skipped: list,
) -> tuple:
    """递归收集 folder 下所有 file + 跨子 folder, 越权文件入 skipped"""
    from app.services.folder_service import FolderService
    folder_svc = FolderService(db)

    # 1) 校验 folder 越权
    folder = await folder_svc.get_folder(folder_id)
    if folder is None:
        return [], skipped + [f"folder_id={folder_id} 不存在"]
    if folder.visibility == "private" and folder.owner_id != current_user_id:
        return [], skipped + [f"folder_id={folder_id} 无权访问"]

    # 2) 列当前 folder 的文件
    files, _ = await drive_svc.list_files(
        current_user_id=current_user_id,
        folder_id=folder_id,
        storage_mode="drive",
        page=1,
        page_size=1000,  # 单 folder 上限 1000 个文件
    )
    # 过滤已软删 + 真实可见
    file_records = [f for f in files if f.deleted_at is None and f.file_path]

    # 3) 递归子 folder
    children = await folder_svc.list_children(folder_id=folder_id, include_deleted=False)
    for child in children:
        if child.visibility == "private" and child.owner_id != current_user_id:
            skipped.append(f"folder_id={child.id} 跳过 (无权限)")
            continue
        sub_files, skipped = await _collect_folder_files(
            db, drive_svc, child.id, current_user_id, skipped,
        )
        file_records.extend(sub_files)

    return file_records, skipped


# === Stats 补 time import ===
from datetime import datetime as _dt_now
