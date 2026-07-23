"""Drive v2 PR9 — 评论 thread Service (2026-07-24)

负责 drive_comments 表的 CRUD + 嵌套回复树构建 + resolved 状态管理。

核心边界:
- 写评论: 用户必须有 file/folder 的 read 权限 (类似 GitHub issue 讨论低门槛)
- 编辑评论: 仅 author 本人 (不开放给 admin, 保证作者主权)
- 删除评论: 仅 author 本人 (CASCADE 自动删子回复, 软删改 hard delete)
- resolve: author / file owner / folder owner / folder admin member 可操作
- mention 提醒: 留给 PR10 集成 WS notification, 本 PR 仅写 mentions 字段

权限模型 (与 PR6 FileComment 一致 + 新增 folder 级):
- file_id 写评论: 校验 `get_user_folder_permission(file.folder_id, user_id)` 不为 None
  (file 的 folder 是 visibility=public 时 read 即可, 否则需要 folder 访问权限)
- folder_id 写评论: 校验 `get_user_folder_permission(folder_id, user_id)` >= 'read'

调用方 (API 层):
- create_comment(db, payload, author_id) → DriveComment
- list_comments(db, file_id?, folder_id?, author_id?, is_resolved?, limit, offset)
  → {top_level_comments_with_replies, total}
- get_comment(db, comment_id) → DriveComment
- update_comment(db, comment_id, user_id, content) → DriveComment
- delete_comment(db, comment_id, user_id) → bool (CASCADE 删子回复)
- resolve_comment(db, comment_id, user_id) → DriveComment (idempotent)
- unresolve_comment(db, comment_id, user_id) → DriveComment

抛错: DriveCommentServiceError, 业务级错误 (status_code 400/403/404)
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.drive_comment import DriveComment
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_share_service import DriveShareService
from app.utils.datetime_utils import to_naive_datetime

logger = logging.getLogger("microbubble.drive_comment")


class DriveCommentServiceError(Exception):
    """业务级错误，调用方映射到 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ==========================================================================
# 权限校验辅助
# ==========================================================================


