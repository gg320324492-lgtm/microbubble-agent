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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._drive_error_helper import (
    ERR_BATCH_PARAM_MISSING,
    ERR_FILE_FORBIDDEN,
    ERR_FILE_NOT_FOUND,
    ERR_SHARE_LINK_NOT_FOUND,
    raise_app_error,
)
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
    download_count: int = 0
    share_token: Optional[str] = None
    share_expires_at: Optional[str] = None
    # v2 PR2: 收藏字段
    is_starred: bool = False
    starred_at: Optional[str] = None
    # v2 PR4: 秒传 + 版本历史
    file_hash: Optional[str] = None
    is_latest: bool = True
    version_number: int = 1
    # v2 PR5: 缩略图字段
    thumbnail_path: Optional[str] = None
    thumbnail_status: str = "pending"  # pending | ready | failed
    # v2 PR6-P19: 团队共享盘隔离 (uploaded from specialView='team' = True)
    # 决定 list_drive_files view=personal|team 过滤
    is_team_shared: bool = False

    class Config:
        from_attributes = True


class DriveFileListResponse(BaseModel):
    items: List[DriveFileItem]
    total: int
    page: int
    page_size: int


class DriveFileUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    file_name: Optional[str] = Field(None, max_length=500)  # PR4.4: 修复 PR2.5 漏的 file_name 字段
    visibility: Optional[str] = None  # private | team | public
    folder_id: Optional[int] = None  # 0 = move to root


class ExtractToKBRequest(BaseModel):
    target_visibility: str = "team"  # team | public (不能 private)


class StorageStatsResponse(BaseModel):
    file_count: int
    by_visibility: dict
    active: bool = True


# === v2 PR5 Schemas: 配额 + 分片 + 缩略图 ===

class StorageQuotaResponse(BaseModel):
    """GET /api/v1/drive/storage-quota 响应"""
    user_id: int
    used_bytes: int
    quota_bytes: int
    percent: float
    file_count: int
    is_over_quota: bool
    updated_at: Optional[str] = None


class ChunkedUploadInitRequest(BaseModel):
    """POST /api/v1/drive/files/upload/init 请求"""
    file_name: str = Field(..., max_length=500)
    file_size: int = Field(..., gt=0, le=2 * 1024 * 1024 * 1024)  # 上限 2GB
    total_chunks: int = Field(..., ge=1, le=2000)
    file_hash: Optional[str] = Field(None, max_length=64)
    folder_id: Optional[int] = None
    visibility: str = "team"
    # v2 PR6-P19: is_team_shared 在 complete 阶段才传, 这里不接 (前端可在最后决定)


class ChunkedUploadInitResponse(BaseModel):
    """POST /api/v1/drive/files/upload/init 响应"""
    upload_id: str  # session_id
    object_name: str  # 临时占位
    total_chunks: int
    chunk_size_hint: int = 5 * 1024 * 1024  # 5MB 提示
    uploaded_chunks: List[int] = []
    expires_at: str


class ChunkedUploadStatusResponse(BaseModel):
    """GET /api/v1/drive/files/upload/{id} 响应 (断点续传)"""
    upload_id: str
    file_name: str
    file_size: int
    total_chunks: int
    uploaded_chunks: List[int]
    status: str  # active | completed | aborted
    expires_at: str


class ChunkedUploadCompleteRequest(BaseModel):
    """POST /api/v1/drive/files/upload/{id}/complete 请求"""
    change_note: Optional[str] = Field(None, max_length=500)
    # v2 PR6-P19: 团队共享盘标识 (init 时已传过, complete 时可再传覆盖)
    is_team_shared: Optional[bool] = Field(
        None, description="v2 PR6-P19: 覆盖 init 时的设置 (None=沿用)"
    )


class ThumbnailResponse(BaseModel):
    """GET /api/v1/drive/files/{id}/thumbnail 响应 (返 URL)"""
    file_id: int
    thumbnail_path: Optional[str] = None
    thumbnail_status: str  # pending | ready | failed
    thumbnail_url: Optional[str] = None  # MinIO 公开读 URL 或 None


def _to_item(k: Knowledge, owner_lookup: Optional[dict] = None) -> DriveFileItem:
    """Build DriveFileItem.

    v2.16 (2026-07-11): 可选 owner_lookup 传 {member_id: Member} 字典,
    一次 JOIN 查所有 owner 后批量 attach (避免 N+1 query).
    老 callsite 不传 owner_lookup 时, owner_name/owner_username 字段为 None,
    前端 fallback 到 "#<created_by>" 显示 (CLAUDE.md 兼容原则).
    """
    owner_name = None
    owner_username = None
    if owner_lookup and k.created_by in owner_lookup:
        m = owner_lookup[k.created_by]
        owner_name = m.name if m.name else None
        owner_username = m.username if m.username else None
    return DriveFileItem(
        id=k.id,
        title=k.title,
        file_path=k.file_path or "",
        file_name=k.file_name or "",
        file_type=k.file_type or "",
        file_size=k.file_size or 0,  # PR4: 真值 (PR2 之前 0)
        storage_mode=k.storage_mode,
        visibility=k.visibility,
        folder_id=k.folder_id,
        created_by=k.created_by,
        owner_name=owner_name,
        owner_username=owner_username,
        source_type=k.source_type,
        created_at=str(k.created_at) if k.created_at else None,
        updated_at=str(k.updated_at) if k.updated_at else None,
        deleted_at=str(k.deleted_at) if k.deleted_at else None,
        download_count=k.download_count or 0,
        share_token=k.share_token,
        share_expires_at=str(k.share_expires_at) if k.share_expires_at else None,
        is_starred=bool(k.is_starred),
        starred_at=str(k.starred_at) if k.starred_at else None,
        file_hash=k.file_hash,        # PR4
        is_latest=bool(k.is_latest),  # PR4
        version_number=k.version_number or 1,  # PR4
        thumbnail_path=k.thumbnail_path,  # PR5
        thumbnail_status=k.thumbnail_status or "pending",  # PR5
        is_team_shared=bool(k.is_team_shared),  # v2 PR6-P19
    )


