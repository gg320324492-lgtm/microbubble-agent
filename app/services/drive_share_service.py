"""Drive v2 PR7 — Folder Share Service (2026-07-23)

负责 drive_folder_shares + drive_folder_members 两表的 CRUD。

核心边界:
- 只有 folder owner / admin member 才能分享 folder (越权返 403)
- 公开 share token 过期/撤销后立即失效 (校验 revoked_at + expires_at)
- member 邀请可重复调用同一 member_id (idempotent — 已邀请则更新 permission)
- token 安全: `secrets.token_urlsafe(32)` 32 字节 = 43 字符 base64

调用方 (API 层):
- create_folder_share(db, folder_id, user_id, permission, expires_days)
- get_folder_by_share_token(db, token) → folder + permission + files/subfolders
- add_folder_member(db, folder_id, inviter_id, member_id, permission)
- remove_folder_member(db, folder_id, member_id)

抛错: DriveShareServiceError, 业务级错误 (status_code 400/403/404)
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_share import (
    VALID_FOLDER_PERMISSIONS,
    DriveFolderMember,
    DriveFolderShare,
)
from app.models.folder import Folder
from app.models.member import Member
from app.utils.datetime_utils import to_naive_datetime

logger = logging.getLogger("microbubble.drive_share")


# ===== 常量 =====
DEFAULT_SHARE_EXPIRES_DAYS = 7      # 默认 7 天过期
MAX_SHARE_EXPIRES_DAYS = 365         # 上限 365 天
SHARE_TOKEN_BYTES = 32               # 32 字节 = 43 字符 url-safe base64


class DriveShareServiceError(Exception):
    """业务级错误，调用方映射成 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _validate_permission(permission: str) -> None:
    """校验 permission 在合法枚举中"""
    if permission not in VALID_FOLDER_PERMISSIONS:
        raise DriveShareServiceError(
            f"非法 permission '{permission}', 必须是 {'/'.join(VALID_FOLDER_PERMISSIONS)}",
            status_code=400,
        )


def _validate_expires_days(expires_days: int) -> None:
    """校验过期天数 1-365"""
    if expires_days < 1 or expires_days > MAX_SHARE_EXPIRES_DAYS:
        raise DriveShareServiceError(
            f"expires_days {expires_days} 超出范围 [1, {MAX_SHARE_EXPIRES_DAYS}]",
            status_code=400,
        )


