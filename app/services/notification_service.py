"""notification_service — v2 PR6 @ 提醒通知服务

核心职责:
1. create_mention(): 创建 file_mention 记录 (单 user 推送)
2. create_bulk_mentions(): 批量创建 (评论里 @ N 人)
3. list_unread / list_all: 拉取通知 (按 mentioned_user_id 隔离)
4. mark_read / mark_all_read: 标记已读
5. count_unread: 红点数字
6. parse_mentions_from_text(): 解析 @username 字符串为 user_id 列表
7. notify_websocket(): 通过 NotificationManager 推 WS 给在线用户

设计要点:
- 每个 file_mention 是 (mentioned_user, file, actor, context) 4 元组
- mentioned_user 不在线也存表, WS 连接时拉 unread 补推送
- is_read 字段: False=未读, True=已读
- read_at: 已读时间戳 (前端 NotificationBell 时间显示)
- v2 PR6-P8: title/body 实时拼 + 存 DB 双轨 (推送服务的 metadata 增强)
- W68 PR8d: 通知优先级 (HIGH/MEDIUM/LOW) + 离线消息队列 (Redis list) +
  批量通知合并 (combine 多个小事件为 batch event)

不与现有 Notification 系统冲突:
- 现有 app/api/v1/notification.py (chat reminder 类) 用的是 Notification 模型 + reminder_service
- 本服务**只**管 file_mentions (drive 网盘协作提醒),不混合
"""
import json
import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.knowledge import FileMention, ActivityEvent, Knowledge, FileComment
from app.models.member import Member
from app.services.cleanup_backup import execute_backup_then_delete

logger = logging.getLogger(__name__)

# v2 PR6-P7: 5s 通知去重窗口 (同 receiver + file + context)
NOTIFICATION_DEDUP_WINDOW_SECONDS = 5

