"""Drive v2 PR18 — Team Folder Service (2026-07-24, W68 第 14 批 B-2)

5 个公开方法:
- create_team_folder(db, name, owner_id, member_ids, visibility='team') -> TeamFolder
- add_member(db, team_folder_id, actor_id, target_user_id) -> TeamFolder
- remove_member(db, team_folder_id, actor_id, target_user_id) -> bool
- record_audit(db, team_folder_id, actor_id, action, target_type, target_id, extra=None) -> AuditLog
- list_audit(db, team_folder_id, page=1, page_size=20, actor_id=None, action=None,
             target_type=None, since=None, until=None) -> Tuple[List[AuditLog], int]

4 维审计铁律 (CLAUDE.md 2026-07-24 v78 audit_log 模式):
- write action: create / add_member / remove_member / 文件写操作 调用时自动写
- share action: add_member 调用时同时写 (PR18 团队共享盘 share 语义)
- restore action: 软删的 restore 调用时写 (本期未实现 restore, 留接口)
- delete action: remove_member 调用时写 (成员被踢出)
- read action: 后续 PR (folder detail / file list) 高频操作, 本期留接口

不破坏的边界:
- 不动 drive_folder_share / drive_folder_members (PR7 老机制保持不变)
- 不动 DriveComment / DriveFileVersion 等其他 drive_* 表
- 不动 Folder 主表 (team folder 是独立域, 不与个人 folder 共享 path)
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models.member import Member
from app.models.team_folder import (
    TeamFolder,
    TeamFolderAuditLog,
    VALID_TEAM_FOLDER_AUDIT_ACTIONS,
    VALID_TEAM_FOLDER_AUDIT_TARGETS,
    VALID_TEAM_FOLDER_VISIBILITIES,
)

logger = logging.getLogger(__name__)


# === 审计 action 常量 (4 维, 与 model + schemas + alembic 同步) ===
class AuditAction:
    """5 种合法审计动作 (CLAUDE.md 2026-07-24 v78 audit_log 模式)"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SHARE = "share"
    RESTORE = "restore"

    ALL: tuple = VALID_TEAM_FOLDER_AUDIT_ACTIONS


class AuditTarget:
    """4 种合法审计对象类型"""
    FOLDER = "folder"
    FILE = "file"
    MEMBER = "member"
    PERMISSION = "permission"

    ALL: tuple = VALID_TEAM_FOLDER_AUDIT_TARGETS


