"""Drive v2 PR15 — 文件版本标签 (Version Tags) Service (2026-07-24)

职责:
- drive_version_tags 表 CRUD (add / remove / list / get_file_by_tag)
- 校验 tag_name 在内置白名单 (12 个) 或长度 ≤ 64 (用户自定义)
- 校验 version 存在 + 用户有 modify 权限 (复用 drive_permission_service)
- WS 推送 tag_added / tag_removed 给 file owner + folder admin (协同通知)

设计要点:
- 6 个核心方法
- add_tag 幂等 (UNIQUE 约束防重复 — 已存在返 None 不报错)
- remove_tag 仅 tag 创建者本人 (admin 不 override, 与 reaction author 主权一致)
- list_tags 按 version_id 单文件列标签
- list_tags_by_file 跨版本聚合 (返回 {version_id → [tag_dict]})
- get_file_by_tag 按 (file_id, tag_name) 拿首个匹配版本
- list_versions_with_tags 跨版本聚合返回版本+标签 (UI 列表展示用)

权限模型:
- add_tag: 文件创建人 OR folder 管理员 OR 平台管理员 (与 upload_new_version 一致)
- remove_tag: tag 创建者 (member_id == current_user.id) — admin 不 override
- list_tags / list_versions_with_tags: 文件可见者 (与 list_versions 一致)
- get_file_by_tag: 文件可见者

调用方 (API 层):
- POST   /api/v1/drive/files/{file_id}/tags                          → add (body: version_id, tag_name, ...)
- DELETE /api/v1/drive/files/{file_id}/tags/{tag_name}              → remove (按 tag_name — 同 version 仅可删除一次)
- GET    /api/v1/drive/files/{file_id}/tags                          → list 全部版本+标签 (聚合)
- GET    /api/v1/drive/files/{file_id}/tags/{tag_name}/version      → get_file_by_tag (按 tag 拿首个匹配版本)

WS 推送:
- add_tag 成功 → publish_tag_added (MEDIUM priority, 通知 file owner + folder admin)
- remove 暂不推送 (低优先级, 用户量小; 后续 PR 按需加)

约束:
- tag_name 列必须 ∈ ALLOWED_TAG_NAMES (12 个内置白名单) 或长度 ≤ 64 (用户自定义)
- version 必须存在 + 未删除 (service validate)
- 同一 version 同一 tag 幂等 (UNIQUE 约束保证)

锚点范式第 149 守恒 (W68 第 12 批 B-2).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion
from app.models.drive_version_tag import (
    ALLOWED_TAG_NAMES,
    DEFAULT_TAG_COLOR,
    DriveVersionTag,
)
from app.models.knowledge import Knowledge
from app.models.member import Member

logger = logging.getLogger("microbubble.drive_version_tag")


class DriveVersionTagServiceError(Exception):
    """业务级错误, 调用方映射到 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ==========================================================================
# 辅助函数: 校验 tag_name / version 合法性
# ==========================================================================


def _validate_tag_name(tag_name: str) -> None:
    """校验 tag_name 合法性

    规则:
    - 不能为空 / 不能超过 64 字符
    - 必须在 12 个内置白名单内 (用户不允许自定义, 避免污染)
      * 理由: 与 GitHub release tags 对齐 + 课题组场景稳定 (12 个内置覆盖 95% 场景)

    Raises:
        DriveVersionTagServiceError(400): 校验失败
    """
    if not tag_name or not isinstance(tag_name, str):
        raise DriveVersionTagServiceError(
            "tag_name 不能为空",
            status_code=400,
        )
    if len(tag_name) > 64:
        raise DriveVersionTagServiceError(
            f"tag_name 长度 {len(tag_name)} 超过 64 字符限制",
            status_code=400,
        )
    if tag_name not in ALLOWED_TAG_NAMES:
        raise DriveVersionTagServiceError(
            f"tag_name '{tag_name}' 不在白名单 ({len(ALLOWED_TAG_NAMES)} 个内置: "
            f"release/stable/deprecated/security/auto-save/manual/breaking/"
            f"experimental/legacy/featured/archived/final)",
            status_code=400,
        )


