"""Drive v2 PR9 — 评论 thread REST API (2026-07-24)

端点:
  POST   /api/v1/drive/comments                  → 创建顶层/嵌套回复
  GET    /api/v1/drive/comments                  → 列表 (按 file_id/folder_id/author/is_resolved 过滤)
  GET    /api/v1/drive/comments/{id}             → 详情 (含子回复树)
  PATCH  /api/v1/drive/comments/{id}             → 编辑内容 (仅 author)
  DELETE /api/v1/drive/comments/{id}             → 删除 (仅 author, CASCADE 子回复)
  POST   /api/v1/drive/comments/{id}/resolve     → 标记已解决 (幂等)
  POST   /api/v1/drive/comments/{id}/unresolve   → 取消已解决 (幂等)

限流: 自动走 drive_upload tier (50/min, 在 app/core/rate_limit.py:285 路径匹配)
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import get_current_user
from app.models.member import Member
from app.schemas.drive_comment import (
    CommentCreate,
    CommentListResponse,
    CommentRead,
    CommentUpdate,
)
from app.services.drive_comment_service import (
    DriveCommentService,
    DriveCommentServiceError,
)

router = APIRouter(prefix="/drive/comments", tags=["网盘评论 thread"])


def _reraise_comment_service_error(e: DriveCommentServiceError) -> None:
    """DriveCommentServiceError → 统一异常响应 (drive_share 同 pattern)

    错误码:
    - 400 → VALIDATION_ERROR
    - 403 → FORBIDDEN
    - 404 → RESOURCE_NOT_FOUND
    """
    code_map = {
        400: "VALIDATION_ERROR",
        403: "FORBIDDEN",
        404: "RESOURCE_NOT_FOUND",
    }
    raise AppException(
        code=code_map.get(e.status_code, "DRIVE_COMMENT_ERROR"),
        message=str(e),
        status_code=e.status_code,
    )


# ==========================================================================
# CRUD
# ==========================================================================


@router.post("", response_model=CommentRead, status_code=201)
async def create_comment(
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR9: 创建评论 (顶层 / 嵌套回复)

    Body:
      file_id / folder_id: 二选一
      parent_id: None=顶层, int=嵌套回复
      content: 1-10000 字符
      mentions: @ user_id 列表

    权限:
    - 读权限 (read) 足够 (类似 GitHub issue 讨论)
    - 仅 author 本人可编辑/删除 (保证作者主权)
    """
    svc = DriveCommentService(db)
    try:
        comment = await svc.create_comment(
            author_id=current_user.id,
            file_id=payload.file_id,
            folder_id=payload.folder_id,
            parent_id=payload.parent_id,
            content=payload.content,
            mentions=payload.mentions,
        )
    except DriveCommentServiceError as e:
        _reraise_comment_service_error(e)

    return CommentRead(
        id=comment.id,
        file_id=comment.file_id,
        folder_id=comment.folder_id,
        author={
            "id": current_user.id,
            "name": current_user.name,
            "avatar_url": getattr(current_user, "avatar_url", None),
        },
        parent_id=comment.parent_id,
        content=comment.content,
        mentions=comment.mentions,
        is_top_level=comment.is_top_level,
        is_resolved=comment.is_resolved,
        resolved_at=comment.resolved_at,
        resolved_by=comment.resolved_by,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=[],
    )


@router.get("", response_model=CommentListResponse)
async def list_comments(
    file_id: Optional[int] = Query(None, gt=0, description="按 file 过滤"),
    folder_id: Optional[int] = Query(None, gt=0, description="按 folder 过滤"),
    author_id: Optional[int] = Query(None, gt=0, description="按作者过滤"),
    is_resolved: Optional[bool] = Query(None, description="按 resolved 状态过滤"),
    parent_id: Optional[int] = Query(None, gt=0, description="按 parent 过滤 (查子回复)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),  # noqa: ARG001
):
    """v2 PR9: 列评论 (顶层 + 内嵌 replies 树)

    Query:
      file_id / folder_id / author_id / is_resolved / parent_id
      page, page_size (默认 1, 50; 上限 100)

    默认返回顶层评论 (parent_id IS NULL), 每个顶层评论的 replies 数组包含所有子回复 (按 created_at 升序)
    """
    svc = DriveCommentService(db)
    items, total = await svc.list_comments(
        file_id=file_id,
        folder_id=folder_id,
        author_id=author_id,
        is_resolved=is_resolved,
        parent_id=parent_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )

    # 转 CommentRead (含 replies 嵌套)
    read_items: list = []
    for c in items:
        replies_attr = getattr(c, "replies", [])
        read_items.append(CommentRead(
            id=c.id,
            file_id=c.file_id,
            folder_id=c.folder_id,
            author={
                "id": c.author.id if c.author else 0,
                "name": c.author.name if c.author else "[已注销用户]",
                "avatar_url": getattr(c.author, "avatar_url", None) if c.author else None,
            },
            parent_id=c.parent_id,
            content=c.content,
            mentions=c.mentions,
            is_top_level=c.is_top_level,
            is_resolved=c.is_resolved,
            resolved_at=c.resolved_at,
            resolved_by=c.resolved_by,
            created_at=c.created_at,
            updated_at=c.updated_at,
            replies=[
                CommentRead(
                    id=r.id,
                    file_id=r.file_id,
                    folder_id=r.folder_id,
                    author={
                        "id": r.author.id if r.author else 0,
                        "name": r.author.name if r.author else "[已注销用户]",
                        "avatar_url": getattr(r.author, "avatar_url", None) if r.author else None,
                    },
                    parent_id=r.parent_id,
                    content=r.content,
                    mentions=r.mentions,
                    is_top_level=r.is_top_level,
                    is_resolved=r.is_resolved,
                    resolved_at=r.resolved_at,
                    resolved_by=r.resolved_by,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                    replies=[],
                )
                for r in replies_attr
            ],
        ))

    return CommentListResponse(items=read_items, total=total)


@router.get("/{comment_id}", response_model=CommentRead)
async def get_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),  # noqa: ARG001
):
    """v2 PR9: 单条评论详情 (含直接子回复)"""
    svc = DriveCommentService(db)
    comment = await svc.get_comment(comment_id, load_replies=True)
    if comment is None:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message=f"Comment id={comment_id} 不存在",
            status_code=404,
        )

    replies_attr = getattr(comment, "replies", [])
    return CommentRead(
        id=comment.id,
        file_id=comment.file_id,
        folder_id=comment.folder_id,
        author={
            "id": comment.author.id if comment.author else 0,
            "name": comment.author.name if comment.author else "[已注销用户]",
            "avatar_url": getattr(comment.author, "avatar_url", None) if comment.author else None,
        },
        parent_id=comment.parent_id,
        content=comment.content,
        mentions=comment.mentions,
        is_top_level=comment.is_top_level,
        is_resolved=comment.is_resolved,
        resolved_at=comment.resolved_at,
        resolved_by=comment.resolved_by,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=[
            CommentRead(
                id=r.id,
                file_id=r.file_id,
                folder_id=r.folder_id,
                author={
                    "id": r.author.id if r.author else 0,
                    "name": r.author.name if r.author else "[已注销用户]",
                    "avatar_url": getattr(r.author, "avatar_url", None) if r.author else None,
                },
                parent_id=r.parent_id,
                content=r.content,
                mentions=r.mentions,
                is_top_level=r.is_top_level,
                is_resolved=r.is_resolved,
                resolved_at=r.resolved_at,
                resolved_by=r.resolved_by,
                created_at=r.created_at,
                updated_at=r.updated_at,
                replies=[],
            )
            for r in replies_attr
        ],
    )


