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

不与现有 Notification 系统冲突:
- 现有 app/api/v1/notification.py (chat reminder 类) 用的是 Notification 模型 + reminder_service
- 本服务**只**管 file_mentions (drive 网盘协作提醒),不混合
"""
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FileMention, ActivityEvent, Knowledge, FileComment
from app.models.member import Member

logger = logging.getLogger(__name__)

# v2 PR6-P7: 5s 通知去重窗口 (同 receiver + file + context)
NOTIFICATION_DEDUP_WINDOW_SECONDS = 5

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
        # PR6-P7 dedup: 检查 5s 内 (mentioned_user_id, file_id, context) 是否有 unread mention
        merged = False
        ctx = context or "mention"
        threshold = datetime.utcnow() - timedelta(seconds=NOTIFICATION_DEDUP_WINDOW_SECONDS)
        existing_recent = (await db.execute(
            select(FileMention)
            .where(
                and_(
                    FileMention.mentioned_user_id == mentioned_user_id,
                    FileMention.file_id == file_id,
                    FileMention.context == ctx,
                    FileMention.is_read == False,  # noqa: E712
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
            # v2 PR6-P8: title/body 重拼 (preview/file_type 已变, 重复最新)
            new_title, new_body = NotificationService._build_title_body(
                actor_name=actor_name, meta=meta, context=ctx,
                repeated_count=existing_recent.repeated_count,
            )
            existing_recent.title = new_title
            existing_recent.body = new_body
            existing_recent.file_type = meta.get("file_type")
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
    - deleted_count = 0 是健康状态, 不报错

    Returns:
        int: 删除行数 (0 = 无过期, N = 实际清理 N 行)
    """
    if cutoff_date.tzinfo is not None:
        cutoff_naive = cutoff_date.replace(tzinfo=None)
    else:
        cutoff_naive = cutoff_date
    stmt = delete(FileMention).where(FileMention.created_at < cutoff_naive)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0