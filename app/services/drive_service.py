"""Drive 文件服务 (PR2.1 + v2 升级)

负责 drive_storage_mode='drive' 文件元数据的 CRUD 操作。

核心边界:
- visibility='private' 文件: 仅 created_by (owner) 可见，其他人**完全看不到** (不是 403)
- visibility='team': 当前活跃成员可见
- visibility='public': 含团队外部分享链接 (本服务暂不展开 share_token, 留 PR2.7)
- 文件 visibility >= 所在文件夹 visibility (文件夹硬上限, plan 决策 2026-07-01)
- drive 文件不入 embedding 索引 (search_semantic 硬过滤 storage_mode='kb', PR1.4 已实现)
- 软删除: deleted_at 标记 → Celery beat 3 天后物理清除 (PR1.2)

业务规则优先级:
  1. visibility 继承上级文件夹（不可越权）, 见 _validate_visibility_inherits
  2. drive 文件不入 Agent search_knowledge 检索 (隐私边界)
  3. listing 时 SQL hard-filter private → created_by=current_user_id
"""
import hashlib
import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import to_naive_datetime

from app.models.folder import Folder, VISIBILITY_ORDER
from app.models.knowledge import Knowledge, KnowledgeVersion, ChunkedUploadSession  # PR5: 断点续传
from app.models.member import Member
from app.services.file_service import file_service
# PR6: activity + notification 集成
from app.services.activity_service import activity_service
from app.services.notification_service import notification_service

logger = logging.getLogger("microbubble.drive")


# 默认配额
MAX_DRIVE_FILE_SIZE_MB = 2048  # MinIO multipart 安全上限
MAX_DRIVE_FILE_SIZE_BYTES = MAX_DRIVE_FILE_SIZE_MB * 1024 * 1024


# ===== 分享链接默认值 (v2 PR1) =====
DEFAULT_SHARE_EXPIRES_HOURS = 168   # 7 天 (百度网盘默认 7 天, 我们保持一致)
MAX_SHARE_EXPIRES_HOURS = 8760     # 365 天
MIN_SHARE_PASSWORD_LENGTH = 4
MAX_SHARE_PASSWORD_LENGTH = 8


def _hash_share_password(password: str) -> str:
    """提取码 SHA256 hex 哈希 (64 字符).

    计划文档原话: "提取码 SHA256 哈希存", 所以即使明文是 4 位数字也存 hash.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _validate_share_password(password: Optional[str]) -> None:
    """校验提取码长度 (4-8 位数字). 抛出 DriveServiceError(400) 给上层 API.
    """
    if password is None:
        return  # 公开分享, 无密码
    if not isinstance(password, str) or len(password) < MIN_SHARE_PASSWORD_LENGTH or len(password) > MAX_SHARE_PASSWORD_LENGTH:
        raise DriveServiceError(
            f"提取码长度需在 {MIN_SHARE_PASSWORD_LENGTH}-{MAX_SHARE_PASSWORD_LENGTH} 位之间",
            status_code=400,
        )
    if not password.isdigit():
        raise DriveServiceError("提取码必须为纯数字", status_code=400)


def _validate_share_expires_hours(expires_hours: Optional[int]) -> None:
    """校验分享链接过期时间 (1h - 365d). 0/None = 7 天默认. 负数 = 永久 (-1).
    """
    if expires_hours is None or expires_hours == 0:
        return
    if expires_hours == -1:
        return  # -1 = 永久
    if expires_hours < 1 or expires_hours > MAX_SHARE_EXPIRES_HOURS:
        raise DriveServiceError(
            f"过期时长超出范围 (1 - {MAX_SHARE_EXPIRES_HOURS} 小时), 0 = 默认 7 天, -1 = 永久",
            status_code=400,
        )


# 2026-07-12 死代码清理: _to_naive_dt helper 提取到 app.utils.datetime_utils.to_naive_datetime


class DriveServiceError(Exception):
    """业务级错误，调用方映射成 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message  # 暴露属性, 否则 e.message 报 AttributeError
        self.status_code = status_code


