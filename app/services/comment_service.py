"""comment_service — v2 PR6 文件评论服务 + PR6-P5 threading

职责:
1. create_comment(): 写评论 + 自动解析 @ 提及 (同步创建 file_mention)
   - v2 PR6-P5: 加 parent_comment_id 参数, 自动算 thread_depth, MAX_DEPTH=2 截断
2. list_comments(): 列文件评论 (按时间倒序,含 user_name 冗余)
3. delete_comment(): 删评论 (owner or file owner 才能删)
   - v2 PR6-P5: CASCADE 自动删所有 child replies

设计要点:
- 评论写入与 mention 解析在同一事务 (commit 顺序: comment 先 add + flush 拿 id → 写 mention)
- mentions ARRAY 字段存 user_id 列表 (前端 O(1) 显示 '@王天志')
- 软删除: 删除评论 = 物理删 (评论字数短, 无需软删)
- activity_events.comment: 评论创建后 log 一条活动
- v2 PR6-P5 threading:
  - parent_comment_id: NULL = 顶层评论, 整数 = 该评论的回复
  - thread_depth: 0/1/2 (顶层/回复/回复的回复), MAX_DEPTH=2 (硬上限)
  - reply_count: 父评论的回复数 +1 (触发 reply notification 时同步更新)
  - 删除评论 → CASCADE 自动删所有子评论
"""
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select, and_, delete, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import FileComment, Knowledge
from app.models.member import Member
from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

# v2 PR6-P5: 评论嵌套最大深度 (顶层 depth=0, 允许 depth=0/1/2 共 3 层)
# depth=2 是允许的最后一层回复, 再回复会被 reject (depth=3 不允许)
MAX_COMMENT_DEPTH = 2

# v2 PR6-P6: 评论编辑窗口 (秒) — 5 分钟内 owner 可编辑
# 5 分钟是 GitHub issue comment / Slack message edit 的标准窗口
# 超过窗口: 返回 422 (前端隐藏编辑按钮), 鼓励用户"如需修改请发新评论"
COMMENT_EDIT_WINDOW_SECONDS = 300


