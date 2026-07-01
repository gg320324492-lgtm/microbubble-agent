"""Drive 文件服务 (PR2.1)

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
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder, VISIBILITY_ORDER
from app.models.knowledge import Knowledge
from app.services.file_service import file_service

logger = logging.getLogger("microbubble.drive")


# 默认配额
MAX_DRIVE_FILE_SIZE_MB = 2048  # MinIO multipart 安全上限
MAX_DRIVE_FILE_SIZE_BYTES = MAX_DRIVE_FILE_SIZE_MB * 1024 * 1024


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
            f"visibility={visibility} folder_id={folder_id}"
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
    ) -> Tuple[List[Knowledge], int]:
        """列 drive 文件 (含列表 SQL 越权防御)

        Args:
            current_user_id: 当前用户 (用于 private 文件过滤)
            folder_id: 仅列该文件夹的文件 (None = 顶级)
            visibility_filter: 过滤特定 visibility (None = 不限定)
            storage_mode: 默认 drive (filter out kb)
            include_deleted: True = 含已软删 (admin)
            page, page_size: 分页

        Returns:
            (items, total)
        """
        stmt = select(Knowledge)
        count_stmt = select(func.count(Knowledge.id))

        filters = [Knowledge.storage_mode == storage_mode]
        if not include_deleted:
            filters.append(Knowledge.deleted_at.is_(None))
        if folder_id is not None:
            filters.append(Knowledge.folder_id == folder_id)
        if visibility_filter:
            filters.append(Knowledge.visibility == visibility_filter)

        # 核心隐私边界: private 文件仅 owner 可见
        visibility_see_cond = or_(
            Knowledge.created_by == current_user_id,
            Knowledge.visibility != "private",
        )
        filters.append(visibility_see_cond)

        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

        # 排序: 最新的在前
        stmt = stmt.order_by(Knowledge.created_at.desc())

        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items_result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = count_result.scalar() or 0

        return items, total

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