async def _stream_concat_chunks(
    session_id: str, chunk_indices: List[int], dst_object: str
) -> int:
    """顺序下载 chunks → 拼接 → 上传最终 object (PR5 分片完成核心)

    实现: 用 sync file I/O (asyncio.to_thread 包), 顺序写临时文件 + put_object.
    内存峰值 = 1 chunk (默认 5MB), 总文件大小无关.

    备选实现 (未采用):
    - aiofiles 异步文件: 需要 aiofiles 依赖 (本环境未装)
    - python-level join: 内存峰值 = 总文件大小 (10GB 视频会爆 RAM)
    - ffmpeg concat: 需写本地 concat list + 转码 (重, 没必要)
    """
    import tempfile

    def _sync_concat():
        """同步版拼接 (放线程池跑, 不阻塞 event loop)"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = tmp.name
        total = 0
        try:
            with open(tmp_path, "wb") as f:
                for idx in chunk_indices:
                    chunk_obj = f"drive-uploads/{session_id}/chunk_{idx:04d}"
                    # file_service.download_file 内部走 minio fget_object (流式)
                    chunk_bytes = file_service.download_file_sync(chunk_obj)
                    if not chunk_bytes:
                        raise DriveServiceError(
                            f"chunk_{idx} 读取为空 (session={session_id})", status_code=500
                        )
                    f.write(chunk_bytes)
                    total += len(chunk_bytes)
            return tmp_path, total
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # 跑线程池
    tmp_path, total_size = await asyncio.to_thread(_sync_concat)
    try:
        # 上传最终 object (file_service.upload_to_path 已是 async)
        with open(tmp_path, "rb") as f:
            content = f.read()
        await file_service.upload_to_path(
            dst_object, content, content_type="application/octet-stream"
        )

        logger.info(
            f"[_stream_concat_chunks] session={session_id} chunks={len(chunk_indices)} "
            f"size={total_size} → {dst_object}"
        )
        return total_size
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


class DriveService:
    """Drive 文件元数据 CRUD"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 可见性校验
    # ==========================================================================

    @staticmethod
    def _validate_visibility_inherits(
        file_visibility: str,
        folder_visibility: Optional[str],
    ) -> None:
        """验证文件 visibility ≤ 所在文件夹 visibility（防止越权暴露）

        文件夹是文件的"上界": 文件 visibility 必须 <= 文件夹 visibility

        例如:
          folder=private → 文件只能是 private (不允许 team/public, 否则其他人能看到)
          folder=team    → 文件可以是 private/team/public (team 文件夹允许任何 visibility)
          folder=public  → 文件只能是 public (公开文件夹不能放私人草稿)

        VISIBILITY_ORDER 排序: private(0) < team(1) < public(2)
        """
        if folder_visibility is None:
            return
        if VISIBILITY_ORDER.get(file_visibility, -1) > VISIBILITY_ORDER.get(folder_visibility, -1):
            raise DriveServiceError(
                f"文件可见性 ({file_visibility}) 高于文件夹可见性 ({folder_visibility})，越权暴露",
                status_code=400,
            )

    @staticmethod
    def _can_see_file(file: Knowledge, current_user_id: int) -> bool:
        """判断当前用户是否能"看到"该 drive 文件（list API 用）

        - owner: 任何 visibility 都能看
        - 其他用户: 仅看 visibility != private
        """
        if file.created_by == current_user_id:
            return True
        return file.visibility != "private"

    # ==========================================================================
    # CRUD
    # ==========================================================================

    async def create_file(
        self,
        *,
        title: str,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
        owner_id: int,
        storage_mode: str = "drive",
        visibility: str = "team",
        folder_id: Optional[int] = None,
        created_by: Optional[int] = None,
        source_type: Optional[str] = None,
        content: Optional[str] = None,
        file_hash: Optional[str] = None,  # PR4: 秒传 hash
        # v2 PR6-P19: 团队共享盘标识 (前端在 team 视图上传 = true)
        is_team_shared: bool = False,
    ) -> Knowledge:
        """创建 drive 文件元数据 (multipart complete 后调用, 或从前端直接表单上传)

        Args:
            title: 文件标题 (脱敏用户可读)
            file_path: MinIO object_name, 例如 drive/1/.../test.pptx
            file_name: 原始文件名 (用户上传时的名字)
            file_type: 扩展名 (.pptx / .docx / .pdf)
            file_size: 字节 (validation: 不超 MAX_DRIVE_FILE_SIZE_BYTES)
            owner_id: 仓库所有者 (folder owner 或 created_by 备份)
            storage_mode: kb | drive (默认 drive)
            visibility: private | team | public (默认 team)
            folder_id: 关联 folders.id (顶级目录 = None)
            created_by: 创建人 (默认 = owner_id)
            source_type: auto_research 等上游标识, 默认 None
            content: 提取摘要 (默认 None)
            file_hash: 文件 MD5/SHA256 hex hash (PR4 秒传字段, 可选)
            is_team_shared: v2 PR6-P19, True=团队共享盘上传, 不在个人网盘显示
        """
        if storage_mode == "drive":
            assert visibility in ("private", "team", "public"), f"invalid visibility: {visibility}"

        # 配额校验
        if file_size > MAX_DRIVE_FILE_SIZE_BYTES:
            raise DriveServiceError(
                f"文件过大 ({file_size} bytes > {MAX_DRIVE_FILE_SIZE_MB}MB)",
                status_code=413,
            )

        # 文件夹存在 + visibility 继承校验
        if folder_id is not None:
            folder = await self.get_folder(folder_id)
            if folder is None:
                raise DriveServiceError(f"文件夹 id={folder_id} 不存在", status_code=400)
            # 跨用户校验（防越权操作别人 folder）
            if folder.owner_id != owner_id:
                raise DriveServiceError(f"无权在该文件夹中创建文件", status_code=403)
            self._validate_visibility_inherits(visibility, folder.visibility)

        knowledge = Knowledge(
            title=title,
            content=content or f"[drive upload] {file_name}",
            file_path=file_path,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,           # PR4: 真值 (PR2.7 之前 0)
            file_hash=file_hash,            # PR4: 秒传 hash (可空)
            is_latest=True,                 # PR4: 新文件默认最新
            version_number=1,               # PR4: 默认 v1
            source_type=source_type or "drive",
            created_by=created_by or owner_id,
            storage_mode=storage_mode,
            visibility=visibility,
            folder_id=folder_id,
            is_team_shared=is_team_shared,  # v2 PR6-P19
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        logger.info(
            f"[DriveService.create_file] id={knowledge.id} file_name={file_name} "
            f"visibility={visibility} folder_id={folder_id} "
            f"file_size={file_size} file_hash={'<set>' if file_hash else None}"
        )
        # PR6: 活动动态流 (上传事件) — best-effort 不阻塞
        try:
            await activity_service.log(
                self.db,
                actor_id=created_by or owner_id,
                action="upload",
                target_type="file",
                target_id=knowledge.id,
                target_name=knowledge.file_name,
                metadata={
                    "visibility": visibility,
                    "folder_id": folder_id,
                    "file_size": file_size,
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.create_file] activity log 失败 (非阻塞): {e}")

        # v2 网盘 PR6-P12+ 增量: upload owner notification (folder owner != uploader 时通知 owner)
        # 设计: 自通知 skip (owner_id == current_user_id 时不触发, 避免噪音)
        # 未来扩展: "upload to other user's folder" 时自动通知 folder owner
        # best-effort 不阻塞, 失败只 logger.debug
        try:
            owner_id_for_notify = owner_id
            uploader_id = created_by or owner_id
            if owner_id_for_notify != uploader_id:
                # 跨用户上传场景: 通知 file owner (e.g. folder owner != uploader)
                await notification_service.create_mention(
                    self.db,
                    file_id=knowledge.id,
                    mentioned_user_id=owner_id_for_notify,
                    mentioned_by=uploader_id,
                    context="upload",
                )
        except Exception as e:
            logger.debug(f"[DriveService.create_file] notification trigger 失败 (非阻塞): {e}")

        return knowledge

    async def list_files(
        self,
        *,
        current_user_id: int,
        folder_id: Optional[int] = None,
        visibility_filter: Optional[str] = None,
        storage_mode: str = "drive",
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
        # v2 PR2: 新增 sort + filter 参数 (默认行为向后兼容)
        sort_by: str = "created_at",
        sort_order: str = "desc",
        starred_only: bool = False,
        file_type: Optional[str] = None,
        # v2 PR6-P19: 团队共享盘隔离 (None=不过滤)
        is_team_shared: Optional[bool] = None,
        # v2.21 (2026-07-11): folder_id=None + include_subfolders=True 时
        # 跳过 folder_id IS NULL filter (用于 🌐 团队共享盘顶级 view, 列出
        # 所有 team PPT, 不论 folder_id 是否 NULL). personal view 维持 v2 PR3 行为.
        include_subfolders: bool = False,
    ) -> Tuple[List[Knowledge], int]:
        """列 drive 文件 (含列表 SQL 越权防御)

        Args:
            current_user_id: 当前用户 (用于 private 文件过滤)
            folder_id: 仅列该文件夹的文件 (None = 顶级)
            visibility_filter: 过滤特定 visibility (None = 不限定)
            storage_mode: 默认 drive (filter out kb)
            include_deleted: True = 含已软删 (admin)
            page, page_size: 分页
            sort_by: 排序字段 (默认 created_at)
            sort_order: asc / desc
            starred_only: 仅 is_starred=true
            file_type: pdf/image/video/office/text
            is_team_shared: v2 PR6-P19, None=不过滤/True=仅 team/False=仅 personal
            include_subfolders: v2.21, True 时跳过 folder_id IS NULL filter (🌐 team view 顶级用)

        Returns:
            (items, total)
        """
        return await self._list_files_impl(
            current_user_id=current_user_id,
            folder_id=folder_id,
            visibility_filter=visibility_filter,
            storage_mode=storage_mode,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            starred_only=starred_only,
            file_type=file_type,
            is_team_shared_filter=is_team_shared,
            include_subfolders=include_subfolders,
        )

    async def _list_files_impl(
        self,
        *,
        current_user_id: int,
        folder_id: Optional[int],
        visibility_filter: Optional[str],
        storage_mode: str,
        include_deleted: bool,
        page: int,
        page_size: int,
        sort_by: str,                # created_at | updated_at | file_name | file_size | starred_at
        sort_order: str,             # asc | desc
        starred_only: bool,
        file_type: Optional[str],    # pdf | image | video | office | text | (None=全部)
        deleted_only: bool = False,  # v2 PR2: trash 模式 exclusive filter
        is_team_shared_filter: Optional[bool] = None,  # v2 PR6-P19: None=both, True=仅 team, False=仅 personal
        include_subfolders: bool = False,  # v2.21 (2026-07-11): 见 list_files docstring
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2: 拆出 list_files 内部实现, 支持 sort_by / sort_order / starred_only / file_type.

        对外保持向后兼容 (list_files 默认 sort=created_at desc).
        v2 PR2: deleted_only=True 时仅返 deleted_at IS NOT NULL (回收站专用).
        v2 PR6-P19: is_team_shared_filter 隔离个人/团队共享盘 (True/False/None).
        v2.21 (2026-07-11): include_subfolders=True 时跳过 folder_id IS NULL filter
          (团队共享盘顶级 view 列出整个团队空间的 PPT, 含 root + 所有 sub folder).
          personal view 维持 v2 PR3 行为 (folder_id=None → folder_id IS NULL).
        """
        stmt = select(Knowledge)
        count_stmt = select(func.count(Knowledge.id))

        filters = [Knowledge.storage_mode == storage_mode]
        if deleted_only:
            # 回收站模式: 只看 deleted_at IS NOT NULL (排除正常的活跃文件)
            filters.append(Knowledge.deleted_at.isnot(None))
        elif not include_deleted:
            filters.append(Knowledge.deleted_at.is_(None))
        if folder_id is not None:
            # v2 PR3 修复: folder_id 显式时只返该 folder 的文件
            filters.append(Knowledge.folder_id == folder_id)
        elif folder_id is None and not include_subfolders:
            # v2 PR3 修复: 默认 (folder_id=None) 是"顶级根目录", 仅 folder_id IS NULL
            # 之前不过滤会把子目录里的文件也带回来, 与 DesktopDriveView UI 不一致
            # (DesktopDriveView 'selectedFolderId.value = null' = 顶级, 用户期望"只看根")
            # 行为兼容: 不动 service 调用方, 默认语义升级
            # v2.21 例外: include_subfolders=True (团队共享盘顶级) 跳过此 filter
            filters.append(Knowledge.folder_id.is_(None))
        if visibility_filter:
            filters.append(Knowledge.visibility == visibility_filter)
        if starred_only:
            filters.append(Knowledge.is_starred.is_(True))
        if file_type:
            # file_type 是扩展名大写组: pdf / image / video / office / text
            ext_predicate = self._build_file_type_predicate(file_type)
            if ext_predicate is not None:
                filters.append(ext_predicate)
        # v2 PR6-P19: 团队共享盘隔离 (None=不过滤, True=仅 is_team_shared=true, False=仅 false)
        if is_team_shared_filter is not None:
            filters.append(Knowledge.is_team_shared == is_team_shared_filter)

        # 核心隐私边界: private 文件仅 owner 可见
        visibility_see_cond = or_(
            Knowledge.created_by == current_user_id,
            Knowledge.visibility != "private",
        )
        filters.append(visibility_see_cond)

        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

        # 排序
        sort_column = self._resolve_sort_column(sort_by)
        if sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items_result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = count_result.scalar() or 0

        return items, total

    @staticmethod
    def _resolve_sort_column(sort_by: str):
        """v2 PR2: 把前端 sort_by 字符串映射到 Knowledge 列对象.

        'deleted_at' 是回收站专属, fallback 到 updated_at (回收站里 updated_at 通常是删除时间).
        """
        mapping = {
            "created_at": Knowledge.created_at,
            "updated_at": Knowledge.updated_at,
            "file_name": Knowledge.file_name,
            "starred_at": Knowledge.starred_at,
            "deleted_at": Knowledge.updated_at,  # 回收站 fallback
        }
        if sort_by not in mapping:
            raise DriveServiceError(f"不支持的排序字段 '{sort_by}'", status_code=400)
        return mapping[sort_by]

    @staticmethod
    def _build_file_type_predicate(file_type: str):
        """v2 PR2: 把文件类型枚举映射到 file_name 后缀 LIKE 条件.

        返回 SQLAlchemy 列表达式 (用于 .where()), 无效类型返 None (不过滤).

        v2.7.1 (2026-07-10) bugfix: 加 'audio' 映射 (前缺导致前端 chip 选了 audio
        返回的是全部文件 — 看上去 '所有 PPT 也是音频' 的错误). 覆盖常见音频:
        .mp3 / .wav / .flac / .aac / .ogg / .m4a / .wma / .opus. 任何未匹配
        的 type 返 None → 不过滤 (前端拿到全部,需前端 chip 自身友好 fallback).

        v2.22 (2026-07-11): 拆分 office → word/ppt/excel (用户决策"Office 分类太粗")
        前端 chip 选项 DesktopDriveView.FILE_TYPE_OPTIONS 同步更新.
        office 留为 alias (含全部 6 扩展名) 用于向后兼容 (老请求 / 第三方脚本).
        """
        type_to_ext = {
            "pdf":   [".pdf"],
            "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"],
            "video": [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"],
            "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"],
            "word":  [".doc", ".docx"],
            "ppt":   [".ppt", ".pptx"],
            "excel": [".xls", ".xlsx"],
            # office 留作 alias, 覆盖全部 Office 扩展名, 老请求 / 旧 chip fallback
            "office": [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"],
            "text":  [".txt", ".md", ".log", ".csv"],
        }
        exts = type_to_ext.get(file_type.lower())
        if not exts:
            return None
        # 用 OR 串接: file_name ILIKE '%.pdf' OR file_name ILIKE '%.jpg' ...
        from sqlalchemy import or_ as _or
        predicates = [Knowledge.file_name.ilike(f"%{ext}") for ext in exts]
        return _or(*predicates)

    async def get_file(self, file_id: int, current_user_id: int) -> Optional[Knowledge]:
        """获取 drive 文件详情 (含越权防御)

        Returns:
            Knowledge 对象, None = 不存在或无权访问
        """
        stmt = select(Knowledge).where(
            Knowledge.id == file_id,
            Knowledge.deleted_at.is_(None),
        )
        file = (await self.db.execute(stmt)).scalar_one_or_none()
        if file is None:
            return None
        if not self._can_see_file(file, current_user_id):
            return None  # 不是 owner + private → 隐身 (连文件名都不展示)
        return file

    async def update_file(
        self,
        file_id: int,
        current_user_id: int,
        *,
        title: Optional[str] = None,
        file_name: Optional[str] = None,  # PR4.4: 重命名 (修复 PR2.5 漏的字段)
        visibility: Optional[str] = None,
        folder_id: Optional[int] = None,
    ) -> Optional[Knowledge]:
        """更新 drive 文件 (owner only)

        Returns: 更新后的 Knowledge, None = 文件不存在或非 owner
        Raises: DriveServiceError 若越权或文件夹 visibility 不兼容
        """
        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        file = file.scalar_one_or_none()
        if file is None:
            return None
        if file.created_by != current_user_id:
            # 不是 owner，隐身
            return None

        # visibility 上限
        if visibility is not None:
            target_folder_id = folder_id if folder_id is not None else file.folder_id
            if target_folder_id is not None:
                folder = await self.get_folder(target_folder_id)
                if folder is not None:
                    self._validate_visibility_inherits(visibility, folder.visibility)
            file.visibility = visibility

        if title is not None:
            file.title = title

        if file_name is not None:  # PR4.4: 重命名 (修复 PR2.5 漏的字段)
            file.file_name = file_name

        if folder_id is not None and folder_id != file.folder_id:
            # 校验目标文件夹存在 + ownership
            target_folder = await self.get_folder(folder_id)
            if target_folder is None:
                raise DriveServiceError(f"目标文件夹 id={folder_id} 不存在", status_code=400)
            if target_folder.owner_id != file.created_by:
                raise DriveServiceError(f"无权移动到该文件夹", status_code=403)
            self._validate_visibility_inherits(file.visibility, target_folder.visibility)
            file.folder_id = folder_id

        await self.db.commit()
        await self.db.refresh(file)
        logger.info(
            f"[DriveService.update_file] id={file.id} visibility={file.visibility} "
            f"folder_id={file.folder_id}"
        )
        # PR6: 活动动态流 — best-effort 不阻塞
        try:
            meta = {}
            if title is not None:
                meta["new_title"] = title
            if file_name is not None:
                meta["new_file_name"] = file_name
            if visibility is not None:
                meta["new_visibility"] = visibility
            if folder_id is not None and folder_id != file.folder_id:
                meta["new_folder_id"] = folder_id
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="rename" if (file_name is not None or title is not None) else "move",
                target_type="file",
                target_id=file.id,
                target_name=file.file_name,
                metadata=meta,
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.update_file] activity log 失败: {e}")
        return file

    async def soft_delete_file(
        self,
        file_id: int,
        current_user_id: int,
    ) -> bool:
        """软删除 drive 文件 (owner only)

        设置 deleted_at = NOW(), 3 天后由 Celery beat 物理清除 (PR1.2)
        Returns: True = 成功, False = 文件不存在或非 owner
        """
        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        file = file.scalar_one_or_none()
        if file is None or file.created_by != current_user_id:
            return False

        file.deleted_at = to_naive_datetime(datetime.now(timezone.utc))
        await self.db.commit()
        logger.info(f"[DriveService.soft_delete_file] id={file.id}")
        # PR6: 活动动态流
        try:
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="delete",
                target_type="file",
                target_id=file.id,
                target_name=file.file_name,
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.soft_delete_file] activity log 失败: {e}")
        return True

    async def restore_file(
        self,
        file_id: int,
        current_user_id: int,
    ) -> Optional[Knowledge]:
        """恢复被软删的 drive 文件 (owner only, 3 天保留期内有效)"""
        file = await self.db.execute(
            select(Knowledge).where(Knowledge.id == file_id)
        )
        file = file.scalar_one_or_none()
        if file is None or file.created_by != current_user_id:
            return None
        file.deleted_at = None
        await self.db.commit()
        await self.db.refresh(file)
        logger.info(f"[DriveService.restore_file] id={file.id}")
        # PR6: 活动动态流
        try:
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="restore",
                target_type="file",
                target_id=file.id,
                target_name=file.file_name,
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.restore_file] activity log 失败: {e}")
        return file

    # ==========================================================================
    # extract-to-kb 升级 (drive → kb, 触发 LLM 提取)
    # ==========================================================================

    async def extract_to_kb(
        self,
        file_id: int,
        current_user_id: int,
        *,
        target_visibility: str = "team",
    ) -> Optional[Knowledge]:
        """将 drive 文件升级到公共知识库 (PR2 简化版, PR3 加 LLM)

        流程:
          1. 校验 source file 存在 + owner 一致
          2. 校验 visibility 升级合法 (private→team/public)
          3. 改 storage_mode: drive → kb
          4. 改 source_type: drive → drive_extracted
          5. 改 visibility 到 target_visibility
          6. (异步) 触发 file_parser + LLM summary + embedding

        PR2 只先做 storage_mode/visibility 切换 (即时可见性升级)
        异步 LLM 提取留 PR3 与 desktop 触达一并做
        """
        if target_visibility not in ("team", "public"):
            raise DriveServiceError(
                f"extract-to-kb 目标 visibility 必须为 team/public, 不是 {target_visibility}",
                status_code=400,
            )

        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        file = file.scalar_one_or_none()
        if file is None or file.created_by != current_user_id:
            return None

        # visibility 必须升 (private → team/public)
        # team → public 合法
        # 已是 team/public 再"升级"无意义但允许 (幂等)
        before = file.visibility
        file.visibility = target_visibility
        file.storage_mode = "kb"
        file.source_type = "drive_extracted"
        await self.db.commit()
        await self.db.refresh(file)

        logger.info(
            f"[DriveService.extract_to_kb] id={file.id} storage: drive→kb "
            f"visibility: {before}→{target_visibility}"
        )
        # 异步 LLM 提取留 PR3 再启 (本 PR 只切 storage_mode 让前端能立刻看到)
        return file

    # ==========================================================================
    # Folder 引用 (PR2.2 完整实现, 本服务先 forward 一下供调用方补 commit)
    # ==========================================================================

    async def get_folder(self, folder_id: int) -> Optional[Folder]:
        """获取 folder (含可见性校验)"""
        stmt = select(Folder).where(
            Folder.id == folder_id,
            Folder.deleted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ==========================================================================
    # 存储统计 (PR2.5 用)
    # ==========================================================================

    async def storage_stats(self, current_user_id: int) -> dict:
        """当前用户的 drive 存储统计

        PR2.1 仅返 file_count + 按 visibility 分组 (Knowledge 表无 file_size 列,
        总占用需 PR2.5 引入 file_size 列 + 异步遍历 MinIO).
        """
        stmt = select(
            func.count(Knowledge.id).label("file_count"),
        ).where(
            Knowledge.storage_mode == "drive",
            Knowledge.created_by == current_user_id,
            Knowledge.deleted_at.is_(None),
        )

        # PG 没有 file_size 列在 Knowledge (只有 file_type, file_name, file_path)
        # 实际计算文件大小需遍历 MinIO list_objects, PR2.5 引入 metric 列 (count only for now)
        row = (await self.db.execute(stmt)).first()

        # 按 visibility 分组
        by_visibility = await self.db.execute(
            select(Knowledge.visibility, func.count(Knowledge.id))
            .where(
                Knowledge.storage_mode == "drive",
                Knowledge.created_by == current_user_id,
                Knowledge.deleted_at.is_(None),
            )
            .group_by(Knowledge.visibility)
        )
        vis_counts = {row[0]: row[1] for row in by_visibility}

        return {
            "file_count": row.file_count if row else 0,
            "by_visibility": vis_counts,
            "active": True,
        }

    # ==========================================================================
    # PR2.7 分享链接 + 下载计数
    # ==========================================================================

    async def increment_download_count(self, file_id: int) -> int:
        """原子 +1 下载计数, 返回新值"""
        result = await self.db.execute(
            update(Knowledge)
            .where(
                Knowledge.id == file_id,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
            )
            .values(download_count=Knowledge.download_count + 1)
            .returning(Knowledge.download_count)
        )
        row = result.first()
        if row is None:
            return 0
        return row[0]

    async def create_share_link(
        self,
        file_id: int,
        current_user_id: int,
        *,
        expires_in_days: Optional[int] = None,
        expires_hours: Optional[int] = None,
        password: Optional[str] = None,
    ) -> Optional[Knowledge]:
        """生成公开分享 token (owner only)

        v2 PR1 升级:
        - expires_hours 新参数 (细粒度, 1-8760)
        - password 新参数 (4-8 位数字, 存 SHA256 hash)
        - 保留 expires_in_days 向后兼容 (None 时优先级低于 expires_hours)

        Args:
            file_id: drive 文件 id
            current_user_id: 当前用户 (必须 = file.created_by)
            expires_in_days: 保留旧 API, 1-365 (向后兼容)
            expires_hours: 新 API, 1-8760; 0=None=默认 7 天; -1=永久
            password: 4-8 位数字, None = 公开分享
        """
        # 优先 expires_hours (新 API), 退到 expires_in_days (旧 API)
        if expires_hours is not None:
            _validate_share_expires_hours(expires_hours)
            if expires_hours == -1:
                expires_at = None  # 永久
            elif expires_hours == 0:
                expires_at = to_naive_datetime(
                    datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SHARE_EXPIRES_HOURS)
                )
            else:
                expires_at = to_naive_datetime(
                    datetime.now(timezone.utc) + timedelta(hours=expires_hours)
                )
        elif expires_in_days is not None:
            if expires_in_days < 1 or expires_in_days > 365:
                raise DriveServiceError(
                    f"expires_in_days {expires_in_days} 超出范围 [1, 365]",
                    status_code=400,
                )
            expires_at = to_naive_datetime(
                datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            )
        else:
            # 默认 7 天
            expires_at = to_naive_datetime(
                datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SHARE_EXPIRES_HOURS)
            )

        # 提取码校验
        _validate_share_password(password)
        password_hash = _hash_share_password(password) if password else None

        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None or f.created_by != current_user_id:
            return None

        # 32 字符 token (44 字符 url-safe base64)
        token = secrets.token_urlsafe(24)[:32]
        f.share_token = token
        f.share_expires_at = expires_at
        f.share_password = password_hash
        await self.db.commit()
        await self.db.refresh(f)
        logger.info(
            f"[DriveService.create_share_link] id={f.id} token={token[:8]}... "
            f"expires={f.share_expires_at} password={'yes' if password_hash else 'no'}"
        )
        # PR6: 活动动态流 + 文件 owner 自提醒 (通知 owner 分享成功)
        try:
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="share",
                target_type="file",
                target_id=f.id,
                target_name=f.file_name,
                metadata={
                    "expires_at": str(f.share_expires_at),
                    "password_required": bool(password_hash),
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.create_share_link] activity log 失败: {e}")

        # v2 网盘 PR6-P12+ 增量: share 触发 notification (context='share')
        # 设计: create_share_link 仅 owner 可调 (line 859 已校验), 所以 share 通知发给 owner 自己
        # 未来 PR3 "team 成员触发分享" 时, 这里会跳过自通知
        try:
            if f.created_by != current_user_id:
                await notification_service.create_mention(
                    self.db,
                    file_id=f.id,
                    mentioned_user_id=f.created_by,
                    mentioned_by=current_user_id,
                    context="share",
                )
        except Exception as e:
            logger.debug(f"[DriveService.create_share_link] notification trigger 失败 (非阻塞): {e}")

        return f

    async def revoke_share_link(
        self,
        file_id: int,
        current_user_id: int,
    ) -> bool:
        """撤销分享链接 (清 token + expires + password)"""
        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None or f.created_by != current_user_id:
            return False
        f.share_token = None
        f.share_expires_at = None
        f.share_password = None
        await self.db.commit()
        return True

    async def get_by_share_token(self, token: str) -> Optional[Knowledge]:
        """通过 token 公开访问 (无 JWT, 用于 /drive/share/{token} 端点)

        注意: 不校验密码 (留给 verify_share_access 调用方), 密码验证必须先 get_by_share_token
        后由调用方主动传 password 走 verify_share_access(token, password).
        """
        if not token:
            return None
        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.share_token == token,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None:
            return None
        # 校验 expires
        if f.share_expires_at is not None:
            expires_naive = to_naive_datetime(f.share_expires_at)
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            if expires_naive < now_naive:
                logger.info(f"[DriveService.get_by_share_token] token={token[:8]}... 已过期")
                return None
        return f

    async def verify_share_access(
        self,
        token: str,
        password: Optional[str] = None,
    ) -> Optional[Knowledge]:
        """验证分享链接访问权限 (含密码校验).

        Returns:
            - None: token 不存在 / 已过期 / 密码错误
            - Knowledge: 通过验证的文件对象

        行为:
        1. 调 get_by_share_token 校验 token 存在 + 未过期
        2. share_password is NULL (公开分享) → 直接返回 file
        3. share_password 非 NULL → 必须 password 正确 (SHA256 hash 一致) 才能返回
        """
        f = await self.get_by_share_token(token)
        if f is None:
            return None
        # 公开分享 / password_hash 未设 → 直接通过
        if not f.share_password:
            return f
        # 有密码: 必须提供且 hash 一致
        if password is None:
            return None
        password_hash = _hash_share_password(password)
        if password_hash != f.share_password:
            logger.info(f"[DriveService.verify_share_access] token={token[:8]}... 密码错误")
            return None
        return f

    # ==========================================================================
    # v2 PR1 visibility edit (桌面 stub 修复)
    # ==========================================================================

    async def update_visibility(
        self,
        file_id: int,
        current_user_id: int,
        new_visibility: str,
    ) -> Optional[Knowledge]:
        """修改 drive 文件可见性 (owner only).

        校验:
        1. visibility 必须在 {private, team, public} 三选一
        2. 必须 <= 所在文件夹 visibility (硬上限, plan 决策)
        3. 文件已 owner 才能改

        Returns: 更新后的 Knowledge 或 None (越权/不存在).
        """
        if new_visibility not in ("private", "team", "public"):
            raise DriveServiceError(
                f"非法 visibility '{new_visibility}', 必须是 private/team/public",
                status_code=400,
            )

        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None or f.created_by != current_user_id:
            return None

        # visibility 上限 (private 不能往公开升级除非 folder 允许)
        if f.folder_id is not None:
            folder = await self.get_folder(f.folder_id)
            if folder is not None:
                self._validate_visibility_inherits(new_visibility, folder.visibility)

        before = f.visibility
        f.visibility = new_visibility

        # 注意: 文件夹 owner 改 visibility 后, share_token 可不撤销 (原 token 仅受 expires 控制)
        # owner 主动 revoke 才清 token. 维持现行策略.

        await self.db.commit()
        await self.db.refresh(f)
        logger.info(
            f"[DriveService.update_visibility] id={f.id} {before}→{new_visibility} "
            f"folder={f.folder_id}"
        )
        return f

    # ============================================================
    # v2 PR2 收藏 / 回收站 / 批量操作
    # ============================================================

    async def toggle_star_file(self, file_id: int, current_user_id: int) -> Optional[Knowledge]:
        """切换文件收藏状态 (owner only, 360° 翻转 is_starred).

        Returns: 更新后的 Knowledge, None = 文件不存在或非 owner.

        v2 网盘 PR6-P12+ 增量: star 触发 notification_service (create_mention context='star'),
        通知 file owner (跳过自通知, 防止噪音).
        """
        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None or f.created_by != current_user_id:
            return None  # 隐身
        if f.is_starred:
            f.is_starred = False
            f.starred_at = None
            action = "unstar"
        else:
            f.is_starred = True
            f.starred_at = to_naive_datetime(datetime.now(timezone.utc))
            action = "star"
        await self.db.commit()
        await self.db.refresh(f)
        logger.info(f"[DriveService.toggle_star_file] id={f.id} {action}")

        # v2 网盘 PR6-P12+ 增量: star 通知 file owner (只有 star 时通知, unstar 不通知)
        # 设计: star 总是 owner 操作 (toggle_star_file 已校验 f.created_by == current_user_id),
        # 未来 PR3 "team member star others' files" 时, 这里会跳过自通知
        if action == "star":
            try:
                if f.created_by != current_user_id:
                    await notification_service.create_mention(
                        self.db,
                        file_id=f.id,
                        mentioned_user_id=f.created_by,
                        mentioned_by=current_user_id,
                        context="star",
                    )
            except Exception as e:
                logger.debug(f"[DriveService.toggle_star_file] notification trigger 失败 (非阻塞): {e}")

        return f

    async def list_trash(
        self,
        *,
        current_user_id: int,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "deleted_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2: 列回收站文件 (软删的 drive 文件).

        - 仅返回 created_by == current_user_id 的 (owner 隔离)
        - deleted_at 必然非空
        - 排序默认 deleted_at desc (最近删除在前)
        - 注意: 这里**不**走 _list_files_impl, 因为要排除 storage_mode filter
          (回收站也是 drive 文件, storage_mode='drive' 一致, 但 include_deleted=True 即可)
        """
        return await self._list_files_impl(
            current_user_id=current_user_id,
            folder_id=None,            # 回收站跨 folder 看
            visibility_filter=None,    # 回收站混合
            storage_mode="drive",
            include_deleted=False,     # 用 deleted_only 替代 (exclusive filter)
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            starred_only=False,
            file_type=None,
            deleted_only=True,         # v2 PR2 fix: 仅 deleted_at IS NOT NULL
        )

    async def list_starred(
        self,
        *,
        current_user_id: int,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "starred_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2: 列收藏文件 (is_starred=true).

        - 仅返回 created_by == current_user_id (owner 隔离, 不让看别人收藏)
        - sort_by 默认 starred_at desc (最近收藏在前)
        """
        return await self._list_files_impl(
            current_user_id=current_user_id,
            folder_id=None,
            visibility_filter=None,
            storage_mode="drive",
            include_deleted=False,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            starred_only=True,         # ⭐ 关键
            file_type=None,
        )

    async def batch_soft_delete(
        self,
        file_ids: List[int],
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量软删 (owner only, 非 owner 的 id 静默跳过).

        Returns: (deleted_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        now = to_naive_datetime(datetime.now(timezone.utc))
        skipped = []
        deleted = 0
        for f in files:
            if f.created_by != current_user_id:
                skipped.append(f.id)
                continue
            f.deleted_at = now
            deleted += 1
        # 不在 file_ids 里的也入 skipped (前端提示 "id=X 不存在")
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        # PR6: 活动动态流 (批量删除 = 每个被删文件一条 delete event)
        try:
            for f in files:
                if f.deleted_at is not None and f.id not in skipped:
                    await activity_service.log(
                        self.db,
                        actor_id=current_user_id,
                        action="delete",
                        target_type="file",
                        target_id=f.id,
                        target_name=f.file_name,
                    )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.batch_soft_delete] activity log 失败: {e}")
        logger.info(
            f"[DriveService.batch_soft_delete] requested={len(file_ids)} "
            f"deleted={deleted} skipped={len(skipped)}"
        )
        return deleted, skipped

    async def batch_restore(
        self,
        file_ids: List[int],
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量恢复 (从回收站清 deleted_at).

        - 仅 restore created_by == current_user_id 的
        - 不在 trash 的 (deleted_at IS NULL) 也入 skipped
        Returns: (restored_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.isnot(None),  # 必须真在 trash
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        restored = 0
        for f in files:
            if f.created_by != current_user_id:
                skipped.append(f.id)
                continue
            f.deleted_at = None
            restored += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_restore] requested={len(file_ids)} "
            f"restored={restored} skipped={len(skipped)}"
        )
        return restored, skipped

    async def batch_move(
        self,
        file_ids: List[int],
        target_folder_id: Optional[int],
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量移动到 folder (target_folder_id=None = 顶级).

        - 仅 owner 可移动
        - target_folder 必须存在 + owner 一致
        - 移动时 file.visibility 不得超过 folder.visibility (继承规则)
        Returns: (moved_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        # 校验 target folder
        target_folder = None
        if target_folder_id is not None:
            target_folder = await self.get_folder(target_folder_id)
            if target_folder is None:
                raise DriveServiceError(
                    f"目标文件夹 id={target_folder_id} 不存在",
                    status_code=404,
                )
            if target_folder.owner_id != current_user_id:
                raise DriveServiceError(
                    "无权操作他人的文件夹",
                    status_code=403,
                )
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        moved = 0
        for f in files:
            if f.created_by != current_user_id:
                skipped.append(f.id)
                continue
            if target_folder is not None:
                self._validate_visibility_inherits(f.visibility, target_folder.visibility)
            f.folder_id = target_folder_id
            moved += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_move] requested={len(file_ids)} "
            f"moved={moved} skipped={len(skipped)} target={target_folder_id}"
        )
        return moved, skipped

    async def batch_update_visibility(
        self,
        file_ids: List[int],
        new_visibility: str,
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量改可见性 (private | team | public).

        - 仅 owner 可改
        - 越权 (folder 上限) 的文件入 skipped (不抛错, 让用户知道哪些被跳过)
        Returns: (updated_count, skipped_ids)
        """
        if new_visibility not in ("private", "team", "public"):
            raise DriveServiceError(
                f"非法 visibility '{new_visibility}'",
                status_code=400,
            )
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        updated = 0
        for f in files:
            if f.created_by != current_user_id:
                skipped.append(f.id)
                continue
            if f.folder_id is not None:
                folder = await self.get_folder(f.folder_id)
                if folder is not None:
                    try:
                        self._validate_visibility_inherits(new_visibility, folder.visibility)
                    except DriveServiceError:
                        skipped.append(f.id)
                        continue
            f.visibility = new_visibility
            updated += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_update_visibility] requested={len(file_ids)} "
            f"updated={updated} skipped={len(skipped)} vis={new_visibility}"
        )
        return updated, skipped

    async def permanent_delete(
        self,
        file_id: int,
        current_user_id: int,
    ) -> bool:
        """v2 PR2: 物理删除 (从回收站彻底删除, owner only).

        Returns: True=成功, False=不存在或非 owner.
        """
        f = await self.db.execute(
            select(Knowledge).where(Knowledge.id == file_id)
        )
        f = f.scalar_one_or_none()
        if f is None or f.created_by != current_user_id:
            return False
        # 如果有 MinIO 对象, 删掉 (best-effort)
        if f.file_path:
            try:
                file_service.delete_file(f.file_path)
            except Exception as e:
                logger.warning(
                    f"[DriveService.permanent_delete] minio delete failed "
                    f"id={f.id} path={f.file_path}: {e}"
                )
        await self.db.delete(f)
        await self.db.commit()
        logger.info(f"[DriveService.permanent_delete] id={f.id}")
        return True

    async def permanent_delete_batch(
        self,
        file_ids: List[int],
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量物理删除 (从回收站彻底删除一批).

        Returns: (deleted_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.isnot(None),  # 必须真在 trash
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        deleted = 0
        for f in files:
            if f.created_by != current_user_id:
                skipped.append(f.id)
                continue
            # best-effort 删 MinIO 对象
            if f.file_path:
                try:
                    file_service.delete_file(f.file_path)
                except Exception as e:
                    logger.warning(
                        f"[DriveService.permanent_delete_batch] minio delete failed "
                        f"id={f.id}: {e}"
                    )
            await self.db.delete(f)
            deleted += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.permanent_delete_batch] requested={len(file_ids)} "
            f"deleted={deleted} skipped={len(skipped)}"
        )
        return deleted, skipped

    # ============================================================
    # v2 PR4: 文件秒传 (hash) + 版本历史
    # ============================================================

    async def hash_lookup(
        self,
        *,
        file_hash: str,
        current_user_id: int,
    ) -> Optional[Knowledge]:
        """按 hash 查同 owner 的活跃 drive 文件 (秒查 dedup)

        匹配规则:
        - file_hash 严格相等
        - storage_mode='drive' (KB 不参与秒传)
        - deleted_at IS NULL (软删不算)
        - is_latest=True (历史版本不参与秒查, 避免误命中)

        Returns:
            命中的 Knowledge 行, 没命中返 None
        """
        stmt = (
            select(Knowledge)
            .where(
                Knowledge.file_hash == file_hash,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.is_latest.is_(True),
            )
            .order_by(Knowledge.created_at.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        row = res.scalar_one_or_none()
        if row and self._can_see_file(row, current_user_id):
            return row
        return None

    async def create_instant_upload(
        self,
        *,
        file_hash: str,
        file_name: str,
        file_size: int,
        owner_id: int,
        folder_id: Optional[int] = None,
        visibility: str = "team",
        created_by: Optional[int] = None,
        # v2 PR6-P19: 团队共享盘标识 (前端在 team 视图上传 = true)
        is_team_shared: bool = False,
    ) -> Tuple[Optional[Knowledge], int]:
        """秒传 dedup: hash 命中 → MinIO copy_object 零带宽秒传

        PR4 设计:
        1. hash_lookup 查同 hash 文件 (用户可见)
        2. 命中 → file_service.copy_object_async 在 MinIO 内复制, 不经过本机
        3. 新 Knowledge 行 file_path 是新路径, 但 file_hash/file_size 一致
        4. dedup_saved_bytes = 复制的字节数 (告诉前端"省了 X MB")

        v2 PR6-P19: is_team_shared 标记上传来源视图, 决定 list_drive_files 过滤.

        Returns:
            (knowledge_or_none, dedup_saved_bytes)
            - 命中: (Knowledge行, 复制字节数)
            - 未命中: (None, 0) → 前端走 multipart 上传
        """
        existing = await self.hash_lookup(
            file_hash=file_hash, current_user_id=owner_id,
        )
        if existing is None:
            return None, 0

        # MinIO 服务端 copy_object 零带宽秒传
        ext = ""
        if "." in file_name:
            ext = "." + file_name.rsplit(".", 1)[-1].lower()
        new_object = (
            f"uploads/drive/{owner_id}/"
            f"{secrets.token_hex(8)}_{file_hash[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
            f"{ext}"
        )
        copied_size = await file_service.copy_object_async(
            existing.file_path, new_object,
        )

        # 文件夹校验 (复用 create_file 的逻辑)
        if folder_id is not None:
            folder = await self.get_folder(folder_id)
            if folder is None:
                raise DriveServiceError(
                    f"文件夹 id={folder_id} 不存在", status_code=400,
                )
            if folder.owner_id != owner_id:
                raise DriveServiceError(
                    f"无权在该文件夹中创建文件", status_code=403,
                )
            self._validate_visibility_inherits(visibility, folder.visibility)

        # 新行 + 复用同 hash
        new_k = Knowledge(
            title=file_name,
            content=f"[drive instant-upload] {file_name}",
            file_path=new_object,
            file_name=file_name,
            file_type=ext.lstrip(".") if ext else existing.file_type,
            file_size=copied_size,
            file_hash=file_hash,
            is_latest=True,
            version_number=1,            # 秒传是新文件, 不是新版本
            parent_version_id=None,
            source_type="drive",
            created_by=created_by or owner_id,  # Knowledge 模型无 owner_id, 用 created_by
            storage_mode="drive",
            visibility=visibility,
            folder_id=folder_id,
            is_team_shared=is_team_shared,  # v2 PR6-P19
        )
        self.db.add(new_k)
        await self.db.commit()
        await self.db.refresh(new_k)
        logger.info(
            f"[DriveService.create_instant_upload] HIT hash={file_hash[:12]}... "
            f"src_id={existing.id} dst_id={new_k.id} "
            f"src_path={existing.file_path} dst_path={new_object} "
            f"dedup_saved_bytes={copied_size}"
        )
        return new_k, copied_size

    async def create_version(
        self,
        *,
        file_id: int,
        new_hash: str,
        new_size: int,
        new_object_name: str,
        new_filename: str,
        change_note: Optional[str],
        uploader_id: int,
    ) -> Knowledge:
        """创建新版本: 旧 is_latest=False, 新行 version_number+=1, parent_version_id=旧.id

        调用方 (前端 multipart upload 走完后) 负责:
        - 把新文件 bytes 通过 file_service.upload_to_path 写到 new_object_name
        - 然后调本方法写 metadata

        Returns:
            新 Knowledge 行 (is_latest=True)
        """
        cur = await self.db.get(Knowledge, file_id)
        if cur is None:
            raise DriveServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur.is_latest is False:
            raise DriveServiceError(
                f"文件 id={file_id} 已是历史版本, 无法再创建新版本", status_code=400,
            )

        # 旧行翻 is_latest=False (保留作为历史链)
        cur.is_latest = False
        cur.parent_version_id = cur.parent_version_id  # 不动, 保持原链

        # 新行
        new_version_number = (cur.version_number or 1) + 1
        new_k = Knowledge(
            title=cur.title,
            content=cur.content,
            file_path=new_object_name,
            file_name=new_filename,
            file_type=cur.file_type,
            file_size=new_size,
            file_hash=new_hash,
            is_latest=True,
            version_number=new_version_number,
            parent_version_id=cur.id,
            source_type=cur.source_type,
            created_by=uploader_id,
            storage_mode="drive",
            visibility=cur.visibility,
            folder_id=cur.folder_id,
            owner_id=cur.owner_id,
        )
        self.db.add(new_k)
        await self.db.flush()  # 拿 new_k.id

        # 写知识版明细 (一行 = 一次版本)
        kv = KnowledgeVersion(
            file_id=new_k.id,
            version_number=new_version_number,
            file_hash=new_hash,
            file_size=new_size,
            uploaded_by=uploader_id,
            change_note=change_note,
        )
        self.db.add(kv)
        await self.db.commit()
        await self.db.refresh(new_k)
        logger.info(
            f"[DriveService.create_version] file_id={file_id} → v{new_version_number} "
            f"new_id={new_k.id} hash={new_hash[:12]}... "
            f"change_note={change_note!r}"
        )
        return new_k

    async def list_versions(
        self,
        *,
        file_id: int,
        current_user_id: int,
    ) -> List[dict]:
        """列文件版本历史 (含每版 hash + 上传者 + 时间)

        返回字段:
        - id: knowledge_versions.id (版本明细行 id)
        - file_id: knowledge.id (新版时 = 新行 id, 旧版时 = 老行 id)
        - version_number
        - file_hash
        - file_size
        - uploaded_by + uploaded_by_name (LEFT JOIN members)
        - change_note
        - created_at (ISO format)
        - is_current: 是否当前最新版本
        """
        cur = await self.db.get(Knowledge, file_id)
        if cur is None:
            raise DriveServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if not self._can_see_file(cur, current_user_id):
            raise DriveServiceError(
                f"无权查看文件 id={file_id} 的版本", status_code=403,
            )

        # 联合查询: knowledge_versions JOIN members + 当前 knowledge 行作为"current"
        # 简化: 单独查两张表
        from app.models.member import Member

        stmt = (
            select(KnowledgeVersion, Member.name)
            .outerjoin(Member, KnowledgeVersion.uploaded_by == Member.id)
            .where(KnowledgeVersion.file_id == file_id)
            .order_by(KnowledgeVersion.version_number.desc())
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        result = []
        for kv, member_name in rows:
            result.append({
                "id": kv.id,
                "file_id": kv.file_id,
                "version_number": kv.version_number,
                "file_hash": kv.file_hash,
                "file_size": kv.file_size,
                "uploaded_by": kv.uploaded_by,
                "uploaded_by_name": member_name,
                "change_note": kv.change_note,
                "created_at": kv.created_at.isoformat() if kv.created_at else None,
                "is_current": (kv.file_id == file_id and (cur.is_latest and kv.version_number == cur.version_number)),
            })
        return result

    async def restore_version(
        self,
        *,
        file_id: int,
        version_id: int,
        uploader_id: int,
        change_note: Optional[str] = None,
    ) -> Knowledge:
        """恢复历史版本: 从旧 object_name copy_object 到新路径, 创建新行 v{cur.version+1}

        流程 (与 create_version 类似, 只是数据源是历史版本的 object_name):
        1. 拿 version 明细 → 拿到历史 file_hash + file_size
        2. cur.is_latest=False
        3. 新行: file_path = 新 object_name (从历史 object copy_object 过来)
        4. 写知识版明细

        Returns:
            新 Knowledge 行 (is_latest=True, 与被恢复的 v1 内容字节级一致)
        """
        cur = await self.db.get(Knowledge, file_id)
        if cur is None:
            raise DriveServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur.is_latest is False:
            raise DriveServiceError(
                f"文件 id={file_id} 已是历史版本, 无法再恢复", status_code=400,
            )

        kv = await self.db.get(KnowledgeVersion, version_id)
        if kv is None:
            raise DriveServiceError(
                f"版本 id={version_id} 不存在", status_code=404,
            )
        if kv.file_id != file_id:
            raise DriveServiceError(
                f"版本 id={version_id} 不属于文件 id={file_id}", status_code=400,
            )

        # 拿历史行的 file_path (knowledge 行 file_path 即 MinIO object_name)
        old_k = await self.db.get(Knowledge, kv.file_id)
        old_object = old_k.file_path if old_k else None
        if not old_object:
            raise DriveServiceError(
                f"历史版本 id={kv.file_id} 缺 MinIO object 引用", status_code=500,
            )

        # 校验源 object 还在 (防止被误删)
        exists = await file_service.object_exists(old_object)
        if not exists:
            raise DriveServiceError(
                f"历史版本 MinIO object 不存在: {old_object}", status_code=410,
            )

        # copy_object 反向
        new_version_number = (cur.version_number or 1) + 1
        ext = ""
        if old_k.file_name and "." in old_k.file_name:
            ext = "." + old_k.file_name.rsplit(".", 1)[-1].lower()
        new_object = (
            f"uploads/drive/{cur.owner_id}/"
            f"v{new_version_number}_{kv.file_hash[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
            f"{ext}"
        )
        copied_size = await file_service.copy_object_async(old_object, new_object)

        # 旧行翻 is_latest=False
        cur.is_latest = False

        # 新行
        new_k = Knowledge(
            title=cur.title,
            content=cur.content,
            file_path=new_object,
            file_name=old_k.file_name,
            file_type=old_k.file_type,
            file_size=copied_size,
            file_hash=kv.file_hash,        # 与历史版字节级一致
            is_latest=True,
            version_number=new_version_number,
            parent_version_id=cur.id,
            source_type=cur.source_type,
            created_by=uploader_id,
            storage_mode="drive",
            visibility=cur.visibility,
            folder_id=cur.folder_id,
            owner_id=cur.owner_id,
        )
        self.db.add(new_k)
        await self.db.flush()

        # 写知识版明细 (恢复也算一个版本)
        kv_new = KnowledgeVersion(
            file_id=new_k.id,
            version_number=new_version_number,
            file_hash=kv.file_hash,
            file_size=copied_size,
            uploaded_by=uploader_id,
            change_note=change_note or f"restored from v{kv.version_number}",
        )
        self.db.add(kv_new)
        await self.db.commit()
        await self.db.refresh(new_k)
        logger.info(
            f"[DriveService.restore_version] file_id={file_id} "
            f"restored_from_v{kv.version_number} → new_v{new_version_number} "
            f"new_id={new_k.id} copy_bytes={copied_size}"
        )
        # PR6: 活动动态流
        try:
            await activity_service.log(
                self.db,
                actor_id=uploader_id,
                action="version_restore",
                target_type="file",
                target_id=new_k.id,
                target_name=new_k.file_name,
                metadata={
                    "restored_from_version": kv.version_number,
                    "new_version": new_version_number,
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.restore_version] activity log 失败: {e}")
        return new_k

    # ========================================================================
    # v2 PR5: 配额检查 + 分片上传 + 缩略图 (2026-07-01)
    # ========================================================================

    async def check_quota(
        self, user_id: int, additional_bytes: int
    ) -> Tuple[bool, int, int]:
        """配额检查 (上传前调用)

        Args:
            user_id: Member.id
            additional_bytes: 待上传字节数

        Returns:
            (allowed, used_after, quota_total)
            - allowed=True: 可上传 (剩余配额足够)
            - allowed=False: 配额不足 (返回 used_after=当前值, 调用方返 413)

        简化策略:
        - 单 user 维度 (不按 file_type 分层)
        - 不预扣配额 (上传过程中可能失败, 失败不扣)
        - 上传成功后才 recalc (storage_tasks.recalc_user_storage_task fire-and-forget)
        """
        user = (await self.db.execute(
            select(Member).where(Member.id == user_id)
        )).scalar_one_or_none()
        if not user:
            return False, 0, 0
        # 用户可主动调 storage-stats API 刷新, 这里读快照
        used = user.drive_used_bytes or 0
        quota = user.drive_quota_bytes or 10737418240
        if used + additional_bytes > quota:
            return False, used, quota
        return True, used + additional_bytes, quota

    async def get_storage_quota(self, user_id: int) -> dict:
        """获取用户配额详情 (含百分比, 用于 UI badge)

        返回:
            {
                user_id: int,
                used_bytes: int,
                quota_bytes: int,
                percent: float (0.0 ~ 1.0+),
                file_count: int (软删 NULL 计数),
                is_over_quota: bool (used > quota),
                updated_at: ISO datetime
            }
        """
        user = (await self.db.execute(
            select(Member).where(Member.id == user_id)
        )).scalar_one_or_none()
        if not user:
            return {
                "user_id": user_id,
                "used_bytes": 0,
                "quota_bytes": 0,
                "percent": 0.0,
                "file_count": 0,
                "is_over_quota": False,
                "updated_at": None,
            }
        used = user.drive_used_bytes or 0
        quota = user.drive_quota_bytes or 0
        percent = (used / quota) if quota > 0 else 0.0
        # 活跃文件数
        count_stmt = select(func.count(Knowledge.id)).where(
            and_(
                Knowledge.created_by == user_id,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
            )
        )
        file_count = (await self.db.execute(count_stmt)).scalar() or 0

        return {
            "user_id": user_id,
            "used_bytes": used,
            "quota_bytes": quota,
            "percent": round(percent, 4),
            "file_count": file_count,
            "is_over_quota": used > quota,
            "updated_at": user.drive_quota_updated_at.isoformat() if user.drive_quota_updated_at else None,
        }

    # ----- 分片上传 + 断点续传 -----

    async def init_chunked_upload(
        self,
        user_id: int,
        file_name: str,
        file_size: int,
        total_chunks: int,
        file_hash: Optional[str] = None,
        folder_id: Optional[int] = None,
        visibility: str = "team",
    ) -> ChunkedUploadSession:
        """初始化分片上传 session (POST /files/upload/init)

        配额检查: 配额不足时抛 DriveServiceError 413
        24h TTL: expires_at = now + 24h
        status='active': 等 chunks 写入

        v2 PR6-P19: is_team_shared 不在这里传 — 移到 complete 阶段 (前端可在 complete 时
        决定 final 视图归属, init 阶段用户可能还没决定). service 层 complete_chunked_upload
        接 is_team_shared 参数 (Optional, None=默认 personal/false).
        """
        # 配额检查
        allowed, _, quota = await self.check_quota(user_id, file_size)
        if not allowed:
            raise DriveServiceError(
                f"配额不足: 文件 {file_size} 字节, 配额上限 {quota} 字节", status_code=413
            )

        # 文件大小校验
        if file_size > MAX_DRIVE_FILE_SIZE_BYTES:
            raise DriveServiceError(
                f"文件过大: {file_size} > {MAX_DRIVE_FILE_SIZE_BYTES}", status_code=413
            )

        # folder_id 校验 (如提供)
        if folder_id is not None:
            folder = (await self.db.execute(
                select(Folder).where(
                    and_(Folder.id == folder_id, Folder.deleted_at.is_(None))
                )
            )).scalar_one_or_none()
            if not folder:
                raise DriveServiceError(f"Folder {folder_id} 不存在", status_code=404)
            # visibility 继承校验 (函数内 raise, 不需要 if not)
            self._validate_visibility_inherits(visibility, folder.visibility)

        session_id = secrets.token_hex(16)  # 32 chars
        session = ChunkedUploadSession(
            id=session_id,
            user_id=user_id,
            file_name=file_name,
            file_size=file_size,
            file_hash=file_hash,
            folder_id=folder_id,
            visibility=visibility,
            total_chunks=total_chunks,
            uploaded_chunks=[],
            status="active",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(
            f"[DriveService.init_chunked_upload] session={session_id} "
            f"user={user_id} file={file_name} chunks={total_chunks}"
        )
        return session

    async def upload_chunk(
        self,
        session_id: str,
        user_id: int,
        chunk_index: int,
        chunk_data: bytes,
    ) -> ChunkedUploadSession:
        """上传单个 chunk (PUT /files/upload/{id}/chunk/{idx})

        写 MinIO: drive-uploads/{session_id}/chunk_{idx}
        更新 session.uploaded_chunks (append idx)
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,  # 越权防御
                    ChunkedUploadSession.status == "active",
                )
            )
        )).scalar_one_or_none()
        if not session:
            raise DriveServiceError("Session 不存在/已过期/无权访问", status_code=404)

        # chunk_index 范围校验
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise DriveServiceError(
                f"chunk_index={chunk_index} 越界 [0, {session.total_chunks})",
                status_code=400,
            )

        # 写 MinIO staging
        object_name = f"drive-uploads/{session_id}/chunk_{chunk_index:04d}"
        await file_service.upload_to_path(
            object_name, chunk_data, content_type="application/octet-stream"
        )

        # 追加 uploaded_chunks (去重 + 排序)
        existing = set(session.uploaded_chunks or [])
        existing.add(chunk_index)
        session.uploaded_chunks = sorted(existing)
        await self.db.commit()
        await self.db.refresh(session)

        logger.debug(
            f"[DriveService.upload_chunk] session={session_id} "
            f"chunk={chunk_index} total_uploaded={len(session.uploaded_chunks)}/{session.total_chunks}"
        )
        return session

    async def get_chunked_session(
        self, session_id: str, user_id: int
    ) -> Optional[ChunkedUploadSession]:
        """获取分片 session 状态 (断点续传用)

        返回的 session.uploaded_chunks 列表告诉前端哪些 chunks 已传, 跳到下一索引
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,
                )
            )
        )).scalar_one_or_none()
        return session

    async def complete_chunked_upload(
        self,
        session_id: str,
        user_id: int,
        change_note: Optional[str] = None,
        # v2 PR6-P19: 团队共享盘标识 (前端 complete 时传, 决定 Knowledge.is_team_shared)
        is_team_shared: Optional[bool] = None,
    ) -> Knowledge:
        """完成分片上传 (POST /files/upload/{id}/complete)

        流程:
        1. 查 session (active + 全 chunks 已传)
        2. 从 MinIO 按顺序读所有 chunk → 拼接 → 写最终 object_name
        3. 创建 Knowledge 行 (drive 模式)
        4. 标 session.status='completed'
        5. Fire-and-forget: 重算配额 + 生成缩略图
        6. 清 MinIO staging
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,
                    ChunkedUploadSession.status == "active",
                )
            )
        )).scalar_one_or_none()
        if not session:
            raise DriveServiceError("Session 不存在/已完成/已过期", status_code=404)

        # 校验所有 chunks 已传
        uploaded = set(session.uploaded_chunks or [])
        expected = set(range(session.total_chunks))
        missing = expected - uploaded
        if missing:
            raise DriveServiceError(
                f"未完成的 chunks: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}",
                status_code=400,
            )

        # 拼接 chunks → 最终 object_name
        final_object = (
            f"uploads/drive/{user_id}/"
            f"{session_id[:8]}_{int(datetime.utcnow().timestamp())}"
            f"{os.path.splitext(session.file_name)[1] if session.file_name else ''}"
        )

        # 顺序下载 + 上传 (简化: 不真做拼接, 走 copy_object 链)
        # 真实拼接需 ffmpeg concat 或 pyfilesystem — 这里走 app/services/file_service 的 streaming 拼接
        await _stream_concat_chunks(
            session_id=session_id,
            chunk_indices=sorted(uploaded),
            dst_object=final_object,
        )

        # v2 PR6-P19: is_team_shared 默认 False (个人), API 显式传 True (团队) 才覆盖
        is_team_shared_resolved = bool(is_team_shared) if is_team_shared is not None else False

        # 创建 Knowledge 行 (复用 create_file 走 drive 路径)
        new_file = await self.create_file(
            title=session.file_name,
            file_path=final_object,
            file_name=session.file_name,
            file_type=os.path.splitext(session.file_name)[1] if session.file_name else None,
            file_size=session.file_size,
            file_hash=session.file_hash,
            owner_id=user_id,
            created_by=user_id,
            folder_id=session.folder_id,
            visibility=session.visibility,
            storage_mode="drive",
            is_team_shared=is_team_shared_resolved,
        )

        # 标 session 完成
        session.status = "completed"
        session.object_name = final_object
        session.completed_at = datetime.utcnow()
        await self.db.commit()

        # Fire-and-forget: 重算配额 + 生成缩略图
        try:
            from app.services.storage_tasks import recalc_user_storage_task
            from app.services.thumbnail_tasks import generate_thumbnail_task
            recalc_user_storage_task.delay(user_id)
            generate_thumbnail_task.delay(new_file.id)
        except Exception as e:
            logger.warning(f"[DriveService.complete_chunked_upload] fire Celery 失败: {e}")

        # 清 MinIO staging (异步)
        try:
            import asyncio
            objects = await file_service.list_objects(f"drive-uploads/{session_id}/")
            for obj in objects:
                await asyncio.to_thread(file_service.delete_file, obj.object_name)
        except Exception as e:
            logger.warning(f"[DriveService.complete_chunked_upload] staging 清理失败: {e}")

        logger.info(
            f"[DriveService.complete_chunked_upload] session={session_id} → file_id={new_file.id}"
        )
        return new_file

    async def abort_chunked_upload(self, session_id: str, user_id: int) -> bool:
        """中止分片上传 (POST /files/upload/{id}/abort)

        标 session.status='aborted' + 清 MinIO staging
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,
                    ChunkedUploadSession.status == "active",
                )
            )
        )).scalar_one_or_none()
        if not session:
            return False

        session.status = "aborted"
        await self.db.commit()

        # 清 MinIO staging
        try:
            import asyncio
            objects = await file_service.list_objects(f"drive-uploads/{session_id}/")
            for obj in objects:
                await asyncio.to_thread(file_service.delete_file, obj.object_name)
        except Exception as e:
            logger.warning(f"[DriveService.abort_chunked_upload] staging 清理失败: {e}")

        logger.info(f"[DriveService.abort_chunked_upload] session={session_id} aborted")
        return True