# === 单端点 multipart 上传 (PR2.3 简化版) ===

@router.post("/files/upload", response_model=DriveFileItem, status_code=201)
async def upload_drive_file(
    file: UploadFile = File(..., description="文件二进制"),
    filename: Optional[str] = Form(None, description="原始文件名 (默认 file.filename)"),
    content_type: Optional[str] = Form(None, description="MIME (默认 file.content_type)"),
    folder_id: Optional[int] = Form(None, description="目标 folder id (None=顶级)"),
    visibility: str = Form("team", description="private|team|public"),
    # v2 PR6-P19: 用户上传时所在的视图 (specialView='team' = True)
    is_team_shared: bool = Form(False, description="v2 PR6-P19: True=团队共享盘上传, 不在个人网盘显示"),
    title: Optional[str] = Form(None, description="文件标题 (默认 = filename)"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """单端点 drive 文件上传 (FastAPI 接收 multipart, minio 自管分片)

    不超过 2GB (MAX_DRIVE_FILE_SIZE_BYTES); 走 init/complete pattern 简化为单端点.

    v2 PR6-P19: is_team_shared 标记上传来源, 前端在团队共享盘视图上传时 = true,
    个人视图上传 = false. 后端 list_drive_files 走 view=personal|team 隔离过滤.
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
            is_team_shared=is_team_shared,  # v2 PR6-P19
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    # PR5: Fire-and-forget 缩略图生成 + 配额重算
    try:
        from app.services.thumbnail_tasks import generate_thumbnail_task
        from app.services.storage_tasks import recalc_user_storage_task
        generate_thumbnail_task.delay(knowledge.id)
        recalc_user_storage_task.delay(current_user.id)
    except Exception as e:
        logger.warning(f"[drive.upload] fire Celery 失败 (非阻塞): {e}")

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
    # v2 PR2: sort + filter 新参数
    sort_by: Optional[str] = Query(
        None,
        description="排序字段: created_at | updated_at | file_name | starred_at",
    ),
    sort_order: Optional[str] = Query("desc", description="asc | desc"),
    starred_only: bool = Query(False, description="仅显示收藏"),
    file_type: Optional[str] = Query(
        None,
        description="类型过滤: pdf | image | video | audio | word | ppt | excel | text (无值=全部, office 仍兼容)",
    ),
    # v2 PR6-P19: 视图隔离 (personal=个人网盘默认, team=团队共享盘, all=全显)
    view: Optional[str] = Query(
        "personal",
        description="视图隔离: personal (默认, 不含 is_team_shared=true) | team (仅 is_team_shared=true) | all (不过滤)",
    ),
    # v2.21 (2026-07-11): 团队共享盘顶级列出整个团队空间 (root + sub folder)
    # 默认 False 保持 v2 PR3 行为 (folder_id=None → folder_id IS NULL)
    # 个人顶级 view=personal 不该传 True (会 leak team view 行为)
    include_subfolders: bool = Query(
        False,
        description="v2.21: folder_id=None 时是否包含 sub folder PPT (🌐 团队共享盘顶级 view 用)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列 drive 文件 (含越权过滤: private 仅 owner 可见)

    v2 PR2: 支持 sort_by/sort_order/starred_only/file_type.
    v2 PR6-P19: view 参数隔离个人/团队共享盘.
    v2.21: include_subfolders=True 让 🌐 团队共享盘顶级 view 列出整个团队空间
      (root + 23 sub folder), 而不是只看 root folder 的 2 个 PPT.
    - sort_by 默认 None = 维持原 created_at desc 行为 (向后兼容)
    - view 默认 personal = 不显示 is_team_shared=true (老调用方升级即隔离)
    """
    # v2 PR6-P19: view → is_team_shared 映射
    if view == "personal":
        is_team_shared_filter = False
    elif view == "team":
        is_team_shared_filter = True
    elif view == "all":
        is_team_shared_filter = None
    else:
        raise HTTPException(
            status_code=400,
            detail=f"无效 view 参数: '{view}', 必须是 personal|team|all",
        )

    # v2.21: include_subfolders 仅对 team/all 顶级 view 有意义
    # personal 顶级 view 维持 v2 PR3 行为 (folder_id IS NULL = 个人根目录)
    if include_subfolders and view == "personal":
        # 防御性: personal view 不应该跨 folder 显示, 即便前端传了也忽略
        # 防止泄露其他 folder 的 PPT
        include_subfolders = False

    svc = DriveService(db)
    try:
        items, total = await svc.list_files(
            current_user_id=current_user.id,
            folder_id=folder_id,
            visibility_filter=visibility,
            storage_mode="drive",
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            sort_by=sort_by or "created_at",
            sort_order=sort_order or "desc",
            starred_only=starred_only,
            file_type=file_type,
            is_team_shared=is_team_shared_filter,
            include_subfolders=include_subfolders,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
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
            file_name=payload.file_name,  # PR4.4: 透传 file_name
            visibility=payload.visibility,
            folder_id=payload.folder_id,
        )
    except DriveServiceError as e:
        # W1 T1 migration: DriveServiceError → AppException envelope (helper)
        raise_app_error(e.status_code, ERR_FILE_FORBIDDEN, str(e), file_id=file_id)
    if f is None:
        raise_app_error(404, ERR_FILE_NOT_FOUND, "file 不存在或非 owner", file_id=file_id)
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


# ==========================================================
# v2 PR8.6: 文件级软锁 (防冲突协作)
# Redis TTL 5 分钟自动过期, 释放/重新获取强制覆盖
# ==========================================================

import time as _time

DRIVE_FILE_LOCK_TTL_SECONDS = 300  # 5 分钟
_DRIVE_LOCK_KEY_PREFIX = "drive:file_lock:"


async def _get_redis_client():
    """延迟创建 Redis 客户端 (CLAUDE.md 752 行铁律: 不在模块顶部创建)"""
    import redis.asyncio as aioredis
    from app.config import settings
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def _drive_lock_get_holder(file_id: int) -> Optional[dict]:
    """读 Redis 锁 holder, 无锁返 None"""
    client = await _get_redis_client()
    try:
        raw = await client.get(f"{_DRIVE_LOCK_KEY_PREFIX}{file_id}")
        if not raw:
            return None
        import json
        try:
            data = json.loads(raw)
            # 校验 TTL 实际剩余 (Redis 5 分钟已重新校准)
            ttl = await client.ttl(f"{_DRIVE_LOCK_KEY_PREFIX}{file_id}")
            data["ttl_remaining"] = ttl if ttl > 0 else 0
            return data
        except Exception:
            return None
    finally:
        await client.aclose()


class FileLockResponse(BaseModel):
    """v2 PR8.6: 锁状态响应"""
    file_id: int
    locked: bool
    holder_user_id: Optional[int] = None
    holder_username: Optional[str] = None
    holder_name: Optional[str] = None
    acquired_at: Optional[str] = None
    ttl_remaining: int = 0  # 秒


@router.post("/files/{file_id}/lock", response_model=FileLockResponse)
async def acquire_file_lock(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR8.6: 软锁 drive 文件 (5 分钟 Redis TTL)

    - 同用户重复 acquire: 续期 TTL (返回新 acquired_at)
    - 异用户 acquire: 返 409 + 当前 holder 信息
    """
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或无权访问")

    client = await _get_redis_client()
    try:
        key = f"{_DRIVE_LOCK_KEY_PREFIX}{file_id}"
        import json
        now_iso = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
        payload = json.dumps({
            "user_id": current_user.id,
            "username": getattr(current_user, "username", None) or "",
            "name": getattr(current_user, "name", "") or "",
            "acquired_at": now_iso,
        })
        existing_raw = await client.get(key)
        if existing_raw:
            try:
                existing = json.loads(existing_raw)
                if int(existing.get("user_id", 0)) != current_user.id:
                    return FileLockResponse(
                        file_id=file_id,
                        locked=True,
                        holder_user_id=int(existing.get("user_id", 0)) or None,
                        holder_username=existing.get("username"),
                        holder_name=existing.get("name"),
                        acquired_at=existing.get("acquired_at"),
                        ttl_remaining=max(await client.ttl(key), 0),
                    )
            except Exception:
                # 损坏的 JSON 直接覆盖
                pass
        # 同用户续期 / 异用户第一次拿到 → 写入
        await client.set(key, payload, ex=DRIVE_FILE_LOCK_TTL_SECONDS)
        return FileLockResponse(
            file_id=file_id,
            locked=True,
            holder_user_id=current_user.id,
            holder_username=getattr(current_user, "username", None) or "",
            holder_name=getattr(current_user, "name", "") or "",
            acquired_at=now_iso,
            ttl_remaining=DRIVE_FILE_LOCK_TTL_SECONDS,
        )
    finally:
        await client.aclose()


@router.delete("/files/{file_id}/lock", response_model=FileLockResponse)
async def release_file_lock(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR8.6: 释放 drive 文件锁

    - 仅 holder 可释放, 异用户返 403
    - 锁不存在返 200 + locked=False (幂等)
    """
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或无权访问")

    client = await _get_redis_client()
    try:
        key = f"{_DRIVE_LOCK_KEY_PREFIX}{file_id}"
        raw = await client.get(key)
        if not raw:
            return FileLockResponse(file_id=file_id, locked=False)
        import json
        try:
            existing = json.loads(raw)
            if int(existing.get("user_id", 0)) != current_user.id:
                raise HTTPException(status_code=403, detail="非锁持有者, 无法释放")
        except HTTPException:
            raise
        except Exception:
            pass
        await client.delete(key)
        return FileLockResponse(file_id=file_id, locked=False)
    finally:
        await client.aclose()


@router.get("/files/{file_id}/lock", response_model=FileLockResponse)
async def get_file_lock(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR8.6: 查 drive 文件当前锁状态

    任何可见该文件的人都能查 (含 public/team), 无锁时 locked=False
    """
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或无权访问")
    holder = await _drive_lock_get_holder(file_id)
    if not holder:
        return FileLockResponse(file_id=file_id, locked=False)
    return FileLockResponse(
        file_id=file_id,
        locked=True,
        holder_user_id=int(holder.get("user_id", 0)) or None,
        holder_username=holder.get("username"),
        holder_name=holder.get("name"),
        acquired_at=holder.get("acquired_at"),
        ttl_remaining=int(holder.get("ttl_remaining", 0)),
    )


# ==========================================================
# v2 PR2: 回收站 + 收藏 + 批量操作
# ==========================================================


class TrashListResponse(BaseModel):
    """v2 PR2: 回收站列表响应 (复用 DriveFileListResponse schema)"""
    items: List[DriveFileItem]
    total: int
    page: int
    page_size: int


class StarredListResponse(BaseModel):
    """v2 PR2: 收藏列表响应"""
    items: List[DriveFileItem]
    total: int
    page: int
    page_size: int


class ToggleStarResponse(BaseModel):
    """v2 PR2: 收藏切换响应"""
    file_id: int
    is_starred: bool
    starred_at: Optional[str] = None


class BatchIdsRequest(BaseModel):
    """v2 PR2: 通用 batch ids body"""
    file_ids: List[int]


class BatchMoveRequest(BaseModel):
    """v2 PR2: 批量移动请求体"""
    file_ids: List[int]
    target_folder_id: Optional[int] = None  # None = 顶级


class BatchVisibilityRequest(BaseModel):
    """v2 PR2: 批量改可见性请求体"""
    file_ids: List[int]
    visibility: str  # private | team | public


class BatchOperationResponse(BaseModel):
    """v2 PR2: 批量操作统一响应"""
    succeeded_count: int
    skipped_ids: List[int]
    skipped_reasons: Optional[dict] = None  # {file_id: "越权/folder不兼容/不在trash/..."}


# ---------- 收藏 ----------

@router.post("/files/{file_id}/toggle-star", response_model=ToggleStarResponse)
async def toggle_file_star(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """切换文件收藏状态 (owner only). 隐身 404 给非 owner."""
    svc = DriveService(db)
    f = await svc.toggle_star_file(file_id, current_user_id=current_user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或非 owner")
    return ToggleStarResponse(
        file_id=f.id,
        is_starred=bool(f.is_starred),
        starred_at=str(f.starred_at) if f.starred_at else None,
    )


# ---------- 收藏列表 ----------

@router.get("/starred", response_model=StarredListResponse)
async def list_starred_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    sort_by: Optional[str] = Query("starred_at", description="starred_at | created_at | updated_at"),
    sort_order: Optional[str] = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列我收藏的文件 (仅 created_by == me)."""
    svc = DriveService(db)
    items, total = await svc.list_starred(
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by or "starred_at",
        sort_order=sort_order or "desc",
    )
    return StarredListResponse(
        items=[_to_item(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------- 回收站 ----------

@router.get("/trash", response_model=TrashListResponse)
async def list_trash_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    sort_by: Optional[str] = Query("deleted_at"),
    sort_order: Optional[str] = Query("desc"),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """列回收站文件 (软删的 drive 文件, 仅 owner)."""
    svc = DriveService(db)
    items, total = await svc.list_trash(
        current_user_id=current_user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by or "deleted_at",
        sort_order=sort_order or "desc",
    )
    return TrashListResponse(
        items=[_to_item(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/trash/permanent-delete", response_model=BatchOperationResponse)
async def permanent_delete_files(
    payload: BatchIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """批量物理删除回收站中的文件 (owner only, 不可逆)."""
    svc = DriveService(db)
    deleted, skipped = await svc.permanent_delete_batch(
        payload.file_ids, current_user_id=current_user.id,
    )
    return BatchOperationResponse(
        succeeded_count=deleted,
        skipped_ids=skipped,
        skipped_reasons={fid: "不在回收站/不存在/非 owner" for fid in skipped},
    )


# ---------- 批量操作 ----------

@router.post("/files/batch-soft-delete", response_model=BatchOperationResponse)
async def batch_soft_delete_files(
    payload: BatchIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """批量软删 (进入回收站)."""
    svc = DriveService(db)
    deleted, skipped = await svc.batch_soft_delete(
        payload.file_ids, current_user_id=current_user.id,
    )
    return BatchOperationResponse(
        succeeded_count=deleted,
        skipped_ids=skipped,
        skipped_reasons={fid: "不存在/非 owner" for fid in skipped},
    )


@router.post("/files/batch-restore", response_model=BatchOperationResponse)
async def batch_restore_files(
    payload: BatchIdsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """批量从回收站恢复."""
    svc = DriveService(db)
    restored, skipped = await svc.batch_restore(
        payload.file_ids, current_user_id=current_user.id,
    )
    return BatchOperationResponse(
        succeeded_count=restored,
        skipped_ids=skipped,
        skipped_reasons={fid: "不在回收站/不存在/非 owner" for fid in skipped},
    )


@router.post("/files/batch-move", response_model=BatchOperationResponse)
async def batch_move_files(
    payload: BatchMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """批量移动到 folder (target_folder_id=None = 顶级)."""
    svc = DriveService(db)
    try:
        moved, skipped = await svc.batch_move(
            payload.file_ids,
            target_folder_id=payload.target_folder_id,
            current_user_id=current_user.id,
        )
    except DriveServiceError as e:
        # W1 T1 migration: DriveServiceError → AppException envelope
        raise_app_error(e.status_code, ERR_FILE_FORBIDDEN, str(e))
    return BatchOperationResponse(
        succeeded_count=moved,
        skipped_ids=skipped,
        skipped_reasons={fid: "folder 上限/不存在/非 owner" for fid in skipped},
    )


@router.post("/files/batch-update-visibility", response_model=BatchOperationResponse)
async def batch_update_files_visibility(
    payload: BatchVisibilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """批量改可见性 (folder 上限校验)."""
    svc = DriveService(db)
    try:
        updated, skipped = await svc.batch_update_visibility(
            payload.file_ids,
            new_visibility=payload.visibility,
            current_user_id=current_user.id,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return BatchOperationResponse(
        succeeded_count=updated,
        skipped_ids=skipped,
        skipped_reasons={fid: "folder 上限/不存在/非 owner" for fid in skipped},
    )


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


def build_content_disposition(disposition: str, filename: str) -> str:
    """构建 Content-Disposition 头 (RFC 5987 + RFC 6266).

    历史教训 (2026-07-02):
      旧实现用 `filename="{filename}"; filename*=UTF-8''{encoded}`
      双 attribute 看似稳妥, 实则 `filename=` 部分走 latin-1 codec,
      一旦 filename 含中文 (如 "组会ppt/冯懿鑫/2025.7.2 研一 冯懿鑫.pptx"),
      Starlette/FastAPI 调用 latin-1 encode → UnicodeEncodeError → 500.

    修复: 仅输出 `filename*=UTF-8''<encoded>` (RFC 5987 标准化形式),
    移除非 ASCII safe 的 `filename="..."` 旧 attribute.
    现代浏览器 (Chrome / Firefox / Safari / Edge) 全部支持 filename*,
    老 IE (≤ IE9) 不支持但本项目目标用户无 IE.

    Args:
        disposition: 'attachment' 或 'inline'
        filename: 原始文件名 (可含中文)

    Returns:
        e.g. "inline; filename*=UTF-8''%E7%BB%84%E4%BC%9Appt.pptx"
    """
    encoded = quote(filename, safe='')
    return f"{disposition}; filename*=UTF-8''{encoded}"


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
    # PR4.6 修复: f.file_type 是 ".txt" 字面量 (DB 存的是扩展名), 直接返会触发 nosniff 阻断
    # 用 mimetypes 模块从扩展名推断真实 MIME (image/jpeg, video/mp4, application/pdf 等)
    import mimetypes
    if f.file_type and f.file_type.startswith("."):
        # f.file_type 是 ".ext" 形式 (我们 KB 上传时存的就是这个)
        guessed, _ = mimetypes.guess_type(f"a{f.file_type}")
        content_type = guessed or "application/octet-stream"
    else:
        content_type = f.file_type or "application/octet-stream"

    if content_type and not content_type.startswith("video/") and not content_type.startswith("image/") and disposition == "inline":
        # text 类保持原 mime, 其他 inline 也按 octet-stream
        pass
    filename = f.file_name or f.title or f"file_{f.id}"

    # PR2.7: 原子 +1 下载计数
    new_count = await svc.increment_download_count(file_id)

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

                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                    "Content-Disposition": build_content_disposition(disposition, filename),
                }
                return StreamingResponse(
                    _range_stream(),
                    status_code=206,
                    media_type=content_type,
                    headers=headers,
                )

    # 完整下载
    file_size = await _get_object_size(f.file_path)
    headers = {
        "Content-Disposition": build_content_disposition(disposition, filename),
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
        # W1 T1 migration: 400 → AppException envelope (BATCH_PARAM_MISSING)
        raise_app_error(400, ERR_BATCH_PARAM_MISSING, "ids 或 folder_id 必填其一")

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
        # W1 T1 migration: 404 → AppException envelope
        raise_app_error(404, ERR_FILE_NOT_FOUND, "无可下载文件")

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

    return StreamingResponse(
        _zip_stream(),
        media_type="application/zip",
        headers={
            "Content-Disposition": build_content_disposition("attachment", zip_filename),
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


# ==========================================================================
# PR2.7 分享链接 + 公开下载
# ==========================================================================

class ShareLinkRequest(BaseModel):
    """v2 PR1: 新增 expires_hours (细粒度) + password (提取码) 字段

    expires_in_days 保留旧字段向后兼容 (优先级低于 expires_hours).
    password 必填 4-8 位数字, 后端存 SHA256 hash (不存明文).
    """
    expires_in_days: Optional[int] = None  # 旧 API, 1-365
    expires_hours: Optional[int] = None    # 新 API, 1-8760; 0=默认 7 天; -1=永久
    password: Optional[str] = None          # 4-8 位数字, None=无密码


class ShareLinkResponse(BaseModel):
    file_id: int
    token: str
    share_url: str
    expires_at: Optional[str] = None
    password_required: bool = False         # v2 PR1 新增: 是否需要提取码


@router.post("/files/{file_id}/share-link", response_model=ShareLinkResponse)
async def create_share_link(
    file_id: int,
    payload: ShareLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """生成 drive 文件公开分享链接 (owner only)

    返回 token + 完整 share_url + expires_at + password_required
    """
    svc = DriveService(db)
    try:
        f = await svc.create_share_link(
            file_id,
            current_user_id=current_user.id,
            expires_in_days=payload.expires_in_days,
            expires_hours=payload.expires_hours,
            password=payload.password,
        )
    except DriveServiceError as e:
        # W1 T1 migration: DriveServiceError → AppException envelope
        raise_app_error(e.status_code, ERR_FILE_FORBIDDEN, str(e), file_id=file_id)
    if f is None:
        raise_app_error(404, ERR_SHARE_LINK_NOT_FOUND, "file 不存在或非 owner", file_id=file_id)

    # share_url 用 settings.PUBLIC_BASE_URL (前端拼) - 这里用相对路径
    share_url = f"/drive/share/{f.share_token}"
    return ShareLinkResponse(
        file_id=f.id,
        token=f.share_token,
        share_url=share_url,
        expires_at=str(f.share_expires_at) if f.share_expires_at else None,
        password_required=bool(f.share_password),
    )


@router.delete("/files/{file_id}/share-link", status_code=204)
async def revoke_share_link(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """撤销 share link (清 token)"""
    svc = DriveService(db)
    ok = await svc.revoke_share_link(file_id, current_user_id=current_user.id)
    if not ok:
        raise_app_error(404, ERR_SHARE_LINK_NOT_FOUND, "file 不存在或非 owner", file_id=file_id)
    return


# === v2 PR1 公开分享 GET 端点 (含密码验证) ===

class PublicShareInfoResponse(BaseModel):
    """公开分享链接的元信息 (验证密码后才返回下载链接)."""
    file_name: str
    file_size: Optional[int] = None
    expires_at: Optional[str] = None
    password_required: bool = False
    verify_token: Optional[str] = None  # 验证密码后由后端签发的短期 token, 传给下载端点


class PublicShareDownloadRequest(BaseModel):
    """下载请求 body. password 留空时直接尝试下载 (公开分享无密码模式)."""
    password: Optional[str] = None


# === share_router endpoints 注册放在 share_router 定义之后 (顺序依赖) ===
# 见下方 share_router 段


# ==========================================================================
# v2 PR1 visibility edit endpoint (桌面 stub 修复)
# ==========================================================================

class UpdateVisibilityRequest(BaseModel):
    """修改 drive 文件可见性请求体."""
    visibility: str  # private | team | public


class UpdateVisibilityResponse(BaseModel):
    file_id: int
    visibility: str
    folder_id: Optional[int] = None


@router.put("/files/{file_id}/visibility", response_model=UpdateVisibilityResponse)
async def update_file_visibility(
    file_id: int,
    payload: UpdateVisibilityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """PUT /api/v1/drive/files/{file_id}/visibility

    修改 drive 文件可见性 (owner only, 校验文件夹硬上限).
    桌面 DriveView 的 handleFileUpdateVisibility stub 修复由此端点支撑.
    """
    svc = DriveService(db)
    try:
        f = await svc.update_visibility(
            file_id,
            current_user_id=current_user.id,
            new_visibility=payload.visibility,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    if f is None:
        raise HTTPException(status_code=404, detail="file 不存在或非 owner")
    return UpdateVisibilityResponse(
        file_id=f.id,
        visibility=f.visibility,
        folder_id=f.folder_id,
    )


# === 公开 share 端点 (无需 JWT, token 验证) ===

# 注: 放在前缀 /drive/share 路径下, router prefix = /drive
# 实际 URL: GET /api/v1/drive/share/{token}
# 为简化, 把 share 端点放到 root 上
# 但 FastAPI router prefix 是 /drive, 加 /share/{token} 即可
# 这里用独立 APIRouter 避免与 /files/{file_id} 冲突
share_router = APIRouter(prefix="/drive/share", tags=["网盘公开分享"])


@share_router.get("/{token}/info", response_model=PublicShareInfoResponse)
async def public_share_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """GET /api/v1/drive/share/{token}/info — 查看分享链接元信息 + 是否需要密码.

    注意: 此端点不返回密码本身, 仅返回 password_required flag + 文件元信息.
    """
    svc = DriveService(db)
    f = await svc.get_by_share_token(token)
    if f is None:
        raise HTTPException(status_code=404, detail="分享链接不存在或已过期")
    return PublicShareInfoResponse(
        file_name=f.file_name or f.title or f"file_{f.id}",
        file_size=None,  # 暂不返具体 size (避免被白嫖)
        expires_at=str(f.share_expires_at) if f.share_expires_at else None,
        password_required=bool(f.share_password),
    )


@share_router.post("/{token}/verify-password")
async def public_share_verify_password(
    token: str,
    request: PublicShareDownloadRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST /api/v1/drive/share/{token}/verify-password

    验证提取码. 失败返 403 (不放任何提示防枚举). 成功返 verify_token (短期有效).
    """
    svc = DriveService(db)
    f = await svc.verify_share_access(token, password=request.password)
    if f is None:
        # 整体返 403 不区分"不存在/过期/密码错" 防 token 枚举
        raise HTTPException(status_code=403, detail="分享链接已过期或密码错误")
    # v2 PR1 暂用文件 id 作为 verify_token (无 JWT 时跳转用)
    return {"verified": True, "file_id": f.id}


@share_router.get("/{token}")
async def public_download_by_token(
    token: str,
    request: Request,
    password: Optional[str] = Query(None, description="提取码 (分享链接有密码时必填)"),
    db: AsyncSession = Depends(get_db),
):
    """公开分享下载 (无 JWT, 校验 token + 可选提取码)

    GET /api/v1/drive/share/{token}?password=1234 -> 流式下载
    GET /api/v1/drive/share/{token}              -> 无密码公开分享直接下载

    v2 PR1 升级: 当 share 有密码时, 必须 query ?password=xxx 才返流;
    缺少或错密码返 403. 防枚举: 整体返 403 不区分 404 vs 403.
    """
    svc = DriveService(db)
    f = await svc.verify_share_access(token, password=password)
    if f is None:
        # 一律 403 (不区分"不存在/过期/密码错")
        raise HTTPException(status_code=403, detail="分享链接已过期或密码错误")
    if not f.file_path:
        raise HTTPException(status_code=404, detail="分享文件无 MinIO 对象")

    # 公开访问: 不需要 visibility 校验 (token 本身代表 owner 主动授权)
    # 但仍原子 +1 下载计数
    new_count = await svc.increment_download_count(f.id)

    filename = f.file_name or f.title or f"file_{f.id}"
    content_type = f.file_type or "application/octet-stream"
    file_size = await _get_object_size(f.file_path)

    # Range 支持 (与 /files/{id}/download 一致)
    range_header = request.headers.get("Range")
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m and file_size is not None:
            start = int(m.group(1))
            end_str = m.group(2)
            if end_str:
                end = min(int(end_str), file_size - 1)
            else:
                end = file_size - 1
            length = end - start + 1
            async def _range_stream():
                chunk = await _download_range(f.file_path, start, length)
                yield chunk
            return StreamingResponse(
                _range_stream(),
                status_code=206,
                media_type=content_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                    "Content-Disposition": build_content_disposition("attachment", filename),
                },
            )

    # 完整下载
    headers = {
        "Content-Disposition": build_content_disposition("attachment", filename),
        "Accept-Ranges": "bytes",
    }
    if file_size is not None:
        headers["Content-Length"] = str(file_size)

    async def _full_stream():
        data = await file_service.download_file(f.file_path)
        yield data

    return StreamingResponse(
        _full_stream(),
        media_type=content_type,
        headers=headers,
    )


# ============================================================
# v2 PR4: 文件秒传 (hash) + 版本历史
# ============================================================


class InstantUploadRequest(BaseModel):
    """秒传查询请求 — 前端算完 hash 后 POST"""
    file_hash: str = Field(..., min_length=32, max_length=64, description="MD5/SHA256 hex (32/64 chars)")
    file_name: str = Field(..., min_length=1, max_length=200)
    file_size: int = Field(..., ge=1, le=MAX_DRIVE_FILE_SIZE_BYTES)
    folder_id: Optional[int] = None
    visibility: str = Field("team", pattern="^(private|team|public)$")
    # v2 PR6-P19: 团队共享盘标识 (前端在 specialView='team' 视图上传 = true)
    is_team_shared: bool = Field(False, description="True=团队共享盘上传, 不在个人网盘显示")


class InstantUploadResponse(BaseModel):
    """秒传响应
    - instant=true  命中: 新 file_id 已创建, 不用再上传字节
    - instant=false 未命中: 前端走老 multipart 上传路径
    """
    instant: bool
    file_id: Optional[int] = None
    file_name: Optional[str] = None
    dedup_saved_bytes: int = 0
    file_size: Optional[int] = None
    file_hash: Optional[str] = None
    # miss 时返前端走老路径的提示
    upload_url: Optional[str] = None


class VersionItem(BaseModel):
    """版本历史明细 (一行 = 一次版本)"""
    id: int
    file_id: int
    version_number: int
    file_hash: str
    file_size: int
    uploaded_by: int
    uploaded_by_name: Optional[str] = None
    change_note: Optional[str] = None
    created_at: str
    is_current: bool = False


class RestoreVersionRequest(BaseModel):
    """恢复版本请求 — 可选 change_note"""
    change_note: Optional[str] = Field(None, max_length=500)


@router.post("/files/instant-upload", response_model=InstantUploadResponse)
async def instant_upload(
    body: InstantUploadRequest,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """秒传 dedup 查询 + 创建 (命中时)

    命中: hash_lookup 找到同 owner 同 hash 文件 → MinIO copy_object 零带宽 → 新 Knowledge 行
    未命中: 返 instant=false, 前端走老 multipart 上传
    """
    svc = DriveService(db)
    try:
        k, saved = await svc.create_instant_upload(
            file_hash=body.file_hash,
            file_name=body.file_name,
            file_size=body.file_size,
            owner_id=user.id,
            folder_id=body.folder_id,
            visibility=body.visibility,
            created_by=user.id,
            is_team_shared=body.is_team_shared,  # v2 PR6-P19
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if k:
        return InstantUploadResponse(
            instant=True,
            file_id=k.id,
            file_name=k.file_name,
            dedup_saved_bytes=saved,
            file_size=k.file_size,
            file_hash=k.file_hash,
        )
    return InstantUploadResponse(
        instant=False,
        upload_url="/api/v1/drive/files/upload",
    )


@router.get("/files/{file_id}/versions", response_model=List[VersionItem])
async def list_file_versions(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """列文件版本历史 (按 version_number desc)

    权限: 走 _can_see_file, private 文件仅 owner 可看
    """
    svc = DriveService(db)
    try:
        items = await svc.list_versions(file_id=file_id, current_user_id=user.id)
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return [VersionItem(**item) for item in items]


@router.post("/files/{file_id}/versions/{version_id}/restore", response_model=DriveFileItem)
async def restore_file_version(
    file_id: int,
    version_id: int,
    body: RestoreVersionRequest = RestoreVersionRequest(),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """恢复历史版本

    创建新行 v{cur.version+1}, file_hash 与历史版一致 (字节级还原)
    旧版本链保留 (cur.is_latest=False), 新行 is_latest=True
    """
    svc = DriveService(db)
    try:
        new_k = await svc.restore_version(
            file_id=file_id,
            version_id=version_id,
            uploader_id=user.id,
            change_note=body.change_note,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    await db.refresh(new_k)
    return _to_item(new_k)


# ============================================================
# v2 PR5: 配额 + 分片上传 + 断点续传 + 缩略图 (2026-07-01)
# ============================================================


@router.get("/storage-quota", response_model=StorageQuotaResponse)
async def get_storage_quota(
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 获取当前用户的网盘配额详情

    返回:
    - used_bytes / quota_bytes / percent: 用于 UI badge 颜色阈值 (≥80% 黄, ≥95% 红)
    - file_count: 活跃 drive 文件数
    - is_over_quota: 已超额 (≤0)
    """
    svc = DriveService(db)
    return await svc.get_storage_quota(user.id)


@router.post("/files/upload/init", response_model=ChunkedUploadInitResponse)
async def init_chunked_upload(
    body: ChunkedUploadInitRequest,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 初始化分片上传 session

    配额检查: 文件大小超配额返 413
    24h TTL: session.expires_at = now + 24h

    返回 upload_id, 前端 chunk 0 写到 PUT /files/upload/{id}/chunk/0
    """
    svc = DriveService(db)
    try:
        session = await svc.init_chunked_upload(
            user_id=user.id,
            file_name=body.file_name,
            file_size=body.file_size,
            total_chunks=body.total_chunks,
            file_hash=body.file_hash,
            folder_id=body.folder_id,
            visibility=body.visibility,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return ChunkedUploadInitResponse(
        upload_id=session.id,
        object_name=f"drive-uploads/{session.id}/final",
        total_chunks=session.total_chunks,
        chunk_size_hint=5 * 1024 * 1024,
        uploaded_chunks=list(session.uploaded_chunks or []),
        expires_at=session.expires_at.isoformat(),
    )


@router.put("/files/upload/{upload_id}/chunk/{chunk_index}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 上传单个 chunk (raw bytes body, NOT multipart)

    - session 不存在 / 已完成 / 已过期 → 404
    - chunk_index 越界 → 400
    - 成功返回 {uploaded_chunks: [0, 1, ...], total_chunks}

    注: 接收 raw bytes 而非 multipart File, 避免 5MB+ chunk 走 multipart 编码膨胀 33%
    """
    chunk_data = await request.body()
    if not chunk_data:
        raise HTTPException(status_code=400, detail="chunk body 为空")

    svc = DriveService(db)
    try:
        session = await svc.upload_chunk(
            session_id=upload_id,
            user_id=user.id,
            chunk_index=chunk_index,
            chunk_data=chunk_data,
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return {
        "upload_id": upload_id,
        "uploaded_chunks": list(session.uploaded_chunks or []),
        "total_chunks": session.total_chunks,
    }


@router.get("/files/upload/{upload_id}", response_model=ChunkedUploadStatusResponse)
async def get_chunked_upload_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 断点续传 - 查 session 已传 chunks 列表

    前端 reload 后调此端点 → 拿到 uploaded_chunks → 跳过这些索引
    """
    svc = DriveService(db)
    session = await svc.get_chunked_session(upload_id, user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在或无权访问")

    return ChunkedUploadStatusResponse(
        upload_id=session.id,
        file_name=session.file_name,
        file_size=session.file_size,
        total_chunks=session.total_chunks,
        uploaded_chunks=list(session.uploaded_chunks or []),
        status=session.status,
        expires_at=session.expires_at.isoformat(),
    )


@router.post("/files/upload/{upload_id}/complete", response_model=DriveFileItem)
async def complete_chunked_upload(
    upload_id: str,
    body: ChunkedUploadCompleteRequest = ChunkedUploadCompleteRequest(),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 完成分片上传 → 拼接 → 创建 Knowledge 行

    前置条件: 全部 chunks 已传 (uploaded_chunks == total_chunks)
    副作用:
    - session.status='completed'
    - Fire-and-forget: 重算配额 + 生成缩略图
    - 清 MinIO staging objects
    """
    svc = DriveService(db)
    try:
        new_file = await svc.complete_chunked_upload(
            session_id=upload_id,
            user_id=user.id,
            change_note=body.change_note,
            is_team_shared=body.is_team_shared,  # v2 PR6-P19
        )
    except DriveServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return _to_item(new_file)


@router.post("/files/upload/{upload_id}/abort", status_code=204)
async def abort_chunked_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 中止分片上传 + 清 MinIO staging"""
    svc = DriveService(db)
    success = await svc.abort_chunked_upload(upload_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Session 不存在或已完成")


@router.get("/files/{file_id}/thumbnail", response_model=ThumbnailResponse)
async def get_thumbnail(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR5: 获取文件缩略图信息

    - status=ready → 返 thumbnail_url (MinIO 公开读 URL, 前端 <img src>)
    - status=pending → 返 null URL, 前端 fallback 到 type icon
    - status=failed → 同 pending, UI 可显示 retry 按钮

    越权: 必须能 _can_see_file 才返 (复用 drive_service.get_file 路径)
    """
    svc = DriveService(db)
    k = await svc.get_file(file_id, user.id)
    if not k:
        raise HTTPException(status_code=404, detail="文件不存在或无权访问")

    thumb_url = None
    if k.thumbnail_status == "ready" and k.thumbnail_path:
        # 用 file_service.get_url 返 MinIO 公开读 URL
        thumb_url = file_service.get_url(k.thumbnail_path, expires=3600)

    return ThumbnailResponse(
        file_id=file_id,
        thumbnail_path=k.thumbnail_path,
        thumbnail_status=k.thumbnail_status or "pending",
        thumbnail_url=thumb_url,
    )


# ============================================================
# v2 PR8.5: 移动端聚合 feed 端点 (减少移动端 N 次请求)
# ============================================================

class MobileFeedResponse(BaseModel):
    """PR8.5 mobile feed 响应 (一次返回驱动网盘首页所有数据)
    设计要点:
      - 一次 HTTP 请求 = 减少移动端 N 次往返 (网络延迟对移动端敏感)
      - 各 section 独立 try/except, 失败不阻塞其他 section
      - limit 参数控制每个 section 大小, 默认 10
    """
    recent: List[dict] = Field(default_factory=list)
    starred: List[dict] = Field(default_factory=list)
    team: List[dict] = Field(default_factory=list)
    trash_count: int = 0
    unread_notifications: int = 0
    storage_used_bytes: int = 0
    storage_quota_bytes: int = 0
    generated_at: str = ""


@router.get("/mobile-feed", response_model=MobileFeedResponse)
async def get_mobile_feed(
    limit: int = Query(10, ge=1, le=50, description="每个 section 返回条数"),
    user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v2 PR8.5: 移动端首页聚合 (4 sections + 2 stats)

    Sections:
      - recent: 最近修改 drive 文件 (visibility 含自己可见)
      - starred: 用户收藏
      - team: 团队空间最新
      - (server-side) trash_count + unread_notifications

    失败隔离: 任一 section 失败时返空列表, 不抛 5xx 让整个 feed 失败
    """
    from datetime import datetime, timezone
    svc = DriveService(db)
    feed = MobileFeedResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    # recent
    try:
        items, _ = await svc.list_files(
            current_user_id=user.id, sort_by="updated_at", sort_order="desc",
            page=1, page_size=limit,
        )
        feed.recent = [_drive_file_to_dict(f, user.id) for f in items]
    except Exception as e:
        logger.warning(f"[MobileFeed] recent failed: {e}")

    # starred
    try:
        items, _ = await svc.list_files(
            current_user_id=user.id, sort_by="starred_at", sort_order="desc",
            page=1, page_size=limit, starred_only=True,
        )
        feed.starred = [_drive_file_to_dict(f, user.id) for f in items]
    except Exception as e:
        logger.warning(f"[MobileFeed] starred failed: {e}")

    # team (visibility=team)
    try:
        items, _ = await svc.list_files(
            current_user_id=user.id, sort_by="updated_at", sort_order="desc",
            page=1, page_size=limit, visibility_filter="team",
        )
        feed.team = [_drive_file_to_dict(f, user.id) for f in items]
    except Exception as e:
        logger.warning(f"[MobileFeed] team failed: {e}")

    # trash count (PR2 已实现 list_trash)
    try:
        _, total = await svc.list_trash(current_user_id=user.id, page=1, page_size=1)
        feed.trash_count = total
    except Exception as e:
        logger.warning(f"[MobileFeed] trash_count failed: {e}")

    # unread notifications (PR6)
    try:
        from app.services.notification_service import notification_service
        unread = await notification_service.count_unread(db, user_id=user.id)
        feed.unread_notifications = unread
    except Exception as e:
        logger.warning(f"[MobileFeed] unread_notifications failed: {e}")

    # storage stats (PR5 引入 file_size 列后启用 used_bytes/quota_bytes)
    try:
        stats = await svc.storage_stats(user.id)
        # 当前 PR2 阶段 storage_stats 仅返 file_count + by_visibility,
        # used_bytes/quota_bytes 留 0 等 PR5 引入 size 列后填充
        feed.storage_used_bytes = 0
        feed.storage_quota_bytes = 0
    except Exception as e:
        logger.warning(f"[MobileFeed] storage stats failed: {e}")

    return feed


def _drive_file_to_dict(file: Knowledge, user_id: int) -> dict:
    """PR8.5 helper: Knowledge → mobile feed dict

    复用 drive_service 已有 _to_dict 模式 (如果有), 这里独立实现避免循环 import
    """
    return {
        "id": file.id,
        "title": file.title,
        "file_name": file.file_name,
        "file_type": file.file_type,
        "file_size": file.file_size,
        "visibility": file.visibility,
        "is_starred": bool(getattr(file, "is_starred", False)),
        "updated_at": file.updated_at.isoformat() if file.updated_at else None,
        "folder_id": getattr(file, "folder_id", None),
    }
