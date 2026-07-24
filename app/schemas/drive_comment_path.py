"""Drive v2 PR11 — path 物化 schemas (2026-07-24, W68 第 8 批)

用途: drive_comments.path 列物化嵌套路径, 衍生以下 schemas:
- CommentPathRead: 含 computed depth + breadcrumb
- CommentBreadcrumbItem: 单层面包屑 (id + content preview + author name + depth)
- CommentBreadcrumbResponse: 完整面包屑 (按深度排序, 顶层在前)

调用方 (API 层):
- GET /api/v1/drive/comments?path_prefix=/1/2/         → 列表 (path prefix 过滤)
- GET /api/v1/drive/comments/{id}/breadcrumb             → 祖先链 (1 query 走 path LIKE)

设计:
- CommentPathRead.path + depth 提供前端 O(1) 渲染嵌套层级 (不再依赖 parent_id 递归)
- breadcrumb 走 GIN trigram 索引 (path LIKE '/1/2/%') 一次 query 拉祖先链
- depth 计算由 ORM property 提供, schema 层冗余避免重复计算

W68 第 8 批 PR11 增量:
- 加 path 物化列 (migration 066)
- service.create_comment 自动算 path (parent.path + str(parent.id) + '/')
- service.list_comments 支持 path_prefix 过滤
- service.get_breadcrumb 1 query 拿祖先链
- API 加 path_prefix query + breadcrumb 端点
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# Request/Response for Path
# ============================================================


class CommentPathRead(BaseModel):
    """GET /drive/comments 列表元素 (含 path + depth 物化字段)

    在 CommentRead 基础上加 path + depth, 不破坏老接口
    """
    id: int
    file_id: Optional[int] = None
    folder_id: Optional[int] = None
    author_id: int
    parent_id: Optional[int] = None
    content: str
    mentions: Optional[List[int]] = None
    is_top_level: bool = False
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    path: str = Field("/", description="物化嵌套路径, 例 '/1/2/3/42/'")
    depth: int = Field(0, ge=0, description="嵌套深度, 顶层=0")
    created_at: datetime
    updated_at: datetime


class CommentPathListResponse(BaseModel):
    """GET /drive/comments?path_prefix=... 列表响应"""
    items: List[CommentPathRead]
    total: int
    matched_path_prefix: Optional[str] = Field(
        None, description="实际使用的 path_prefix (规范化后)"
    )


# ============================================================
# Breadcrumb 响应
# ============================================================


class CommentBreadcrumbItem(BaseModel):
    """面包屑单层 (含 author name + content preview)

    前端 O(1) 渲染面包屑导航 (从顶层到当前评论的链路)
    """
    id: int
    parent_id: Optional[int] = None
    content_preview: str = Field(
        ..., max_length=100, description="内容前 100 字符预览"
    )
    author_name: str = Field(..., description="作者名字")
    path: str = Field(..., description="该评论的 path")
    depth: int = Field(..., ge=0, description="嵌套深度")
    created_at: datetime


class CommentBreadcrumbResponse(BaseModel):
    """GET /drive/comments/{id}/breadcrumb 响应

    ancestors: 从顶层到当前评论的链 (depth 升序)
    current: 当前评论自身 (depth 最高)
    """
    ancestors: List[CommentBreadcrumbItem]
    current: CommentBreadcrumbItem
    total: int = Field(..., description="ancestors + current 总数")


__all__ = [
    "CommentPathRead",
    "CommentPathListResponse",
    "CommentBreadcrumbItem",
    "CommentBreadcrumbResponse",
]