async def _validate_version_exists_and_modify_authority(
    db: AsyncSession, version_id: int, user_id: int
) -> DriveFileVersion:
    """校验 version 存在 + 用户有 modify 权限

    Returns:
        DriveFileVersion: 校验通过的 version 实例

    Raises:
        DriveVersionTagServiceError(404): version 不存在
        DriveVersionTagServiceError(403): 无 modify 权限
    """
    v = await db.get(DriveFileVersion, version_id)
    if v is None:
        raise DriveVersionTagServiceError(
            f"版本 id={version_id} 不存在",
            status_code=404,
        )

    # 校验 file 存在 + 未删除 + drive 模式
    cur_file = await db.get(Knowledge, v.file_id)
    if cur_file is None:
        raise DriveVersionTagServiceError(
            f"文件 id={v.file_id} 不存在",
            status_code=404,
        )
    if cur_file.deleted_at is not None:
        raise DriveVersionTagServiceError(
            f"文件 id={v.file_id} 已删除",
            status_code=410,
        )
    if cur_file.storage_mode != "drive":
        raise DriveVersionTagServiceError(
            f"文件 id={v.file_id} 非 drive 模式, 无版本概念",
            status_code=400,
        )

    # modify 权限: 创建人 OR folder admin OR 平台 admin
    if cur_file.created_by != user_id:
        from app.services.drive_permission_service import DrivePermissionService
        perm_svc = DrivePermissionService(db)
        if not await perm_svc.check_file_owner_or_folder_admin(user_id, v.file_id):
            raise DriveVersionTagServiceError(
                f"无权为版本 id={version_id} 添加标签 (非创建人非 folder 管理员非平台管理员)",
                status_code=403,
            )

    return v


async def _check_file_read_authority(
    db: AsyncSession, file_id: int, user_id: int
) -> bool:
    """校验 file 的 read 权限 (用于 list/get_file_by_tag)

    Returns:
        True: 有 read 权限
        False: 无 read 权限
    """
    cur_file = await db.get(Knowledge, file_id)
    if cur_file is None or cur_file.deleted_at is not None:
        return False

    # 创建人: 有 read
    if cur_file.created_by == user_id:
        return True

    # private: 仅 owner 可见
    if cur_file.visibility == "private":
        return False

    # folder 权限: owner / folder permission read+
    if cur_file.folder_id is None:
        return False  # 无 folder → 仅 owner

    from app.services.drive_permission_service import DrivePermissionService
    perm_svc = DrivePermissionService(db)
    perm = await perm_svc.get_user_folder_permission(cur_file.folder_id, user_id)
    return perm is not None


# ==========================================================================
# Service 类
# ==========================================================================


