"""Drive v2 PR15 — 文件版本标签 (Version Tags) REST API (2026-07-24, W68 第 12 批 B-2)

端点:
  POST   /api/v1/drive/files/{file_id}/tags                  → 增 (body: version_id, tag_name, ...)
  DELETE /api/v1/drive/files/{file_id}/tags/{tag_name}       → 删 (按 version_id + tag_name — 仅 tag 创建者)
  GET    /api/v1/drive/files/{file_id}/tags                  → 列全部版本+标签 (聚合)
  GET    /api/v1/drive/files/{file_id}/tags/{tag_name}       → 按 tag_name 拿首个匹配版本

设计:
- add 幂等: 重复加同一 (version_id, tag_name) 返 200 OK + 已存在 tag (不抛错)
- remove 仅本人: admin 不 override (与 reaction author 主权一致)
- list 聚合: 返回 {file_id, file_name, versions: [{version_id, version_number, is_current, tags: [...]}]}
- get by tag: 按 (file_id, tag_name) 拿最新 version

限流:
- POST/DELETE: drive_upload tier (50/min, app/core/rate_limit.py:285)
- GET: drive_list tier (300/min, app/core/rate_limit.py:287)

锚点范式第 149 守恒.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import get_current_user
from app.models.drive_version_tag import ALLOWED_TAG_NAMES, DriveVersionTag
from app.models.member import Member
from app.services.drive_version_tag_service import (
    DriveVersionTagService,
    DriveVersionTagServiceError,
)

router = APIRouter(prefix="/drive/files", tags=["网盘文件版本标签"])


def _reraise_tag_service_error(e: DriveVersionTagServiceError) -> None:
    """DriveVersionTagServiceError → 统一异常响应

    错误码:
    - 400 → VALIDATION_ERROR
    - 403 → FORBIDDEN
    - 404 → RESOURCE_NOT_FOUND
    - 410 → RESOURCE_GONE
    """
    code_map = {
        400: "VALIDATION_ERROR",
        403: "FORBIDDEN",
        404: "RESOURCE_NOT_FOUND",
        410: "RESOURCE_GONE",
    }
    raise AppException(
        code=code_map.get(e.status_code, "DRIVE_VERSION_TAG_ERROR"),
        message=str(e),
        status_code=e.status_code,
    )


# ==========================================================================
# Pydantic Schemas (本地定义, 避免新增 schema 文件)
# ==========================================================================


class TagCreate(BaseModel):
    """POST /drive/files/{file_id}/tags 请求体"""
    version_id: int = Field(..., gt=0, description="DriveFileVersion.id — 标签关联的具体版本")
    tag_name: str = Field(
        ..., min_length=1, max_length=64,
        description="标签名称 (12 个内置白名单之一: release/stable/deprecated/...)",
    )
    tag_description: Optional[str] = Field(
        None, description="标签描述 (可选, e.g. '2024 年 10 月发布版 - 论文终稿')",
    )
    color: Optional[str] = Field(
        None, max_length=16,
        description="标签颜色 (16 进制 hex e.g. '#FF7A5C', NULL 用默认色)",
    )


class TagRead(BaseModel):
    """POST /drive/files/{file_id}/tags 单条响应"""
    id: int
    version_id: int
    tag_name: str
    tag_description: Optional[str] = None
    color: str
    created_by: int
    created_at: str
    updated_at: str


class TagListItem(BaseModel):
    """GET /drive/files/{file_id}/tags 列表元素 (单个 tag)"""
    id: int
    tag_name: str
    tag_description: Optional[str] = None
    color: str
    created_by: int
    creator_name: Optional[str] = None
    created_at: Optional[str] = None


class VersionWithTags(BaseModel):
    """GET /drive/files/{file_id}/tags 列表元素 (单个版本聚合)"""
    version_id: int
    version_number: int
    is_current: bool
    tags: List[TagListItem] = Field(default_factory=list)


class FileTagsListResponse(BaseModel):
    """GET /drive/files/{file_id}/tags 完整响应"""
    file_id: int
    file_name: Optional[str] = None
    versions: List[VersionWithTags] = Field(default_factory=list)


class FileByTagResponse(BaseModel):
    """GET /drive/files/{file_id}/tags/{tag_name} 响应"""
    version_id: int
    file_id: int
    version_number: int
    is_current: bool
    tag_id: int
    tag_name: str
    tag_description: Optional[str] = None
    color: str
    created_by: int
    created_at: Optional[str] = None


# ==========================================================================
# CRUD
# ==========================================================================


@router.post("/{file_id}/tags", response_model=TagRead, status_code=201)
async def add_tag(
    file_id: int,
    payload: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR15: 给版本添加标签 (幂等)

    Args:
        file_id: 文件 ID (Knowledge.id) — 仅校验 file_id 与 version.file_id 一致
        payload: {version_id, tag_name, tag_description?, color?}

    Returns:
        TagRead: {id, version_id, tag_name, color, created_by, created_at, updated_at}

    幂等:
      同一 (version_id, tag_name) 重复调用返 200 OK + 已存在 tag
      (不抛错, 前端 toggle 体验平滑)

    权限:
      文件创建人 OR folder 管理员 OR 平台管理员 (与 upload_new_version 一致)
    """
    svc = DriveVersionTagService(db)
    try:
        tag = await svc.add_tag(
            version_id=payload.version_id,
            tag_name=payload.tag_name,
            tag_description=payload.tag_description,
            color=payload.color,
            member_id=current_user.id,
        )
    except DriveVersionTagServiceError as e:
        _reraise_tag_service_error(e)

    # 幂等命中 → 查已存在的 tag
    if tag is None:
        existing = (await db.execute(
            __import__("sqlalchemy").select(DriveVersionTag).where(
                DriveVersionTag.version_id == payload.version_id,
                DriveVersionTag.tag_name == payload.tag_name,
            )
        )).scalar_one_or_none()
        if existing is None:
            raise AppException(
                code="DRIVE_VERSION_TAG_ERROR",
                message="标签已存在但无法定位",
                status_code=500,
            )
        tag = existing

    return TagRead(
        id=tag.id,
        version_id=tag.version_id,
        tag_name=tag.tag_name,
        tag_description=tag.tag_description,
        color=tag.color,
        created_by=tag.created_by,
        created_at=tag.created_at.isoformat(),
        updated_at=tag.updated_at.isoformat(),
    )


