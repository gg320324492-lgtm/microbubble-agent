"""Drive v2 PR9 — 事件 Publisher (WS 推送桥接层)

W68 第 1 批 a-1 (commit f5a4b2586) 已建 notification_service 基础设施:
- NotificationPriority (HIGH/MEDIUM/LOW)
- push_with_priority(user_id, payload, priority)
- enqueue_offline (Redis list, FIFO, OFFLINE_QUEUE_MAX_SIZE=100)
- drain_offline_queue (reconnect 时拉)
- notification_manager.push_to_user (WS 推送)

W68 第 3 批 F-1/F-2 (commits 0bfe36751 + 04e06f6fd) 已建 DriveComment + DriveFileVersion
数据层 + service + API, 但 service 写操作未触发 WS 推送 (F-1 报告明示 '留给 PR10 集成').
本模块承担 PR10 角色: 把 DriveComment + DriveFileVersion 6 个写操作的"事件"包装为
WS payload, 走 push_with_priority 推送.

设计要点:
- 6 个 publish_* 函数, 每个对应 service 层一个写操作, payload schema 固定
- 全部走 push_with_priority (在线 WS push, 离线入 Redis queue, reconnect drain)
- 失败 best-effort: try/except + logger.error(exc_info=True), 不抛出 (caller 不感知)
- 复用 caller 的 db session (不再开新 session — DRY 原则, 与 a-1 一致)
- 收件人解析 = 同步 DB lookup (走 caller 的 db session, 单 SQL, 性能可忽略)
- mention 提醒单独走 notification_service.create_bulk_mentions (PR6 已建, 本模块不重做)
- delete 场景特殊处理: comment ORM 已被删, 仅传 ID 即可

调用方 (service 层集成):
- drive_comment_service.create_comment() → publish_comment_created(db, comment)
- drive_comment_service.update_comment() → publish_comment_updated(db, comment, actor_id)
- drive_comment_service.delete_comment() → publish_comment_deleted(db, comment_id, file_id, folder_id, author_id, actor_id)
- drive_comment_service.resolve_comment() → publish_comment_resolved(db, comment_id, file_id, folder_id, resolved_by)
- drive_version_service.create_version() → publish_version_uploaded(db, version, file_name)
- drive_version_service.rollback() → publish_version_rollback(db, version, file_name, target_v)

约束:
- 不阻塞 service 主流程: publish_* 内部 try/except 包住 push_with_priority
- 不重复推送: caller 负责 (避免在 create + update 各发一次)
- 不持久化推送记录 (a-1 push_with_priority 已含 offline queue + FileMention 兜底)
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_comment import DriveComment
from app.models.drive_file_version import DriveFileVersion
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.notification_service import (
    NotificationPriority,
    push_with_priority,
)

logger = logging.getLogger("microbubble.drive_event_publisher")


# ==========================================================================
# Comment events (4 个)
# ==========================================================================


async def publish_comment_created(
    db: AsyncSession,
    comment: DriveComment,
    *,
    actor_id: Optional[int] = None,
) -> int:
    """新评论推送 — 通知 file/folder owner

    Args:
        db: caller 的 AsyncSession (复用, 不新开)
        comment: DriveComment ORM 实例 (含 file_id 或 folder_id, author_id)
        actor_id: 操作者 (默认 comment.author_id)

    收件人:
    - file_id 不为空 → Knowledge.uploader_id (file owner)
    - folder_id 不为空 → Folder.owner_id (folder owner)
    - 注意: mentions 由 PR6 notification_service.create_bulk_mentions 单独推,
      本推送是补的"协作事件"通知 (priority=MEDIUM)

    priority=MEDIUM (普通协作事件, 非 @ 提醒)
    """
    target_user_id = await _resolve_comment_target_owner(db, comment)
    if target_user_id is None or target_user_id == (actor_id or comment.author_id):
        # file/folder 不存在 或 自推 → 跳过
        return 0
    payload = _build_comment_payload("comment_created", comment, actor_id=actor_id or comment.author_id)
    return await _safe_push(target_user_id, payload, priority=NotificationPriority.MEDIUM)


async def publish_comment_updated(
    db: AsyncSession,
    comment: DriveComment,
    *,
    actor_id: int,
) -> int:
    """评论编辑推送 — author 修改自己的评论 → 通知 file/folder owner

    priority=MEDIUM
    """
    target_user_id = await _resolve_comment_target_owner(db, comment)
    if target_user_id is None or target_user_id == actor_id:
        return 0
    payload = _build_comment_payload("comment_updated", comment, actor_id=actor_id)
    return await _safe_push(target_user_id, payload, priority=NotificationPriority.MEDIUM)


async def publish_comment_deleted(
    db: AsyncSession,
    *,
    comment_id: int,
    file_id: Optional[int],
    folder_id: Optional[int],
    author_id: int,
    actor_id: int,
) -> int:
    """评论删除推送 — comment 已 hard delete, 仅传 ID → 通知 file/folder owner

    priority=LOW (删除是低优先级, 离线入队即可)
    """
    target_user_id = await _resolve_target_owner(db, file_id=file_id, folder_id=folder_id)
    if target_user_id is None or target_user_id == actor_id:
        return 0
    payload = {
        "type": "comment_deleted",
        "comment_id": comment_id,
        "file_id": file_id,
        "folder_id": folder_id,
        "author_id": author_id,
        "actor_id": actor_id,
        "ts": _now_iso(),
    }
    return await _safe_push(target_user_id, payload, priority=NotificationPriority.LOW)


async def publish_comment_resolved(
    db: AsyncSession,
    *,
    comment_id: int,
    file_id: Optional[int],
    folder_id: Optional[int],
    resolved_by: int,
    author_id: Optional[int] = None,
) -> int:
    """评论标记 resolved 推送 — 通知 comment.author

    author_id 可选传入 (避免 1 次 SQL lookup, 由 caller 在 resolve_comment 路径
    里传过来 — comment ORM 已知 author_id). 缺省时查表.

    priority=MEDIUM
    """
    if author_id is None:
        author_id = await _resolve_comment_author(db, comment_id)
    if author_id is None or author_id == resolved_by:
        # 作者自己标记自己 — 不通知 (避免自推)
        return 0
    payload = {
        "type": "comment_resolved",
        "comment_id": comment_id,
        "file_id": file_id,
        "folder_id": folder_id,
        "resolved_by": resolved_by,
        "ts": _now_iso(),
    }
    return await _safe_push(author_id, payload, priority=NotificationPriority.MEDIUM)


# ==========================================================================
# Version events (2 个)
# ==========================================================================


async def publish_version_uploaded(
    db: AsyncSession,
    version: DriveFileVersion,
    *,
    file_name: Optional[str] = None,
    actor_id: Optional[int] = None,
) -> int:
    """新版本上传推送 — 通知 file owner (uploader)

    priority=MEDIUM
    """
    actor = actor_id or version.uploader_id
    target_user_id = await _resolve_file_owner(db, version.file_id)
    if target_user_id is None or target_user_id == actor:
        # file 不存在 或 自推
        return 0
    payload = {
        "type": "version_uploaded",
        "version_id": version.id,
        "file_id": version.file_id,
        "version_number": version.version_number,
        "file_name": file_name,
        "uploader_id": actor,
        "size": version.size,
        "comment": version.comment,
        "ts": _now_iso(),
    }
    return await _safe_push(target_user_id, payload, priority=NotificationPriority.MEDIUM)


async def publish_version_rollback(
    db: AsyncSession,
    version: DriveFileVersion,
    *,
    file_name: Optional[str] = None,
    target_version_number: Optional[int] = None,
    actor_id: Optional[int] = None,
) -> int:
    """版本回滚推送 — 通知 file owner

    Args:
        version: 新创建的 DriveFileVersion (rollback 创建的新行, version_number=N+1)
        target_version_number: 回滚到的目标版本号 (e.g. target_v=3 → new_v=4)

    priority=MEDIUM
    """
    actor = actor_id or version.uploader_id
    target_user_id = await _resolve_file_owner(db, version.file_id)
    if target_user_id is None or target_user_id == actor:
        return 0
    payload = {
        "type": "version_rollback",
        "version_id": version.id,
        "file_id": version.file_id,
        "version_number": version.version_number,
        "target_version_number": target_version_number,
        "file_name": file_name,
        "uploader_id": actor,
        "ts": _now_iso(),
    }
    return await _safe_push(target_user_id, payload, priority=NotificationPriority.MEDIUM)


# ==========================================================================
# Internal helpers (复用 caller db session)
# ==========================================================================


async def _resolve_comment_target_owner(
    db: AsyncSession, comment: DriveComment
) -> Optional[int]:
    """comment → file/folder owner (单 SQL 复用 caller db session)"""
    return await _resolve_target_owner(
        db, file_id=comment.file_id, folder_id=comment.folder_id
    )


async def _resolve_target_owner(
    db: AsyncSession,
    *,
    file_id: Optional[int],
    folder_id: Optional[int],
) -> Optional[int]:
    """file_id / folder_id 二选一 → owner user_id"""
    if file_id is not None:
        return await _resolve_file_owner(db, file_id)
    if folder_id is not None:
        return await _resolve_folder_owner(db, folder_id)
    return None


async def _resolve_file_owner(db: AsyncSession, file_id: int) -> Optional[int]:
    """Knowledge.created_by — file owner (PR9 drive 文件的 'uploader' 字段就是 created_by)"""
    if file_id is None:
        return None
    try:
        row = (await db.execute(
            select(Knowledge.created_by).where(Knowledge.id == file_id)
        )).first()
        return row[0] if row else None
    except Exception as e:
        logger.warning(f"[DriveEventPublisher] _resolve_file_owner({file_id}) 失败: {e!r}")
        return None


async def _resolve_folder_owner(db: AsyncSession, folder_id: int) -> Optional[int]:
    """Folder.owner_id"""
    if folder_id is None:
        return None
    try:
        row = (await db.execute(
            select(Folder.owner_id).where(Folder.id == folder_id)
        )).first()
        return row[0] if row else None
    except Exception as e:
        logger.warning(f"[DriveEventPublisher] _resolve_folder_owner({folder_id}) 失败: {e!r}")
        return None


async def _resolve_comment_author(
    db: AsyncSession, comment_id: int
) -> Optional[int]:
    """DriveComment.author_id — 1 SQL lookup"""
    try:
        row = (await db.execute(
            select(DriveComment.author_id).where(DriveComment.id == comment_id)
        )).first()
        return row[0] if row else None
    except Exception as e:
        logger.warning(f"[DriveEventPublisher] _resolve_comment_author({comment_id}) 失败: {e!r}")
        return None


def _build_comment_payload(
    event_type: str, comment: DriveComment, *, actor_id: int
) -> dict:
    """comment → WS payload (含 author + target info)"""
    return {
        "type": event_type,
        "comment_id": comment.id,
        "file_id": comment.file_id,
        "folder_id": comment.folder_id,
        "parent_id": comment.parent_id,
        "author_id": comment.author_id,
        "actor_id": actor_id,
        "is_resolved": comment.resolved_at is not None,
        "mentions": comment.mentions or [],
        "ts": _now_iso(),
    }


async def _safe_push(
    user_id: int,
    payload: dict,
    *,
    priority: Optional[NotificationPriority] = None,
) -> int:
    """async 包装 push_with_priority — 失败 best-effort, 不抛错

    Returns:
        1 = WS 推送成功, 0 = 离线入队, -1 = 失败/跳过
    """
    if user_id is None:
        return -1
    try:
        return await push_with_priority(user_id, payload, priority=priority)
    except Exception as e:
        logger.error(
            f"[DriveEventPublisher] push_with_priority 失败 user_id={user_id} "
            f"type={payload.get('type')} error={e!r}",
            exc_info=True,
        )
        return -1


def _now_iso() -> str:
    """ISO 8601 UTC timestamp (string) — push payload 的 ts 字段"""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "publish_comment_created",
    "publish_comment_updated",
    "publish_comment_deleted",
    "publish_comment_resolved",
    "publish_version_uploaded",
    "publish_version_rollback",
]