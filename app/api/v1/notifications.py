"""notifications + activity + comments REST API (PR6)

端点:
- GET    /api/v1/notifications              列我的 mentions (含 unread_count)
- GET    /api/v1/notifications/unread-count  仅未读数 (红点数字)
- POST   /api/v1/notifications/{id}/read    标记单条已读
- POST   /api/v1/notifications/read-all     标记全部已读

- GET    /api/v1/activities                活动动态流 (cursor 分页)

- GET    /api/v1/drive/files/{file_id}/comments      列评论
- POST   /api/v1/drive/files/{file_id}/comments      写评论 (自动解析 @)
- DELETE /api/v1/drive/files/{file_id}/comments/{cid} 删评论 (owner of comment OR owner of file)
- PATCH  /api/v1/drive/files/{file_id}/comments/{cid} 编辑评论 (v2 PR6-P6: owner only, 5 分钟窗口)
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.knowledge import FileComment, ActivityEvent, Knowledge
from app.models.member import Member
from app.services.notification_service import notification_service
from app.services.activity_service import activity_service
from app.services.comment_service import comment_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["通知+活动+评论"])


# ============================================================
# Schemas
# ============================================================

class NotificationItem(BaseModel):
    """单条 @ 提醒"""
    id: int
    file_id: int
    file_name: Optional[str] = None
    mentioned_by: Optional[int] = None
    mentioned_by_name: Optional[str] = None
    context: Optional[str] = None
    is_read: bool
    read_at: Optional[str] = None
    created_at: Optional[str] = None


class NotificationListResponse(BaseModel):
    items: List[NotificationItem]
    unread_count: int
    total: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class ReadAllResponse(BaseModel):
    marked_count: int


class ActivityItem(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_name: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: Optional[str] = None


class ActivityFeedResponse(BaseModel):
    items: List[ActivityItem]
    has_more: bool


class CommentItem(BaseModel):
    id: int
    file_id: int
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    content: str
    mentions: Optional[List[int]] = None
    parent_comment_id: Optional[int] = None  # v2 PR6-P5 threading
    thread_depth: int = 0                   # v2 PR6-P5: 0/1/2
    reply_count: int = 0                    # v2 PR6-P5: 冗余子评论数
    created_at: Optional[str] = None


class CommentListResponse(BaseModel):
    items: List[CommentItem]
    total: int


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[int] = Field(
        None, description="v2 PR6-P5: 父评论 id, None=顶层评论"
    )


class CommentCreateResponse(BaseModel):
    """POST 评论响应 (含 mention 列表)"""
    comment: CommentItem
    mentioned_user_ids: List[int]


class CommentUpdateRequest(BaseModel):
    """v2 PR6-P6: PATCH 评论请求体 (仅 content, owner only, 5 分钟窗口)"""
    content: str = Field(..., min_length=1, max_length=2000)


class CommentUpdateResponse(BaseModel):
    """v2 PR6-P6: PATCH 评论响应 (含新 mentions 列表)"""
    comment: CommentItem
    mentioned_user_ids: List[int]


# ============================================================
# Helper: 批量查 user_name (避免 N+1)
# ============================================================

async def _batch_user_names(db: AsyncSession, user_ids: List[int]) -> dict:
    if not user_ids:
        return {}
    stmt = select(Member.id, Member.username, Member.name).where(Member.id.in_(set(user_ids)))
    rows = (await db.execute(stmt)).all()
    return {r.id: (r.username or r.name or f"用户{r.id}") for r in rows}


# ============================================================
# Notification endpoints
# ============================================================

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """列我的 mentions (按时间倒序) + 未读总数"""
    mentions = await notification_service.list_for_user(
        db, user_id=user.id, unread_only=unread_only, limit=limit,
    )

    # 批量查 file_name + mentioned_by_name (避免 N+1)
    file_ids = [m.file_id for m in mentions]
    user_ids = [m.mentioned_by for m in mentions if m.mentioned_by]
    file_names = {}
    if file_ids:
        stmt = select(Knowledge.id, Knowledge.file_name).where(Knowledge.id.in_(set(file_ids)))
        rows = (await db.execute(stmt)).all()
        file_names = {r.id: (r.file_name or "") for r in rows}
    user_names = await _batch_user_names(db, user_ids)

    items = [
        NotificationItem(
            id=m.id,
            file_id=m.file_id,
            file_name=file_names.get(m.file_id),
            mentioned_by=m.mentioned_by,
            mentioned_by_name=user_names.get(m.mentioned_by) if m.mentioned_by else None,
            context=m.context,
            is_read=m.is_read,
            read_at=str(m.read_at) if m.read_at else None,
            created_at=str(m.created_at) if m.created_at else None,
        )
        for m in mentions
    ]

    unread_count = await notification_service.count_unread(db, user_id=user.id)
    return NotificationListResponse(
        items=items,
        unread_count=unread_count,
        total=len(items),
    )


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """仅未读数 (前端 NotificationBell 红点数字, 轻量级 polling)"""
    count = await notification_service.count_unread(db, user_id=user.id)
    return UnreadCountResponse(unread_count=count)


@router.post("/notifications/{mention_id}/read", status_code=204)
async def mark_notification_read(
    mention_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """标记单条已读"""
    ok = await notification_service.mark_read(db, mention_id=mention_id, user_id=user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在或无权访问")


@router.post("/notifications/read-all", response_model=ReadAllResponse)
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """标记全部已读"""
    count = await notification_service.mark_all_read(db, user_id=user.id)
    return ReadAllResponse(marked_count=count)


# ============================================================
# Activity endpoints
# ============================================================

@router.get("/activities", response_model=ActivityFeedResponse)
async def list_activities(
    scope: str = Query("team", pattern="^(team|all|me)$"),
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """活动动态流

    scope:
      - 'team': 全部 team 范围活动 (默认, 包括 owner=any)
      - 'me':   仅我看得到的 (file owned by me / 我参与的)
      - 'all':  全部 (admin only — PR7 加 admin 校验)
    """
    if scope == "me":
        # 查我作为 actor 的活动
        events = await activity_service.feed(
            db, actor_ids=[user.id], limit=limit, before_id=before_id,
        )
    else:
        # team / all: 不限 actor (PR7+ 加 admin 校验)
        events = await activity_service.feed(
            db, limit=limit, before_id=before_id,
        )

    # 批量查 actor_name
    actor_ids = [e.actor_id for e in events if e.actor_id]
    user_names = await _batch_user_names(db, actor_ids)

    items = [
        ActivityItem(
            **activity_service.to_dict(e, actor_name=user_names.get(e.actor_id))
        )
        for e in events
    ]
    has_more = len(items) == limit
    return ActivityFeedResponse(items=items, has_more=has_more)


# ============================================================
# Comment endpoints
# ============================================================

@router.get("/drive/files/{file_id}/comments", response_model=CommentListResponse)
async def list_file_comments(
    file_id: int,
    limit: int = Query(100, ge=1, le=200),
    before_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """列文件评论 (按时间倒序)"""
    # 越权: 必须能 _can_see_file 才返 (drive_service 已有 _can_see_file)
    from app.services.drive_service import DriveService
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="文件不存在或无权访问")

    rows = await comment_service.list_comments(
        db, file_id=file_id, limit=limit, before_id=before_id,
    )

    items = [
        CommentItem(
            id=c.id,
            file_id=c.file_id,
            user_id=c.user_id,
            user_name=user_name,
            content=c.content,
            mentions=c.mentions,
            parent_comment_id=c.parent_comment_id,  # v2 PR6-P5
            thread_depth=c.thread_depth,             # v2 PR6-P5
            reply_count=c.reply_count,               # v2 PR6-P5
            created_at=str(c.created_at) if c.created_at else None,
        )
        for c, user_name in rows
    ]
    return CommentListResponse(items=items, total=len(items))


@router.post("/drive/files/{file_id}/comments", response_model=CommentCreateResponse, status_code=201)
async def create_file_comment(
    file_id: int,
    payload: CommentCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """写评论 + 自动解析 @username → 创建 mention (+ v2 PR6-P5 reply)

    v2 PR6-P5: payload.parent_comment_id 可选
      - None: 顶层评论 (默认, 向后兼容 PR6 所有老数据)
      - int: 该评论的回复, 自动算 thread_depth, MAX_DEPTH=2 截断
    """
    from app.services.drive_service import DriveService
    svc = DriveService(db)
    f = await svc.get_file(file_id, current_user_id=user.id)
    if f is None:
        raise HTTPException(status_code=404, detail="文件不存在或无权访问")

    try:
        comment, mentioned_user_ids = await comment_service.create_comment(
            db,
            file_id=file_id,
            user_id=user.id,
            content=payload.content,
            parent_comment_id=payload.parent_comment_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    user_names = await _batch_user_names(db, [user.id])

    return CommentCreateResponse(
        comment=CommentItem(
            id=comment.id,
            file_id=comment.file_id,
            user_id=comment.user_id,
            user_name=user_names.get(user.id),
            content=comment.content,
            mentions=comment.mentions,
            parent_comment_id=comment.parent_comment_id,
            thread_depth=comment.thread_depth,
            reply_count=comment.reply_count,
            created_at=str(comment.created_at) if comment.created_at else None,
        ),
        mentioned_user_ids=mentioned_user_ids,
    )


@router.delete("/drive/files/{file_id}/comments/{comment_id}", status_code=204)
async def delete_file_comment(
    file_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """删评论 (comment owner OR file owner)"""
    ok = await comment_service.delete_comment(
        db, comment_id=comment_id, user_id=user.id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="评论不存在或无权访问")


@router.patch("/drive/files/{file_id}/comments/{comment_id}", response_model=CommentUpdateResponse)
async def update_file_comment(
    file_id: int,
    comment_id: int,
    payload: CommentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """v2 PR6-P6: 编辑评论 (owner only + 5 分钟窗口)

    422 错误码:
      - "评论不存在" / "无权编辑此评论"
      - "编辑窗口已过" (now - created_at > 300s)
      - "评论内容不能为空" / "评论内容超长"
    """
    try:
        comment, mentioned_user_ids = await comment_service.update_comment(
            db,
            comment_id=comment_id,
            user_id=user.id,
            new_content=payload.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    user_names = await _batch_user_names(db, [user.id])

    return CommentUpdateResponse(
        comment=CommentItem(
            id=comment.id,
            file_id=comment.file_id,
            user_id=comment.user_id,
            user_name=user_names.get(user.id),
            content=comment.content,
            mentions=comment.mentions,
            parent_comment_id=comment.parent_comment_id,
            thread_depth=comment.thread_depth,
            reply_count=comment.reply_count,
            created_at=str(comment.created_at) if comment.created_at else None,
        ),
        mentioned_user_ids=mentioned_user_ids,
    )