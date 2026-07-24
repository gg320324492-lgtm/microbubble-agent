"""Drive v2 PR9 — 评论 thread Service (2026-07-24, W68 第 8 批 PR11 path 物化)

负责 drive_comments 表的 CRUD + 嵌套回复树构建 + resolved 状态管理。

核心边界:
- 写评论: 用户必须有 file/folder 的 read 权限 (类似 GitHub issue 讨论低门槛)
- 编辑评论: 仅 author 本人 (不开放给 admin, 保证作者主权)
- 删除评论: 仅 author 本人 (CASCADE 自动删子回复, 软删改 hard delete)
- resolve: author / file owner / folder owner / folder admin member 可操作
- mention 提醒: W68 PR10 已集成 WS notification (publish_comment_mention)
  — mentions ARRAY 字段自动从 content 解析 @username 填充
  — 每个 mentioned user 触发 1 条 HIGH priority push

权限模型 (与 PR6 FileComment 一致 + 新增 folder 级):
- file_id 写评论: 校验 `get_user_folder_permission(file.folder_id, user_id)` 不为 None
  (file 的 folder 是 visibility=public 时 read 即可, 否则需要 folder 访问权限)
- folder_id 写评论: 校验 `get_user_folder_permission(folder_id, user_id)` >= 'read'

W68 第 8 批 PR11 增量 (path 物化):
- create_comment 自动根据 parent.path 计算 path (parent.path + str(parent.id) + '/')
- list_comments 支持 path_prefix 过滤 (走 GIN trigram 索引, 1 query)
- 新增 list_by_path_prefix (path prefix LIKE 查询, 替代 N+1 递归)
- 新增 rebuild_paths (数据修复 CLI 用, WITH RECURSIVE 重算全部 path)
- 新增 get_breadcrumb (1 query 走 path LIKE 拿祖先链)

调用方 (API 层):
- create_comment(db, payload, author_id) → DriveComment
- list_comments(db, file_id?, folder_id?, author_id?, is_resolved?, limit, offset)
  → {top_level_comments_with_replies, total}
- list_by_path_prefix(db, file_id?, path_prefix='/') → 1 query 走 GIN
- rebuild_paths(db, file_id/folder_id) → 修复用
- get_breadcrumb(db, comment_id) → ancestor chain (1 query)
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

    # file owner 默认可访问 (Knowledge ORM 字段: created_by, 不是 uploader_id)
    if file_row.created_by == user_id:
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
    - file owner (comment.file_id → file.created_by == user_id)
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
            mentions: @ 提醒 user_id 列表 (caller 显式传的优先, 否则从 content 自动解析)

        Returns:
            DriveComment (含 author / replies)

        Raises:
            DriveCommentServiceError on validation / not-found / forbidden

        W68 PR10 (锚点范式第 63 守恒):
        - mentions 为 None → 自动从 content 解析 @username
        - 每个 mentioned_user_id 触发 1 条 HIGH priority WS push (独立 publish_comment_mention)
        - 解析 / 推送失败 best-effort (try/except + logger.warning/error)
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

        # W68 PR10: mentions 兜底 — caller 没传或传空 → 从 content 自动解析
        resolved_mentions: Optional[List[int]] = mentions
        if not resolved_mentions:
            try:
                from app.services.mention_parser import parse_mentions
                parsed = await parse_mentions(
                    self.db, content, exclude_user_id=author_id,
                )
                if parsed:
                    resolved_mentions = parsed
                    logger.info(
                        f"[DriveCommentService.create_comment] 自动解析 mentions: "
                        f"parsed={parsed} from content (length={len(content)})"
                    )
            except Exception as e:
                logger.warning(
                    f"[DriveCommentService.create_comment] mentions 解析失败 (非阻塞): {e!r}",
                    exc_info=True,
                )

        # W68 PR11: 计算 path
        # - 顶层 (parent_id IS NULL): path = '/'
        # - 子评论: path = parent.path + str(parent.id) + '/'
        # 例: parent.id=5, parent.path='/1/2/' → child.path='/1/2/5/'
        if parent_id is not None and parent is not None:
            # parent 已在前面 query 出来, 复用
            parent_path = parent.path if parent.path else "/"
            new_path = f"{parent_path}{parent.id}/"
        else:
            new_path = "/"

        comment = DriveComment(
            file_id=file_id,
            folder_id=folder_id,
            author_id=author_id,
            parent_id=parent_id,
            content=content,
            mentions=resolved_mentions,
            path=new_path,
        )
        self.db.add(comment)
        await self.db.commit()
        # 重新 load 含 author 关系 (Pydantic 渲染需要)
        await self.db.refresh(comment, attribute_names=["author", "resolver"])

        logger.info(
            f"[DriveCommentService.create_comment] id={comment.id} "
            f"file_id={file_id} folder_id={folder_id} author={author_id} "
            f"parent_id={parent_id} path='{new_path}' mentions={resolved_mentions}"
        )

        # W68 PR9 WS 推送: 通知 file/folder owner (best-effort, 不阻塞主流程)
        try:
            from app.services.drive_event_publisher import publish_comment_created
            await publish_comment_created(self.db, comment, actor_id=author_id)
        except Exception as e:
            logger.debug(f"[DriveCommentService] publish_comment_created 失败 (非阻塞): {e!r}")

        # W68 PR10 WS 推送: 通知每个 mentioned user (HIGH priority, 独立推送)
        # 每个 mention 1 条 publish (不批量合并 — 立即送达是基础体验)
        # best-effort: 任何 1 条推送失败不影响其他 + 不阻塞 caller
        if resolved_mentions:
            try:
                from app.services.drive_event_publisher import publish_combined_notification
                from app.services.mention_parser import extract_snippet
                snippet = extract_snippet(content, max_chars=80)
                for uid in resolved_mentions:
                    try:
                        await publish_combined_notification(
                            self.db, target_user_id=uid, combined_actions=["@mentioned"],
                            source_comment_id=comment.id, actor_id=author_id, snippet=snippet,
                        )
                    except Exception as e:
                        logger.warning(
                            f"[DriveCommentService.create_comment] mention 推送失败 "
                            f"uid={uid} (非阻塞): {e!r}"
                        )
            except Exception as e:
                logger.warning(
                    f"[DriveCommentService.create_comment] mention 推送整体失败 (非阻塞): {e!r}",
                    exc_info=True,
                )

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

        # W68 第 12 批 C-2: 默认过滤软删评论 (deleted_at IS NULL)
        # 注: 这是 list API 默认行为; 内部 service (breadcrumb 等) 仍能看到软删评论
        if where_clause is not None:
            where_clause = and_(where_clause, DriveComment.deleted_at.is_(None))
        else:
            where_clause = DriveComment.deleted_at.is_(None)

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
    # W68 PR11: path 物化查询 (高性能)
    # ==========================================================================

    async def list_by_path_prefix(
        self,
        *,
        file_id: Optional[int] = None,
        folder_id: Optional[int] = None,
        path_prefix: str = "/",
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DriveComment], int]:
        """按 path prefix 过滤列评论 (W68 PR11, 替代 N+1 递归)

        利用 GIN trigram 索引 (migration 066 加) 加速 path LIKE 查询.
        走 file_id + path 复合索引 (PR11 加).

        Args:
            file_id / folder_id: 二选一 (Pydantic 校验)
            path_prefix: 必须以 '/' 开头和结尾, 例 '/1/2/'
                          规范化: 补尾 '/' 但不去头 '/'
            limit / offset: 分页

        Returns:
            (items, total)

        Notes:
            - path_prefix '/' 查所有顶层 + 所有嵌套 (全部命中)
            - path_prefix '/1/2/' 查 file_id=1 的所有直接子评论 (深度 2)
            - path_prefix '/1/2/3/' 查 file_id=1+2 的所有子评论 (深度 3)
              (例: path='/1/2/3/4/' 包含 '/1/2/3/' 因为 LIKE '%/1/2/3/%' 匹配)
            - 必须接 file_id 或 folder_id 之一 (无全表 path LIKE)
        """
        # 规范化 path_prefix: 补尾 '/', 不强制补头 '/'
        if not path_prefix.startswith("/"):
            path_prefix = "/" + path_prefix
        if not path_prefix.endswith("/"):
            path_prefix = path_prefix + "/"

        conditions = []
        if file_id is not None:
            conditions.append(DriveComment.file_id == file_id)
        if folder_id is not None:
            conditions.append(DriveComment.folder_id == folder_id)
        if (file_id is None) and (folder_id is None):
            raise DriveCommentServiceError(
                "list_by_path_prefix 必须指定 file_id 或 folder_id 之一 (无全表 path LIKE)",
                status_code=400,
            )
        # LIKE 过滤: path 包含 prefix (走 GIN trigram 索引加速)
        conditions.append(DriveComment.path.like(f"%{path_prefix}%"))

        where_clause = and_(*conditions)

        # W68 第 12 批 C-2: 默认过滤软删评论
        where_clause = and_(where_clause, DriveComment.deleted_at.is_(None))

        # total
        total_stmt = select(func.count()).select_from(DriveComment).where(where_clause)
        total = (await self.db.execute(total_stmt)).scalar_one()

        # items
        items_stmt = (
            select(DriveComment)
            .where(where_clause)
            .options(selectinload(DriveComment.author))
            .order_by(DriveComment.path.asc(), DriveComment.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        items = (await self.db.execute(items_stmt)).scalars().all()

        return list(items), total

    async def rebuild_paths(
        self,
        *,
        file_id: Optional[int] = None,
        folder_id: Optional[int] = None,
    ) -> int:
        """重算指定 file/folder 下所有评论的 path (W68 PR11 数据修复 CLI)

        用法:
        - 数据迁移后 path 缺失/错误时跑
        - migration 066 已自动 UPDATE 现有数据, 此函数是手动修复入口
        - CLI: `python -m app.scripts.rebuild_drive_comment_paths --file-id 42`

        Args:
            file_id / folder_id: 二选一 (无 = 不允许全表 UPDATE, 防止误操作)

        Returns:
            更新的 comment 数

        Notes:
            - 走 PostgreSQL WITH RECURSIVE (同 migration 066 逻辑)
            - 1 次 query 完成, 不用 ORM 对象级 UPDATE
            - 走 file_id 索引限定范围, 防全表扫
        """
        if (file_id is None) and (folder_id is None):
            raise DriveCommentServiceError(
                "rebuild_paths 必须指定 file_id 或 folder_id 之一",
                status_code=400,
            )
        if (file_id is not None) and (folder_id is not None):
            raise DriveCommentServiceError(
                "rebuild_paths 不能同时指定 file_id 和 folder_id",
                status_code=400,
            )

        target_col = "file_id" if file_id is not None else "folder_id"
        target_val = file_id if file_id is not None else folder_id

        # 走 raw SQL 走 WITH RECURSIVE
        # 注意: 用 SQLAlchemy text + execute
        from sqlalchemy import text

        sql = text(
            f"""
            WITH RECURSIVE comment_path_calc AS (
                SELECT
                    id,
                    parent_id,
                    '/'::text AS path
                FROM drive_comments
                WHERE parent_id IS NULL
                  AND {target_col} = :target_val

                UNION ALL

                SELECT
                    c.id,
                    c.parent_id,
                    (cp.path || cp.id::text || '/')::text AS path
                FROM drive_comments c
                INNER JOIN comment_path_calc cp ON c.parent_id = cp.id
                WHERE c.{target_col} = :target_val
            )
            UPDATE drive_comments dc
            SET path = cpc.path
            FROM comment_path_calc cpc
            WHERE dc.id = cpc.id
              AND dc.{target_col} = :target_val
            """
        )
        result = await self.db.execute(sql, {"target_val": target_val})
        await self.db.commit()
        updated_count = result.rowcount or 0

        logger.info(
            f"[DriveCommentService.rebuild_paths] {target_col}={target_val} "
            f"updated {updated_count} comments"
        )
        return updated_count

    async def get_breadcrumb(
        self, comment_id: int
    ) -> List[DriveComment]:
        """拿祖先链 (W68 PR11, 1 query 走 path LIKE)

        Args:
            comment_id: 目标评论 id

        Returns:
            ancestors + current (depth 升序, 顶层在前)

        Raises:
            DriveCommentServiceError(404) 评论不存在

        Notes:
            - 走 path LIKE '%/X/%' (用 GIN trigram 索引)
            - 1 query 拿祖先链, 不用 ORM 自连接递归
        """
        # 先拿目标评论 (必须存在)
        current = (await self.db.execute(
            select(DriveComment)
            .where(DriveComment.id == comment_id)
            .options(selectinload(DriveComment.author))
        )).scalar_one_or_none()
        if current is None:
            raise DriveCommentServiceError(
                f"Comment id={comment_id} 不存在", status_code=404
            )

        # 走 path LIKE 拿祖先链
        # 例: current.path='/1/2/3/42/' → path LIKE '%/1/%' (depth 1)
        #                                   OR '%/1/2/%' (depth 2)
        #                                   OR '%/1/2/3/%' (depth 3)
        # 简化: 全部 path segments 都包含就算祖先
        # 例: current.path='/1/2/3/42/' → split → ['1','2','3','42']
        # 父评论 path 必然包含 '/1/', '/1/2/', '/1/2/3/' 中至少一个

        # 取 ancestors: file_id 或 folder_id 必须与 current 一致
        if current.file_id is not None:
            target_cond = DriveComment.file_id == current.file_id
        else:
            target_cond = DriveComment.folder_id == current.folder_id

        # 解析 current.path 拿祖先 ID 集合
        # path='/1/2/3/42/' → segments=['1','2','3','42'] → ancestor_ids=[1,2,3]
        ancestor_ids: list = []
        if current.path and current.path != "/":
            segments = [s for s in current.path.split("/") if s]
            ancestor_ids = [int(s) for s in segments[:-1]]  # 去掉最后一个 (是 current 自己)

        if not ancestor_ids:
            # 顶层评论, 无祖先
            return [current]

        # 1 query: 拿祖先 + current 一起
        stmt = (
            select(DriveComment)
            .where(
                DriveComment.id.in_(ancestor_ids + [current.id]),
                target_cond,
            )
            .options(selectinload(DriveComment.author))
            .order_by(DriveComment.path.asc(), DriveComment.created_at.asc())
        )
        all_rows = (await self.db.execute(stmt)).scalars().all()

        # 按 path 升序排 (顶层 '/...') 已经在前
        # 防御: 如果 GIN trigram 索引让某些祖先未命中, 这里补查
        found_ids = {r.id for r in all_rows}
        missing = [aid for aid in ancestor_ids if aid not in found_ids]
        if missing:
            missing_stmt = (
                select(DriveComment)
                .where(DriveComment.id.in_(missing))
                .options(selectinload(DriveComment.author))
            )
            missing_rows = (await self.db.execute(missing_stmt)).scalars().all()
            all_rows = list(all_rows) + list(missing_rows)

        # 按 depth 排序 (path 越短 = depth 越小)
        all_rows.sort(key=lambda c: (len(c.path or "/"), c.id))

        return all_rows

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
    # 删除 (W68 第 12 批 C-2: 改软删 + 3 角色权限)
    # ==========================================================================

    async def delete_comment(self, comment_id: int, user_id: int) -> bool:
        """软删评论 (author / file owner / 平台 admin)

        W68 第 12 批 C-2 改造 (W68 第 8 批 PR9 老 hard delete + 仅 author):
        - 软删: set deleted_at + deleted_by (不 DELETE FROM, 不 CASCADE 子回复)
        - 3 角色权限 (满足任一可删):
          * author 本人 (comment.author_id == user_id)
          * file owner (file.created_by == user_id) — 仅当 comment.file_id 非 NULL
          * 平台 admin (Member.role == 'admin')
        - 保留 audit_log (调用方写, service 层不写避免破坏幂等性)
        - 子回复不自动删除 (PR9 老 CASCADE 移除, 软删保留父子关系供追溯)

        Args:
            comment_id: 目标评论 id
            user_id: 操作人

        Returns:
            True: 成功软删
            False: 评论不存在

        Raises:
            DriveCommentServiceError(403) 无权限 (非 author / 非 file owner / 非 admin)
            DriveCommentServiceError(404) 评论不存在

        Notes:
            - 已软删 (deleted_at IS NOT NULL) 再次删 → 返回 False (幂等性保持)
              不抛 404, 不抛 403 — 调用方视为幂等成功
            - 软删后 list_comments 默认过滤 deleted_at IS NULL (历史数据保留在 DB)
            - audit_log 写入由 API 层做 (DELETE /api/v1/drive/comments/{id})
        """
        comment = (await self.db.execute(
            select(DriveComment).where(DriveComment.id == comment_id)
        )).scalar_one_or_none()
        if comment is None:
            raise DriveCommentServiceError(
                f"Comment id={comment_id} 不存在", status_code=404
            )

        # 幂等: 已软删 → 直接返回 False (让 API 层返 404)
        if comment.deleted_at is not None:
            return False

        # 权限校验: author / file owner / 平台 admin
        is_author = comment.author_id == user_id
        is_admin = False
        is_file_owner = False

        # 查 actor 的 role (平台 admin 判断)
        actor = (await self.db.execute(
            select(Member).where(Member.id == user_id)
        )).scalar_one_or_none()
        if actor is not None and getattr(actor, "role", None) == "admin":
            is_admin = True

        # file owner 判断 (仅 file_id 非 NULL)
        if comment.file_id is not None:
            file_row = (await self.db.execute(
                select(Knowledge).where(Knowledge.id == comment.file_id)
            )).scalar_one_or_none()
            if file_row is not None and file_row.created_by == user_id:
                is_file_owner = True

        if not (is_author or is_file_owner or is_admin):
            raise DriveCommentServiceError(
                "无权限删除该评论 (需要 author / file owner / 平台 admin)",
                status_code=403,
            )

        # 软删: set deleted_at + deleted_by
        comment.deleted_at = to_naive_datetime(datetime.now(timezone.utc))
        comment.deleted_by = user_id
        await self.db.commit()
        await self.db.refresh(comment, attribute_names=["author"])

        logger.info(
            f"[DriveCommentService.delete_comment] id={comment_id} by user={user_id} "
            f"(author={is_author} file_owner={is_file_owner} admin={is_admin})"
        )

        # W68 PR9 WS 推送: 通知 file/folder owner (best-effort, 不阻塞)
        # 注: 软删而非 hard delete, 子回复保留, 推送语义不变
        try:
            from app.services.drive_event_publisher import publish_comment_deleted
            await publish_comment_deleted(
                self.db,
                comment_id=comment_id,
                file_id=comment.file_id,
                folder_id=comment.folder_id,
                author_id=comment.author_id,
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