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

不与现有 Notification 系统冲突:
- 现有 app/api/v1/notification.py (chat reminder 类) 用的是 Notification 模型 + reminder_service
- 本服务**只**管 file_mentions (drive 网盘协作提醒),不混合
"""
import logging
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FileMention, ActivityEvent
from app.models.member import Member

logger = logging.getLogger(__name__)

# @ 提及正则: @张三 / @王天志 (中文 2-4 字)
_MENTION_PATTERN = re.compile(r"@([一-龥A-Za-z0-9_]{1,32})")


class NotificationService:
    """v2 PR6: file_mention CRUD"""

    @staticmethod
    async def create_mention(
        db: AsyncSession,
        *,
        file_id: int,
        mentioned_user_id: int,
        mentioned_by: Optional[int] = None,
        context: Optional[str] = None,
    ) -> FileMention:
        """创建单条 mention (立即 commit)

        返回 FileMention 实例 (含 id)
        触发 WS push (best-effort, 失败不抛)
        """
        m = FileMention(
            file_id=file_id,
            mentioned_user_id=mentioned_user_id,
            mentioned_by=mentioned_by,
            context=context or "mention",
            is_read=False,
        )
        db.add(m)
        await db.commit()
        await db.refresh(m)

        # 推送 WS (best-effort)
        try:
            from app.api.v1.ws_notifications import notification_manager
            await notification_manager.push_to_user(mentioned_user_id, {
                "type": "mention",
                "id": m.id,
                "file_id": file_id,
                "mentioned_by": mentioned_by,
                "context": context,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
        except Exception as e:
            logger.debug(f"[Notify] WS push 失败 (非阻塞): {e}")

        logger.info(
            f"[Notify] mention file_id={file_id} → user={mentioned_user_id} "
            f"by={mentioned_by} context={context}"
        )
        return m

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
        """
        if not mentioned_user_ids:
            return []

        # 去重 (同一用户)
        unique_ids = list(set(mentioned_user_ids))

        # 24h 内的已有 mention 检查 (避免重复推送)
        from datetime import timedelta
        threshold = datetime.utcnow() - timedelta(hours=24)
        existing = (await db.execute(
            select(FileMention.mentioned_user_id).where(
                and_(
                    FileMention.file_id == file_id,
                    FileMention.mentioned_user_id.in_(unique_ids),
                    FileMention.created_at >= threshold,
                )
            )
        )).scalars().all()
        existing_set = set(existing)
        new_ids = [uid for uid in unique_ids if uid not in existing_set]

        if not new_ids:
            logger.debug(f"[Notify] 24h 内已 @ 过 {list(existing_set)} 跳过")
            return []

        mentions = [
            FileMention(
                file_id=file_id,
                mentioned_user_id=uid,
                mentioned_by=mentioned_by,
                context=context,
                is_read=False,
            )
            for uid in new_ids
        ]
        db.add_all(mentions)
        await db.commit()

        # 推送 WS (each)
        try:
            from app.api.v1.ws_notifications import notification_manager
            for m in mentions:
                await notification_manager.push_to_user(m.mentioned_user_id, {
                    "type": "mention",
                    "id": m.id,
                    "file_id": file_id,
                    "mentioned_by": mentioned_by,
                    "context": context,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                })
        except Exception as e:
            logger.debug(f"[Notify] WS push 失败 (非阻塞): {e}")

        logger.info(f"[Notify] bulk mentions file_id={file_id} → {len(mentions)} users")
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