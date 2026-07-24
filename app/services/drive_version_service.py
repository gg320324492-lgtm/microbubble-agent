"""Drive v2 PR9 — File Version Service (2026-07-24)

功能: 文件版本管理 (上传新版本 / 列出版本 / 下载历史版 / 回滚 / 删除某版)

设计:
- 与 PR4 KnowledgeVersion (审计日志) 互补:
  * KnowledgeVersion = immutable audit log (每次 create_version/restore 调用一行)
  * DriveFileVersion = 历史版本仓库 (每版本一行, 含 minio_object_key)
- Knowledge 主表只保留**当前**版本 (file_path/file_size/version_number)
- 业务上, 第一次上传文件 → service 自动创建 v1 (is_current=1)
- 后续上传 → service 创建 v(N+1), 把旧 v(N) 的 is_current 翻 0, 更新 Knowledge 行的 file_path 等

权限模型:
- list / download: 走 DriveService._can_see_file (private 仅 owner)
- upload_new_version / rollback / delete: 创建人 OR folder 管理员 OR 平台管理员
- 删除中间版本: 不允许 (会悬空 rollback), 只能删最新非当前版本

调用方 (API 层):
- app/api/v1/drive_versions.py
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_permission_service import DrivePermissionService

logger = logging.getLogger(__name__)


# ============================================================
# 自定义异常 (与 DriveServiceError 兼容)
# ============================================================


class DriveVersionServiceError(Exception):
    """Drive v2 PR9 版本服务错误

    - message: 错误消息
    - status_code: HTTP 状态码 (默认 400)
    """
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ============================================================
# Service 类
# ============================================================


class DriveVersionService:
    """Drive v2 PR9 文件版本管理服务

    设计要点:
    - Knowledge.file_id = Knowledge.id (主文件行)
    - DriveFileVersion.file_id = Knowledge.id (FK 关联)
    - 创建新版本: 旧行 is_current=0 → 新行 is_current=1 → 更新 Knowledge.file_path/file_size/version_number
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 权限校验 (PR9 W68 第 4 批: 改用 drive_permission_service.check_file_owner_or_folder_admin)
    # ==========================================================================

    @staticmethod
    def _can_modify_file(file: Knowledge, user_id: int) -> bool:
        """判断当前用户是否能"修改"该文件 (上传新版本/回滚/删除版本)

        - 创建人: 可改
        - folder 管理员 (含 owner): 可改 (W68 PR9 drive_permission_service)
        - 平台管理员 (Member.role='admin'): 可改

        Returns:
            True: 有权限 (file 改动可能)
            False: 无权限 (调用方应 raise 403)

        注意: 此方法同步 + 简化版, 实际 drive_permission_service 是 async.
        完整异步版本请直接调用 drive_permission_service.check_file_owner_or_folder_admin.
        """
        # 同步简化判断: 只能检查 created_by (folder admin 需查表, 异步)
        # 真正的 PR9 服务端用 drive_permission_service.check_file_owner_or_folder_admin
        if file.created_by == user_id:
            return True
        return False

    @staticmethod
    def _is_platform_admin(user_id: int, db: AsyncSession) -> bool:
        """检查是否为平台管理员 (Member.role='admin')

        注意: 这是同步函数 (用 db.query), 真正的 async 写法见 _is_platform_admin_async
        """
        return False  # 占位

    # ==========================================================================
    # 创建版本 (核心 API)
    # ==========================================================================

    async def create_version(
        self,
        *,
        file_id: int,
        new_content: bytes,
        new_filename: str,
        new_content_type: str,
        uploader_id: int,
        comment: Optional[str] = None,
    ) -> DriveFileVersion:
        """创建新版本 (上传新内容)

        流程:
        1. 校验 file_id 存在 + 权限 (_can_modify_file)
        2. 算下一版本号 = max(version_number) + 1
        3. 写 MinIO: uploads/drive/{owner_id}/v{n}_{ts}_{hash}{ext}
        4. 创建 DriveFileVersion 行 (is_current=1)
        5. 把旧 DriveFileVersion 行的 is_current 翻 0
        6. 更新 Knowledge 行: file_path/file_size/version_number+1/file_hash
        7. 触发 activity log (PR6)

        Args:
            file_id: 主文件行 Knowledge.id
            new_content: 新文件 bytes
            new_filename: 新文件名 (可与旧名不同, 比如 v1.docx → v2.docx)
            new_content_type: MIME type (e.g. 'application/pdf')
            uploader_id: 上传者 member.id
            comment: 可选备注

        Returns:
            新创建的 DriveFileVersion (is_current=True)

        Raises:
            DriveVersionServiceError: 404 文件不存在, 403 无权限, 500 内部错误
        """
        # 1. 校验
        cur_file = await self.db.get(Knowledge, file_id)
        if cur_file is None:
            raise DriveVersionServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur_file.deleted_at is not None:
            raise DriveVersionServiceError(
                f"文件 id={file_id} 已删除", status_code=410,
            )
        if cur_file.storage_mode != "drive":
            raise DriveVersionServiceError(
                f"文件 id={file_id} 非 drive 模式, 无版本概念", status_code=400,
            )

        # 权限: 创建人 OR 平台管理员 OR folder admin (W68 PR9)
        if not self._can_modify_file(cur_file, uploader_id):
            # 检查 folder admin / 平台管理员 (PR9 走 drive_permission_service)
            perm_svc = DrivePermissionService(self.db)
            if not await perm_svc.check_file_owner_or_folder_admin(
                uploader_id, file_id
            ):
                logger.error(
                    f"[DriveVersionService.create_version] 权限拒绝: "
                    f"file_id={file_id} uploader={uploader_id} "
                    f"(非创建人 + 非 folder admin + 非平台 admin)"
                )
                raise DriveVersionServiceError(
                    f"无权修改文件 id={file_id} (非创建人非 folder 管理员非平台管理员)",
                    status_code=403,
                )

        # 2. 算下一版本号
        max_v_stmt = (
            select(func.coalesce(func.max(DriveFileVersion.version_number), 0))
            .where(DriveFileVersion.file_id == file_id)
        )
        max_v = (await self.db.execute(max_v_stmt)).scalar() or 0
        new_version_number = max_v + 1

        # 3. 写 MinIO
        # 路径: uploads/drive/{owner_id}/v{n}_{ts}_{hash12}{ext}
        import hashlib
        new_hash = hashlib.sha256(new_content).hexdigest()
        ext = ""
        if new_filename and "." in new_filename:
            ext = "." + new_filename.rsplit(".", 1)[-1].lower()
        ts = int(datetime.now(timezone.utc).timestamp())
        new_object_key = (
            f"uploads/drive/{cur_file.created_by}/"
            f"v{new_version_number}_{new_hash[:12]}_{ts}{ext}"
        )

        # 异步导入 file_service (避免循环依赖)
        from app.services.file_service import file_service
        await file_service.upload_to_path(
            new_object_key, new_content, content_type=new_content_type,
        )

        # 4. 创建 DriveFileVersion 行 (is_current=1)
        new_version = DriveFileVersion(
            file_id=file_id,
            version_number=new_version_number,
            minio_object_key=new_object_key,
            size=len(new_content),
            uploader_id=uploader_id,
            comment=comment,
            is_current=1,
        )
        self.db.add(new_version)

        # 5. 把旧 DriveFileVersion 行的 is_current 翻 0
        # (同 file_id 下, 旧版本可能 0 行 (首次创建) 或 1 行)
        if max_v > 0:
            old_current_stmt = (
                select(DriveFileVersion)
                .where(
                    and_(
                        DriveFileVersion.file_id == file_id,
                        DriveFileVersion.is_current == 1,
                    )
                )
            )
            old_current = (await self.db.execute(old_current_stmt)).scalars().first()
            if old_current:
                old_current.is_current = 0

        # 6. 更新 Knowledge 行
        cur_file.file_path = new_object_key
        cur_file.file_size = len(new_content)
        cur_file.file_hash = new_hash
        cur_file.version_number = new_version_number

        await self.db.commit()
        await self.db.refresh(new_version)
        logger.info(
            f"[DriveVersionService.create_version] file_id={file_id} → "
            f"v{new_version_number} by uploader={uploader_id} "
            f"object={new_object_key} size={len(new_content)}"
        )

        # W68 PR9 WS 推送: 通知 file owner (best-effort)
        try:
            from app.services.drive_event_publisher import publish_version_uploaded
            await publish_version_uploaded(
                self.db,
                new_version,
                file_name=cur_file.file_name,
                actor_id=uploader_id,
            )
        except Exception as e:
            logger.debug(f"[DriveVersionService] publish_version_uploaded 失败 (非阻塞): {e!r}")

        return new_version

    # ==========================================================================
    # 列表 (列出版本历史)
    # ==========================================================================

    async def list_versions(
        self,
        *,
        file_id: int,
        current_user_id: int,
    ) -> dict:
        """列文件所有版本 (按 version_number desc)

        Returns:
            {
                "file_id": int,
                "file_name": str,
                "count": int,
                "items": List[DriveFileVersion 序列化 dict]
            }
        """
        # 校验文件存在 + 可见性
        cur_file = await self.db.get(Knowledge, file_id)
        if cur_file is None:
            raise DriveVersionServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        # 可见性 (复用 DriveService._can_see_file 逻辑, 简化版内联)
        if cur_file.created_by != current_user_id and cur_file.visibility == "private":
            raise DriveVersionServiceError(
                f"无权查看文件 id={file_id} (private)", status_code=403,
            )

        # 列 DriveFileVersion + JOIN members
        stmt = (
            select(DriveFileVersion, Member.name)
            .outerjoin(Member, DriveFileVersion.uploader_id == Member.id)
            .where(DriveFileVersion.file_id == file_id)
            .order_by(desc(DriveFileVersion.version_number))
        )
        rows = (await self.db.execute(stmt)).all()

        items = []
        for v, uploader_name in rows:
            items.append({
                "id": v.id,
                "file_id": v.file_id,
                "version_number": v.version_number,
                "minio_object_key": v.minio_object_key,
                "size": v.size,
                "uploader_id": v.uploader_id,
                "uploader_name": uploader_name,
                "comment": v.comment,
                "is_current": bool(v.is_current),
                "created_at": v.created_at.isoformat() if v.created_at else None,
            })

        return {
            "file_id": file_id,
            "file_name": cur_file.file_name,
            "count": len(items),
            "items": items,
        }

    # ==========================================================================
    # 下载指定版本
    # ==========================================================================

    async def get_version_download(
        self,
        *,
        version_id: int,
        current_user_id: int,
    ) -> dict:
        """获取指定版本的下载信息 (presigned URL)

        Returns:
            {
                "version_id": int,
                "file_id": int,
                "version_number": int,
                "download_url": str (presigned),
                "expires_in": int,
                "file_name": str,
                "size": int
            }
        """
        v = await self.db.get(DriveFileVersion, version_id)
        if v is None:
            raise DriveVersionServiceError(
                f"版本 id={version_id} 不存在", status_code=404,
            )

        # 校验文件可见性
        cur_file = await self.db.get(Knowledge, v.file_id)
        if cur_file is None:
            raise DriveVersionServiceError(
                f"文件 id={v.file_id} 不存在", status_code=404,
            )
        if cur_file.created_by != current_user_id and cur_file.visibility == "private":
            raise DriveVersionServiceError(
                f"无权下载文件 id={v.file_id} 的版本 (private)", status_code=403,
            )

        # 生成 presigned URL (1 小时有效期)
        from app.services.file_service import file_service
        download_url = file_service.get_url(v.minio_object_key, expires=3600)

        return {
            "version_id": v.id,
            "file_id": v.file_id,
            "version_number": v.version_number,
            "download_url": download_url,
            "expires_in": 3600,
            "file_name": cur_file.file_name,
            "size": v.size,
        }

    # ==========================================================================
    # 回滚 (rollback)
    # ==========================================================================

    async def rollback(
        self,
        *,
        file_id: int,
        version_id: int,
        user_id: int,
        new_comment: Optional[str] = None,
    ) -> DriveFileVersion:
        """回滚到历史版本

        流程:
        1. 校验目标版本存在 + file_id 匹配
        2. 权限: _can_modify_file
        3. 从目标版本 minio_object_key copy_object 到新路径
        4. 创建新 DriveFileVersion 行 (version_number = max+1)
        5. 旧 current 翻 0, 新行 is_current=1
        6. 更新 Knowledge 行 (file_path/file_size)

        Returns:
            新创建的 DriveFileVersion (复制自目标, version_number=cur+1)
        """
        # 1. 校验目标版本
        target = await self.db.get(DriveFileVersion, version_id)
        if target is None:
            raise DriveVersionServiceError(
                f"版本 id={version_id} 不存在", status_code=404,
            )
        if target.file_id != file_id:
            raise DriveVersionServiceError(
                f"版本 id={version_id} 不属于文件 id={file_id}", status_code=400,
            )

        # 校验文件 + 权限
        cur_file = await self.db.get(Knowledge, file_id)
        if cur_file is None:
            raise DriveVersionServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur_file.deleted_at is not None:
            raise DriveVersionServiceError(
                f"文件 id={file_id} 已删除", status_code=410,
            )

        if not self._can_modify_file(cur_file, user_id):
            # PR9: 检查 folder admin / 平台管理员 (走 drive_permission_service)
            perm_svc = DrivePermissionService(self.db)
            if not await perm_svc.check_file_owner_or_folder_admin(
                user_id, file_id
            ):
                logger.error(
                    f"[DriveVersionService.rollback] 权限拒绝: "
                    f"file_id={file_id} user={user_id} "
                    f"(非创建人 + 非 folder admin + 非平台 admin)"
                )
                raise DriveVersionServiceError(
                    f"无权回滚文件 id={file_id}", status_code=403,
                )

        # 2. 算下一版本号
        max_v_stmt = (
            select(func.coalesce(func.max(DriveFileVersion.version_number), 0))
            .where(DriveFileVersion.file_id == file_id)
        )
        max_v = (await self.db.execute(max_v_stmt)).scalar() or 0
        new_version_number = max_v + 1

        # 3. copy_object 反向
        from app.services.file_service import file_service
        ext = ""
        if cur_file.file_name and "." in cur_file.file_name:
            ext = "." + cur_file.file_name.rsplit(".", 1)[-1].lower()
        ts = int(datetime.now(timezone.utc).timestamp())
        new_object_key = (
            f"uploads/drive/{cur_file.created_by}/"
            f"v{new_version_number}_{target.minio_object_key.split('_')[1] if '_' in target.minio_object_key else 'restored'}_{ts}{ext}"
        )

        # 复制 MinIO 对象
        copied_size = await file_service.copy_object_async(
            target.minio_object_key, new_object_key,
        )

        # 4. 创建新 DriveFileVersion 行
        comment_text = new_comment or f"Rolled back to v{target.version_number}"
        new_version = DriveFileVersion(
            file_id=file_id,
            version_number=new_version_number,
            minio_object_key=new_object_key,
            size=copied_size,
            uploader_id=user_id,
            comment=comment_text,
            is_current=1,
        )
        self.db.add(new_version)

        # 5. 旧 current 翻 0
        if max_v > 0:
            old_current_stmt = (
                select(DriveFileVersion)
                .where(
                    and_(
                        DriveFileVersion.file_id == file_id,
                        DriveFileVersion.is_current == 1,
                    )
                )
            )
            old_current = (await self.db.execute(old_current_stmt)).scalars().first()
            if old_current:
                old_current.is_current = 0

        # 6. 更新 Knowledge 行
        cur_file.file_path = new_object_key
        cur_file.file_size = copied_size
        cur_file.version_number = new_version_number

        await self.db.commit()
        await self.db.refresh(new_version)
        logger.info(
            f"[DriveVersionService.rollback] file_id={file_id} "
            f"target_v{target.version_number} → new_v{new_version_number} "
            f"by user={user_id} copy_bytes={copied_size}"
        )

        # W68 PR9 WS 推送: 通知 file owner (best-effort)
        try:
            from app.services.drive_event_publisher import publish_version_rollback
            await publish_version_rollback(
                self.db,
                new_version,
                file_name=cur_file.file_name,
                target_version_number=target.version_number,
                actor_id=user_id,
            )
        except Exception as e:
            logger.debug(f"[DriveVersionService] publish_version_rollback 失败 (非阻塞): {e!r}")

        return new_version

    # ==========================================================================
    # 删除指定版本 (有限制: 只能删最新非当前版本)
    # ==========================================================================

    async def delete_version(
        self,
        *,
        version_id: int,
        user_id: int,
    ) -> dict:
        """删除指定版本

        限制:
        - 不能删 is_current=1 的版本 (那是当前版本)
        - 只能删"最新非当前版本" (max(version_number where is_current=0))
          防误删中间版 → rollback 悬空

        Returns:
            {"deleted_version_id", "deleted_object_key", "remaining_versions"}
        """
        v = await self.db.get(DriveFileVersion, version_id)
        if v is None:
            raise DriveVersionServiceError(
                f"版本 id={version_id} 不存在", status_code=404,
            )

        # 权限
        cur_file = await self.db.get(Knowledge, v.file_id)
        if cur_file is None:
            raise DriveVersionServiceError(
                f"文件 id={v.file_id} 不存在", status_code=404,
            )
        if not self._can_modify_file(cur_file, user_id):
            # PR9: 检查 folder admin / 平台管理员 (走 drive_permission_service)
            perm_svc = DrivePermissionService(self.db)
            if not await perm_svc.check_file_owner_or_folder_admin(
                user_id, v.file_id
            ):
                logger.error(
                    f"[DriveVersionService.delete_version] 权限拒绝: "
                    f"file_id={v.file_id} user={user_id} "
                    f"(非创建人 + 非 folder admin + 非平台 admin)"
                )
                raise DriveVersionServiceError(
                    f"无权删除文件 id={v.file_id} 的版本", status_code=403,
                )

        # 不能删当前版本
        if v.is_current == 1:
            raise DriveVersionServiceError(
                f"不能删除当前版本 (is_current=1), 请先上传新版本", status_code=400,
            )

        # 校验是"最新非当前版本"
        max_non_current_stmt = (
            select(func.coalesce(func.max(DriveFileVersion.version_number), 0))
            .where(
                and_(
                    DriveFileVersion.file_id == v.file_id,
                    DriveFileVersion.is_current == 0,
                )
            )
        )
        max_non_current = (await self.db.execute(max_non_current_stmt)).scalar() or 0
        if v.version_number != max_non_current:
            raise DriveVersionServiceError(
                f"只能删除最新非当前版本 (v{max_non_current}), "
                f"当前想删 v{v.version_number} 是中间版本",
                status_code=400,
            )

        # 删 MinIO 对象 (best effort, 失败不阻塞 DB 删除)
        object_key = v.minio_object_key
        try:
            from app.services.file_service import file_service
            file_service.delete_file(object_key)
        except Exception as e:
            logger.warning(
                f"[DriveVersionService.delete_version] 删 MinIO 失败 "
                f"(DB 仍会删): {object_key} error={e!r}"
            )

        # 删 DB 行
        await self.db.delete(v)
        await self.db.commit()

        # 算剩余版本数
        count_stmt = (
            select(func.count(DriveFileVersion.id))
            .where(DriveFileVersion.file_id == v.file_id)
        )
        remaining = (await self.db.execute(count_stmt)).scalar() or 0

        logger.info(
            f"[DriveVersionService.delete_version] file_id={v.file_id} "
            f"deleted v{v.version_number} object={object_key} remaining={remaining}"
        )
        return {
            "deleted_version_id": v.id,
            "deleted_object_key": object_key,
            "remaining_versions": remaining,
        }

    # ==========================================================================
    # W68 第 12 批 B-2 (Drive v2 PR15): 按 tag 查询版本 (复用 drive_version_tag_service)
    # ==========================================================================

    async def get_version_by_tag(
        self,
        *,
        file_id: int,
        tag_name: str,
        current_user_id: int,
    ) -> Optional[dict]:
        """按 (file_id, tag_name) 拿首个匹配版本 (复用 PR15 service)

        Args:
            file_id: 文件 ID (Knowledge.id)
            tag_name: 标签名称 (12 个内置白名单之一)
            current_user_id: 当前用户 (权限校验)

        Returns:
            Dict: {version_id, version_number, is_current, tag_id, tag_name, color, ...} or None

        Raises:
            DriveVersionServiceError(403): 无 read 权限
        """
        from app.services.drive_version_tag_service import DriveVersionTagService

        tag_svc = DriveVersionTagService(self.db)
        try:
            return await tag_svc.get_file_by_tag(
                file_id=file_id,
                tag_name=tag_name,
                current_user_id=current_user_id,
            )
        except DriveVersionTagServiceError as e:
            # 统一异常类型, 方便调用方 (API 层) 捕获
            raise DriveVersionServiceError(
                str(e), status_code=e.status_code,
            )

    async def list_versions_with_tags(
        self,
        *,
        file_id: int,
        current_user_id: int,
    ) -> dict:
        """列文件所有版本 (含 tags, PR15 增强)

        与 list_versions 区别: 返回的 items 额外含 tags 字段
        (调用方无需 2 次 query: 先 list_versions 再 list_tags_by_file)

        Returns:
            {
                "file_id": int,
                "file_name": str,
                "count": int,
                "items": [
                    {
                        "id": int, "version_number": int, "uploader_id": int, ...,
                        "tags": [{tag_name, color, description, ...}, ...]
                    }
                ]
            }

        性能:
        - 1 次 query 拿 version + tags (LEFT OUTER JOIN)
        - 比 list_versions + list_tags_by_file 节省 50% query 数
        """
        # 校验文件存在 + 可见性 (复用 list_versions 逻辑)
        cur_file = await self.db.get(Knowledge, file_id)
        if cur_file is None:
            raise DriveVersionServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur_file.created_by != current_user_id and cur_file.visibility == "private":
            raise DriveVersionServiceError(
                f"无权查看文件 id={file_id} (private)", status_code=403,
            )

        # LEFT OUTER JOIN: version + tags (无 tag 的版本 tags=[])
        from app.models.drive_version_tag import DEFAULT_TAG_COLOR, DriveVersionTag

        stmt = (
            select(DriveFileVersion, Member.name, DriveVersionTag)
            .outerjoin(Member, DriveFileVersion.uploader_id == Member.id)
            .outerjoin(
                DriveVersionTag,
                DriveVersionTag.version_id == DriveFileVersion.id,
            )
            .where(DriveFileVersion.file_id == file_id)
            .order_by(
                desc(DriveFileVersion.version_number),
                DriveVersionTag.created_at.asc(),
            )
        )
        rows = (await self.db.execute(stmt)).all()

        # 聚合: version_id → {info + tags}
        version_map: dict = {}
        for v, uploader_name, tag in rows:
            entry = version_map.setdefault(v.id, {
                "id": v.id,
                "file_id": v.file_id,
                "version_number": v.version_number,
                "minio_object_key": v.minio_object_key,
                "size": v.size,
                "uploader_id": v.uploader_id,
                "uploader_name": uploader_name,
                "comment": v.comment,
                "is_current": bool(v.is_current),
                "created_at": v.created_at.isoformat() if v.created_at else None,
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

        items = list(version_map.values())
        return {
            "file_id": file_id,
            "file_name": cur_file.file_name,
            "count": len(items),
            "items": items,
        }

    # ==========================================================================
    # 工具: 把 DriveFileVersion 序列化为 dict (API 响应)
    # ==========================================================================

    @staticmethod
    def to_item_dict(v: DriveFileVersion, uploader_name: Optional[str] = None) -> dict:
        """把 DriveFileVersion 序列化为 dict (含 uploader_name)"""
        return {
            "id": v.id,
            "file_id": v.file_id,
            "version_number": v.version_number,
            "minio_object_key": v.minio_object_key,
            "size": v.size,
            "uploader_id": v.uploader_id,
            "uploader_name": uploader_name,
            "comment": v.comment,
            "is_current": bool(v.is_current),
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }