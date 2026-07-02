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
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FileMention, ActivityEvent
from app.models.member import Member

logger = logging.getLogger(__name__)

# v2 PR6-P7: 5s 通知去重窗口 (同 receiver + file + context)
NOTIFICATION_DEDUP_WINDOW_SECONDS = 5

# @ 提及正则: @张三 / @WangTianZhi / @nuyoah. (中文 2-4 字 + 英文 + 数字 + ._-)
# v2 PR6-P4 修复: 原 regex @([一-龥A-Za-z0-9_]{1,32}) 不能匹配 wechat_id 含 '.'
# (nuyoah. / WuWei. / HALO. 等真实用户名), 永久被忽略
# 扩到允许 '.', '-', '_' + max 32 char, 与前端 regex 完全镜像 (CLAUDE.md 铁律)
_MENTION_PATTERN = re.compile(r"@([一-龥A-Za-z0-9_.\-]{1,32})")


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
    ) -> Tuple[FileMention, bool]:
        """创建单条 mention (立即 commit)

        v2 PR6-P7: 5s dedup (receiver, file_id, context) — 命中时合并到现有 mention,
        repeated_count +1, 不创建新 row. 推 WS 时带 merged=True 让前端识别.

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

        if existing_recent is not None:
            # dedup 命中: 合并到第一条, repeated_count +1, 刷新 created_at 让它"看起来新鲜"
            existing_recent.repeated_count = (existing_recent.repeated_count or 1) + 1
            existing_recent.created_at = datetime.utcnow()
            existing_recent.mentioned_by = mentioned_by  # 最新触发人覆盖
            await db.commit()
            await db.refresh(existing_recent)
            merged = True
            logger.info(
                f"[Notify] 5s dedup merge file_id={file_id} → user={mentioned_user_id} "
                f"id={existing_recent.id} repeated_count={existing_recent.repeated_count} context={ctx}"
            )
            m = existing_recent
        else:
            m = FileMention(
                file_id=file_id,
                mentioned_user_id=mentioned_user_id,
                mentioned_by=mentioned_by,
                context=ctx,
                is_read=False,
                repeated_count=1,
            )
            db.add(m)
            await db.commit()
            await db.refresh(m)
            logger.info(
                f"[Notify] mention file_id={file_id} → user={mentioned_user_id} "
                f"by={mentioned_by} context={ctx}"
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

        if new_ids:
            new_mentions = [
                FileMention(
                    file_id=file_id,
                    mentioned_user_id=uid,
                    mentioned_by=mentioned_by,
                    context=context,
                    is_read=False,
                    repeated_count=1,
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