async def _check_folder_share_authority(
    db: AsyncSession, folder_id: int, user_id: int, *, require_admin: bool = True
) -> Tuple[Folder, str]:
    """校验用户对 folder 的分享权限

    Args:
        require_admin: True (默认) = 需要 admin 权限 (owner 隐含 admin)
                       False = 仅需 folder 存在 + 不在回收站

    Returns:
        (folder, effective_permission)
        effective_permission 是该用户在此 folder 的有效权限:
        - 'admin' if owner
        - 'admin'/'write'/'read' if in DriveFolderMember
        - 'public' if folder.visibility == 'public' (任何人都可读)

    Raises:
        DriveShareServiceError(404) if folder not found
        DriveShareServiceError(403) if user lacks permission
    """
    folder = (await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.deleted_at.is_(None),
        )
    )).scalar_one_or_none()
    if folder is None:
        raise DriveShareServiceError(
            f"Folder id={folder_id} 不存在或已删除", status_code=404
        )

    # owner 永远 admin
    if folder.owner_id == user_id:
        return folder, "admin"

    # 批次① B5: 2026-09-05 角色扁平化 + 单一团队空间 — 任何在世成员隐含 admin。
    # 对齐 file 级先例 (drive_files.py create_share_link: owner 门禁已删全员可分享)
    # 与 alembic 132 (Member.role 归一) 口径; DriveFolderMember permission 列降级为
    # 记录机制 (与 folder 协作者名单扁平化决策一致), 不再构成分享操作的上限。
    # 在世判定: Member 无 deleted_at 列, 用 is_active (与 get_current_user 禁号口径
    # 一致) — 已禁/已删号成员不享受隐含 admin, 继续走 member 行 / 403 老路径。
    alive = (await db.execute(
        select(Member.id).where(
            Member.id == user_id,
            Member.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if alive is not None:
        return folder, "admin"

    # 检查 DriveFolderMember
    member_row = (await db.execute(
        select(DriveFolderMember).where(
            DriveFolderMember.folder_id == folder_id,
            DriveFolderMember.member_id == user_id,
        )
    )).scalar_one_or_none()
    if member_row is not None:
        if require_admin and member_row.permission != "admin":
            raise DriveShareServiceError(
                f"无权分享该 folder (当前权限 '{member_row.permission}', 需要 'admin')",
                status_code=403,
            )
        return folder, member_row.permission

    # 非 owner + 非 member → 仅当 folder.visibility == 'public' 且 require_admin=False 时可访问
    if folder.visibility == "public" and not require_admin:
        return folder, "read"

    raise DriveShareServiceError(
        "无权操作该 folder", status_code=403
    )


class DriveShareService:
    """Folder share + member 管理"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 公开分享链接
    # ==========================================================================

    async def create_folder_share(
        self,
        folder_id: int,
        user_id: int,
        *,
        permission: str = "read",
        expires_days: int = DEFAULT_SHARE_EXPIRES_DAYS,
        password: Optional[str] = None,
        max_downloads: Optional[int] = None,
    ) -> DriveFolderShare:
        """创建 folder 公开分享链接 (owner / admin member only)

        Args:
            folder_id: 目标 folder
            user_id: 创建者 (folder owner 或 admin member)
            permission: read | write | admin (链接访问者权限)
            expires_days: 1-365
            password: 4-8 位数字提取码 (W72-B-1 差量, None = 无密码)
            max_downloads: 下载次数上限 (W72-B-1 差量, None = 不限)

        Returns:
            DriveFolderShare (含 share_token, expires_at, password_hash, max_downloads)

        Raises:
            DriveShareServiceError on validation / not-found / forbidden
        """
        _validate_permission(permission)
        _validate_expires_days(expires_days)

        # W72 第 2 批 B-1 差量: password 格式校验 (4-8 位数字)
        if password is not None:
            if not password.isdigit() or not (4 <= len(password) <= 8):
                raise DriveShareServiceError(
                    "password 必须是 4-8 位数字 (None = 无密码保护)",
                    status_code=400,
                )

        # W72 第 2 批 B-1 差量: max_downloads 范围校验 (1-10000)
        if max_downloads is not None and not (1 <= max_downloads <= 10000):
            raise DriveShareServiceError(
                f"max_downloads {max_downloads} 超出范围 [1, 10000]",
                status_code=400,
            )

        folder, _ = await _check_folder_share_authority(
            self.db, folder_id, user_id, require_admin=True
        )

        # 32 字节 url-safe base64 = 43 字符
        token = secrets.token_urlsafe(SHARE_TOKEN_BYTES)

        now_utc = datetime.now(timezone.utc)
        expires_at_naive = to_naive_datetime(
            now_utc + timedelta(days=expires_days)
        )

        # W72 第 2 批 B-1 差量: password 哈希 (SHA256, 与 drive_service.py _hash_share_password 同模式)
        # 走 SHA256 而非 bcrypt: 4-8 位数字密码太短, bcrypt 72-byte 上限 + 兼容性问题不必要
        password_hash = None
        if password is not None:
            import hashlib
            password_hash = hashlib.sha256(
                f"drive_share_v1:{password}".encode("utf-8")
            ).hexdigest()

        share = DriveFolderShare(
            folder_id=folder_id,
            share_token=token,
            permission=permission,
            expires_at=expires_at_naive,
            created_by=user_id,
            password_hash=password_hash,        # W72-B-1 差量
            max_downloads=max_downloads,         # W72-B-1 差量
            download_count=0,                    # W72-B-1 差量 (server_default 兜底)
        )
        self.db.add(share)
        await self.db.commit()
        await self.db.refresh(share)

        # W72 第 2 批 B-1 差量: 审计 (复用 audit_service, 不重复实现)
        try:
            from app.services.audit_service import audit_service
            await audit_service.log(
                self.db,
                user_id=user_id,
                ip_address="",
                user_agent="",
                method="CREATE",
                path=f"/api/v1/drive/folders/{folder_id}/share",
                action="share_created",
                resource_type="folder_share",
                resource_id=str(share.id),
                status_code=200,
                duration_ms=0,
                metadata={
                    "folder_id": folder_id,
                    "permission": permission,
                    "expires_days": expires_days,
                    "has_password": password is not None,
                    "max_downloads": max_downloads,
                },
            )
        except Exception as e:
            logger.warning(f"[DriveShareService.create_folder_share] 审计失败: {e}")

        logger.info(
            f"[DriveShareService.create_folder_share] folder_id={folder_id} "
            f"token={token[:8]}... permission={permission} "
            f"expires={share.expires_at} created_by={user_id} "
            f"has_password={password is not None} max_downloads={max_downloads}"
        )
        return share

    async def get_folder_by_share_token(
        self, token: str, password: Optional[str] = None
    ) -> Optional[Tuple[Folder, DriveFolderShare, List[dict], List[dict]]]:
        """通过 token 公开访问 (无登录)

        W72 第 2 批 B-1 差量:
        - password 校验 (有 password_hash 必须传 password 验证, 否则 403)
        - download_count < max_downloads 校验 (次数超限返 None)

        Args:
            token: 分享链接 token
            password: 提取码 (仅当 link 有密码时需要, None = 不验证)

        Returns:
            None: token 不存在 / 已撤销 / 已过期 / 密码错 / 次数超限
            (folder, share, files, subfolders) tuple

        Raises:
            DriveShareServiceError on internal error (空 token 等)
        """
        if not token:
            return None
        share = (await self.db.execute(
            select(DriveFolderShare).where(
                DriveFolderShare.share_token == token,
            )
        )).scalar_one_or_none()
        if share is None:
            logger.info(f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... 不存在")
            return None

        # 撤销校验
        if share.revoked_at is not None:
            logger.info(
                f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... 已撤销 "
                f"revoked_at={share.revoked_at}"
            )
            return None

        # 过期校验 (统一 naive UTC 比较)
        if share.expires_at is not None:
            expires_naive = share.expires_at
            if expires_naive.tzinfo is not None:
                expires_naive = expires_naive.replace(tzinfo=None)
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            if expires_naive < now_naive:
                logger.info(
                    f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... 已过期 "
                    f"expires={expires_naive} now={now_naive}"
                )
                return None

        # W72 第 2 批 B-1 差量: 密码校验 (SHA256 hash 比对, 与 drive_service.py 一致)
        if share.password_hash is not None:
            if password is None or password == "":
                logger.info(
                    f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... "
                    f"需要密码但未提供"
                )
                return None
            import hashlib
            expected = hashlib.sha256(
                f"drive_share_v1:{password}".encode("utf-8")
            ).hexdigest()
            if expected != share.password_hash:
                logger.info(
                    f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... 密码错误"
                )
                return None

        # W72 第 2 批 B-1 差量: 次数校验 (超限即失效)
        if share.max_downloads is not None and share.download_count >= share.max_downloads:
            logger.info(
                f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... "
                f"下载次数超限 ({share.download_count}/{share.max_downloads})"
            )
            return None

        folder = (await self.db.execute(
            select(Folder).where(
                Folder.id == share.folder_id,
                Folder.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if folder is None:
            logger.warning(
                f"[DriveShareService.get_folder_by_share_token] token={token[:8]}... "
                f"folder_id={share.folder_id} 已不存在"
            )
            return None

        # W72 第 2 批 B-1 差量: 审计 share_downloaded
        try:
            from app.services.audit_service import audit_service
            await audit_service.log(
                self.db,
                user_id=None,  # 公开访问无 user
                ip_address="",
                user_agent="",
                method="GET",
                path=f"/api/v1/drive/folders/share/{token}",
                action="share_downloaded",
                resource_type="folder_share",
                resource_id=str(share.id),
                status_code=200,
                duration_ms=0,
                metadata={
                    "folder_id": share.folder_id,
                    "download_count": share.download_count + 1,  # 即将自增
                },
            )
        except Exception as e:
            logger.warning(f"[DriveShareService.get_folder_by_share_token] 审计失败: {e}")

        # 拉 folder 下文件 (drive 模式 + 未删)
        from app.models.knowledge import Knowledge  # 避免循环 import
        files_stmt = select(Knowledge).where(
            Knowledge.folder_id == folder.id,
            Knowledge.storage_mode == "drive",
            Knowledge.deleted_at.is_(None),
        ).order_by(Knowledge.created_at.desc())
        files_rows = (await self.db.execute(files_stmt)).scalars().all()
        files = [
            {
                "id": f.id,
                "file_name": f.file_name,
                "file_size": f.file_size,
                "file_type": f.file_type,
                "visibility": f.visibility,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files_rows
        ]

        # 拉子 folder
        subfolders_stmt = select(Folder).where(
            Folder.parent_id == folder.id,
            Folder.deleted_at.is_(None),
        ).order_by(Folder.created_at.asc())
        subfolder_rows = (await self.db.execute(subfolders_stmt)).scalars().all()
        subfolders = [
            {
                "id": sf.id,
                "name": sf.name,
                "depth": sf.depth,
                "visibility": sf.visibility,
                "created_at": sf.created_at.isoformat() if sf.created_at else None,
            }
            for sf in subfolder_rows
        ]

        return folder, share, files, subfolders

    async def increment_download_count(
        self, share_id: int
    ) -> int:
        """原子自增 download_count (W72-B-1 差量, 公开下载后调用)

        Args:
            share_id: DriveFolderShare.id

        Returns:
            自增后的 download_count

        Notes:
        - 走 SQL UPDATE ... SET download_count = download_count + 1 (原子)
        - 超限返 -1 (不更新), 调用方应不再继续下载
        """
        # 先查当前 share
        share = (await self.db.execute(
            select(DriveFolderShare).where(DriveFolderShare.id == share_id)
        )).scalar_one_or_none()
        if share is None:
            return -1
        # 超限则不更新
        if share.max_downloads is not None and share.download_count >= share.max_downloads:
            return -1

        # 原子自增 (PR2.7 Knowledge.download_count 同模式)
        from sqlalchemy import update as sql_update
        result = await self.db.execute(
            sql_update(DriveFolderShare)
            .where(DriveFolderShare.id == share_id)
            .values(download_count=DriveFolderShare.download_count + 1)
            .returning(DriveFolderShare.download_count)
        )
        new_count = result.scalar_one_or_none()
        await self.db.commit()
        return int(new_count) if new_count is not None else -1

    async def revoke_folder_share(
        self,
        share_id: int,
        user_id: int,
    ) -> bool:
        """撤销 share 链接 (owner / admin only)

        Returns:
            True: 成功
            False: share 不存在或非 owner/admin
        """
        share = (await self.db.execute(
            select(DriveFolderShare).where(DriveFolderShare.id == share_id)
        )).scalar_one_or_none()
        if share is None:
            return False

        # 越权校验
        await _check_folder_share_authority(
            self.db, share.folder_id, user_id, require_admin=True
        )

        if share.revoked_at is None:
            share.revoked_at = to_naive_datetime(datetime.now(timezone.utc))
            await self.db.commit()

            # W72 第 2 批 B-1 差量: 审计 share_revoked
            try:
                from app.services.audit_service import audit_service
                await audit_service.log(
                    self.db,
                    user_id=user_id,
                    ip_address="",
                    user_agent="",
                    method="DELETE",
                    path=f"/api/v1/drive/folders/share/{share.id}",
                    action="share_revoked",
                    resource_type="folder_share",
                    resource_id=str(share.id),
                    status_code=200,
                    duration_ms=0,
                    metadata={
                        "folder_id": share.folder_id,
                        "revoked_at": share.revoked_at.isoformat(),
                    },
                )
            except Exception as e:
                logger.warning(f"[DriveShareService.revoke_folder_share] 审计失败: {e}")

            logger.info(
                f"[DriveShareService.revoke_folder_share] share_id={share_id} "
                f"by user_id={user_id}"
            )
        return True

    # ==========================================================================
    # 邀请成员
    # ==========================================================================

    async def add_folder_member(
        self,
        folder_id: int,
        inviter_id: int,
        member_id: int,
        *,
        permission: str = "read",
    ) -> DriveFolderMember:
        """邀请成员 (owner / admin only)

        Args:
            folder_id: 目标 folder
            inviter_id: 邀请人 (folder owner / admin)
            member_id: 被邀请成员
            permission: read | write | admin

        Returns:
            DriveFolderMember (新建或更新)

        Notes:
            幂等: 重复邀请同 member + folder → 更新 permission + 返回
            不能邀请 folder.owner (owner 隐含 admin, 邀请无意义 → 400)
            不能邀请自己 (inviter_id == member_id → 400)
        """
        _validate_permission(permission)

        if inviter_id == member_id:
            raise DriveShareServiceError(
                "不能邀请自己为成员 (folder owner 隐含 admin 权限)",
                status_code=400,
            )

        # 校验 inviter 权限 + folder 存在
        folder, _ = await _check_folder_share_authority(
            self.db, folder_id, inviter_id, require_admin=True
        )

        # 不能邀请 folder owner
        if folder.owner_id == member_id:
            raise DriveShareServiceError(
                "folder owner 已是 admin, 无需重复邀请",
                status_code=400,
            )

        # 校验 member 存在
        member = (await self.db.execute(
            select(Member).where(Member.id == member_id)
        )).scalar_one_or_none()
        if member is None:
            raise DriveShareServiceError(
                f"member id={member_id} 不存在", status_code=404
            )

        # 幂等: 查现有
        existing = (await self.db.execute(
            select(DriveFolderMember).where(
                DriveFolderMember.folder_id == folder_id,
                DriveFolderMember.member_id == member_id,
            )
        )).scalar_one_or_none()

        if existing is not None:
            existing.permission = permission
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(
                f"[DriveShareService.add_folder_member] UPDATE folder_id={folder_id} "
                f"member_id={member_id} permission={permission} by inviter={inviter_id}"
            )
            return existing

        new_member = DriveFolderMember(
            folder_id=folder_id,
            member_id=member_id,
            permission=permission,
            invited_by=inviter_id,
        )
        self.db.add(new_member)
        await self.db.commit()
        await self.db.refresh(new_member)

        logger.info(
            f"[DriveShareService.add_folder_member] CREATE folder_id={folder_id} "
            f"member_id={member_id} permission={permission} by inviter={inviter_id}"
        )
        return new_member

    async def remove_folder_member(
        self,
        folder_id: int,
        remover_id: int,
        member_id: int,
    ) -> bool:
        """移除成员 (owner / admin only)

        Returns:
            True: 成功删除
            False: 成员邀请不存在

        Notes:
            - folder owner 不能被移除 (用 400 拦掉, owner 隐含 admin)
            - 不能移除自己 (remover_id == member_id → 400, 防止误操作把自己踢了)
        """
        if remover_id == member_id:
            raise DriveShareServiceError(
                "不能移除自己 (folder owner 隐含 admin, 无需被邀请)",
                status_code=400,
            )

        # 校验 remover 权限 + folder 存在
        folder, _ = await _check_folder_share_authority(
            self.db, folder_id, remover_id, require_admin=True
        )

        # 不能移除 folder owner
        if folder.owner_id == member_id:
            raise DriveShareServiceError(
                "folder owner 是隐含 admin, 不能被移除",
                status_code=400,
            )

        existing = (await self.db.execute(
            select(DriveFolderMember).where(
                DriveFolderMember.folder_id == folder_id,
                DriveFolderMember.member_id == member_id,
            )
        )).scalar_one_or_none()

        if existing is None:
            return False

        await self.db.delete(existing)
        await self.db.commit()

        logger.info(
            f"[DriveShareService.remove_folder_member] folder_id={folder_id} "
            f"member_id={member_id} by remover={remover_id}"
        )
        return True

    async def list_folder_members(
        self, folder_id: int, user_id: int
    ) -> List[DriveFolderMember]:
        """列 folder 已邀请成员 (owner / admin only)

        Raises:
            DriveShareServiceError on forbidden
        """
        await _check_folder_share_authority(
            self.db, folder_id, user_id, require_admin=False
        )
        rows = (await self.db.execute(
            select(DriveFolderMember).where(
                DriveFolderMember.folder_id == folder_id,
            ).order_by(DriveFolderMember.created_at.desc())
        )).scalars().all()
        return list(rows)

    async def list_user_shared_folders(
        self, user_id: int
    ) -> List[int]:
        """列用户被邀请的所有 folder_id (用于前端「我被分享的」视图)

        Returns:
            list of folder_id (去重)

        Notes:
            不含 user 自己 owned 的 folder (owner 隐含)
        """
        rows = (await self.db.execute(
            select(DriveFolderMember.folder_id).where(
                DriveFolderMember.member_id == user_id,
            ).distinct()
        )).scalars().all()
        return list(rows)

    # ==========================================================================
    # 权限查询 (供 DriveService / folder_service 复用)
    # ==========================================================================

    async def get_user_folder_permission(
        self, folder_id: int, user_id: int
    ) -> Optional[str]:
        """获取用户对 folder 的有效权限

        Returns:
            'admin' | 'write' | 'read' | None (None = 无权限或 folder 不存在)

        Notes:
            - folder.owner 永远 admin
            - DriveFolderMember 表存在的 member 拿对应 permission
            - folder.visibility == 'public' 时所有人 read (但不写表)
            - 否则 None
        """
        folder = (await self.db.execute(
            select(Folder).where(
                Folder.id == folder_id,
                Folder.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if folder is None:
            return None

        if folder.owner_id == user_id:
            return "admin"

        member_row = (await self.db.execute(
            select(DriveFolderMember).where(
                DriveFolderMember.folder_id == folder_id,
                DriveFolderMember.member_id == user_id,
            )
        )).scalar_one_or_none()
        if member_row is not None:
            return member_row.permission

        if folder.visibility == "public":
            return "read"

        return None


__all__ = [
    "DriveShareService",
    "DriveShareServiceError",
    "DEFAULT_SHARE_EXPIRES_DAYS",
    "MAX_SHARE_EXPIRES_DAYS",
    "SHARE_TOKEN_BYTES",
]