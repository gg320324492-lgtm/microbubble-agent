"""v2 PR8: 移动端聚合 API

设计目的:
- 移动端首页 dashboard 一站式拉取 (避免 N 次独立请求)
- cursor pagination (last_id) 友好移动滚动
- album-auto-backup 客户端配置开关 (前端持久化)

端点:
- GET   /api/v1/mobile/dashboard        → 移动首页聚合 (5 个 section)
- GET   /api/v1/mobile/feed             → 滚动 feed (cursor pagination, type=activity|recent|starred)
- POST  /api/v1/mobile/album-auto-backup → 相册自动备份开关 (idempotent)

注意:
- 不复用 drive_files.py:/mobile-feed — 那个端点关注 drive 文件 4 sections,
  本端点关注 '首页 dashboard' (活动流 + 文件 + 通知数混合, 语义不同)
- 不复用 drive_files.py:_drive_file_to_dict — 独立实现避免循环 import
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ValidationException
from app.core.security import get_current_user
from app.models.knowledge import ActivityEvent, Knowledge
from app.models.member import Member
from app.schemas.mobile import (
    AlbumAutoBackupRequest,
    AlbumAutoBackupResponse,
    MobileDashboardActivity,
    MobileDashboardMyUpload,
    MobileDashboardResponse,
    MobileDashboardStarredFile,
    MobileDashboardTeamRootFile,
    MobileFeedItem,
    MobileFeedResponse,
)

logger = logging.getLogger("microbubble.mobile_api")

router = APIRouter(prefix="/mobile", tags=["mobile"])


# ============================================================
# Redis-backed album-auto-backup config (per-user)
# ============================================================
# 设计: 用 Redis key `mobile:album-backup:{user_id}` 存 JSON 配置
# 优点: 简单 + 跨设备共享 + 无 DB schema 变更
# 缺点: Redis 挂了返默认值 (不影响主流程)
_BACKUP_CONFIG_KEY = "mobile:album-backup:{user_id}"
_BACKUP_CONFIG_TTL = 86400 * 365  # 1 年 (配置 long-lived)


async def _get_backup_config(user_id: int) -> dict:
    """读相册自动备份配置 (Redis, 失败返默认 disabled)"""
    default = {"enabled": False, "folder_id": None, "wifi_only": True}
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        raw = await r.get(_BACKUP_CONFIG_KEY.format(user_id=user_id))
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"[_get_backup_config] Redis read failed: {e}")
    return default


async def _set_backup_config(user_id: int, config: dict) -> None:
    """写相册自动备份配置 (Redis)"""
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        await r.set(
            _BACKUP_CONFIG_KEY.format(user_id=user_id),
            json.dumps(config),
            ex=_BACKUP_CONFIG_TTL,
        )
    except Exception as e:
        logger.warning(f"[_set_backup_config] Redis write failed: {e}")


# ============================================================
# 1. GET /api/v1/mobile/dashboard
# ============================================================
@router.get("/dashboard", response_model=MobileDashboardResponse)
async def get_mobile_dashboard(
    user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v2 PR8: 移动首页聚合 (5 sections)

    Returns:
      - recent_activities: 最近 10 条活动流 (ActivityEvent)
      - starred_files: 用户收藏文件 (top 8, 按 starred_at desc)
      - team_root_files: 团队空间根文件 (top 8, 按 updated_at desc)
      - my_uploads: 用户最近上传 (top 8, 按 created_at desc)
      - notification_unread_count: 未读通知数

    失败隔离: 任一 section 失败时返空列表/0, 不抛 5xx 让整个 dashboard 失败
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    dashboard = MobileDashboardResponse(generated_at=now_iso)

    # ---- 1. recent_activities (ActivityEvent) ----
    try:
        stmt = (
            select(ActivityEvent, Member.name)
            .outerjoin(Member, Member.id == ActivityEvent.actor_id)
            .order_by(desc(ActivityEvent.created_at))
            .limit(10)
        )
        result = await db.execute(stmt)
        for ev, actor_name in result.all():
            dashboard.recent_activities.append(
                MobileDashboardActivity(
                    id=ev.id,
                    actor_id=ev.actor_id,
                    actor_name=actor_name,
                    action=ev.action,
                    target_type=ev.target_type,
                    target_id=ev.target_id,
                    target_name=ev.target_name,
                    created_at=ev.created_at.isoformat() if ev.created_at else "",
                )
            )
    except Exception as e:
        logger.warning(f"[MobileDashboard] recent_activities failed: {e}")

    # ---- 2. starred_files ----
    try:
        # 隐私边界: 仅 own private + 全部 public/team 可见 (复用 drive service 逻辑)
        visibility_see = or_(
            Knowledge.created_by == user.id,
            Knowledge.visibility != "private",
        )
        stmt = (
            select(Knowledge)
            .where(
                and_(
                    Knowledge.storage_mode == "drive",
                    Knowledge.deleted_at.is_(None),
                    Knowledge.is_starred.is_(True),
                    visibility_see,
                )
            )
            .order_by(desc(Knowledge.starred_at))
            .limit(8)
        )
        result = await db.execute(stmt)
        for f in result.scalars().all():
            dashboard.starred_files.append(
                MobileDashboardStarredFile(
                    id=f.id,
                    title=f.title or f.file_name or f"文件{f.id}",
                    file_name=f.file_name,
                    file_type=f.file_type,
                    file_size=f.file_size,
                    visibility=f.visibility,
                    folder_id=f.folder_id,
                    starred_at=f.starred_at.isoformat() if f.starred_at else None,
                    updated_at=f.updated_at.isoformat() if f.updated_at else None,
                )
            )
    except Exception as e:
        logger.warning(f"[MobileDashboard] starred_files failed: {e}")

    # ---- 3. team_root_files ----
    try:
        stmt = (
            select(Knowledge, Member.name)
            .outerjoin(Member, Member.id == Knowledge.created_by)
            .where(
                and_(
                    Knowledge.storage_mode == "drive",
                    Knowledge.deleted_at.is_(None),
                    Knowledge.visibility == "team",
                    Knowledge.folder_id.is_(None),
                )
            )
            .order_by(desc(Knowledge.updated_at))
            .limit(8)
        )
        result = await db.execute(stmt)
        for f, uploader_name in result.all():
            dashboard.team_root_files.append(
                MobileDashboardTeamRootFile(
                    id=f.id,
                    title=f.title or f.file_name or f"文件{f.id}",
                    file_name=f.file_name,
                    file_type=f.file_type,
                    file_size=f.file_size,
                    folder_id=f.folder_id,
                    updated_at=f.updated_at.isoformat() if f.updated_at else None,
                    uploader_id=f.created_by,
                    uploader_name=uploader_name,
                )
            )
    except Exception as e:
        logger.warning(f"[MobileDashboard] team_root_files failed: {e}")

    # ---- 4. my_uploads ----
    try:
        stmt = (
            select(Knowledge)
            .where(
                and_(
                    Knowledge.storage_mode == "drive",
                    Knowledge.deleted_at.is_(None),
                    Knowledge.created_by == user.id,
                )
            )
            .order_by(desc(Knowledge.created_at))
            .limit(8)
        )
        result = await db.execute(stmt)
        for f in result.scalars().all():
            dashboard.my_uploads.append(
                MobileDashboardMyUpload(
                    id=f.id,
                    title=f.title or f.file_name or f"文件{f.id}",
                    file_name=f.file_name,
                    file_type=f.file_type,
                    file_size=f.file_size,
                    visibility=f.visibility,
                    folder_id=f.folder_id,
                    created_at=f.created_at.isoformat() if f.created_at else None,
                )
            )
    except Exception as e:
        logger.warning(f"[MobileDashboard] my_uploads failed: {e}")

    # ---- 5. notification_unread_count ----
    try:
        from app.services.notification_service import notification_service
        dashboard.notification_unread_count = await notification_service.count_unread(
            db, user_id=user.id
        )
    except Exception as e:
        logger.warning(f"[MobileDashboard] notification_unread_count failed: {e}")

    return dashboard


# ============================================================
# 2. GET /api/v1/mobile/feed
# ============================================================
@router.get("/feed", response_model=MobileFeedResponse)
async def get_mobile_feed(
    type: str = Query(..., description="feed 类型: activity | recent | starred"),
    cursor: Optional[int] = Query(None, description="上次最后一条 id (last_id cursor)"),
    limit: int = Query(10, ge=1, le=50, description="每页条数"),
    user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """v2 PR8: 滚动 feed (cursor pagination, 移动端友好)

    Args:
      type: activity (ActivityEvent timeline) | recent (我最近上传) | starred (收藏)
      cursor: 上次最后一条 id, NULL = 第一页 (从最新开始)
      limit: 每页条数 (1-50, 默认 10)

    Returns:
      items: 按 timestamp desc 排序
      next_cursor: 下一批的 cursor (NULL = 到底)
      has_more: bool (True if 还有下一页)
    """
    # type 校验 (422 fail fast)
    if type not in ("activity", "recent", "starred"):
        raise ValidationException(
            message=f"type 必须是 activity / recent / starred, 收到: {type!r}",
            field="type",
        )

    feed = MobileFeedResponse(items=[], next_cursor=None, has_more=False)

    if type == "activity":
        await _feed_activity(db, user, cursor, limit, feed)
    elif type == "recent":
        await _feed_recent(db, user, cursor, limit, feed)
    elif type == "starred":
        await _feed_starred(db, user, cursor, limit, feed)

    return feed


async def _feed_activity(
    db: AsyncSession,
    user: Member,
    cursor: Optional[int],
    limit: int,
    feed: MobileFeedResponse,
):
    """activity feed: ActivityEvent 按 id desc (cursor pagination)"""
    stmt = (
        select(ActivityEvent, Member.name)
        .outerjoin(Member, Member.id == ActivityEvent.actor_id)
        .order_by(desc(ActivityEvent.id))
        .limit(limit + 1)  # 多取 1 条判断 has_more
    )
    if cursor is not None:
        stmt = stmt.where(ActivityEvent.id < cursor)

    try:
        result = await db.execute(stmt)
        rows = result.all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        for ev, actor_name in rows:
            payload = {
                "id": ev.id,
                "actor_id": ev.actor_id,
                "actor_name": actor_name,
                "action": ev.action,
                "target_type": ev.target_type,
                "target_id": ev.target_id,
                "target_name": ev.target_name,
            }
            feed.items.append(
                MobileFeedItem(
                    type="activity",
                    timestamp=ev.created_at.isoformat() if ev.created_at else "",
                    payload=payload,
                )
            )
        if has_more and rows:
            feed.next_cursor = str(rows[-1][0].id)
        feed.has_more = has_more
    except Exception as e:
        logger.warning(f"[MobileFeed] activity failed: {e}")


async def _feed_recent(
    db: AsyncSession,
    user: Member,
    cursor: Optional[int],
    limit: int,
    feed: MobileFeedResponse,
):
    """recent feed: 我最近上传 (按 id desc, cursor=last id)"""
    stmt = (
        select(Knowledge)
        .where(
            and_(
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.created_by == user.id,
            )
        )
        .order_by(desc(Knowledge.id))
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(Knowledge.id < cursor)

    try:
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        for f in rows:
            payload = {
                "id": f.id,
                "title": f.title or f.file_name or f"文件{f.id}",
                "file_name": f.file_name,
                "file_type": f.file_type,
                "file_size": f.file_size,
                "visibility": f.visibility,
                "folder_id": f.folder_id,
                "updated_at": f.updated_at.isoformat() if f.updated_at else None,
            }
            feed.items.append(
                MobileFeedItem(
                    type="recent",
                    timestamp=f.created_at.isoformat() if f.created_at else "",
                    payload=payload,
                )
            )
        if has_more and rows:
            feed.next_cursor = str(rows[-1].id)
        feed.has_more = has_more
    except Exception as e:
        logger.warning(f"[MobileFeed] recent failed: {e}")


async def _feed_starred(
    db: AsyncSession,
    user: Member,
    cursor: Optional[int],
    limit: int,
    feed: MobileFeedResponse,
):
    """starred feed: 用户收藏 (按 id desc 兜底, starred_at 可能 NULL)"""
    visibility_see = or_(
        Knowledge.created_by == user.id,
        Knowledge.visibility != "private",
    )
    stmt = (
        select(Knowledge)
        .where(
            and_(
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.is_starred.is_(True),
                visibility_see,
            )
        )
        .order_by(desc(Knowledge.id))  # 用 id 兜底保证 cursor pagination 稳定
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(Knowledge.id < cursor)

    try:
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        for f in rows:
            payload = {
                "id": f.id,
                "title": f.title or f.file_name or f"文件{f.id}",
                "file_name": f.file_name,
                "file_type": f.file_type,
                "file_size": f.file_size,
                "visibility": f.visibility,
                "folder_id": f.folder_id,
                "starred_at": f.starred_at.isoformat() if f.starred_at else None,
            }
            feed.items.append(
                MobileFeedItem(
                    type="starred",
                    timestamp=f.starred_at.isoformat() if f.starred_at else (
                        f.updated_at.isoformat() if f.updated_at else ""
                    ),
                    payload=payload,
                )
            )
        if has_more and rows:
            feed.next_cursor = str(rows[-1].id)
        feed.has_more = has_more
    except Exception as e:
        logger.warning(f"[MobileFeed] starred failed: {e}")


# ============================================================
# 3. POST /api/v1/mobile/album-auto-backup
# ============================================================
@router.post("/album-auto-backup", response_model=AlbumAutoBackupResponse)
async def post_album_auto_backup(
    body: AlbumAutoBackupRequest,
    user: Member = Depends(get_current_user),
):
    """v2 PR8: 相册自动备份开关 (idempotent)

    POST 设配置 + 立即返当前配置. 前端拿到 result 后无需再发 GET (idempotent).

    Body: AlbumAutoBackupRequest (enabled / folder_id / wifi_only)

    Returns: AlbumAutoBackupResponse (当前配置 + updated_at + message)
    """
    config = {
        "enabled": body.enabled,
        "folder_id": body.folder_id,
        "wifi_only": body.wifi_only,
    }
    await _set_backup_config(user.id, config)

    return AlbumAutoBackupResponse(
        enabled=config["enabled"],
        folder_id=config["folder_id"],
        wifi_only=config["wifi_only"],
        updated_at=datetime.now(timezone.utc).isoformat(),
        message="配置已保存" if body.enabled else "配置已禁用",
    )


@router.get("/album-auto-backup", response_model=AlbumAutoBackupResponse)
async def get_album_auto_backup(
    user: Member = Depends(get_current_user),
):
    """v2 PR8: 读相册自动备份配置 (Redis)"""
    config = await _get_backup_config(user.id)
    return AlbumAutoBackupResponse(
        enabled=config["enabled"],
        folder_id=config.get("folder_id"),
        wifi_only=config.get("wifi_only", True),
        updated_at="",  # 不在 Redis 里 (PUT-only)
        message="当前配置",
    )