"""Drive v2 PR11 recursive fallback schemas (2026-07-24, W68 第 9 批 B-2)

PR11 fallback breadcrumb 响应 — 含 path 字段标识 (X-Fallback header / body path):
- ancestors: 祖先链 (depth 升序)
- current: 目标评论 (depth=0)
- path: "gin" 或 "recursive" — 哪条路径被采纳 (便于前端调试 / 监控)
- duration_ms: 性能 (GIN < 10ms / recursive < 50ms 预期)

设计原则:
- 不依赖 DriveComment ORM 字段 (path 列可能尚未物化)
- 复用 PR11 的 CommentBreadcrumbItem 形态 (id / parent_id / content_preview
  / author_name / depth / created_at), 加 path 字段
- 路径标识符 (X-Fallback header) 由 API 层注入 (避免污染 response body schema)
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class FallbackBreadcrumbItem(BaseModel):
    """单层面包屑 — PR11 fallback 专用 (path 字段可空, 兼容老 schema)

    与 PR11 CommentBreadcrumbItem 类似, 但 path 字段改为 Optional
    (fallback 走 PG function 时不一定有 path)
    """
    id: int
    parent_id: Optional[int] = None
    content_preview: str = ""
    author_name: str = "[未知]"
    path: Optional[str] = None  # 兼容老 schema (path 列可能未物化)
    depth: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


class FallbackBreadcrumbResponse(BaseModel):
    """完整面包屑响应

    Attributes:
        ancestors: 祖先链 (depth 升序, 顶层在前)
        current: 目标评论 (depth=0)
        total: 总条数 (ancestors + current)
        path: "gin" 或 "recursive" — 哪条路径被采纳
        duration_ms: 本次调用耗时 (ms)
    """
    ancestors: List[FallbackBreadcrumbItem] = Field(default_factory=list)
    current: Optional[FallbackBreadcrumbItem] = None
    total: int = 0
    path: str = "gin"  # gin | recursive
    duration_ms: float = 0.0


class FallbackDescendantsResponse(BaseModel):
    """子树响应 (depth 升序, 同 depth 按 created_at 升序)

    Attributes:
        root_id: 起始评论 id
        max_depth: 嵌套深度上限 (PG function 内 clamp 到 [0, 1000])
        rows: 全部后代 (含 root)
        total: 总条数
        path: "gin" 或 "recursive"
        duration_ms: 耗时
    """
    root_id: int
    max_depth: int = 100
    rows: List[FallbackBreadcrumbItem] = Field(default_factory=list)
    total: int = 0
    path: str = "recursive"
    duration_ms: float = 0.0


__all__ = [
    "FallbackBreadcrumbItem",
    "FallbackBreadcrumbResponse",
    "FallbackDescendantsResponse",
]