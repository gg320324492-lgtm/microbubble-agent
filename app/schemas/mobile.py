"""v2 PR8: 移动端聚合 API Pydantic schemas

设计原则:
- 字段命名 snake_case (与 drive_files.py 一致, 前端 axios 直接消费)
- 移动端友好: cursor pagination (last_id) + 精简 payload
- 类型严格: Optional 字段 nullable 默认值清晰
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# GET /api/v1/mobile/dashboard — 移动首页聚合
# ============================================================
class MobileDashboardActivity(BaseModel):
    """单条活动动态"""
    id: int
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    action: str  # upload | rename | move | delete | share | star | comment | mention
    target_type: str  # file | folder | comment
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    created_at: str  # ISO 8601


class MobileDashboardStarredFile(BaseModel):
    """收藏文件摘要 (drive_files 摘要版, 不含完整 owner)"""
    id: int
    title: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    visibility: Optional[str] = None
    folder_id: Optional[int] = None
    starred_at: Optional[str] = None
    updated_at: Optional[str] = None


class MobileDashboardTeamRootFile(BaseModel):
    """团队空间根文件 (visibility=team)"""
    id: int
    title: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    folder_id: Optional[int] = None
    updated_at: Optional[str] = None
    uploader_id: Optional[int] = None
    uploader_name: Optional[str] = None


class MobileDashboardMyUpload(BaseModel):
    """我最近上传"""
    id: int
    title: str
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    visibility: Optional[str] = None
    folder_id: Optional[int] = None
    created_at: Optional[str] = None


class MobileDashboardResponse(BaseModel):
    """移动端首页聚合响应

    与 drive_files.py:/mobile-feed 不同:
    - /mobile-feed 关注 drive 文件清单 (4 sections 全是文件)
    - /mobile/dashboard 关注 '首页 dashboard' (活动 + 文件 + 通知数混合)
    - 这里是真正的 '移动首页 dashboard' (语义: 用户一进 app 看到的卡片)
    """
    recent_activities: List[MobileDashboardActivity] = Field(default_factory=list)
    starred_files: List[MobileDashboardStarredFile] = Field(default_factory=list)
    team_root_files: List[MobileDashboardTeamRootFile] = Field(default_factory=list)
    my_uploads: List[MobileDashboardMyUpload] = Field(default_factory=list)
    notification_unread_count: int = 0
    generated_at: str = ""


# ============================================================
# GET /api/v1/mobile/feed — 滚动 feed (cursor pagination)
# ============================================================
class MobileFeedItem(BaseModel):
    """单条 feed item (统一活动流)"""
    type: str  # activity | recent | starred
    timestamp: str  # ISO 8601, 客户端按此排序
    payload: Dict[str, Any]  # type-specific 数据 (activity=Activity dict, file=file dict)


class MobileFeedResponse(BaseModel):
    """滚动 feed 响应 (last_id cursor pagination)"""
    items: List[MobileFeedItem] = Field(default_factory=list)
    next_cursor: Optional[str] = None  # 下一批的 cursor (NULL = 到底了)
    has_more: bool = False


# ============================================================
# POST /api/v1/mobile/album-auto-backup — 相册自动备份开关
# ============================================================
class AlbumAutoBackupRequest(BaseModel):
    """相册自动备份配置"""
    enabled: bool = False
    folder_id: Optional[int] = None  # 备份到哪个网盘文件夹 (NULL = 根目录)
    wifi_only: bool = True  # 仅 Wi-Fi 下备份 (默认开启防流量)


class AlbumAutoBackupResponse(BaseModel):
    """相册自动备份配置 (idempotent POST: 返当前配置)"""
    enabled: bool
    folder_id: Optional[int] = None
    wifi_only: bool = True
    updated_at: str = ""
    message: str = ""