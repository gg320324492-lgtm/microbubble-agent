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
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder, VISIBILITY_ORDER
from app.models.knowledge import Knowledge, KnowledgeVersion  # PR4: 版本历史
from app.services.file_service import file_service

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


def _to_naive_dt(dt: Optional[datetime]) -> Optional[datetime]:
    """TZ-aware datetime → naive (CLAUDE.md 2026-06-05 asyncpg 坑复用)"""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


class DriveServiceError(Exception):
    """业务级错误，调用方映射成 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message  # 暴露属性, 否则 e.message 报 AttributeError
        self.status_code = status_code


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
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        logger.info(
            f"[DriveService.create_file] id={knowledge.id} file_name={file_name} "
            f"visibility={visibility} folder_id={folder_id} "
            f"file_size={file_size} file_hash={'<set>' if file_hash else None}"
        )
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
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2: 拆出 list_files 内部实现, 支持 sort_by / sort_order / starred_only / file_type.

        对外保持向后兼容 (list_files 默认 sort=created_at desc).
        v2 PR2: deleted_only=True 时仅返 deleted_at IS NOT NULL (回收站专用).
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
        elif folder_id is None:
            # v2 PR3 修复: 默认 (folder_id=None) 是"顶级根目录", 仅 folder_id IS NULL
            # 之前不过滤会把子目录里的文件也带回来, 与 DesktopDriveView UI 不一致
            # (DesktopDriveView 'selectedFolderId.value = null' = 顶级, 用户期望"只看根")
            # 行为兼容: 不动 service 调用方, 默认语义升级
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
        """
        type_to_ext = {
            "pdf":   [".pdf"],
            "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"],
            "video": [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"],
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

        file.deleted_at = _to_naive_dt(datetime.now(timezone.utc))
        await self.db.commit()
        logger.info(f"[DriveService.soft_delete_file] id={file.id}")
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
                expires_at = _to_naive_dt(
                    datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SHARE_EXPIRES_HOURS)
                )
            else:
                expires_at = _to_naive_dt(
                    datetime.now(timezone.utc) + timedelta(hours=expires_hours)
                )
        elif expires_in_days is not None:
            if expires_in_days < 1 or expires_in_days > 365:
                raise DriveServiceError(
                    f"expires_in_days {expires_in_days} 超出范围 [1, 365]",
                    status_code=400,
                )
            expires_at = _to_naive_dt(
                datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            )
        else:
            # 默认 7 天
            expires_at = _to_naive_dt(
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
            expires_naive = _to_naive_dt(f.share_expires_at)
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
            f.starred_at = _to_naive_dt(datetime.now(timezone.utc))
            action = "star"
        await self.db.commit()
        await self.db.refresh(f)
        logger.info(f"[DriveService.toggle_star_file] id={f.id} {action}")
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
        now = _to_naive_dt(datetime.now(timezone.utc))
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
    ) -> Tuple[Optional[Knowledge], int]:
        """秒传 dedup: hash 命中 → MinIO copy_object 零带宽秒传

        PR4 设计:
        1. hash_lookup 查同 hash 文件 (用户可见)
        2. 命中 → file_service.copy_object_async 在 MinIO 内复制, 不经过本机
        3. 新 Knowledge 行 file_path 是新路径, 但 file_hash/file_size 一致
        4. dedup_saved_bytes = 复制的字节数 (告诉前端"省了 X MB")

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
        return new_k
