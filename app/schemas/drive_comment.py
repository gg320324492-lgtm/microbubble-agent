"""Drive v2 PR9 + PR12 — 评论 thread Pydantic Schemas (2026-07-24)

Request / Response models for:
- POST   /api/v1/drive/comments
- GET    /api/v1/drive/comments
- GET    /api/v1/drive/comments/{id}
- PATCH  /api/v1/drive/comments/{id}
- DELETE /api/v1/drive/comments/{id}
- POST   /api/v1/drive/comments/{id}/resolve
- POST   /api/v1/drive/comments/{id}/unresolve

W68 PR12 (锚点范式第 94 守恒) — CommentRead 加 reactions 字段 (List[ReactionSummary]):
- 表达 comment 的 emoji reactions 聚合 (前端 O(1) 渲染表情选择器 + 数量徽章)
- 默认空列表 (comment 详情/列表接口按需 populate — 避免 N+1)
- 单 reaction summary = {emoji, count, members, my_reacted}

设计:
- CommentCreate: 必须 file_id / folder_id 之一 + content + 可选 parent_id/mentions
- CommentUpdate: 仅 content (其他字段不能改, 防滥用)
- CommentRead: 完整字段 + 派生 is_resolved / is_top_level / author 概要 + PR12 reactions
- 嵌套回复通过 CommentRead.replies (children) 列表, 不强制按时间戳
- 列表接口支持过滤: file_id / folder_id / author_id / is_resolved / parent_id

校验:
- content 长度: 1-10000 (Pydantic constr)
- parent_id 必须是已存在评论 (service 层校验)
- file_id / folder_id 必须存在 (service 层校验)
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================
# PR12 Reaction Schemas (W68 第 8 批 B-2)
# ============================================================


class ReactionMemberSummary(BaseModel):
    """反应者概要 (前端 O(1) 渲染头像 + 名字)"""
    id: int
    name: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class ReactionSummary(BaseModel):
    """单个 emoji 聚合 (W68 PR12)

    字段:
    - emoji: emoji 字面值
    - count: 该 emoji 的总反应数
    - members: 反应者列表 (按 created_at 升序)
    - my_reacted: 当前用户是否反应过该 emoji (前端 toggle 高亮用)
    """
    emoji: str
    count: int
    members: List[ReactionMemberSummary] = Field(default_factory=list)
    my_reacted: bool = False

    class Config:
        from_attributes = True


# ============================================================
# Request Schemas
# ============================================================


class CommentCreate(BaseModel):
    """POST /drive/comments 请求体

    三种用法:
    1. 文件顶层评论: file_id=N, parent_id=None
    2. 文件夹顶层评论: folder_id=N, parent_id=None
    3. 嵌套回复: file_id/folder_id 任意一个 (与 parent 一致), parent_id=M
    """
    file_id: Optional[int] = Field(None, gt=0, description="目标文件 ID (与 folder_id 二选一)")
    folder_id: Optional[int] = Field(None, gt=0, description="目标文件夹 ID (与 file_id 二选一)")
    parent_id: Optional[int] = Field(None, gt=0, description="父评论 ID (None=顶层)")
    content: str = Field(..., min_length=1, max_length=10000, description="评论内容")
    mentions: Optional[List[int]] = Field(
        None, description="@ 提醒的 user_id 列表 (前端 O(1) 高亮)"
    )

    @model_validator(mode="after")
    def _check_target_xor(self):
        if (self.file_id is None) == (self.folder_id is None):
            raise ValueError("file_id / folder_id 必须二选一 (不能同时为空或同时存在)")
        return self


class CommentUpdate(BaseModel):
    """PATCH /drive/comments/{id} 请求体 (仅 author 可调)

    仅 content 可改 (mentions / parent_id / target 不允许改, 防滥用)
    """
    content: str = Field(..., min_length=1, max_length=10000)


# ============================================================
# Response Schemas
# ============================================================


class CommentAuthorSummary(BaseModel):
    """作者概要 (前端 O(1) 渲染头像 + 名字)"""
    id: int
    name: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class CommentRead(BaseModel):
    """GET /drive/comments/{id} 单条响应 + 列表元素

    含:
    - 主体字段 (id / file_id / folder_id / author / content / mentions / parent_id)
    - 时间戳 (created_at / updated_at)
    - resolved 状态 (resolved_at / resolved_by / is_resolved)
    - 派生 is_top_level (parent_id NULL)
    - 子回复列表 replies (默认空, 列表接口按需 populate)
    - **W68 PR12**: reactions 字段 (List[ReactionSummary], 默认 [])
      — 表情反应聚合, 前端 O(1) 渲染 emoji 选择器 + 数量徽章
    """
    id: int
    file_id: Optional[int] = None
    folder_id: Optional[int] = None
    author: CommentAuthorSummary
    parent_id: Optional[int] = None
    content: str
    mentions: Optional[List[int]] = None
    is_top_level: bool = False
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # 子回复 (嵌套), 默认空, list_threads 接口 populate
    replies: List["CommentRead"] = Field(default_factory=list)

    # W68 PR12: 表情反应聚合 (默认空, 详情/列表接口按需 populate)
    reactions: List[ReactionSummary] = Field(default_factory=list)

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """GET /drive/comments 列表响应 (顶层评论 + 内嵌 replies)

    items: 顶层评论列表 (parent_id IS NULL)
    total: 总评论数 (含 replies, 不只顶层)
    """
    items: List[CommentRead]
    total: int


# 解决 Pydantic v2 自引用 (CommentRead.replies: List[CommentRead])
CommentRead.model_rebuild()


__all__ = [
    "CommentCreate",
    "CommentUpdate",
    "CommentAuthorSummary",
    "CommentRead",
    "CommentListResponse",
    # W68 PR12 (锚点范式第 94 守恒)
    "ReactionSummary",
    "ReactionMemberSummary",
]