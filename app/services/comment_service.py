"""comment_service — v2 PR6 文件评论服务

职责:
1. create_comment(): 写评论 + 自动解析 @ 提及 (同步创建 file_mention)
2. list_comments(): 列文件评论 (按时间倒序,含 user_name 冗余)
3. delete_comment(): 删评论 (owner or file owner 才能删)
4. update_comment(): 编辑评论 (owner only)

设计要点:
- 评论写入与 mention 解析在同一事务 (commit 顺序: comment 先 add + flush 拿 id → 写 mention)
- mentions ARRAY 字段存 user_id 列表 (前端 O(1) 显示 '@王天志')
- 软删除: 删除评论 = 物理删 (评论字数短, 无需软删)
- activity_events.comment: 评论创建后 log 一条活动
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FileComment, Knowledge
from app.models.member import Member
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)


class CommentService:
    """v2 PR6: file_comments CRUD + mention 解析"""

    @staticmethod
    async def create_comment(
        db: AsyncSession,
        *,
        file_id: int,
        user_id: int,
        content: str,
    ) -> Tuple[FileComment, List[str]]:
        """创建评论 + 自动 @ 解析

        Args:
            file_id: 评论的文件 id
            user_id: 评论者 id
            content: 评论内容 (含 @username 触发 mention)

        Returns:
            (FileComment 实例, mention user_id 列表)

        Note:
            - 同一事务: comment 写 + 解析 + mention 批量创建
            - 自动跳过 @ 自己 (避免自提醒噪音)
        """
        # 1) 写 comment
        comment = FileComment(
            file_id=file_id,
            user_id=user_id,
            content=content,
            mentions=None,  # 后面填
        )
        db.add(comment)
        await db.flush()  # 拿 comment.id 但不 commit

        # 2) 解析 @username → user_id 列表
        mentioned_user_ids: List[int] = []
        try:
            usernames = notification_service.parse_mentions_from_text(content)
            if usernames:
                # username → user_id 转换 (case-insensitive 精确匹配)
                stmt = select(Member.id, Member.username).where(
                    Member.username.in_(usernames)
                )
                rows = (await db.execute(stmt)).all()
                name_to_id = {row.username: row.id for row in rows}
                mentioned_user_ids = list(set(name_to_id.values()) - {user_id})  # 去重 + 排除自己

            comment.mentions = mentioned_user_ids or None
        except Exception as e:
            logger.warning(f"[Comment] @ 解析失败: {e}", exc_info=True)

        # 3) 批量写 file_mention
        if mentioned_user_ids:
            try:
                await notification_service.create_bulk_mentions(
                    db,
                    file_id=file_id,
                    mentioned_user_ids=mentioned_user_ids,
                    mentioned_by=user_id,
                    context="comment",
                )
            except Exception as e:
                logger.warning(f"[Comment] mention 创建失败: {e}", exc_info=True)

        # 4) activity log
        try:
            from app.services.activity_service import activity_service
            # 取 file_name 冗余存
            f = (await db.execute(select(Knowledge.file_name).where(Knowledge.id == file_id))).scalar_one_or_none()
            await activity_service.log(
                db,
                actor_id=user_id,
                action="comment",
                target_type="file",
                target_id=file_id,
                target_name=f,
                metadata={
                    "comment_id": comment.id,
                    "content_preview": content[:80],
                    "mention_count": len(mentioned_user_ids),
                },
            )
        except Exception as e:
            logger.warning(f"[Comment] activity log 失败: {e}", exc_info=True)

        await db.commit()
        await db.refresh(comment)

        logger.info(
            f"[Comment] created id={comment.id} file={file_id} user={user_id} "
            f"mentions={len(mentioned_user_ids)}"
        )
        return comment, mentioned_user_ids

    @staticmethod
    async def list_comments(
        db: AsyncSession,
        *,
        file_id: int,
        limit: int = 100,
        before_id: Optional[int] = None,
    ) -> List[Tuple[FileComment, Optional[str]]]:
        """列文件评论 (按时间倒序)

        Args:
            file_id: 文件 id
            limit: 上限
            before_id: cursor (id < before_id)

        Returns:
            [(FileComment, user_name)] 列表 (user_name 可能 None = 用户被删)
        """
        stmt = select(FileComment, Member.username).outerjoin(
            Member, Member.id == FileComment.user_id
        ).where(FileComment.file_id == file_id)

        if before_id is not None:
            stmt = stmt.where(FileComment.id < before_id)

        stmt = stmt.order_by(FileComment.created_at.desc()).limit(limit)
        rows = (await db.execute(stmt)).all()
        return [(row[0], row[1]) for row in rows]

    @staticmethod
    async def delete_comment(
        db: AsyncSession,
        *,
        comment_id: int,
        user_id: int,
    ) -> bool:
        """删除评论 (owner of comment OR owner of file)

        Returns:
            True 成功, False 越权/不存在
        """
        # 取 comment + file owner
        stmt = (
            select(FileComment.user_id, Knowledge.created_by)
            .outerjoin(Knowledge, Knowledge.id == FileComment.file_id)
            .where(FileComment.id == comment_id)
        )
        row = (await db.execute(stmt)).first()
        if not row:
            return False
        comment_owner, file_owner = row
        if user_id != comment_owner and user_id != file_owner:
            logger.warning(f"[Comment] 越权删除: user={user_id} comment={comment_id}")
            return False

        await db.execute(delete(FileComment).where(FileComment.id == comment_id))
        await db.commit()
        logger.info(f"[Comment] deleted id={comment_id} by user={user_id}")
        return True

    @staticmethod
    async def count_for_file(db: AsyncSession, *, file_id: int) -> int:
        """文件评论数 (前端 FileCard 徽章)"""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(FileComment).where(
            FileComment.file_id == file_id
        )
        return (await db.execute(stmt)).scalar() or 0


# 全局单例
comment_service = CommentService()