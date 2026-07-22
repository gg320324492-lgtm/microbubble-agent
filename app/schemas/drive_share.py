"""Drive v2 PR7 — Folder Share Pydantic Schemas (2026-07-23)

Request / Response models for:
- POST /api/v1/drive/folders/{id}/share
- GET  /api/v1/drive/folders/share/{token}        (无登录)
- POST /api/v1/drive/folders/{id}/members
- DELETE /api/v1/drive/folders/{id}/members/{member_id}

设计:
- 权限枚举: read | write | admin (admin = 可分享给其他人)
- expires 默认 7 天, 上限 365 天
- shares / members 都用统一 FolderShareResponse 包装, 字段一致
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.drive_share import VALID_FOLDER_PERMISSIONS


# ============================================================
# Request Schemas
# ============================================================


class FolderShareCreate(BaseModel):
    """POST /drive/folders/{id}/share 请求体

    permission: read | write | admin
    expires_days: 默认 7, 上限 365 (不允许永久, 安全性)
    """
    permission: str = Field(
        default="read",
        description="read=只读, write=读写, admin=可分享给其他人",
    )
    expires_days: int = Field(
        default=7,
        ge=1,
        le=365,
        description="链接有效期天数 (1-365, 默认 7)",
    )


class FolderMemberAdd(BaseModel):
    """POST /drive/folders/{id}/members 请求体

    member_id: 被邀请成员 ID
    permission: read | write | admin
    """
    member_id: int = Field(..., gt=0, description="被邀请成员 ID")
    permission: str = Field(
        default="read",
        description="read=只读, write=读写, admin=可分享给其他人",
    )


# ============================================================
# Response Schemas
# ============================================================


class FolderShareResponse(BaseModel):
    """分享链接 / 成员邀请的统一响应

    用于:
    - POST /share  → token + url + expires_at + permission
    - GET  /share/{token} → folder 信息 + permission + expires_at
    - POST /members → member_id + permission + invited_by
    - DELETE /members/{member_id} → 确认消息
    """
    id: int
    folder_id: int
    permission: str
    expires_at: Optional[datetime] = None  # member 邀请无过期 = None
    created_by: Optional[int] = None  # member 邀请时为 inviter id
    created_at: datetime

    # 分享链接特有字段 (member 邀请时为 None)
    share_token: Optional[str] = None
    share_url: Optional[str] = None

    # 成员邀请特有字段 (share 链接时为 None)
    member_id: Optional[int] = None

    class Config:
        from_attributes = True


class FolderShareTokenAccess(BaseModel):
    """GET /share/{token} 公开访问响应 (无登录)

    返回 folder 概要 + 访问者权限 + 过期时间
    """
    folder_id: int
    folder_name: str
    owner_id: int
    visibility: str
    permission: str  # 访问者的权限 (read/write/admin)
    expires_at: datetime
    created_by: int
    files: List[dict] = Field(
        default_factory=list,
        description="folder 下的文件列表 (含 file_id + file_name + size 等)",
    )
    subfolders: List[dict] = Field(
        default_factory=list,
        description="folder 下的子 folder 列表",
    )


class FolderMemberListResponse(BaseModel):
    """GET /folders/{id}/members 列表响应 (未来 PR8 扩展, 本 PR 不实现 endpoint)

    本 PR 仅返回单条 (POST/DELETE), 故仅暴露给后续 PR 参考
    """
    folder_id: int
    members: List[FolderShareResponse]
    total: int


# 重新导出, 方便上层统一 import
__all__ = [
    "VALID_FOLDER_PERMISSIONS",
    "FolderShareCreate",
    "FolderMemberAdd",
    "FolderShareResponse",
    "FolderShareTokenAccess",
    "FolderMemberListResponse",
]