class TeamFolderServiceError(Exception):
    """Team Folder 业务异常 (包装 422/403/404 各种情况)"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class TeamFolderService:
    """团队共享盘 (Team Folder) 服务层 — PR18 (W68 第 14 批 B-2)"""

    # ============================================================
    # CRUD: create_team_folder
    # ============================================================

    @staticmethod
    async def create_team_folder(
        db: AsyncSession,
        *,
        name: str,
        owner_id: int,
        initial_member_ids: Optional[List[int]] = None,
        visibility: str = "team",
    ) -> TeamFolder:
        """创建团队共享盘

        Args:
            db: AsyncSession
            name: team folder 名 (1-200 字符)
            owner_id: 创建者 member ID (从 JWT 来)
            initial_member_ids: 初始邀请成员 ID 列表 (可选, 默认 [])
            visibility: private/team/public (默认 team)

        Returns:
            创建成功的 TeamFolder ORM 对象

        Raises:
            ValidationException: name/visibility 非法
            NotFoundException: owner_id 对应的 member 不存在
        """
        # 1. 校验 name
        if not name or len(name) > 200:
            raise ValidationException(
                message=f"name 长度必须 1-200 字符, 实际 {len(name or '')}",
                field="name",
            )
        # 2. 校验 visibility
        if visibility not in VALID_TEAM_FOLDER_VISIBILITIES:
            raise ValidationException(
                message=f"visibility 必须 {VALID_TEAM_FOLDER_VISIBILITIES} 之一, 实际 '{visibility}'",
                field="visibility",
            )
        # 3. 校验 owner 存在
        owner = await db.get(Member, owner_id)
        if not owner:
            raise NotFoundException(resource="Member", resource_id=owner_id)

        # 4. 校验 initial_member_ids (去重 + 都存在)
        clean_member_ids: List[int] = []
        if initial_member_ids:
            seen = set()
            for mid in initial_member_ids:
                if mid in seen or mid == owner_id:
                    continue  # 跳过重复和 owner 自己
                if mid <= 0:
                    continue
                seen.add(mid)
                clean_member_ids.append(mid)
            if clean_member_ids:
                existing = await db.execute(
                    select(Member.id).where(Member.id.in_(clean_member_ids))
                )
                valid_ids = {row[0] for row in existing.all()}
                clean_member_ids = [mid for mid in clean_member_ids if mid in valid_ids]

        # 5. 创建 TeamFolder
        team_folder = TeamFolder(
            name=name,
            owner_id=owner_id,
            member_ids=clean_member_ids,
            visibility=visibility,
        )
        db.add(team_folder)
        await db.flush()  # 拿 id

        # 6. 记录 audit_log (write action: target_type=folder)
        await TeamFolderService.record_audit(
            db,
            team_folder_id=team_folder.id,
            actor_id=owner_id,
            action=AuditAction.WRITE,
            target_type=AuditTarget.FOLDER,
            target_id=str(team_folder.id),
            extra={"operation": "create", "name": name, "visibility": visibility},
        )
        # 7. 记录 audit_log (share action: 每个 invited member 写一条)
        for mid in clean_member_ids:
            await TeamFolderService.record_audit(
                db,
                team_folder_id=team_folder.id,
                actor_id=owner_id,
                action=AuditAction.SHARE,
                target_type=AuditTarget.MEMBER,
                target_id=f"member:{mid}",
                extra={"operation": "create_invite", "permission": "read"},
            )

        await db.commit()
        await db.refresh(team_folder)
        logger.info(
            "team_folder %s created by member=%s, members=%s",
            team_folder.id, owner_id, clean_member_ids,
        )
        return team_folder

    # ============================================================
    # MEMBER: add_member + remove_member
    # ============================================================

    @staticmethod
    async def add_member(
        db: AsyncSession,
        *,
        team_folder_id: int,
        actor_id: int,
        target_user_id: int,
        permission: str = "read",
    ) -> TeamFolder:
        """添加成员到 team folder

        权限校验: 只有 owner 或 admin 可邀请成员 (本 PR 简化: 仅 owner)

        Args:
            db: AsyncSession
            team_folder_id: team folder ID
            actor_id: 操作者 ID (邀请发起人, 需是 owner)
            target_user_id: 被邀请者 ID
            permission: read/write (默认 read, 仅记录在 audit extra, 本期不校验)

        Returns:
            更新后的 TeamFolder

        Raises:
            NotFoundException: team_folder 或 target_user 不存在
            ForbiddenException: actor 不是 owner
            ValidationException: 成员已存在 / actor 是 owner 自己
        """
        team_folder = await db.get(TeamFolder, team_folder_id)
        if not team_folder or team_folder.deleted_at is not None:
            raise NotFoundException(resource="TeamFolder", resource_id=team_folder_id)

        if team_folder.owner_id != actor_id:
            raise ForbiddenException(
                message=f"只有 owner (id={team_folder.owner_id}) 可以邀请成员, actor={actor_id}",
            )

        if actor_id == target_user_id:
            raise ValidationException(
                message="不能邀请 owner 自己",
                field="target_user_id",
            )

        target_member = await db.get(Member, target_user_id)
        if not target_member:
            raise NotFoundException(resource="Member", resource_id=target_user_id)

        if target_user_id in (team_folder.member_ids or []):
            raise ValidationException(
                message=f"成员 {target_user_id} 已在 team folder {team_folder_id} 中",
                field="target_user_id",
            )

        # 更新 member_ids (PG ARRAY mutate 后必须 flag_modified)
        new_member_ids = list(team_folder.member_ids or []) + [target_user_id]
        team_folder.member_ids = new_member_ids
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(team_folder, "member_ids")

        # 写 audit (write + share 两条)
        await TeamFolderService.record_audit(
            db,
            team_folder_id=team_folder_id,
            actor_id=actor_id,
            action=AuditAction.WRITE,
            target_type=AuditTarget.MEMBER,
            target_id=f"member:{target_user_id}",
            extra={"operation": "add_member", "permission": permission},
        )
        await TeamFolderService.record_audit(
            db,
            team_folder_id=team_folder_id,
            actor_id=actor_id,
            action=AuditAction.SHARE,
            target_type=AuditTarget.MEMBER,
            target_id=f"member:{target_user_id}",
            extra={"operation": "add_member_invite", "permission": permission},
        )

        await db.commit()
        await db.refresh(team_folder)
        logger.info(
            "team_folder %s +member %s by actor=%s",
            team_folder_id, target_user_id, actor_id,
        )
        return team_folder

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        *,
        team_folder_id: int,
        actor_id: int,
        target_user_id: int,
    ) -> bool:
        """从 team folder 移除成员

        权限校验: 只有 owner 可踢人 (本期简化)

        Returns:
            True (删除成功)

        Raises:
            NotFoundException / ForbiddenException / ValidationException
        """
        team_folder = await db.get(TeamFolder, team_folder_id)
        if not team_folder or team_folder.deleted_at is not None:
            raise NotFoundException(resource="TeamFolder", resource_id=team_folder_id)

        if team_folder.owner_id != actor_id:
            raise ForbiddenException(
                message=f"只有 owner (id={team_folder.owner_id}) 可以移除成员, actor={actor_id}",
            )

        if target_user_id not in (team_folder.member_ids or []):
            raise ValidationException(
                message=f"成员 {target_user_id} 不在 team folder {team_folder_id} 中",
                field="target_user_id",
            )

        # 更新 member_ids (flag_modified 防 PG ARRAY mutate 不持久)
        new_member_ids = [m for m in (team_folder.member_ids or []) if m != target_user_id]
        team_folder.member_ids = new_member_ids
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(team_folder, "member_ids")

        # 写 audit (delete action)
        await TeamFolderService.record_audit(
            db,
            team_folder_id=team_folder_id,
            actor_id=actor_id,
            action=AuditAction.DELETE,
            target_type=AuditTarget.MEMBER,
            target_id=f"member:{target_user_id}",
            extra={"operation": "remove_member"},
        )

        await db.commit()
        logger.info(
            "team_folder %s -member %s by actor=%s",
            team_folder_id, target_user_id, actor_id,
        )
        return True

    # ============================================================
    # AUDIT: record_audit (强制 4 维度) + list_audit (4 维过滤)
    # ============================================================

    @staticmethod
    async def record_audit(
        db: AsyncSession,
        *,
        team_folder_id: int,
        actor_id: int,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> TeamFolderAuditLog:
        """强制 4 维审计写入

        CLAUDE.md 2026-07-24 v78 audit_log 模式: read/write/delete/share + restore
        本方法是 service 层唯一审计入口, 任何"team folder 操作"必走这里

        Args:
            db: AsyncSession
            team_folder_id: 哪个 team folder (FK)
            actor_id: 谁做的 (FK members)
            action: 5 个合法枚举之一
            target_type: 4 个合法枚举之一
            target_id: 字符串 ID (允许 NULL, 如 read 类操作)
            extra: 5+ 结构化字段 (JSONB, 默认 None)

        Returns:
            创建的 TeamFolderAuditLog ORM
        """
        # 1. 校验 4 维参数
        if action not in AuditAction.ALL:
            raise ValidationException(
                message=f"action 必须 {AuditAction.ALL} 之一, 实际 '{action}'",
                field="action",
            )
        if target_type not in AuditTarget.ALL:
            raise ValidationException(
                message=f"target_type 必须 {AuditTarget.ALL} 之一, 实际 '{target_type}'",
                field="target_type",
            )

        # 2. 校验 actor_id 存在 (FK 兜底)
        actor = await db.get(Member, actor_id)
        if not actor:
            raise NotFoundException(resource="Member", resource_id=actor_id)

        # 3. 写入
        audit_log = TeamFolderAuditLog(
            team_folder_id=team_folder_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            extra=extra,
        )
        db.add(audit_log)
        await db.flush()
        await db.refresh(audit_log)
        # 注: 不 commit, 由调用方统一 commit (add_member 等已 commit)

        return audit_log

    @staticmethod
    async def list_audit(
        db: AsyncSession,
        *,
        team_folder_id: int,
        page: int = 1,
        page_size: int = 20,
        actor_id: Optional[int] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Tuple[List[TeamFolderAuditLog], int]:
        """查 team folder 审计日志 (4 维过滤 + 分页)

        Args:
            db: AsyncSession
            team_folder_id: 必填, 哪个 team folder
            page: 页码 (1-based)
            page_size: 每页条数 (1-100)
            actor_id: 可选 actor 过滤
            action: 可选 action 过滤 (5 种合法)
            target_type: 可选 target_type 过滤 (4 种合法)
            since/until: 时间范围

        Returns:
            (items, total) 元组
        """
        # 1. 校验 team_folder 存在
        team_folder = await db.get(TeamFolder, team_folder_id)
        if not team_folder or team_folder.deleted_at is not None:
            raise NotFoundException(resource="TeamFolder", resource_id=team_folder_id)

        # 2. 校验可选 enum 参数
        if action is not None and action not in AuditAction.ALL:
            raise ValidationException(
                message=f"action 必须 {AuditAction.ALL} 之一, 实际 '{action}'",
                field="action",
            )
        if target_type is not None and target_type not in AuditTarget.ALL:
            raise ValidationException(
                message=f"target_type 必须 {AuditTarget.ALL} 之一, 实际 '{target_type}'",
                field="target_type",
            )

        # 3. 构造过滤条件
        conditions = [TeamFolderAuditLog.team_folder_id == team_folder_id]
        if actor_id is not None:
            conditions.append(TeamFolderAuditLog.actor_id == actor_id)
        if action is not None:
            conditions.append(TeamFolderAuditLog.action == action)
        if target_type is not None:
            conditions.append(TeamFolderAuditLog.target_type == target_type)
        if since is not None:
            conditions.append(TeamFolderAuditLog.created_at >= since)
        if until is not None:
            conditions.append(TeamFolderAuditLog.created_at <= until)

        where_clause = and_(*conditions)

        # 4. 计数
        count_query = select(func.count()).select_from(TeamFolderAuditLog).where(where_clause)
        total = (await db.execute(count_query)).scalar_one()

        # 5. 分页拉数据 (按 created_at DESC)
        offset = (page - 1) * page_size
        list_query = (
            select(TeamFolderAuditLog)
            .where(where_clause)
            .order_by(desc(TeamFolderAuditLog.created_at), desc(TeamFolderAuditLog.id))
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(list_query)
        items = list(result.scalars().all())

        return items, total


# ============================================================
# 模块级便捷函数 (API 层可能直接调用)
# ============================================================


async def create_team_folder(
    db: AsyncSession,
    name: str,
    owner_id: int,
    member_ids: Optional[List[int]] = None,
    visibility: str = "team",
) -> TeamFolder:
    """便捷函数 — 同 TeamFolderService.create_team_folder"""
    return await TeamFolderService.create_team_folder(
        db,
        name=name,
        owner_id=owner_id,
        initial_member_ids=member_ids,
        visibility=visibility,
    )


async def add_member(
    db: AsyncSession,
    team_folder_id: int,
    actor_id: int,
    target_user_id: int,
    permission: str = "read",
) -> TeamFolder:
    """便捷函数 — 同 TeamFolderService.add_member"""
    return await TeamFolderService.add_member(
        db,
        team_folder_id=team_folder_id,
        actor_id=actor_id,
        target_user_id=target_user_id,
        permission=permission,
    )


async def remove_member(
    db: AsyncSession,
    team_folder_id: int,
    actor_id: int,
    target_user_id: int,
) -> bool:
    """便捷函数 — 同 TeamFolderService.remove_member"""
    return await TeamFolderService.remove_member(
        db,
        team_folder_id=team_folder_id,
        actor_id=actor_id,
        target_user_id=target_user_id,
    )


async def record_audit(
    db: AsyncSession,
    team_folder_id: int,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    extra: Optional[dict] = None,
) -> TeamFolderAuditLog:
    """便捷函数 — 同 TeamFolderService.record_audit"""
    return await TeamFolderService.record_audit(
        db,
        team_folder_id=team_folder_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        extra=extra,
    )


async def list_audit(
    db: AsyncSession,
    team_folder_id: int,
    page: int = 1,
    page_size: int = 20,
    actor_id: Optional[int] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> Tuple[List[TeamFolderAuditLog], int]:
    """便捷函数 — 同 TeamFolderService.list_audit"""
    return await TeamFolderService.list_audit(
        db,
        team_folder_id=team_folder_id,
        page=page,
        page_size=page_size,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        since=since,
        until=until,
    )


__all__ = [
    "AuditAction",
    "AuditTarget",
    "TeamFolderService",
    "TeamFolderServiceError",
    "create_team_folder",
    "add_member",
    "remove_member",
    "record_audit",
    "list_audit",
]