@router.delete("/{file_id}/tags/{tag_name}", status_code=204)
async def remove_tag(
    file_id: int,
    tag_name: str,
    version_id: int = Query(
        ..., gt=0, description="要删除标签关联的 DriveFileVersion.id",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR15: 删除版本标签 (仅 tag 创建者)

    Args:
        file_id: 文件 ID
        tag_name: 标签名称
        version_id: query 参数, DriveFileVersion.id (复合主键第二段)

    权限:
      仅 tag 创建者本人 (admin 不 override, 与 reaction author 主权一致)
    """
    svc = DriveVersionTagService(db)
    try:
        ok = await svc.remove_tag(
            version_id=version_id,
            tag_name=tag_name,
            member_id=current_user.id,
        )
    except DriveVersionTagServiceError as e:
        _reraise_tag_service_error(e)

    if not ok:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message=f"标签 '{tag_name}' (version_id={version_id}) 不存在",
            status_code=404,
        )


@router.get("/{file_id}/tags", response_model=FileTagsListResponse)
async def list_tags(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR15: 列文件的所有版本+标签 (跨版本聚合)

    Returns:
        FileTagsListResponse: {file_id, file_name, versions: [{version_id, version_number, is_current, tags: [...]}]}

    权限:
      文件可见者 (与 list_versions 一致)
    """
    svc = DriveVersionTagService(db)
    try:
        result = await svc.list_tags_by_file(
            file_id=file_id,
            current_user_id=current_user.id,
        )
    except DriveVersionTagServiceError as e:
        _reraise_tag_service_error(e)

    # 拼装 Pydantic 响应
    versions: List[VersionWithTags] = []
    for v in result["versions"]:
        tag_items: List[TagListItem] = []
        for t in v["tags"]:
            tag_items.append(TagListItem(
                id=t["id"],
                tag_name=t["tag_name"],
                tag_description=t["tag_description"],
                color=t["color"],
                created_by=t["created_by"],
                creator_name=None,  # list_tags_by_file 不返回 creator_name (避免 JOIN N+1)
                created_at=t["created_at"],
            ))
        versions.append(VersionWithTags(
            version_id=v["version_id"],
            version_number=v["version_number"],
            is_current=v["is_current"],
            tags=tag_items,
        ))

    return FileTagsListResponse(
        file_id=result["file_id"],
        file_name=result["file_name"],
        versions=versions,
    )


@router.get("/{file_id}/tags/{tag_name}", response_model=FileByTagResponse)
async def get_file_by_tag(
    file_id: int,
    tag_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR15: 按 (file_id, tag_name) 拿首个匹配版本

    多个版本可共享同一 tag_name, 返回最新 (version_number desc) 的版本

    Returns:
        FileByTagResponse: {version_id, file_id, version_number, is_current, tag_id, tag_name, ...}

    Raises:
        404: 未找到 (file 不存在 / tag 不存在)
    """
    svc = DriveVersionTagService(db)
    try:
        result = await svc.get_file_by_tag(
            file_id=file_id,
            tag_name=tag_name,
            current_user_id=current_user.id,
        )
    except DriveVersionTagServiceError as e:
        _reraise_tag_service_error(e)

    if result is None:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message=f"文件 id={file_id} 标签 '{tag_name}' 不存在",
            status_code=404,
        )

    return FileByTagResponse(
        version_id=result["version_id"],
        file_id=result["file_id"],
        version_number=result["version_number"],
        is_current=result["is_current"],
        tag_id=result["tag_id"],
        tag_name=result["tag_name"],
        tag_description=result["tag_description"],
        color=result["color"],
        created_by=result["created_by"],
        created_at=result["created_at"],
    )


__all__ = [
    "router",
    "TagCreate",
    "TagRead",
    "TagListItem",
    "VersionWithTags",
    "FileTagsListResponse",
    "FileByTagResponse",
    "ALLOWED_TAG_NAMES",
]