class CommentService:
    """v2 PR6: file_comments CRUD + mention 解析 + PR6-P5 threading"""

    @staticmethod
    async def create_comment(
        db: AsyncSession,
        *,
        file_id: int,
        user_id: int,
        content: str,
        parent_comment_id: Optional[int] = None,
    ) -> Tuple[FileComment, List[str]]:
        """创建评论 + 自动 @ 解析 (+ v2 PR6-P5 嵌套 + reply notification)

        Args:
            file_id: 评论的文件 id
            user_id: 评论者 id
            content: 评论内容 (含 @username 触发 mention)
            parent_comment_id: 父评论 id (v2 PR6-P5, None=顶层评论)

        Returns:
            (FileComment 实例, mention user_id 列表)

        Note:
            - 同一事务: comment 写 + 解析 + mention 批量创建
            - 自动跳过 @ 自己 (避免自提醒噪音)
            - v2 PR6-P5: 校验 parent_comment.thread_depth < MAX_COMMENT_DEPTH
              否则 raise ValueError (HTTP 422)
        """
        # 1) v2 PR6-P5: 校验 parent_comment + 计算 thread_depth
        parent: Optional[FileComment] = None
        thread_depth = 0  # 顶层
        if parent_comment_id is not None:
            parent = (await db.execute(
                select(FileComment).where(FileComment.id == parent_comment_id)
            )).scalar_one_or_none()
            if parent is None:
                raise ValueError(f"父评论不存在: id={parent_comment_id}")
            if parent.file_id != file_id:
                raise ValueError(f"父评论不属于该文件: parent.file_id={parent.file_id}, file_id={file_id}")
            if parent.thread_depth >= MAX_COMMENT_DEPTH:
                raise ValueError(
                    f"评论嵌套深度超限: 父评论 depth={parent.thread_depth}, "
                    f"最大允许 {MAX_COMMENT_DEPTH} (总 3 层)"
                )
            thread_depth = parent.thread_depth + 1

        # 2) 写 comment
        comment = FileComment(
            file_id=file_id,
            user_id=user_id,
            content=content,
            mentions=None,
            parent_comment_id=parent_comment_id,
            thread_depth=thread_depth,
            reply_count=0,
        )
        db.add(comment)
        await db.flush()

        # 3) 解析 @username → user_id 列表
        mentioned_user_ids: List[int] = []
        try:
            usernames = notification_service.parse_mentions_from_text(content)
            if usernames:
                # v2 PR6-P4 修复: 三路匹配, case-insensitive
                all_stmt = select(Member.id, Member.username, Member.wechat_id, Member.name)
                all_rows = (await db.execute(all_stmt)).all()
                wechat_id_map: dict[str, int] = {}
                username_map: dict[str, int] = {}
                name_map: dict[str, int] = {}
                for row in all_rows:
                    if row.wechat_id:
                        wechat_id_map[row.wechat_id.lower()] = row.id
                    if row.username:
                        username_map[row.username.lower()] = row.id
                    if row.name:
                        name_map[row.name] = row.id
                seen: set[int] = set()
                for u in usernames:
                    u_lower = u.lower()
                    uid = wechat_id_map.get(u_lower) or username_map.get(u_lower) or name_map.get(u)
                    if uid and uid not in seen:
                        seen.add(uid)
                        mentioned_user_ids.append(uid)
                mentioned_user_ids = [uid for uid in mentioned_user_ids if uid != user_id]

            comment.mentions = mentioned_user_ids or None
        except Exception as e:
            logger.warning(f"[Comment] @ 解析失败: {e}", exc_info=True)

        # 4) 批量写 file_mention (24h dedup)
        new_mentioned_ids: List[int] = []
        if mentioned_user_ids:
            try:
                new_mentions = await notification_service.create_bulk_mentions(
                    db,
                    file_id=file_id,
                    mentioned_user_ids=mentioned_user_ids,
                    mentioned_by=user_id,
                    context="comment",
                )
                new_mentioned_ids = [m.mentioned_user_id for m in new_mentions]
                comment.mentions = new_mentioned_ids or None
            except Exception as e:
                logger.warning(f"[Comment] mention 创建失败: {e}", exc_info=True)

        # 5) v2 PR6-P5: reply notification (顶层评论不发, 仅 reply 才发)
        reply_notified_user_id: Optional[int] = None
        if parent is not None and parent.user_id and parent.user_id != user_id:
            try:
                if parent.user_id not in mentioned_user_ids:
                    await notification_service.create_mention(
                        db,
                        file_id=file_id,
                        mentioned_user_id=parent.user_id,
                        mentioned_by=user_id,
                        context=f"reply:{comment.id}",
                    )
                    reply_notified_user_id = parent.user_id
            except Exception as e:
                logger.warning(f"[Comment] reply notification 失败: {e}", exc_info=True)

        # 6) v2 PR6-P5: 父评论 reply_count +1
        if parent is not None:
            try:
                await db.execute(
                    update(FileComment)
                    .where(FileComment.id == parent.id)
                    .values(reply_count=FileComment.reply_count + 1)
                )
            except Exception as e:
                logger.warning(f"[Comment] reply_count 更新失败: {e}", exc_info=True)

        # 7) activity log
        try:
            from app.services.activity_service import activity_service
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
                    "parent_comment_id": parent_comment_id,
                    "thread_depth": thread_depth,
                    "content_preview": content[:80],
                    "mention_count": len(mentioned_user_ids),
                    "reply_notified": reply_notified_user_id,
                },
            )
        except Exception as e:
            logger.warning(f"[Comment] activity log 失败: {e}", exc_info=True)

        await db.commit()
        await db.refresh(comment)

        logger.info(
            f"[Comment] created id={comment.id} file={file_id} user={user_id} "
            f"parent={parent_comment_id} depth={thread_depth} "
            f"mentions={len(new_mentioned_ids)} reply_notified={reply_notified_user_id}"
        )
        return comment, new_mentioned_ids

    @staticmethod
    async def list_comments(
        db: AsyncSession,
        *,
        file_id: int,
        limit: int = 100,
        before_id: Optional[int] = None,
    ) -> List[Tuple[FileComment, Optional[str]]]:
        """列文件评论 (按时间倒序)

        v2 PR6-P5: 返回 flat list, 前端根据 parent_comment_id 组装 tree
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
    async def update_comment(
        db: AsyncSession,
        *,
        comment_id: int,
        user_id: int,
        new_content: str,
    ) -> Tuple[FileComment, List[str]]:
        """v2 PR6-P6: 编辑评论 (owner only + 5 分钟窗口)

        Args:
            comment_id: 评论 id
            user_id: 编辑者 id (必须 = comment.user_id)
            new_content: 新内容 (非空, ≤2000 字符)

        Returns:
            (更新后的 FileComment, 新 mention user_id 列表)

        Raises:
            ValueError: 4 类错误 → HTTP 422
              - "评论不存在"
              - "无权编辑" (user_id != comment.user_id)
              - "编辑窗口已过" (now - created_at > 5 min)
              - "内容为空" / "内容超长"
        """
        # 1) 取 comment
        comment = (await db.execute(
            select(FileComment).where(FileComment.id == comment_id)
        )).scalar_one_or_none()
        if comment is None:
            raise ValueError(f"评论不存在: id={comment_id}")

        # 2) owner 校验
        if comment.user_id != user_id:
            logger.warning(f"[Comment] 越权编辑: user={user_id} comment={comment_id} owner={comment.user_id}")
            raise ValueError("无权编辑此评论")

        # 3) 5 分钟编辑窗口校验 (now - created_at)
        now = datetime.utcnow()
        if comment.created_at is None:
            # created_at 不应该为 None (DB DEFAULT now()), 防御性 fallback
            logger.warning(f"[Comment] created_at is None for id={comment_id}")
        else:
            elapsed = (now - comment.created_at).total_seconds()
            if elapsed > COMMENT_EDIT_WINDOW_SECONDS:
                raise ValueError(
                    f"编辑窗口已过: {int(elapsed)}s > {COMMENT_EDIT_WINDOW_SECONDS}s"
                )

        # 4) 内容校验
        cleaned = (new_content or "").strip()
        if not cleaned:
            raise ValueError("评论内容不能为空")
        if len(cleaned) > 2000:
            raise ValueError(f"评论内容超长: {len(cleaned)} > 2000")

        # 5) 重解析 @ mentions (用户改了内容, 新的 @ 列表)
        new_mentioned_ids: List[int] = []
        try:
            usernames = notification_service.parse_mentions_from_text(cleaned)
            if usernames:
                # v2 PR6-P4: 3 路匹配 + case-insensitive (与 create_comment 镜像)
                all_stmt = select(Member.id, Member.username, Member.wechat_id, Member.name)
                all_rows = (await db.execute(all_stmt)).all()
                wechat_id_map: dict[str, int] = {}
                username_map: dict[str, int] = {}
                name_map: dict[str, int] = {}
                for row in all_rows:
                    if row.wechat_id:
                        wechat_id_map[row.wechat_id.lower()] = row.id
                    if row.username:
                        username_map[row.username.lower()] = row.id
                    if row.name:
                        name_map[row.name] = row.id
                seen: set[int] = set()
                for u in usernames:
                    u_lower = u.lower()
                    uid = wechat_id_map.get(u_lower) or username_map.get(u_lower) or name_map.get(u)
                    if uid and uid not in seen:
                        seen.add(uid)
                        new_mentioned_ids.append(uid)
                new_mentioned_ids = [uid for uid in new_mentioned_ids if uid != user_id]
        except Exception as e:
            logger.warning(f"[Comment] edit @ 解析失败: {e}", exc_info=True)

        # 6) 写新 content + mentions
        # NOTE: 不加 edited_at 列 (overkill), 前端通过对比 mentions 差异显示"已编辑"标记
        comment.content = cleaned
        comment.mentions = new_mentioned_ids or None

        # 7) activity log (action="edit_comment" 与 create_comment 区分)
        try:
            from app.services.activity_service import activity_service
            f = (await db.execute(select(Knowledge.file_name).where(Knowledge.id == comment.file_id))).scalar_one_or_none()
            await activity_service.log(
                db,
                actor_id=user_id,
                action="edit_comment",
                target_type="file",
                target_id=comment.file_id,
                target_name=f,
                metadata={
                    "comment_id": comment.id,
                    "parent_comment_id": comment.parent_comment_id,
                    "thread_depth": comment.thread_depth,
                    "content_preview": cleaned[:80],
                    "mention_count": len(new_mentioned_ids),
                },
            )
        except Exception as e:
            logger.warning(f"[Comment] edit activity log 失败: {e}", exc_info=True)

        await db.commit()
        await db.refresh(comment)

        logger.info(
            f"[Comment] edited id={comment.id} by user={user_id} "
            f"mentions={len(new_mentioned_ids)}"
        )
        return comment, new_mentioned_ids

    @staticmethod
    async def delete_comment(
        db: AsyncSession,
        *,
        comment_id: int,
        user_id: int,
    ) -> bool:
        """删除评论 (owner of comment OR owner of file)

        v2 PR6-P5: CASCADE 自动删所有 child replies
        """
        stmt = (
            select(FileComment.user_id, FileComment.parent_comment_id, Knowledge.created_by)
            .outerjoin(Knowledge, Knowledge.id == FileComment.file_id)
            .where(FileComment.id == comment_id)
        )
        row = (await db.execute(stmt)).first()
        if not row:
            return False
        comment_owner, parent_comment_id, file_owner = row
        if user_id != comment_owner and user_id != file_owner:
            logger.warning(f"[Comment] 越权删除: user={user_id} comment={comment_id}")
            return False

        # v2 PR6-P5: 删 comment 前先 count children
        child_count = 0
        if parent_comment_id is None:
            child_stmt = select(FileComment.id).where(FileComment.parent_comment_id == comment_id)
            child_count = len((await db.execute(child_stmt)).all())

        # P2-1 fix (2026-07-08): 删 file_mentions 关联的 reply mention
        # (避免孤儿 file_mentions 行)
        # FileMention 模型没 file_comment_id FK, 用 context 字段模糊匹配:
        # - context="reply:<comment_id>" (PR6-P5 reply notification) → 可精准删
        # - context="comment" (顶层 comment mention) → 多 comment 共用, 不删 (避免误删)
        # - context="share" 等其他 → 不动
        reply_mention_ctx = f"reply:{comment_id}"
        reply_mention_delete = await db.execute(
            text("DELETE FROM file_mentions WHERE context = :ctx"),
            {"ctx": reply_mention_ctx},
        )
        deleted_mentions = reply_mention_delete.rowcount
        if deleted_mentions > 0:
            logger.info(
                f"[Comment] delete_comment {comment_id} 同时删 {deleted_mentions} 条 reply mention "
                f"(context={reply_mention_ctx})"
            )

        await db.execute(delete(FileComment).where(FileComment.id == comment_id))
        # cascade 自动删 children, reply_count 需手动维护
        if parent_comment_id is not None:
            # 非顶层被删: 其父评论 reply_count -1 (无论此评论有多少子孙)
            await db.execute(
                update(FileComment)
                .where(FileComment.id == parent_comment_id)
                .values(reply_count=FileComment.reply_count - 1)
            )
        elif child_count > 0:
            pass  # 顶层被删 + 有子: cascade 自动删, 顶层也删, reply_count 无意义
        await db.commit()
        logger.info(
            f"[Comment] deleted id={comment_id} by user={user_id} "
            f"parent={parent_comment_id} children_cascade={child_count}"
        )
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