async def _check_file_comment_authority(
    db: AsyncSession, file_id: int, user_id: int
) -> Knowledge:
    """校验用户对 file 的评论权限 (read 权限足够)

    file 必须存在 + 未删除 + storage_mode == 'drive' (普通 kb 文件不入评论流)
    user 必须能访问 file.folder (folder permission read+ 或 file.owner_id == user_id)

    Returns:
        Knowledge (已 load 完整对象)

    Raises:
        DriveCommentServiceError(404) file 不存在/已删除
        DriveCommentServiceError(403) user 无权访问 file 的 folder
    """
    file_row = (await db.execute(
        select(Knowledge).where(
            Knowledge.id == file_id,
            Knowledge.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if file_row is None:
        raise DriveCommentServiceError(
            f"File id={file_id} 不存在或已删除", status_code=404
        )

    # 校验 storage_mode == 'drive' (普通 kb 文件不入评论流, 防止历史 kb 评论污染)
    if file_row.storage_mode != "drive":
        raise DriveCommentServiceError(
            f"File id={file_id} 不是 drive 文件 (storage_mode={file_row.storage_mode}), 不支持评论",
            status_code=400,
        )

    # file owner 默认可访问
    if file_row.uploader_id == user_id:
        return file_row

    # 校验 folder 访问权限 (read 足够)
    if file_row.folder_id is not None:
        share_svc = DriveShareService(db)
        perm = await share_svc.get_user_folder_permission(file_row.folder_id, user_id)
        if perm is None:
            raise DriveCommentServiceError(
                f"无权评论 file id={file_id} (folder id={file_row.folder_id} 无访问权限)",
                status_code=403,
            )
        return file_row

    # file 没有 folder (孤儿 file) → 仅 uploader 可访问
    raise DriveCommentServiceError(
        f"无权评论 file id={file_id} (无 folder, 仅 uploader 可访问)",
        status_code=403,
    )


async def _check_folder_comment_authority(
    db: AsyncSession, folder_id: int, user_id: int
) -> Folder:
    """校验用户对 folder 的评论权限 (read 权限足够)

    folder 必须存在 + 未删除
    user 必须有 folder permission >= read (owner/admin/write/read/public)

    Returns:
        Folder

    Raises:
        DriveCommentServiceError(404) folder 不存在/已删除
        DriveCommentServiceError(403) user 无权访问 folder
    """
    share_svc = DriveShareService(db)
    perm = await share_svc.get_user_folder_permission(folder_id, user_id)
    if perm is None:
        folder = (await db.execute(
            select(Folder).where(
                Folder.id == folder_id,
                Folder.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if folder is None:
            raise DriveCommentServiceError(
                f"Folder id={folder_id} 不存在或已删除", status_code=404
            )
        raise DriveCommentServiceError(
            f"无权评论 folder id={folder_id}", status_code=403
        )

    folder = (await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if folder is None:
        raise DriveCommentServiceError(
            f"Folder id={folder_id} 不存在或已删除", status_code=404
        )
    return folder


async def _check_resolve_authority(
    db: AsyncSession, comment: DriveComment, user_id: int
) -> bool:
    """校验 user 是否有 resolve 权限

    规则 (或关系) — W68 PR9 改走 drive_permission_service.check_comment_resolver:
    - author 本人 (comment.author_id == user_id)
    - file owner (comment.file_id → file.uploader_id == user_id)
    - folder owner (comment.folder_id → folder.owner_id == user_id)
    - folder admin member (DriveFolderMember permission='admin')
    - 平台管理员 (Member.role='admin')

    Returns:
        True: 有权限

    Notes:
        - W68 PR9 前: 内联实现 (走 DriveShareService + DriveFolderMember 直查)
        - W68 PR9 后: 委托 drive_permission_service.check_comment_resolver
                       (统一入口, 未来 PR 复用, 减少重复逻辑)
    """
    from app.services.drive_permission_service import DrivePermissionService
    perm_svc = DrivePermissionService(db)
    return await perm_svc.check_comment_resolver(user_id, comment)


# ==========================================================================
# ORM → Schema 转换
# ==========================================================================


def _to_author_summary(member: Optional[Member]) -> dict:
    """Member → author summary dict"""
    if member is None:
        return {"id": 0, "name": "[已注销用户]", "avatar_url": None}
    return {
        "id": member.id,
        "name": member.name,
        "avatar_url": getattr(member, "avatar_url", None),
    }


def _to_read_schema(comment: DriveComment, replies: Optional[List[DriveComment]] = None) -> dict:
    """DriveComment + replies → CommentRead dict"""
    return {
        "id": comment.id,
        "file_id": comment.file_id,
        "folder_id": comment.folder_id,
        "author": _to_author_summary(comment.author) if hasattr(comment, "author") else None,
        "parent_id": comment.parent_id,
        "content": comment.content,
        "mentions": comment.mentions,
        "is_top_level": comment.is_top_level,
        "is_resolved": comment.is_resolved,
        "resolved_at": comment.resolved_at,
        "resolved_by": comment.resolved_by,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "replies": [_to_read_schema(r) for r in (replies or [])],
    }


# ==========================================================================
# Service 类
# ==========================================================================


class DriveCommentService:
    """DriveComment CRUD + 嵌套树 + resolved 状态管理"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 创建
    # ==========================================================================

    async def create_comment(
        self,
        *,
        author_id: int,
        file_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        content: str,
        mentions: Optional[List[int]] = None,
    ) -> DriveComment:
        """创建评论 (顶层或嵌套回复)

        Args:
            author_id: 评论作者 (从 JWT 取)
            file_id / folder_id: 二选一 (Pydantic 已校验, service 二次校验)
            parent_id: 嵌套回复父评论 (None=顶层)
            content: 评论内容 (Pydantic 已校验 1-10000)
            mentions: @ 提醒 user_id 列表

        Returns:
            DriveComment (含 author / replies)

        Raises:
            DriveCommentServiceError on validation / not-found / forbidden
        """
        if (file_id is None) == (folder_id is None):
            raise DriveCommentServiceError(
                "file_id / folder_id 必须二选一", status_code=400
            )

        # 权限校验
        if file_id is not None:
            await _check_file_comment_authority(self.db, file_id, author_id)
        else:
            assert folder_id is not None
            await _check_folder_comment_authority(self.db, folder_id, author_id)

        # parent_id 校验: 必须存在 + 同一目标 (file/folder 一致)
        if parent_id is not None:
            parent = (await self.db.execute(
                select(DriveComment).where(DriveComment.id == parent_id)
            )).scalar_one_or_none()
            if parent is None:
                raise DriveCommentServiceError(
                    f"父评论 id={parent_id} 不存在", status_code=404
                )
            # 嵌套必须同一目标 (file 与 parent.file 一致, folder 同理)
            if file_id is not None and parent.file_id != file_id:
                raise DriveCommentServiceError(
                    f"嵌套回复必须与父评论同 file (父 file_id={parent.file_id}, 当前 file_id={file_id})",
                    status_code=400,
                )
            if folder_id is not None and parent.folder_id != folder_id:
                raise DriveCommentServiceError(
                    f"嵌套回复必须与父评论同 folder (父 folder_id={parent.folder_id}, 当前 folder_id={folder_id})",
                    status_code=400,
                )

        comment = DriveComment(
            file_id=file_id,
            folder_id=folder_id,
            author_id=author_id,
            parent_id=parent_id,
            content=content,
            mentions=mentions,
        )
        self.db.add(comment)
        await self.db.commit()
        # 重新 load 含 author 关系 (Pydantic 渲染需要)
        await self.db.refresh(comment, attribute_names=["author", "resolver"])

        logger.info(
            f"[DriveCommentService.create_comment] id={comment.id} "
            f"file_id={file_id} folder_id={folder_id} author={author_id} "
            f"parent_id={parent_id} mentions={mentions}"
        )

        # W68 PR9 WS 推送: 通知 file/folder owner (best-effort, 不阻塞主流程)
        try:
            from app.services.drive_event_publisher import publish_comment_created
            await publish_comment_created(self.db, comment, actor_id=author_id)
        except Exception as e:
            logger.debug(f"[DriveCommentService] publish_comment_created 失败 (非阻塞): {e!r}")

        return comment

    # ==========================================================================
    # 列表
    # ==========================================================================

    async def list_comments(
        self,
        *,
        file_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        author_id: Optional[int] = None,
        is_resolved: Optional[bool] = None,
        parent_id: Optional[int] = None,  # None + 不传 = 顶层; 显式 None 也查顶层
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DriveComment], int]:
        """列评论

        默认仅返回顶层 (parent_id IS NULL), 内嵌 replies 树 (按 created_at 升序)
        total = 顶层评论数 (不含 replies)
        """
        conditions = []
        if file_id is not None:
            conditions.append(DriveComment.file_id == file_id)
        if folder_id is not None:
            conditions.append(DriveComment.folder_id == folder_id)
        if author_id is not None:
            conditions.append(DriveComment.author_id == author_id)
        if is_resolved is not None:
            if is_resolved:
                conditions.append(DriveComment.resolved_at.is_not(None))
            else:
                conditions.append(DriveComment.resolved_at.is_(None))
        # parent_id 显式传 None 时查询顶层; 传 int 时查特定 parent 的子回复
        if parent_id is None:
            conditions.append(DriveComment.parent_id.is_(None))
        else:
            conditions.append(DriveComment.parent_id == parent_id)

        where_clause = and_(*conditions) if conditions else None

        # total
        total_stmt = select(func.count()).select_from(DriveComment)
        if where_clause is not None:
            total_stmt = total_stmt.where(where_clause)
        total = (await self.db.execute(total_stmt)).scalar_one()

        # items
        items_stmt = (
            select(DriveComment)
            .where(where_clause)
            .options(selectinload(DriveComment.author))
            .order_by(DriveComment.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        items = (await self.db.execute(items_stmt)).scalars().all()

        # 拉所有子回复 (按 parent_id group), 拼成 replies 树
        if items and parent_id is None:
            item_ids = [c.id for c in items]
            replies_stmt = (
                select(DriveComment)
                .where(
                    DriveComment.parent_id.in_(item_ids),
                )
                .options(selectinload(DriveComment.author))
                .order_by(DriveComment.created_at.asc())
            )
            all_replies = (await self.db.execute(replies_stmt)).scalars().all()
            # group by parent_id
            replies_by_parent: dict = {}
            for r in all_replies:
                replies_by_parent.setdefault(r.parent_id, []).append(r)
            # attach to item.replies (临时属性, ORM 不持久)
            for c in items:
                c.replies = replies_by_parent.get(c.id, [])

        return list(items), total

    # ==========================================================================
    # 详情
    # ==========================================================================

    async def get_comment(
        self, comment_id: int, *, load_replies: bool = True
    ) -> Optional[DriveComment]:
        """查单条评论 (含 author + replies)

        Args:
            load_replies: True (默认) = 一次性 load 该评论的所有直接子回复
        """
        stmt = (
            select(DriveComment)
            .where(DriveComment.id == comment_id)
            .options(selectinload(DriveComment.author))
        )
        comment = (await self.db.execute(stmt)).scalar_one_or_none()
        if comment is None:
            return None

        if load_replies:
            replies_stmt = (
                select(DriveComment)
                .where(DriveComment.parent_id == comment_id)
                .options(selectinload(DriveComment.author))
                .order_by(DriveComment.created_at.asc())
            )
            replies = (await self.db.execute(replies_stmt)).scalars().all()
            comment.replies = list(replies)
        return comment

    # ==========================================================================
    # 编辑
    # ==========================================================================

    async def update_comment(
        self, comment_id: int, user_id: int, content: str
    ) -> DriveComment:
        """编辑评论 (仅 author 可调)

        Raises:
            DriveCommentServiceError(404) 不存在
            DriveCommentServiceError(403) 非 author
        """
        comment = (await self.db.execute(
            select(DriveComment).where(DriveComment.id == comment_id)
        )).scalar_one_or_none()
        if comment is None:
            raise DriveCommentServiceError(
                f"Comment id={comment_id} 不存在", status_code=404
            )

        if comment.author_id != user_id:
            raise DriveCommentServiceError(
                "仅 author 本人可编辑评论", status_code=403
            )

        comment.content = content
        await self.db.commit()
        await self.db.refresh(comment, attribute_names=["author"])

        logger.info(
            f"[DriveCommentService.update_comment] id={comment_id} by user={user_id}"
        )

        # W68 PR9 WS 推送: 通知 file/folder owner (best-effort, 不阻塞)
        try:
            from app.services.drive_event_publisher import publish_comment_updated
            await publish_comment_updated(self.db, comment, actor_id=user_id)
        except Exception as e:
            logger.debug(f"[DriveCommentService] publish_comment_updated 失败 (非阻塞): {e!r}")

        return comment

    # ==========================================================================
    # 删除
    # ==========================================================================

    async def delete_comment(self, comment_id: int, user_id: int) -> bool:
        """删除评论 (仅 author, CASCADE 子回复)

        Returns:
            True: 成功删除
            False: 评论不存在

        Raises:
            DriveCommentServiceError(403) 非 author
        """
        comment = (await self.db.execute(
            select(DriveComment).where(DriveComment.id == comment_id)
        )).scalar_one_or_none()
        if comment is None:
            return False

        if comment.author_id != user_id:
            raise DriveCommentServiceError(
                "仅 author 本人可删除评论", status_code=403
            )

        # W68 PR9 WS 推送: 在 hard delete 前快照 ID 字段 (删除后 ORM 不可访问)
        snapshot_file_id = comment.file_id
        snapshot_folder_id = comment.folder_id
        snapshot_author_id = comment.author_id

        await self.db.delete(comment)
        await self.db.commit()

        logger.info(
            f"[DriveCommentService.delete_comment] id={comment_id} by user={user_id} "
            f"(子回复 CASCADE 已自动删)"
        )

        # W68 PR9 WS 推送: 通知 file/folder owner (best-effort)
        try:
            from app.services.drive_event_publisher import publish_comment_deleted
            await publish_comment_deleted(
                self.db,
                comment_id=comment_id,
                file_id=snapshot_file_id,
                folder_id=snapshot_folder_id,
                author_id=snapshot_author_id,
                actor_id=user_id,
            )
        except Exception as e:
            logger.debug(f"[DriveCommentService] publish_comment_deleted 失败 (非阻塞): {e!r}")

        return True

    # ==========================================================================
    # resolved 状态管理
    # ==========================================================================

    async def resolve_comment(self, comment_id: int, user_id: int) -> DriveComment:
        """标记已解决 (幂等)

        权限:
        - author 本人
        - file owner / folder owner / folder admin member

        Raises:
            DriveCommentServiceError(404) 不存在
            DriveCommentServiceError(403) 无权限
        """
        comment = (await self.db.execute(
            select(DriveComment).where(DriveComment.id == comment_id)
        )).scalar_one_or_none()
        if comment is None:
            raise DriveCommentServiceError(
                f"Comment id={comment_id} 不存在", status_code=404
            )

        if not await _check_resolve_authority(self.db, comment, user_id):
            raise DriveCommentServiceError(
                "无权标记该评论为已解决 (需要 author / file owner / folder admin)",
                status_code=403,
            )

        if comment.resolved_at is None:
            comment.resolved_at = to_naive_datetime(datetime.now(timezone.utc))
            comment.resolved_by = user_id
            await self.db.commit()
            await self.db.refresh(comment, attribute_names=["author"])
            logger.info(
                f"[DriveCommentService.resolve_comment] id={comment_id} by user={user_id}"
            )

            # W68 PR9 WS 推送: 通知 comment.author (best-effort)
            try:
                from app.services.drive_event_publisher import publish_comment_resolved
                await publish_comment_resolved(
                    self.db,
                    comment_id=comment_id,
                    file_id=comment.file_id,
                    folder_id=comment.folder_id,
                    resolved_by=user_id,
                    author_id=comment.author_id,
                )
            except Exception as e:
                logger.debug(f"[DriveCommentService] publish_comment_resolved 失败 (非阻塞): {e!r}")
        return comment

    async def unresolve_comment(self, comment_id: int, user_id: int) -> DriveComment:
        """取消已解决 (幂等)

        权限同 resolve_comment
        """
        comment = (await self.db.execute(
            select(DriveComment).where(DriveComment.id == comment_id)
        )).scalar_one_or_none()
        if comment is None:
            raise DriveCommentServiceError(
                f"Comment id={comment_id} 不存在", status_code=404
            )

        if not await _check_resolve_authority(self.db, comment, user_id):
            raise DriveCommentServiceError(
                "无权取消该评论的已解决状态", status_code=403
            )

        if comment.resolved_at is not None:
            comment.resolved_at = None
            comment.resolved_by = None
            await self.db.commit()
            await self.db.refresh(comment, attribute_names=["author"])
            logger.info(
                f"[DriveCommentService.unresolve_comment] id={comment_id} by user={user_id}"
            )
        return comment


__all__ = [
    "DriveCommentService",
    "DriveCommentServiceError",
]