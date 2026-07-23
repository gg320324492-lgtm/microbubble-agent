"""Drive v2 PR9 — Folder Admin Permission Service (2026-07-24)

将分散在 drive_version_service / drive_comment_service 中的 folder admin
权限检查抽出到独立 service, 供 PR9 + PR10 + 后续 PR 复用.

核心边界 (W68 第 3 批 F-2 报告 TODO: PR10 加 folder admin permission check,
PR9 服务端先打 logger.debug 占位):

权限等级 (W67 Drive v2 PR7 已建 drive_folder_shares + drive_folder_members):
- owner 隐含 admin (folder.owner_id == user_id)
- admin member (DriveFolderMember.permission == 'admin')
- write member (DriveFolderMember.permission == 'write')
- read member (DriveFolderMember.permission == 'read')
- folder.visibility == 'public' 时所有人 read
- 否则 None

3 个公开方法 (供 drive_version_service / drive_comment_service 调用):
1. check_folder_admin(user_id, folder_id) -> bool
   - 文件操作 (上传/回滚/删除版本) 权限: owner / admin / platform admin
2. check_file_owner_or_folder_admin(user_id, file_id) -> bool
   - 复合权限: file.created_by == user_id OR folder admin/owner OR platform admin
3. check_comment_resolver(user_id, comment) -> bool
   - 评论 resolve 权限: author / file owner / folder owner / folder admin member

设计要点:
- 全部走 AsyncSession, 不在模块顶部创建 client (CLAUDE.md 752 行铁律)
- 复用 drive_share_service.get_user_folder_permission (无重复 SQL)
- 失败/异常路径: 返回 False + logger.debug (不抛异常, 让 service 层统一抛 HTTPException)
  ↑ 重要: 这个 service 是"查询类", 不抛业务异常. 调用方拿到 False 后再 raise 业务异常.

调用方 (本 PR 改造):
- app/services/drive_version_service.py: delete_version / rollback (PR10 后扩 upload)
- app/services/drive_comment_service.py: resolve_comment / unresolve_comment (已内联, 后续统一调这里)

未来 PR 扩展:
- PR10 drive_v2_pr10: list_versions 加 visibility check (read 权限足够)
- drive_service.copy_file: 复制到 folder 检查 destination folder admin
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_comment import DriveComment
from app.models.drive_share import DriveFolderMember
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_share_service import DriveShareService

logger = logging.getLogger("microbubble.drive_permission")


class DrivePermissionError(Exception):
    """Drive 权限校验服务错误

    实际很少抛 (本 service 大多数场景是 query + return bool), 仅在 db 异常时抛.
    调用方应 try/except + fallback 到 500.
    """
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DrivePermissionService:
    """Folder / File / Comment 权限校验统一入口 (W68 PR9)

    所有方法接受 AsyncSession (通过外部注入, 避免模块顶部创建单例, 跨 event loop 安全).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 平台管理员辅助 (复用现有 pattern, 不重复实现)
    # ==========================================================================

    async def is_platform_admin(self, user_id: int) -> bool:
        """检查用户是否为平台管理员 (Member.role == 'admin')

        Returns:
            True if Member.role == 'admin'
            False if Member 不存在 或 非 admin
        """
        member = await self.db.get(Member, user_id)
        return member is not None and member.role == "admin"

    # ==========================================================================
    # 1. folder admin 检查 (用于 folder 操作: rename/delete/share/move)
    # ==========================================================================

    async def check_folder_admin(
        self, user_id: int, folder_id: int
    ) -> bool:
        """检查 user 是否为 folder 的 admin (含隐含 owner)

        规则 (或关系):
        - folder.owner_id == user_id (隐含 admin)
        - DriveFolderMember.permission == 'admin' (显式 admin)
        - 平台管理员 (Member.role == 'admin', 兜底: 课题组服务器场控)

        Args:
            user_id: 当前用户 member.id
            folder_id: 目标 folder id

        Returns:
            True: 是 admin (含 owner / 平台 admin)
            False: 非 admin / folder 不存在
        """
        try:
            # 1. owner 隐含 admin
            folder = await self.db.get(Folder, folder_id)
            if folder is None or folder.deleted_at is not None:
                logger.debug(
                    f"[DrivePermissionService.check_folder_admin] "
                    f"folder id={folder_id} 不存在或已删, user={user_id} → False"
                )
                return False
            if folder.owner_id == user_id:
                return True

            # 2. 显式 admin member
            admin_member = (await self.db.execute(
                select(DriveFolderMember).where(
                    DriveFolderMember.folder_id == folder_id,
                    DriveFolderMember.member_id == user_id,
                    DriveFolderMember.permission == "admin",
                )
            )).scalar_one_or_none()
            if admin_member is not None:
                return True

            # 3. 平台管理员
            if await self.is_platform_admin(user_id):
                return True

            logger.debug(
                f"[DrivePermissionService.check_folder_admin] "
                f"user={user_id} folder={folder_id} 非 admin → False"
            )
            return False
        except Exception as e:
            logger.error(
                f"[DrivePermissionService.check_folder_admin] "
                f"user={user_id} folder={folder_id} 异常: {e!r}",
                exc_info=True,
            )
            return False

    # ==========================================================================
    # 2. file owner or folder admin 复合检查 (用于 file 操作: upload new version)
    # ==========================================================================

    async def check_file_owner_or_folder_admin(
        self, user_id: int, file_id: int
    ) -> bool:
        """检查 user 是否可"修改"该 file (upload/rollback/delete version)

        规则 (或关系):
        - file.created_by == user_id (Knowledge 创建人, 走 _can_modify_file 同步路径)
        - file.folder_id 存在 + user 是 folder admin
        - 平台管理员 (Member.role == 'admin')

        Args:
            user_id: 当前用户 member.id
            file_id: Knowledge.id (drive 模式文件)

        Returns:
            True: 有权限
            False: 无权限 / file 不存在 / file 不是 drive 模式
        """
        try:
            file_row = await self.db.get(Knowledge, file_id)
            if file_row is None:
                logger.debug(
                    f"[DrivePermissionService.check_file_owner_or_folder_admin] "
                    f"file id={file_id} 不存在 → False"
                )
                return False
            if file_row.storage_mode != "drive":
                logger.debug(
                    f"[DrivePermissionService.check_file_owner_or_folder_admin] "
                    f"file id={file_id} storage_mode={file_row.storage_mode} 非 drive → False"
                )
                return False

            # 1. file owner (created_by — drive_version_service 一致字段)
            if file_row.created_by == user_id:
                return True

            # 2. folder admin
            if file_row.folder_id is not None:
                if await self.check_folder_admin(user_id, file_row.folder_id):
                    return True

            # 3. 平台管理员
            if await self.is_platform_admin(user_id):
                return True

            logger.debug(
                f"[DrivePermissionService.check_file_owner_or_folder_admin] "
                f"user={user_id} file={file_id} 无权限 → False "
                f"(created_by={file_row.created_by}, folder_id={file_row.folder_id})"
            )
            return False
        except Exception as e:
            logger.error(
                f"[DrivePermissionService.check_file_owner_or_folder_admin] "
                f"user={user_id} file={file_id} 异常: {e!r}",
                exc_info=True,
            )
            return False

    # ==========================================================================
    # 3. comment resolve 权限检查 (author / file owner / folder admin)
    # ==========================================================================

    async def check_comment_resolver(
        self, user_id: int, comment: DriveComment
    ) -> bool:
        """检查 user 是否有 resolve/unresolve 该 comment 的权限

        规则 (或关系, 与 drive_comment_service._check_resolve_authority 一致):
        - comment.author_id == user_id (作者本人)
        - comment.file_id 存在 + file.created_by == user_id (file owner)
        - comment.file_id 存在 + file.folder_id 存在 + user 是 folder admin
        - comment.folder_id 存在 + folder.owner_id == user_id (folder owner)
        - comment.folder_id 存在 + user 是 folder admin member
        - 平台管理员 (Member.role == 'admin')

        Args:
            user_id: 当前用户 member.id
            comment: DriveComment 实例 (不必预 load, 内部会 query)

        Returns:
            True: 有权限 resolve/unresolve
            False: 无权限 / comment 不存在
        """
        try:
            # 1. author 本人
            if comment.author_id == user_id:
                return True

            # 2/3. file-level 权限
            if comment.file_id is not None:
                file_row = await self.db.get(Knowledge, comment.file_id)
                if file_row is not None:
                    # 2a. file owner (uploader)
                    if file_row.created_by == user_id:
                        return True
                    # 2b. file.folder admin
                    if file_row.folder_id is not None:
                        if await self.check_folder_admin(
                            user_id, file_row.folder_id
                        ):
                            return True

            # 4. folder-level 权限 (独立 file_id 走的 folder 评论)
            if comment.folder_id is not None:
                folder = await self.db.get(Folder, comment.folder_id)
                if folder is not None:
                    # 4a. folder owner
                    if folder.owner_id == user_id:
                        return True
                    # 4b. folder admin member
                    admin_member = (await self.db.execute(
                        select(DriveFolderMember).where(
                            DriveFolderMember.folder_id == comment.folder_id,
                            DriveFolderMember.member_id == user_id,
                            DriveFolderMember.permission == "admin",
                        )
                    )).scalar_one_or_none()
                    if admin_member is not None:
                        return True

            # 5. 平台管理员
            if await self.is_platform_admin(user_id):
                return True

            logger.debug(
                f"[DrivePermissionService.check_comment_resolver] "
                f"user={user_id} comment={comment.id} 无权限 → False"
            )
            return False
        except Exception as e:
            logger.error(
                f"[DrivePermissionService.check_comment_resolver] "
                f"user={user_id} comment={comment.id} 异常: {e!r}",
                exc_info=True,
            )
            return False

    # ==========================================================================
    # 4. 扩展: get_user_folder_permission 包装 (供 DriveService / future PR 复用)
    # ==========================================================================

    async def get_user_folder_permission(
        self, folder_id: int, user_id: int
    ) -> Optional[str]:
        """获取用户对 folder 的有效权限 (read/write/admin/None)

        完整复用 DriveShareService.get_user_folder_permission, 避免双份维护.
        返回:
        - 'admin': folder owner / DriveFolderMember.permission='admin'
        - 'write': DriveFolderMember.permission='write'
        - 'read':  DriveFolderMember.permission='read' 或 folder.visibility='public'
        - None:    folder 不存在 / 已删 / 无权限

        Args:
            folder_id: folder id
            user_id: 当前用户

        Returns:
            Optional[str]: 'admin'/'write'/'read'/None
        """
        share_svc = DriveShareService(self.db)
        return await share_svc.get_user_folder_permission(folder_id, user_id)


__all__ = [
    "DrivePermissionService",
    "DrivePermissionError",
]