# W68 PR8d: 通知优先级
class NotificationPriority(str, Enum):
    """v2 PR8d 通知优先级 3 档
    - HIGH: 立即推送 (mention / @ 提醒) — 不允许合并
    - MEDIUM: 普通活动 (文件上传 / 评论) — 可批量合并
    - LOW: 系统提示 (清理 / 巡检) — 仅离线队列
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

# W68 PR8d: 离线队列配置
OFFLINE_QUEUE_KEY = "ws_notify:offline_queue"  # Redis list per user: {user_id}:{priority}
OFFLINE_QUEUE_MAX_SIZE = 100  # 每用户每档最多 100 条 (FIFO trim)
OFFLINE_QUEUE_TTL_SECONDS = 7 * 24 * 3600  # 7 天自动过期

# W68 PR8d: 批量通知配置
BATCH_MERGE_WINDOW_SECONDS = 3  # 3s 内的 MEDIUM 通知合并为 batch event
BATCH_MERGE_MAX_ITEMS = 10  # 单 batch 最多 10 条, 超过即 flush

# v2 PR6-P8: rich body 长度限制 (前端卡片 2 行省略号 ≈ 60 中文字)
BODY_PREVIEW_MAX_CHARS = 60

# v2 PR6-P8: file_type 简化分类 (MIME 或扩展名 → 前端图标友好字符串)
# 前端 NotificationBell 卡片按 file_type 选 icon/color
_FILE_TYPE_MAP = {
    # PDF
    "application/pdf": "pdf",
    ".pdf": "pdf",
    # Word
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
    ".doc": "doc", ".docx": "doc",
    # Excel
    "application/vnd.ms-excel": "excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    ".xls": "excel", ".xlsx": "excel",
    # PPT
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "ppt",
    ".ppt": "ppt", ".pptx": "ppt",
    # Image
    "image/": "image",  # image/png, image/jpeg, image/gif, image/webp 全归 image
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
    ".webp": "image", ".bmp": "image", ".svg": "image", ".heic": "image",
    # Audio
    "audio/": "audio",
    ".mp3": "audio", ".wav": "audio", ".m4a": "audio", ".webm": "audio",
    # Video
    "video/": "video",
    ".mp4": "video", ".mov": "video", ".avi": "video", ".mkv": "video",
    # Text
    "text/plain": "text", ".txt": "text", ".md": "text",
    # Archive
    ".zip": "archive", ".rar": "archive", ".7z": "archive", ".tar": "archive",
}


def _simplify_file_type(mime: Optional[str], file_name: Optional[str]) -> str:
    """v2 PR6-P8: MIME 或 文件名 → 简化分类 (pdf/doc/excel/ppt/image/audio/video/text/archive/other)

    优先用 MIME (精确), 退化用扩展名 (兜底), 最后 'other'.
    """
    if mime:
        # image/audio/video 是 MIME 前缀, 优先匹配
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
        if mime in _FILE_TYPE_MAP:
            return _FILE_TYPE_MAP[mime]
    if file_name:
        name_lower = file_name.lower()
        for ext, t in _FILE_TYPE_MAP.items():
            if ext.startswith(".") and name_lower.endswith(ext):
                return t
    return "other"


# @ 提及正则: @张三 / @WangTianZhi / @nuyoah. (中文 2-4 字 + 英文 + 数字 + ._-)
# v2 PR6-P4 修复: 原 regex @([一-龥A-Za-z0-9_]{1,32}) 不能匹配 wechat_id 含 '.'
# (nuyoah. / WuWei. / HALO. 等真实用户名), 永久被忽略
# 扩到允许 '.', '-', '_' + max 32 char, 与前端 regex 完全镜像 (CLAUDE.md 铁律)
_MENTION_PATTERN = re.compile(r"@([一-龥A-Za-z0-9_.\-]{1,32})")


class NotificationService:
    """v2 PR6: file_mention CRUD"""

    @staticmethod
    async def _lookup_actor_name(
        db: AsyncSession,
        actor_id: Optional[int],
    ) -> Optional[str]:
        """v2 PR6-P8: 查 actor username/name (用于 title 拼 '杜同贺 在 ...')

        Returns:
            username (lowercase, like 'du_tonghe') 或 name (中文, like '杜同贺')
            优先 username (短, 推送 token 省) → fallback name → None = '系统'
        """
        if not actor_id:
            return None
        m = (await db.execute(
            select(Member.username, Member.name).where(Member.id == actor_id)
        )).first()
        if m is None:
            return None
        return m.username or m.name

    @staticmethod
    async def _lookup_rich_metadata(
        db: AsyncSession,
        *,
        file_id: int,
        context: Optional[str],
    ) -> dict:
        """v2 PR6-P8: 拉 file_name + file_type + comment_preview 用于 title/body 拼

        Returns:
            {
                "file_name": "实验数据.xlsx" or None,
                "file_type": "pdf" or "docx" or "image" or ... or None,  # 简化分类
                "file_type_full": "application/pdf" or None,
                "comment_preview": "这个实验数据得重新测一下..." or None,
                "comment_id": int or None,
            }
        """
        out: dict = {
            "file_name": None,
            "file_type": None,
            "file_type_full": None,
            "comment_preview": None,
            "comment_id": None,
        }
        # 1) file 元数据 (Knowledge)
        k = (await db.execute(
            select(Knowledge.file_name, Knowledge.file_type).where(Knowledge.id == file_id)
        )).first()
        if k is not None:
            out["file_name"] = k.file_name
            out["file_type_full"] = k.file_type
            # 简化分类: pdf / image / doc / excel / ppt / other (前端图标 + 颜色)
            out["file_type"] = _simplify_file_type(k.file_type, k.file_name)

        # 2) comment_preview (按 context 类型)
        ctx = context or "mention"
        if ctx.startswith("reply:"):
            try:
                reply_id = int(ctx.split(":", 1)[1])
                c = (await db.execute(
                    select(FileComment.id, FileComment.content, FileComment.file_id)
                    .where(FileComment.id == reply_id)
                )).first()
                if c is not None and c.file_id == file_id:
                    out["comment_id"] = c.id
                    out["comment_preview"] = (c.content or "")[:BODY_PREVIEW_MAX_CHARS]
            except (ValueError, IndexError):
                pass
        elif ctx == "comment":
            # 最新一条 comment (created_at 倒序 limit 1)
            c = (await db.execute(
                select(FileComment.id, FileComment.content)
                .where(FileComment.file_id == file_id)
                .order_by(FileComment.created_at.desc())
                .limit(1)
            )).first()
            if c is not None:
                out["comment_id"] = c.id
                out["comment_preview"] = (c.content or "")[:BODY_PREVIEW_MAX_CHARS]

        return out

    @staticmethod
    def _build_title_body(
        *,
        actor_name: Optional[str],
        meta: dict,
        context: Optional[str],
        repeated_count: int = 1,
    ) -> Tuple[str, str]:
        """v2 PR6-P8: 按 context 类型实时拼 title (主) + body (描述)

        title 模板:
          - 'comment':  '{actor} 在 {file_name} 提到了你'
          - 'reply:N':  '{actor} 回复了你的评论'
          - 'star':     '{actor} 收藏了你的文件'
          - 'share':    '{actor} 分享了 {file_name} 给你'
          - 'mention' (其他): '{actor} 在 {file_name} 提醒了你'

        body 模板 (rich preview):
          - comment:  '{preview} · {file_type} · {time_label}'
            preview 为空时降级为 '{file_type} · {time_label}'
          - reply:N:  '{preview} · 回复于 {time_label}'
          - star/share: '{file_name} · {file_type} · {time_label}'

        Args:
            actor_name: 触发者 username/name (NULL = '系统')
            meta: _lookup_rich_metadata 返的 dict (含 file_name/file_type/comment_preview)
            context: 触发场景
            repeated_count: dedup 合并次数 (>1 时 title 加 ' (x{N})')

        Returns:
            (title, body) — 都已 strip, 不超过字段长度上限
        """
        ctx = context or "mention"
        actor = actor_name or "系统"
        file_name = meta.get("file_name") or f"文件 #{meta.get('file_id', '?')}"
        file_type = meta.get("file_type") or "file"
        preview = meta.get("comment_preview") or ""

        # 1) title 拼 (主标题, 推送服务用)
        if ctx.startswith("reply:"):
            title = f"{actor} 回复了你的评论"
        elif ctx == "star":
            title = f"{actor} 收藏了你的文件"
        elif ctx == "share":
            title = f"{actor} 分享了 {file_name} 给你"
        elif ctx == "comment":
            title = f"{actor} 在 {file_name} 提到了你"
        else:  # 'mention' / 其他
            title = f"{actor} 在 {file_name} 提醒了你"

        if repeated_count > 1:
            title = f"{title} (x{repeated_count})"

        # 2) body 拼 (描述, rich preview)
        if ctx == "comment" and preview:
            body = f"{preview} · {file_type}"
        elif ctx.startswith("reply:") and preview:
            body = f"{preview} · 回复"
        elif ctx in ("star", "share"):
            body = f"{file_name} · {file_type}"
        elif preview:
            body = f"{preview} · {file_type}"
        else:
            body = f"{file_name} · {file_type}"

        # 截断防御 (title 200 char, body 无强限)
        title = title[:200]
        return title.strip(), body.strip()

    @staticmethod
    async def create_mention(
        db: AsyncSession,
        *,
        file_id: int,
        mentioned_user_id: int,
        mentioned_by: Optional[int] = None,
        context: Optional[str] = None,
    ) -> Tuple[FileMention, bool]:
        """创建单条 mention (立即 commit)

        v2 PR6-P7: 5s dedup (receiver, file_id, context) — 命中时合并到现有 mention,
        repeated_count +1, 不创建新 row. 推 WS 时带 merged=True 让前端识别.

        v2 PR6-P8: 实时拼 title/body + 存 DB (推送服务的 metadata 增强),
        WS payload 同步带 title/body/file_type 让前端不查 SQL 即可渲染.

        Returns:
            (FileMention, merged: bool) — merged=True 表示是 dedup 命中
        """
        # PR6-P7 dedup: 检查 5s 内 (mentioned_user_id, file_id, context) 是否有 mention
        merged = False
        ctx = context or "mention"
        threshold = datetime.utcnow() - timedelta(seconds=NOTIFICATION_DEDUP_WINDOW_SECONDS)
        # P1-9 fix (2026-07-08): 去掉 is_read=False 过滤.
        # 之前 bug: 过滤 is_read=False 导致 markAllRead 后的 row 不参与 dedup,
        # 每次 mention 都新建 row, 不合并, 用户视觉上 unreadCount 一直涨但
        # merged=true 设计完全失效. 正确语义: 5s 内 (file_id, user_id, context)
        # 合并, 不论 is_read 状态 (用户已 markRead 后, 新 mention 仍合并到同一 row
        # + 重置 is_read=False 让用户重新看到合并通知).
        existing_recent = (await db.execute(
            select(FileMention)
            .where(
                and_(
                    FileMention.mentioned_user_id == mentioned_user_id,
                    FileMention.file_id == file_id,
                    FileMention.context == ctx,
                    FileMention.created_at >= threshold,
                )
            )
            .order_by(FileMention.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        # v2 PR6-P8: 查 actor_name (Member.username) + file 元数据 + comment preview
        meta = await NotificationService._lookup_rich_metadata(
            db, file_id=file_id, context=ctx,
        )
        actor_name = await NotificationService._lookup_actor_name(db, mentioned_by)

        if existing_recent is not None:
            # dedup 命中: 合并到第一条, repeated_count +1, 刷新 created_at 让它"看起来新鲜"
            existing_recent.repeated_count = (existing_recent.repeated_count or 1) + 1
            existing_recent.created_at = datetime.utcnow()
            existing_recent.mentioned_by = mentioned_by  # 最新触发人覆盖
            # P1-9 fix (2026-07-08): dedup 命中时重置 is_read=False + read_at=None.
            # 之前 bug: 用户 markAllRead 后, dedup 命中不重置 is_read → 红点不再更新
            # (count_unread WHERE is_read=False 仍 = 0), 用户漏看后续 mention 合并.
            # 设计意图: 5s 内合并显示 1 条 (repeated_count=N), 用户标已读后,
            # 第 N+1 次 mention 应该让用户重新看到 → is_read=False.
            existing_recent.is_read = False
            existing_recent.read_at = None
            # P2-2 fix (2026-07-08): dedup 命中时**保留首次 mention 的 title/body**,
            # 不重拼 preview. 之前重拼总是用最新 mention 的 comment_preview,
            # 重复 5 次后用户只看到第 5 条评论内容, 前 4 条永远看不到.
            # 修复: 首次 mention 的 title/body 已包含原始评论内容 (PR6-P8),
            # dedup 后续只更新 mentioned_by (最后一次是谁发的) + repeated_count + created_at.
            # 前端显示 "A 在 实验.xlsx 提到了你" (首次) + "(共 N 次)" 提示合并数.
            existing_recent.mentioned_by = mentioned_by
            existing_recent.repeated_count = (existing_recent.repeated_count or 1) + 1
            existing_recent.created_at = datetime.utcnow()
            # title/body 保持原值 (首次 mention 内容, 含原始 preview)
            # 只在 title 末尾加重复数提示 (PR6-P7 已有 line 247-251 处理 repeated_count > 1)
            await db.commit()
            await db.refresh(existing_recent)
            merged = True
            logger.info(
                f"[Notify] 5s dedup merge file_id={file_id} → user={mentioned_user_id} "
                f"id={existing_recent.id} repeated_count={existing_recent.repeated_count} context={ctx}"
            )
            m = existing_recent
        else:
            title, body = NotificationService._build_title_body(
                actor_name=actor_name, meta=meta, context=ctx, repeated_count=1,
            )
            m = FileMention(
                file_id=file_id,
                mentioned_user_id=mentioned_user_id,
                mentioned_by=mentioned_by,
                context=ctx,
                is_read=False,
                repeated_count=1,
                # v2 PR6-P8: rich metadata 存 DB (推送服务增强 + 列表显示)
                title=title,
                body=body,
                file_type=meta.get("file_type"),
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)
            logger.info(
                f"[Notify] mention file_id={file_id} → user={mentioned_user_id} "
                f"by={mentioned_by} context={ctx} title='{title}'"
            )

        # 推送 WS (best-effort), merged=True 时前端红点不增 + 弹 toast
        try:
            from app.api.v1.ws_notifications import notification_manager
            await notification_manager.push_to_user(mentioned_user_id, {
                "type": "mention",
                "id": m.id,
                "file_id": file_id,
                "mentioned_by": mentioned_by,
                "context": ctx,
                "repeated_count": m.repeated_count,
                "merged": merged,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                # v2 PR6-P8: rich metadata (前端可不查 SQL 渲染)
                "title": m.title,
                "body": m.body,
                "file_name": meta.get("file_name"),
                "file_type": meta.get("file_type"),
            })
        except Exception as e:
            logger.debug(f"[Notify] WS push 失败 (非阻塞): {e}")

        return m, merged

    @staticmethod
    async def get_recent_dedup_count(
        db: AsyncSession,
        *,
        mention_id: int,
    ) -> int:
        """PR6-P7: 拉单条 mention 的 repeated_count (前端 toast 显示 '已合并 X 条')"""
        m = (await db.execute(
            select(FileMention.repeated_count).where(FileMention.id == mention_id)
        )).scalar_one_or_none()
        return m or 1

    @staticmethod
    async def create_bulk_mentions(
        db: AsyncSession,
        *,
        file_id: int,
        mentioned_user_ids: List[int],
        mentioned_by: Optional[int] = None,
        context: str = "comment",
    ) -> List[FileMention]:
        """批量创建 mention (评论里 @ N 人)

        同一 (file_id, mentioned_user_id) 24h 内去重: 已存在未读/已读都跳过 (避免轰炸)

        v2 PR6-P7: 在 24h dedup 之前加 5s dedup — 同一 receiver 5s 内已有 unread
        mention (context 一致) → 合并到现有 row (repeated_count+1), 不创建新 row.
        """
        if not mentioned_user_ids:
            return []

        # 去重 (同一用户)
        unique_ids = list(set(mentioned_user_ids))

        # v2 PR6-P7: 5s dedup window — 命中则合并, 跳过 24h 检查
        recent_threshold = datetime.utcnow() - timedelta(seconds=NOTIFICATION_DEDUP_WINDOW_SECONDS)
        recent_existing = (await db.execute(
            select(FileMention).where(
                and_(
                    FileMention.file_id == file_id,
                    FileMention.mentioned_user_id.in_(unique_ids),
                    FileMention.context == context,
                    FileMention.is_read == False,  # noqa: E712
                    FileMention.created_at >= recent_threshold,
                )
            )
        )).scalars().all()
        recent_set = {m.mentioned_user_id: m for m in recent_existing}

        # v2 PR6-P7: 5s 命中的合并 (repeated_count +1)
        for uid, m in recent_set.items():
            m.repeated_count = (m.repeated_count or 1) + 1
            m.created_at = datetime.utcnow()
            m.mentioned_by = mentioned_by
        if recent_set:
            await db.commit()

        merged_ids = set(recent_set.keys())
        # v2 PR6-P7: 5s 没命中再走 24h dedup (避免轰炸, 与 PR6-P5 兼容)
        long_threshold = datetime.utcnow() - timedelta(hours=24)
        long_existing = (await db.execute(
            select(FileMention.mentioned_user_id).where(
                and_(
                    FileMention.file_id == file_id,
                    FileMention.mentioned_user_id.in_(unique_ids),
                    FileMention.created_at >= long_threshold,
                )
            )
        )).scalars().all()
        long_set = set(long_existing)
        # 排除 5s 已合并的
        new_ids = [uid for uid in unique_ids if uid not in long_set and uid not in merged_ids]

        mentions = list(recent_set.values())  # 5s 合并的也算"创建了" (返给 caller)

        if not new_ids and not recent_set:
            logger.debug(f"[Notify] 24h 内已 @ 过 {list(long_set)} 跳过")
            return []

        # v2 PR6-P8: 查 actor + file 元数据 + comment preview (1 次批量查, 不循环)
        meta = await NotificationService._lookup_rich_metadata(
            db, file_id=file_id, context=context,
        )
        actor_name = await NotificationService._lookup_actor_name(db, mentioned_by)

        if new_ids:
            # v2 PR6-P8: title/body 实时拼 (批量同模板, 每条 row 存一份)
            base_title, base_body = NotificationService._build_title_body(
                actor_name=actor_name, meta=meta, context=context, repeated_count=1,
            )
            new_mentions = [
                FileMention(
                    file_id=file_id,
                    mentioned_user_id=uid,
                    mentioned_by=mentioned_by,
                    context=context,
                    is_read=False,
                    repeated_count=1,
                    # v2 PR6-P8: rich metadata
                    title=base_title,
                    body=base_body,
                    file_type=meta.get("file_type"),
                )
                for uid in new_ids
            ]
            db.add_all(new_mentions)
            await db.commit()
            for m in new_mentions:
                await db.refresh(m)
            mentions.extend(new_mentions)

        # 推送 WS (each)
        try:
            from app.api.v1.ws_notifications import notification_manager
            for m in mentions:
                is_merged = m.mentioned_user_id in merged_ids
                await notification_manager.push_to_user(m.mentioned_user_id, {
                    "type": "mention",
                    "id": m.id,
                    "file_id": file_id,
                    "mentioned_by": mentioned_by,
                    "context": context,
                    "repeated_count": m.repeated_count,
                    "merged": is_merged,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    # v2 PR6-P8: rich metadata
                    "title": m.title,
                    "body": m.body,
                    "file_name": meta.get("file_name"),
                    "file_type": meta.get("file_type"),
                })
        except Exception as e:
            logger.debug(f"[Notify] WS push 失败 (非阻塞): {e}")

        logger.info(f"[Notify] bulk mentions file_id={file_id} → {len(mentions)} users ({len(recent_set)} merged)")
        return mentions

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        *,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[FileMention]:
        """列某用户的 mentions (按时间倒序)

        Args:
            user_id: 受提醒者 id
            unread_only: True 仅未读 (红点), False 全部
            limit: 上限 (避免一次拉太多)
        """
        stmt = select(FileMention).where(FileMention.mentioned_user_id == user_id)
        if unread_only:
            stmt = stmt.where(FileMention.is_read == False)  # noqa: E712
        stmt = stmt.order_by(FileMention.created_at.desc()).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def count_unread(db: AsyncSession, *, user_id: int) -> int:
        """未读通知数 (前端 NotificationBell 红点数字)"""
        stmt = select(func.count()).select_from(FileMention).where(
            and_(
                FileMention.mentioned_user_id == user_id,
                FileMention.is_read == False,  # noqa: E712
            )
        )
        return (await db.execute(stmt)).scalar() or 0

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        *,
        mention_id: int,
        user_id: int,
    ) -> bool:
        """标记单条已读 (越权 = 隐身 404)"""
        stmt = (
            update(FileMention)
            .where(and_(FileMention.id == mention_id, FileMention.mentioned_user_id == user_id))
            .values(is_read=True, read_at=datetime.utcnow())
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def mark_all_read(db: AsyncSession, *, user_id: int) -> int:
        """标记全部已读, 返 count"""
        stmt = (
            update(FileMention)
            .where(and_(FileMention.mentioned_user_id == user_id, FileMention.is_read == False))  # noqa: E712
            .values(is_read=True, read_at=datetime.utcnow())
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    async def cleanup_old_mentions(db: AsyncSession, *, days: int = 30) -> int:
        """Celery beat: 清理已读超过 N 天的 mention

        物理删 (不软删, 减小表体积)
        """
        from datetime import timedelta
        threshold = datetime.utcnow() - timedelta(days=days)
        stmt = (
            FileMention.__table__.delete()
            .where(and_(FileMention.is_read == True, FileMention.read_at < threshold))  # noqa: E712
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0

    @staticmethod
    def parse_mentions_from_text(text: str) -> List[str]:
        """解析 @ 字符串 → username 列表 (不含 @)

        支持中文 (2-4 字) + 英文 (1-16 char) 名字
        不查 DB (caller 负责 username → user_id 转换)
        """
        if not text:
            return []
        return list(set(_MENTION_PATTERN.findall(text)))


# 全局单例 (与 PR5 service 范式一致)
notification_service = NotificationService()


# ============================================================================
# W68 PR8d: 通知优先级 + 离线消息队列 + 批量通知
# ============================================================================

# mention context → priority 映射 (集中管理, 避免散落各分支)
_CONTEXT_PRIORITY_MAP = {
    "comment": NotificationPriority.HIGH,    # @ 提醒必须立刻看到
    "reply": NotificationPriority.HIGH,      # 回复评论同 mention
    "mention": NotificationPriority.HIGH,    # 显式 @ 提及
    "share": NotificationPriority.MEDIUM,    # 分享可稍后看
    "star": NotificationPriority.LOW,        # 收藏低优先级
    "upload": NotificationPriority.MEDIUM,   # 上传通知
    "system": NotificationPriority.LOW,      # 系统级巡检
}


def infer_priority(context: Optional[str]) -> NotificationPriority:
    """W68 PR8d: 根据 context 推断优先级

    Args:
        context: notification context 字符串 (comment/reply/mention/share/star/...)

    Returns:
        NotificationPriority (HIGH/MEDIUM/LOW), 未知 context 默认 MEDIUM
    """
    if not context:
        return NotificationPriority.MEDIUM
    # 'reply:N' 走 prefix 匹配
    key = context.split(":", 1)[0] if ":" in context else context
    return _CONTEXT_PRIORITY_MAP.get(key, NotificationPriority.MEDIUM)


def _offline_queue_key(user_id: int, priority: NotificationPriority) -> str:
    """W68 PR8d: Redis offline queue key"""
    return f"{OFFLINE_QUEUE_KEY}:{user_id}:{priority.value}"


async def enqueue_offline(user_id: int, payload: dict) -> int:
    """W68 PR8d: 离线消息入队 (Redis list, FIFO, 上限 OFFLINE_QUEUE_MAX_SIZE)

    用户离线 (WS 未连接) 时调用, 客户端 reconnect 时 drain。
    payload 会带 priority 字段 (HIGH/MEDIUM/LOW), 用户 reconnect 时按
    priority 拉对应队列。

    Args:
        user_id: 目标 user
        payload: 通知 payload (必须含 'priority' 字段)

    Returns:
        当前队列长度 (>= 0)
    """
    try:
        priority = NotificationPriority(payload.get("priority", "medium"))
    except ValueError:
        priority = NotificationPriority.MEDIUM

    r = await get_redis()
    key = _offline_queue_key(user_id, priority)
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    pipe = r.pipeline()
    pipe.rpush(key, payload_json)
    pipe.ltrim(key, -OFFLINE_QUEUE_MAX_SIZE, -1)  # 只保留最近 N 条
    pipe.expire(key, OFFLINE_QUEUE_TTL_SECONDS)
    results = await pipe.execute()
    queue_len = results[0] if results else 0
    logger.debug(f"[Notify] offline enqueue user_id={user_id} prio={priority.value} len={queue_len}")
    return queue_len


async def drain_offline_queue(
    user_id: int,
    priority_filter: Optional[str] = None,
    max_items: int = 50,
) -> List[dict]:
    """W68 PR8d: 客户端 reconnect 时拉离线消息, 拉完即清

    Args:
        user_id: 目标 user
        priority_filter: 'high' | 'medium' | 'low' | None (None=全部 3 档)
        max_items: 单次最多返回条数 (防 client 重连后一次拉太多)

    Returns:
        通知 payload list (按时间倒序, latest first)
    """
    r = await get_redis()
    keys = []
    if priority_filter:
        try:
            p = NotificationPriority(priority_filter)
            keys = [_offline_queue_key(user_id, p)]
        except ValueError:
            keys = [_offline_queue_key(user_id, p) for p in NotificationPriority]
    else:
        keys = [_offline_queue_key(user_id, p) for p in NotificationPriority]

    # 按 HIGH → MEDIUM → LOW 顺序拉
    out: List[dict] = []
    for k in keys:
        if len(out) >= max_items:
            break
        remaining = max_items - len(out)
        items = await r.lrange(k, -remaining, -1)
        for raw in items:
            try:
                out.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[Notify] offline queue corrupt item in {k}, skip")
        if items:
            await r.ltrim(k, 0, -len(items) - 1)  # 清掉已拉走的 (FIFO)
    return out


async def push_with_priority(
    user_id: int,
    payload: dict,
    *,
    priority: Optional[NotificationPriority] = None,
) -> int:
    """W68 PR8d: 推送通知 (在线走 WS, 离线走队列)

    增强 push_to_user:
    - HIGH: 立即尝试 WS 推送, 失败入 offline HIGH 队列
    - MEDIUM: 尝试 WS 推送, 失败入 offline MEDIUM 队列
    - LOW: 不主动 WS 推送, 直接入 offline LOW 队列 (用户 reconnect 才看)

    Args:
        user_id: 目标 user
        payload: 推送内容
        priority: None=从 payload 读 / 从 context 推断

    Returns:
        1 = WS 推送成功, 0 = 离线入队
    """
    if priority is None:
        priority_str = payload.get("priority")
        if priority_str:
            try:
                priority = NotificationPriority(priority_str)
            except ValueError:
                priority = None
        if priority is None:
            priority = infer_priority(payload.get("context"))
    payload["priority"] = priority.value

    # LOW 不主动推, 只入队
    if priority == NotificationPriority.LOW:
        await enqueue_offline(user_id, payload)
        return 0

    # HIGH/MEDIUM 尝试 WS 推送
    try:
        from app.api.v1.ws_notifications import notification_manager
        delivered = await notification_manager.push_to_user(user_id, payload)
    except Exception as e:
        logger.debug(f"[Notify] push WS 失败, 入离线队列: {e}")
        delivered = 0

    # 在线但 WS 暂时不通 (可能 client 断网) 也入队
    if delivered == 0:
        await enqueue_offline(user_id, payload)
    return delivered


# W68 PR8d: 批量通知合并 (per-user in-memory pending batches)
_batch_pending: dict = {}  # {(user_id, batch_key): (first_ts, items[])}
_batch_lock = None  # asyncio.Lock lazy init on first use


async def push_batch(
    user_id: int,
    payload: dict,
    *,
    batch_key: str,
    window_seconds: int = BATCH_MERGE_WINDOW_SECONDS,
) -> int:
    """W68 PR8d: 批量通知合并 — window_seconds 内的相同 batch_key 合并为单条

    用法示例: 多个文件同时上传 → 合并为 '3 个新文件上传' batch event

    Args:
        user_id: 目标 user
        payload: 单条通知 payload
        batch_key: 合并分组 key (如 'file_upload' / 'comment_added')
        window_seconds: 合并窗口 (秒), 默认 3s

    Returns:
        1 = 立即推送 (首批), 0 = 已合并入 pending
    """
    global _batch_lock
    if _batch_lock is None:
        _batch_lock = __import__("asyncio").Lock()
    async with _batch_lock:
        key = (user_id, batch_key)
        now_ts = __import__("asyncio").get_event_loop().time()
        entry = _batch_pending.get(key)
        if entry is None or (now_ts - entry[0]) > window_seconds:
            # 窗口过期或首批, 启动新 batch
            _batch_pending[key] = (now_ts, [payload])
            # 启动延迟 flush 协程
            __import__("asyncio").create_task(
                _flush_batch(user_id, batch_key, window_seconds)
            )
            # 首批立即推
            return await push_with_priority(user_id, payload)
        # 窗口内: 合并
        items = entry[1]
        items.append(payload)
        if len(items) >= BATCH_MERGE_MAX_ITEMS:
            await _flush_batch_now(user_id, batch_key)
        return 0


async def _flush_batch(user_id: int, batch_key: str, window_seconds: int) -> None:
    """W68 PR8d: 等待 window 后 flush batch (单次)"""
    await __import__("asyncio").sleep(window_seconds)
    await _flush_batch_now(user_id, batch_key)


async def _flush_batch_now(user_id: int, batch_key: str) -> None:
    """W68 PR8d: 立即 flush pending batch (合并 N 条为 batch event)"""
    global _batch_lock
    if _batch_lock is None:
        _batch_lock = __import__("asyncio").Lock()
    async with _batch_lock:
        key = (user_id, batch_key)
        entry = _batch_pending.pop(key, None)
    if not entry:
        return
    items = entry[1]
    if not items:
        return
    # 合并为 batch event
    batched = {
        "type": "batch",
        "batch_key": batch_key,
        "count": len(items),
        "items": items,
        "ts": datetime.utcnow().isoformat(),
    }
    await push_with_priority(user_id, batched)
    logger.debug(f"[Notify] batch flush user_id={user_id} key={batch_key} n={len(items)}")


# ============================================================================
# 2026-07-02 v2 PR6-P9: Celery 物理清理 30 天前 file_mentions
# ============================================================================

async def cleanup_old_mentions(db: AsyncSession, cutoff_date: datetime) -> int:
    """物理清除 `cutoff_date` 之前的 file_mentions 行 (一刀切, 不分已读未读)

    设计要点:
    - 一刀切: is_read=true/false 都删 (与表 docstring "已读后保留 30 天" 对齐,
      但本实现统一按 created_at 而非 read_at, 简化逻辑 + 防止未读通知无限堆积)
    - file_mentions.created_at 是 naive 列 (TIMESTAMP WITHOUT TIME ZONE),
      cutoff_date 可能是 tz-aware (Celery task 用 datetime.now(timezone.utc)),
      必须 _to_naive_datetime 转换 (CLAUDE.md 2026-06-05 tz-aware 教训复用)
    - CASCADE 自动清: 无外键引用 file_mentions, 安全删除
    - **PR6-P10 备份**: 先 SELECT 全字段 → JSON 备份 → 再 DELETE (事故防复发)
      关闭 BACKUP_BEFORE_DELETE_ENABLED=False 可跳过备份
    - deleted_count = 0 是健康状态, 不报错

    Returns:
        int: 删除行数 (0 = 无过期, N = 实际清理 N 行)
    """
    if cutoff_date.tzinfo is not None:
        cutoff_naive = cutoff_date.replace(tzinfo=None)
    else:
        cutoff_naive = cutoff_date
    deleted_count, _backup_path = await execute_backup_then_delete(
        db,
        model=FileMention,
        where_clause=FileMention.created_at < cutoff_naive,
        table_name="file_mentions",
        extra_metadata={
            "cutoff_date": cutoff_naive.isoformat(),
            "strategy": "created_at < cutoff (一刀切, 不分 is_read)",
        },
    )
    return deleted_count