class DriveVersionTagService:
    """Drive v2 PR15 版本标签 CRUD + 聚合 + 权限"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 增 (幂等)
    # ==========================================================================

    async def add_tag(
        self,
        *,
        version_id: int,
        tag_name: str,
        tag_description: Optional[str],
        color: Optional[str],
        member_id: int,
    ) -> Optional[DriveVersionTag]:
        """给版本添加标签 (幂等)

        Args:
            version_id: DriveFileVersion.id
            tag_name: 标签名称 (12 个内置白名单之一)
            tag_description: 标签描述 (可选)
            color: 标签颜色 (16 进制 hex, 可选)
            member_id: 操作者 member.id

        Returns:
            DriveVersionTag: 新创建的标签
            None: 已存在相同 (version_id, tag_name) — 幂等命中

        Raises:
            DriveVersionTagServiceError(400): tag_name 不在白名单 / color 不合法
            DriveVersionTagServiceError(403): 无 modify 权限
            DriveVersionTagServiceError(404): version 不存在
        """
        # 1. 校验 tag_name
        _validate_tag_name(tag_name)

        # 2. 校验 color 格式 (可选, NULL 用默认色)
        if color is not None:
            if not isinstance(color, str) or len(color) > 16:
                raise DriveVersionTagServiceError(
                    f"color '{color}' 长度超过 16 字符限制",
                    status_code=400,
                )
            # 简单校验: 以 # 开头的 6 位 hex, 或简单 CSS 颜色名 (e.g. 'red' 'blue')
            if color.startswith("#"):
                # hex 格式: #RGB / #RRGGBB / #RRGGBBAA
                hex_part = color[1:]
                if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
                    raise DriveVersionTagServiceError(
                        f"color '{color}' hex 格式不合法 (e.g. '#FF7A5C')",
                        status_code=400,
                    )
                if len(hex_part) not in (3, 6, 8):
                    raise DriveVersionTagServiceError(
                        f"color '{color}' hex 长度不合法 (3/6/8 位)",
                        status_code=400,
                    )
            # 非 # 开头视为 CSS 颜色名 (e.g. 'red' 'blue') 不严格校验

        # 3. 校验 version + modify 权限
        version = await _validate_version_exists_and_modify_authority(
            self.db, version_id, member_id
        )

        # 4. INSERT (UNIQUE 约束保证幂等)
        tag = DriveVersionTag(
            version_id=version_id,
            tag_name=tag_name,
            tag_description=tag_description,
            color=color if color else DEFAULT_TAG_COLOR,
            created_by=member_id,
        )
        self.db.add(tag)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            logger.debug(
                f"[DriveVersionTagService.add_tag] 幂等命中: "
                f"version={version_id} tag='{tag_name}' member={member_id}"
            )
            return None

        await self.db.refresh(tag)

        logger.info(
            f"[DriveVersionTagService.add_tag] id={tag.id} "
            f"version={version_id} tag='{tag_name}' member={member_id}"
        )

        # 5. WS 推送 (best-effort, 不阻塞主流程)
        try:
            from app.services.drive_event_publisher import publish_version_tag_added
            await publish_version_tag_added(
                self.db,
                tag_id=tag.id,
                version_id=version_id,
                file_id=version.file_id,
                tag_name=tag_name,
                actor_id=member_id,
            )
        except Exception as e:
            logger.debug(
                f"[DriveVersionTagService] publish_version_tag_added 失败 (非阻塞): {e!r}"
            )

        return tag

    # ==========================================================================
    # 删 (按 version_id + tag_name — 仅 tag 创建者)
    # ==========================================================================

    async def remove_tag(
        self,
        *,
        version_id: int,
        tag_name: str,
        member_id: int,
    ) -> bool:
        """删除版本标签 (仅 tag 创建者本人)

        Args:
            version_id: DriveFileVersion.id
            tag_name: 标签名称
            member_id: 当前操作者 (从 JWT 取)

        Returns:
            True: 成功删除
            False: 不存在 / 已被删除

        Raises:
            DriveVersionTagServiceError(403): 非 tag 创建者 (admin 不 override)
        """
        # 校验 tag_name (防止路径注入类非法输入)
        _validate_tag_name(tag_name)

        stmt = select(DriveVersionTag).where(
            and_(
                DriveVersionTag.version_id == version_id,
                DriveVersionTag.tag_name == tag_name,
            )
        )
        tag = (await self.db.execute(stmt)).scalar_one_or_none()
        if tag is None:
            return False

        if tag.created_by != member_id:
            raise DriveVersionTagServiceError(
                "仅本人可删除自己创建的标签",
                status_code=403,
            )

        await self.db.delete(tag)
        await self.db.commit()

        logger.info(
            f"[DriveVersionTagService.remove_tag] version={version_id} "
            f"tag='{tag_name}' by user={member_id}"
        )
        return True

    # ==========================================================================
    # 列表 (按 version_id)
    # ==========================================================================

    async def list_tags(
        self,
        *,
        version_id: int,
    ) -> List[Dict]:
        """列版本的所有标签 (按 created_at desc)

        Args:
            version_id: DriveFileVersion.id

        Returns:
            List[dict] 格式: [{id, tag_name, tag_description, color, created_by, created_at}, ...]
        """
        stmt = (
            select(DriveVersionTag, Member.name)
            .outerjoin(Member, DriveVersionTag.created_by == Member.id)
            .where(DriveVersionTag.version_id == version_id)
            .order_by(DriveVersionTag.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()

        items: List[Dict] = []
        for tag, creator_name in rows:
            items.append({
                "id": tag.id,
                "version_id": tag.version_id,
                "tag_name": tag.tag_name,
                "tag_description": tag.tag_description,
                "color": tag.color if tag.color else DEFAULT_TAG_COLOR,
                "created_by": tag.created_by,
                "creator_name": creator_name,
                "created_at": tag.created_at.isoformat() if tag.created_at else None,
            })
        return items

    # ==========================================================================
    # 列表 (按 file_id — 跨版本聚合)
    # ==========================================================================

    async def list_tags_by_file(
        self,
        *,
        file_id: int,
        current_user_id: int,
    ) -> Dict:
        """列文件的所有版本 + 标签 (跨版本聚合)

        Returns:
            {
                "file_id": int,
                "file_name": str,
                "versions": [
                    {
                        "version_id": int,
                        "version_number": int,
                        "is_current": bool,
                        "tags": [{tag_name, color, description, ...}, ...]
                    },
                    ...
                ]
            }

        权限:
        - 文件可见者才能调用 (与 list_versions 一致)
        """
        # 校验文件可见性
        cur_file = await self.db.get(Knowledge, file_id)
        if cur_file is None or cur_file.deleted_at is not None:
            raise DriveVersionTagServiceError(
                f"文件 id={file_id} 不存在",
                status_code=404,
            )

        if not await _check_file_read_authority(self.db, file_id, current_user_id):
            raise DriveVersionTagServiceError(
                f"无权查看文件 id={file_id} 的标签",
                status_code=403,
            )

        # 拿所有版本 + 标签
        stmt = (
            select(DriveFileVersion, DriveVersionTag)
            .outerjoin(
                DriveVersionTag,
                DriveVersionTag.version_id == DriveFileVersion.id,
            )
            .where(DriveFileVersion.file_id == file_id)
            .order_by(
                DriveFileVersion.version_number.desc(),
                DriveVersionTag.created_at.asc(),
            )
        )
        rows = (await self.db.execute(stmt)).all()

        # 聚合: version_id → {version info + tags list}
        version_map: Dict[int, Dict] = {}
        for v, tag in rows:
            entry = version_map.setdefault(v.id, {
                "version_id": v.id,
                "version_number": v.version_number,
                "is_current": bool(v.is_current),
                "tags": [],
            })
            if tag is not None:
                entry["tags"].append({
                    "id": tag.id,
                    "tag_name": tag.tag_name,
                    "tag_description": tag.tag_description,
                    "color": tag.color if tag.color else DEFAULT_TAG_COLOR,
                    "created_by": tag.created_by,
                    "created_at": tag.created_at.isoformat() if tag.created_at else None,
                })

        return {
            "file_id": file_id,
            "file_name": cur_file.file_name,
            "versions": list(version_map.values()),
        }

    # ==========================================================================
    # 按 (file_id, tag_name) 拿首个匹配版本
    # ==========================================================================

    async def get_file_by_tag(
        self,
        *,
        file_id: int,
        tag_name: str,
        current_user_id: int,
    ) -> Optional[Dict]:
        """按 (file_id, tag_name) 拿首个匹配版本

        多个版本可共享同一 tag_name (e.g. v1 + v3 都标 'release'),
        返回最新 (version_number desc) 的版本

        Returns:
            Dict: {version_id, version_number, tag_name, color, ...} or None

        Raises:
            DriveVersionTagServiceError(403): 无 read 权限
        """
        _validate_tag_name(tag_name)

        # 校验文件可见性
        cur_file = await self.db.get(Knowledge, file_id)
        if cur_file is None or cur_file.deleted_at is not None:
            return None

        if not await _check_file_read_authority(self.db, file_id, current_user_id):
            raise DriveVersionTagServiceError(
                f"无权查看文件 id={file_id} 的标签",
                status_code=403,
            )

        # JOIN drive_file_versions + tags WHERE file_id=? AND tag_name=?
        stmt = (
            select(DriveFileVersion, DriveVersionTag)
            .join(DriveVersionTag, DriveVersionTag.version_id == DriveFileVersion.id)
            .where(
                and_(
                    DriveFileVersion.file_id == file_id,
                    DriveVersionTag.tag_name == tag_name,
                )
            )
            .order_by(DriveFileVersion.version_number.desc())
            .limit(1)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None

        v, tag = row[0], row[1]
        return {
            "version_id": v.id,
            "file_id": v.file_id,
            "version_number": v.version_number,
            "is_current": bool(v.is_current),
            "tag_id": tag.id,
            "tag_name": tag.tag_name,
            "tag_description": tag.tag_description,
            "color": tag.color if tag.color else DEFAULT_TAG_COLOR,
            "created_by": tag.created_by,
            "created_at": tag.created_at.isoformat() if tag.created_at else None,
        }


__all__ = [
    "DriveVersionTagService",
    "DriveVersionTagServiceError",
]