@router.patch("/{comment_id}", response_model=CommentRead)
async def update_comment(
    comment_id: int,
    payload: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR9: 编辑评论 (仅 author)"""
    svc = DriveCommentService(db)
    try:
        comment = await svc.update_comment(
            comment_id=comment_id,
            user_id=current_user.id,
            content=payload.content,
        )
    except DriveCommentServiceError as e:
        _reraise_comment_service_error(e)

    return CommentRead(
        id=comment.id,
        file_id=comment.file_id,
        folder_id=comment.folder_id,
        author={
            "id": comment.author.id if comment.author else 0,
            "name": comment.author.name if comment.author else "[已注销用户]",
            "avatar_url": getattr(comment.author, "avatar_url", None) if comment.author else None,
        },
        parent_id=comment.parent_id,
        content=comment.content,
        mentions=comment.mentions,
        is_top_level=comment.is_top_level,
        is_resolved=comment.is_resolved,
        resolved_at=comment.resolved_at,
        resolved_by=comment.resolved_by,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=[],
    )


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR9: 删除评论 (仅 author, CASCADE 子回复)"""
    svc = DriveCommentService(db)
    try:
        ok = await svc.delete_comment(
            comment_id=comment_id,
            user_id=current_user.id,
        )
    except DriveCommentServiceError as e:
        _reraise_comment_service_error(e)

    if not ok:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message=f"Comment id={comment_id} 不存在",
            status_code=404,
        )
    return Response(status_code=204)


# ==========================================================================
# resolved 状态
# ==========================================================================


@router.post("/{comment_id}/resolve", response_model=CommentRead)
async def resolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR9: 标记已解决 (author / file owner / folder admin)

    幂等: 已 resolved 的评论再次调用不报错, 直接返回当前状态
    """
    svc = DriveCommentService(db)
    try:
        comment = await svc.resolve_comment(
            comment_id=comment_id,
            user_id=current_user.id,
        )
    except DriveCommentServiceError as e:
        _reraise_comment_service_error(e)

    return CommentRead(
        id=comment.id,
        file_id=comment.file_id,
        folder_id=comment.folder_id,
        author={
            "id": comment.author.id if comment.author else 0,
            "name": comment.author.name if comment.author else "[已注销用户]",
            "avatar_url": getattr(comment.author, "avatar_url", None) if comment.author else None,
        },
        parent_id=comment.parent_id,
        content=comment.content,
        mentions=comment.mentions,
        is_top_level=comment.is_top_level,
        is_resolved=comment.is_resolved,
        resolved_at=comment.resolved_at,
        resolved_by=comment.resolved_by,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=[],
    )


@router.post("/{comment_id}/unresolve", response_model=CommentRead)
async def unresolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """v2 PR9: 取消已解决 (同权限)"""
    svc = DriveCommentService(db)
    try:
        comment = await svc.unresolve_comment(
            comment_id=comment_id,
            user_id=current_user.id,
        )
    except DriveCommentServiceError as e:
        _reraise_comment_service_error(e)

    return CommentRead(
        id=comment.id,
        file_id=comment.file_id,
        folder_id=comment.folder_id,
        author={
            "id": comment.author.id if comment.author else 0,
            "name": comment.author.name if comment.author else "[已注销用户]",
            "avatar_url": getattr(comment.author, "avatar_url", None) if comment.author else None,
        },
        parent_id=comment.parent_id,
        content=comment.content,
        mentions=comment.mentions,
        is_top_level=comment.is_top_level,
        is_resolved=comment.is_resolved,
        resolved_at=comment.resolved_at,
        resolved_by=comment.resolved_by,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        replies=[],
    )