"""Drive v2 PR9 — File Version Pydantic Schemas (2026-07-24)

Request / Response models for:
- POST /api/v1/drive/versions/files/{file_id}/versions                  → 上传新版本
- GET  /api/v1/drive/versions/files/{file_id}/versions                  → 列所有版本
- GET  /api/v1/drive/versions/versions/{version_id}/download            → 下载指定版本
- POST /api/v1/drive/versions/files/{file_id}/versions/{version_id}/rollback → 回滚
- DELETE /api/v1/drive/versions/versions/{version_id}                   → 删除某版

设计:
- DriveFileVersionItem: 列表/详情通用响应 (含 uploader_name JOIN)
- DriveFileVersionUpload: 上传新版本请求 (multipart form: file + comment)
- DriveFileVersionRollback: 回滚请求 (可选新 comment)
- DriveFileVersionDownload: 下载响应 (含临时签名 URL, 复用 file_service)
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Response Schemas
# ============================================================


class DriveFileVersionItem(BaseModel):
    """文件版本明细 (GET list 响应)

    字段说明:
    - id: drive_file_versions.id (版本明细行 id)
    - file_id: Knowledge.id (主文件行)
    - version_number: 1, 2, 3... 单调递增
    - minio_object_key: 历史版 MinIO 路径
    - size: 字节大小
    - uploader_id + uploader_name: 上传者 (LEFT JOIN members)
    - comment: 用户备注
    - is_current: 是否当前版本 (1 行 True, 其它 False)
    - created_at: ISO format
    """
    id: int
    file_id: int
    version_number: int
    minio_object_key: str
    size: int
    uploader_id: int
    uploader_name: Optional[str] = None
    comment: Optional[str] = None
    is_current: bool = False
    created_at: str

    class Config:
        from_attributes = True


class DriveFileVersionListResponse(BaseModel):
    """GET 列表响应 (含 file_id + count + items)

    返回字段:
    - file_id: 主文件行 Knowledge.id
    - file_name: 主文件 file_name (方便 UI 头部展示)
    - count: 版本总数 (含当前 + 历史)
    - items: 版本明细列表, 按 version_number desc 排序
    """
    file_id: int
    file_name: Optional[str] = None
    count: int
    items: list[DriveFileVersionItem]


class DriveFileVersionDownloadResponse(BaseModel):
    """GET 下载响应

    返回字段:
    - version_id / file_id / version_number
    - download_url: 临时签名 URL (复用 file_service.presigned_url)
    - expires_in: 链接有效期 (秒)
    - file_name: 当前文件 file_name (download 时浏览器保存名)
    - size: 字节大小
    """
    version_id: int
    file_id: int
    version_number: int
    download_url: str
    expires_in: int = 3600
    file_name: Optional[str] = None
    size: int


# ============================================================
# Request Schemas
# ============================================================


class DriveFileVersionUploadResponse(BaseModel):
    """POST 上传新版本响应

    返回字段:
    - version: 新创建的 DriveFileVersionItem (is_current=True)
    - file: 更新后的 Knowledge 行 (file_size/version_number 更新)
    """
    version: DriveFileVersionItem
    file_id: int
    new_version_number: int
    file_name: Optional[str] = None
    file_size: int


class DriveFileVersionRollbackRequest(BaseModel):
    """POST 回滚请求

    - target_version_id: 目标历史版本 (被回滚的版本)
    - new_comment: 可选, 新版本的备注 (默认 'Rolled back to v{N}')
    """
    new_comment: Optional[str] = Field(
        None,
        max_length=500,
        description="新版本的备注, 默认 'Rolled back to v{N}'",
    )


class DriveFileVersionRollbackResponse(BaseModel):
    """POST 回滚响应

    返回字段:
    - version: 新创建的 DriveFileVersionItem (复制自 target, version_number=cur+1)
    - rolled_back_from: 被回滚的版本号
    - new_version_number: 新版本号
    """
    version: DriveFileVersionItem
    rolled_back_from: int
    new_version_number: int
    file_id: int


class DriveFileVersionDeleteResponse(BaseModel):
    """DELETE 单个版本响应

    - deleted_version_id: 删除的版本 id
    - deleted_object_key: 删除的 MinIO object
    - remaining_versions: 剩余版本数 (含 current)
    """
    deleted_version_id: int
    deleted_object_key: str
    remaining_versions: int