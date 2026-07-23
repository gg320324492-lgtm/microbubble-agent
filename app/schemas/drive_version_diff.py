"""Drive v2 PR9 — Version Diff Pydantic Schemas (2026-07-24)

对应 service: app/services/drive_version_diff_service.py
对应 API: app/api/v1/drive_version_diff.py

端点:
- GET /api/v1/drive/versions/files/{file_id}/diff?from=N&to=M
- GET /api/v1/drive/versions/files/{file_id}/versions/{version_id}/preview

设计:
- VersionDiffResponse: 文本 diff / metadata diff 统一响应 (is_text 区分)
- VersionPreviewResponse: 文本预览前 N 行
"""
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Diff 响应
# ============================================================


class VersionMeta(BaseModel):
    """DriveFileVersion metadata 摘要 (from_meta / to_meta 共用)

    字段说明:
    - version_id / version_number: drive_file_versions 主键 + 版本号
    - size: 字节大小
    - uploader_id: 上传者 member.id
    - comment: 用户备注 (e.g. "修订实验结论" / "回滚到 v2")
    - is_current: 是否当前版本
    - created_at: ISO format
    - warning: 可选, 大文件或二进制警告
    """
    version_id: int
    version_number: int
    size: int
    uploader_id: int
    comment: Optional[str] = None
    is_current: bool = False
    created_at: Optional[str] = None
    warning: Optional[str] = None


class VersionDiffResponse(BaseModel):
    """GET diff 响应

    字段说明:
    - file_id / file_name: 主文件标识
    - from_version_*: 起始版本 (1-indexed version_number + version_id)
    - to_version_*: 目标版本
    - is_text: True=文本 diff (含 unified_diff/changed_lines/additions/deletions),
               False=metadata only diff (unified_diff/changed_lines = null)
    - unified_diff: unified diff 字符串 (含 @@ hunks), 仅 is_text=True
    - changed_lines: 变更行号列表 (to 视角, 1-indexed), 仅 is_text=True
    - additions / deletions: 增加/删除字符段数, 仅 is_text=True
    - size_delta: to.size - from.size (字节, always present)
    - uploader_delta: from.uploader_id != to.uploader_id 时 True
    - from_meta / to_meta: 各版本 metadata 摘要
    """
    file_id: int
    file_name: str
    from_version_number: int
    from_version_id: int
    to_version_number: int
    to_version_id: int
    is_text: bool
    unified_diff: Optional[str] = None
    changed_lines: Optional[List[int]] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    size_delta: int = 0
    uploader_delta: bool = False
    from_meta: VersionMeta
    to_meta: VersionMeta


# ============================================================
# Preview 响应
# ============================================================


class VersionPreviewResponse(BaseModel):
    """GET preview 响应

    字段说明:
    - version_id / file_id / version_number: 版本标识
    - file_name: 当前文件 file_name
    - head_lines: 最多返回前 N 行 (默认 200, max 2000)
    - preview_lines: 文本行列表 (已 trim 末尾 \\n), 二进制文件 = []
    - total_lines: 完整文件总行数 (文本)
    - truncated: total_lines > head_lines 时 True
    - is_text: 是否走文本预览 (False → preview_lines 空)
    - size: 字节大小
    - note: 可选提示 (e.g. "二进制文件, 不支持文本预览")
    """
    version_id: int
    file_id: int
    version_number: int
    file_name: str
    head_lines: int
    preview_lines: List[str] = Field(default_factory=list)
    total_lines: int = 0
    truncated: bool = False
    is_text: bool
    size: int
    note: Optional[str] = None
