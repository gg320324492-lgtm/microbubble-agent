"""Drive v2 PR18 — Team Folder Pydantic Schemas (2026-07-24, W68 第 14 批 B-2)

4 维审计请求/响应模型:
- POST /api/v1/team-folders
- POST /api/v1/team-folders/{id}/members
- DELETE /api/v1/team-folders/{id}/members/{user_id}
- GET /api/v1/team-folders/{id}/audit

设计:
- TeamFolderCreate: name + initial member_ids (可选)
- TeamFolderResponse: id + name + owner_id + member_ids + visibility + created_at
- AuditLogEntry: 4 维审计行 (actor_id + action + target_type + target_id + created_at + extra)
- AuditLogListResponse: 分页包装 (items + total + page + page_size)
- AuditLogQuery: 4 维过滤 (actor_id/action/target_type/since/until)
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.team_folder import (
    VALID_TEAM_FOLDER_AUDIT_ACTIONS,
    VALID_TEAM_FOLDER_AUDIT_TARGETS,
    VALID_TEAM_FOLDER_VISIBILITIES,
)


# ============================================================
# Request Schemas
# ============================================================


class TeamFolderCreate(BaseModel):
    """POST /api/v1/team-folders 请求体

    创建团队共享盘, 默认 visibility='team', owner_id 从 JWT 来
    """
    name: str = Field(..., min_length=1, max_length=200, description="团队文件夹名")
    initial_member_ids: List[int] = Field(
        default_factory=list,
        description="创建时初始邀请的成员 ID 列表 (可选, 后台可继续 add_member)",
    )
    visibility: str = Field(
        default="team",
        description="可见性: private/team/public (默认 team)",
    )


class TeamFolderAddMember(BaseModel):
    """POST /api/v1/team-folders/{id}/members 请求体

    添加成员到 team folder (audit_log 记录 share action)
    """
    target_user_id: int = Field(..., gt=0, description="被邀请成员 ID")
    permission: str = Field(
        default="read",
        description="read=只读 / write=读写",
    )


class TeamFolderAuditQuery(BaseModel):
    """GET /api/v1/team-folders/{id}/audit 查询参数 (4 维过滤)

    - actor_id: 谁做的 (None = 全部 actor)
    - action: 5 种合法 (read/write/delete/share/restore), None = 全部
    - target_type: 4 种合法 (folder/file/member/permission), None = 全部
    - since/until: 时间范围 (可选)
    - page/page_size: 分页 (默认 1/20)
    """
    actor_id: Optional[int] = Field(default=None, description="按 actor 过滤")
    action: Optional[str] = Field(default=None, description="read/write/delete/share/restore")
    target_type: Optional[str] = Field(default=None, description="folder/file/member/permission")
    since: Optional[datetime] = Field(default=None, description="起始时间")
    until: Optional[datetime] = Field(default=None, description="截止时间")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页条数")


# ============================================================
# Response Schemas
# ============================================================


class TeamFolderResponse(BaseModel):
    """GET / POST team folder 响应

    id + name + owner_id + member_ids + visibility + deleted_at + created_at + updated_at
    """
    id: int
    name: str
    owner_id: int
    member_ids: List[int] = Field(default_factory=list)
    visibility: str
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamFolderAuditLogEntry(BaseModel):
    """审计日志单条

    4 维度:
    1. actor_id (who)
    2. action (what)
    3. target_type + target_id (on_what)
    4. created_at (when)
    + extra (额外结构化字段)
    """
    id: int
    team_folder_id: int
    actor_id: int
    action: str
    target_type: str
    target_id: Optional[str] = None
    extra: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TeamFolderAuditLogListResponse(BaseModel):
    """GET /audit 分页响应"""
    items: List[TeamFolderAuditLogEntry]
    total: int
    page: int
    page_size: int


# 重新导出, 方便上层统一 import
__all__ = [
    "TeamFolderCreate",
    "TeamFolderAddMember",
    "TeamFolderAuditQuery",
    "TeamFolderResponse",
    "TeamFolderAuditLogEntry",
    "TeamFolderAuditLogListResponse",
    # 枚举常量 (供 service 层复用)
    "VALID_TEAM_FOLDER_AUDIT_ACTIONS",
    "VALID_TEAM_FOLDER_AUDIT_TARGETS",
    "VALID_TEAM_FOLDER_VISIBILITIES",
]
