"""Folder 服务 (PR2.2)

负责 folders 表的 CRUD 操作 + 嵌套深度校验 + 可见性继承。

核心规则:
- 嵌套深度 ≤ 5 (PR1 用户决策, 防 UI 渲染崩溃)
- 可见性继承: 子文件夹 visibility 必须 ≤ 父 (同 drive_service 规则)
- 物化路径 path='/1/4/7/' 形式自动维护, 便于 O(子项数) 列出子节点
- 软删除: deleted_at=NOW → Celery beat 3 天后物理清除 (PR1.2 复用 drive 清理)
- owner_id 强制 owner 校验 (防越权操作别人 folder)
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_, select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder, VISIBILITY_ORDER, MAX_FOLDER_DEPTH

logger = logging.getLogger("microbubble.folder")


class FolderServiceError(Exception):
    """业务级错误，调用方映射成 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class FolderService:
    """Folder CRUD + 嵌套管理"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 可见性校验
    # ==========================================================================

    @staticmethod
    def _validate_visibility_inherits(
        child_visibility: str,
        parent_visibility: Optional[str],
    ) -> None:
        """验证子文件夹 visibility ≤ 父文件夹 visibility (防止越权暴露)

        同 drive_service._validate_visibility_inherits, 但作用于 folder↔folder
        例如:
          parent=private → child 只能是 private
          parent=team    → child 可以是 private/team/public
          parent=public  → child 只能是 public
        """
        if parent_visibility is None:
            return
        if VISIBILITY_ORDER.get(child_visibility, -1) > VISIBILITY_ORDER.get(parent_visibility, -1):
            raise FolderServiceError(
                f"子文件夹可见性 ({child_visibility}) 高于父文件夹可见性 ({parent_visibility})，越权暴露",
                status_code=400,
            )

    @staticmethod
    def _compute_depth(parent_depth: Optional[int]) -> int:
        """根据父 folder depth 算子 folder 的 depth (顶 depth=0, max=5)"""
        if parent_depth is None:
            return 0
        return parent_depth + 1

    @staticmethod
    def _check_depth_within_limit(depth: int) -> None:
        """校验 depth 不超过 MAX_FOLDER_DEPTH"""
        if depth > MAX_FOLDER_DEPTH:
            raise FolderServiceError(
                f"嵌套深度 {depth} 超过上限 {MAX_FOLDER_DEPTH} (用户决策 PR1)",
                status_code=400,
            )

    # ==========================================================================
    # CRUD
    # ==========================================================================

    async def create_folder(
        self,
        *,
        name: str,
        owner_id: int,
        parent_id: Optional[int] = None,
        visibility: str = "team",
    ) -> Folder:
        """创建 folder (顶级或子级)

        Args:
            name: 文件夹名 (1-200 chars)
            owner_id: 仓库所有者
            parent_id: 父 folder id (None = 顶级)
            visibility: private/team/public (默认 team)
        Returns: Folder 对象 (path/depth 已自动维护)
        Raises: FolderServiceError on depth/visibility 违规
        """
        if not name or len(name) > 200:
            raise FolderServiceError(f"文件夹名长度非法: '{name[:20]}...'", status_code=400)
        if visibility not in VISIBILITY_ORDER:
            raise FolderServiceError(f"非法 visibility: {visibility}", status_code=400)

        # 父 folder 校验
        parent: Optional[Folder] = None
        if parent_id is not None:
            parent = await self.get_folder(parent_id)
            if parent is None:
                raise FolderServiceError(f"父文件夹 id={parent_id} 不存在", status_code=400)
            # 跨用户校验（防越权）
            if parent.owner_id != owner_id:
                raise FolderServiceError(
                    f"无权在别人 (id={parent.owner_id}) 文件夹下创建子文件夹",
                    status_code=403,
                )
            # visibility 继承
            self._validate_visibility_inherits(visibility, parent.visibility)

        # 深度校验
        depth = self._compute_depth(parent.depth if parent else None)
        self._check_depth_within_limit(depth)

        folder = Folder(
            name=name,
            owner_id=owner_id,
            parent_id=parent_id,
            visibility=visibility,
            path="/",  # 提交后 refresh 前不能根据 id 算 path, 先占位
            depth=depth,
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)

        # 物化 path (refresh 后能拿到 id)
        if parent is not None:
            folder.path = f"{parent.path}{folder.id}/"
        else:
            folder.path = f"/{folder.id}/"
        await self.db.commit()
        await self.db.refresh(folder)

        logger.info(
            f"[FolderService.create_folder] id={folder.id} name='{name}' "
            f"depth={depth} path='{folder.path}' visibility={visibility}"
        )
        return folder

    async def get_folder(
        self,
        folder_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Folder]:
        """获取 folder 详情 (默认过滤软删)"""
        stmt = select(Folder).where(Folder.id == folder_id)
        if not include_deleted:
            stmt = stmt.where(Folder.deleted_at.is_(None))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_folders(
        self,
        *,
        current_user_id: int,
        owner_id: Optional[int] = None,
        parent_id: Optional[int] = None,
        visibility_filter: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Folder], int]:
        """列 folder (含越权防御: 仅 owner/team/public 可见)

        Args:
            current_user_id: 当前用户 (用于 private folder 过滤)
            owner_id: 仅列该 owner 的 folder (None = 不过滤)
            parent_id: 仅列该 parent_id 的直接子 folder (None = 顶级)
            visibility_filter: 过滤特定 visibility
        """
        stmt = select(Folder)
        count_stmt = select(func.count(Folder.id))

        filters = []
        if not include_deleted:
            filters.append(Folder.deleted_at.is_(None))
        if owner_id is not None:
            filters.append(Folder.owner_id == owner_id)
        if parent_id is not None:
            filters.append(Folder.parent_id == parent_id)
        if visibility_filter:
            filters.append(Folder.visibility == visibility_filter)

        # 隐私边界: private folder 仅 owner 可见
        visibility_see_cond = or_(
            Folder.owner_id == current_user_id,
            Folder.visibility != "private",
        )
        filters.append(visibility_see_cond)

        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

        stmt = stmt.order_by(Folder.created_at.desc())
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items_result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = count_result.scalar() or 0
        return items, total

    async def list_children(
        self,
        *,
        folder_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> List[Folder]:
        """列某 folder 的直接子 folder (无越权过滤, 仅 SQL 树遍历用)

        Args:
            folder_id: 父 folder id (None = 顶级)
            include_deleted: 含已软删
        Returns: 直接子 folder 列表 (按 created_at 升序)
        """
        # parent_id IS NULL (顶级) vs = folder_id (子级) 是不同 SQL 语义
        if folder_id is None:
            stmt = select(Folder).where(Folder.parent_id.is_(None))
        else:
            stmt = select(Folder).where(Folder.parent_id == folder_id)
        if not include_deleted:
            stmt = stmt.where(Folder.deleted_at.is_(None))
        stmt = stmt.order_by(Folder.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_folder(
        self,
        folder_id: int,
        current_user_id: int,
        *,
        name: Optional[str] = None,
        visibility: Optional[str] = None,
        parent_id: Optional[int] = None,
    ) -> Optional[Folder]:
        """更新 folder (rename / move / change visibility)

        - rename: 不需越权检查, owner 可改
        - move (parent_id): 需重新算 depth + path, 校验父不超深度
        - change visibility: 校验 ≤ 当前父 folder visibility + 子 folder visibility 兼容

        Returns: 更新后的 Folder, None = folder 不存在或非 owner
        """
        folder = await self.get_folder(folder_id)
        if folder is None or folder.owner_id != current_user_id:
            return None

        if name is not None:
            if not name or len(name) > 200:
                raise FolderServiceError(f"文件夹名长度非法: '{name[:20]}...'", status_code=400)
            folder.name = name

        if visibility is not None:
            if visibility not in VISIBILITY_ORDER:
                raise FolderServiceError(f"非法 visibility: {visibility}", status_code=400)
            # 校验: folder 自身的 visibility (down-grade 时) 必须 ≥ 祖父 folder visibility
            # 即新 visibility ≤ 父 folder visibility
            parent = None
            if folder.parent_id is not None:
                parent = await self.get_folder(folder.parent_id)
            # 参数顺序: (新值, 父值) — 父若 public 才能新值为 public
            self._validate_visibility_inherits(visibility, parent.visibility if parent else None)
            # 校验子 folder visibility 也都兼容 (down-grade 父会违反子)
            if await self._has_incompatible_children(folder, visibility):
                raise FolderServiceError(
                    f"子文件夹存在 visibility 高于 {visibility}, 需先调整子文件夹",
                    status_code=400,
                )
            folder.visibility = visibility

        if parent_id is not None and parent_id != folder.parent_id:
            # move to new parent
            new_parent = await self.get_folder(parent_id) if parent_id != 0 else None
            # parent_id=0 表示顶级 (move 到根)
            if new_parent is None and parent_id != 0:
                raise FolderServiceError(f"目标父文件夹 id={parent_id} 不存在", status_code=400)
            if new_parent is not None and new_parent.owner_id != folder.owner_id:
                raise FolderServiceError(
                    f"无权移动到别人 (id={new_parent.owner_id}) 文件夹下",
                    status_code=403,
                )
            # 不能 move 到自己的子 folder (防环)
            if new_parent is not None and self._is_descendant_of(new_parent, folder):
                raise FolderServiceError(
                    f"不能将 folder 移动到自己的子 folder (会形成环)",
                    status_code=400,
                )
            # 重新算 depth
            new_depth = self._compute_depth(new_parent.depth if new_parent else None)
            self._check_depth_within_limit(new_depth)
            # visibility 兼容 (新父可能 visibility 更高)
            if new_parent is not None:
                self._validate_visibility_inherits(folder.visibility, new_parent.visibility)
            folder.parent_id = parent_id if parent_id != 0 else None
            folder.depth = new_depth
            # path 重建: 触发 _rebuild_subtree_path
            await self._rebuild_subtree_path(folder)

        await self.db.commit()
        await self.db.refresh(folder)
        logger.info(
            f"[FolderService.update_folder] id={folder.id} name='{folder.name}' "
            f"visibility={folder.visibility} parent_id={folder.parent_id} depth={folder.depth}"
        )
        return folder

    async def _has_incompatible_children(
        self,
        folder: Folder,
        new_visibility: str,
    ) -> bool:
        """检查 folder 的子 folder visibility 是否都 ≤ new_visibility

        Args:
            folder: 被改 visibility 的 folder
            new_visibility: 目标 visibility (被 down-grade 后可能违反子)
        Returns: True = 有不兼容子
        """
        # 找 child visibility > new_visibility 的子
        stmt = select(func.count(Folder.id)).where(
            Folder.parent_id == folder.id,
            Folder.deleted_at.is_(None),
            Folder.visibility != new_visibility,
        )
        count = (await self.db.execute(stmt)).scalar() or 0
        if count == 0:
            return False
        # 进一步看是否真的有 child.visibility > new_visibility
        for v in VISIBILITY_ORDER.keys():
            if VISIBILITY_ORDER[v] > VISIBILITY_ORDER[new_visibility]:
                c = (await self.db.execute(
                    select(func.count(Folder.id)).where(
                        Folder.parent_id == folder.id,
                        Folder.deleted_at.is_(None),
                        Folder.visibility == v,
                    )
                )).scalar() or 0
                if c > 0:
                    return True
        return False

    def _is_descendant_of(self, candidate: Folder, ancestor: Folder) -> bool:
        """检查 candidate 是否在 ancestor 的子树中 (用于环检测)

        candidate.path='/4/5/' + ancestor.id 检查前缀
        """
        if candidate.id == ancestor.id:
            return True
        return candidate.path.startswith(ancestor.path)

    async def _rebuild_subtree_path(self, folder: Folder) -> None:
        """重建 folder 及其所有子 folder 的 path (move 后)"""
        # 自己 path 由 update_folder 在 commit 后再设, 这里只递归子
        if folder.parent_id is None:
            new_self_path = f"/{folder.id}/"
        else:
            parent = await self.get_folder(folder.parent_id, include_deleted=True)
            if parent is None:
                new_self_path = f"/{folder.id}/"  # 父被软删, 降级
            else:
                new_self_path = f"{parent.path}{folder.id}/"
        folder.path = new_self_path
        await self.db.flush()

        # 递归子
        children = await self.list_children(folder_id=folder.id, include_deleted=True)
        for child in children:
            child.depth = folder.depth + 1
            child.path = f"{new_self_path}{child.id}/"
            await self.db.flush()
            await self._rebuild_subtree_path(child)

    async def soft_delete_folder(
        self,
        folder_id: int,
        current_user_id: int,
        is_admin: bool = False,
    ) -> bool:
        """软删除 folder (owner only, admin 可越权)

        设 deleted_at=NOW(), 3 天后 Celery beat 物理清除
        Returns: True = 成功
        Raises:
            FolderServiceError(404): folder 真不存在
            FolderServiceError(403): folder 存在但非 owner 且非 admin (越权)
            FolderServiceError(400): folder 下还有未删子 folder/file

        2026-07-10 v2.13: 加 is_admin 越权支持 (对齐 CLAUDE.md 任务权限模型
        "任务: 创建人/负责人/管理员可删除" 的 admin 跨越规则)
        """
        folder = await self.get_folder(folder_id)
        if folder is None:
            # 2026-07-10 修复: 与非 owner 区分 — 前端能看到 team folder 但不能删，
            # 旧行为 return False → 404 「Folder不存在」误导用户，实际是 403 越权
            return False
        # v2.13: admin 可越权删除 (前端 canDelete 守卫同步放宽)
        if folder.owner_id != current_user_id and not is_admin:
            raise FolderServiceError(
                f"无法删除非自己拥有的 folder (folder_id={folder_id}, owner_id={folder.owner_id} != current_user_id={current_user_id}, is_admin={is_admin})",
                status_code=403,
            )

        # 检查是否有未软删的子 folder / 文件 (PR1 铁律: skip 非空 folder)
        stmt = select(func.count(Folder.id)).where(
            Folder.parent_id == folder_id,
            Folder.deleted_at.is_(None),
        )
        child_folder_count = (await self.db.execute(stmt)).scalar() or 0
        if child_folder_count > 0:
            raise FolderServiceError(
                f"folder 下还有 {child_folder_count} 个未删的子 folder, 请先清理",
                status_code=400,
            )

        from app.models.knowledge import Knowledge
        stmt_kb = select(func.count(Knowledge.id)).where(
            Knowledge.folder_id == folder_id,
            Knowledge.deleted_at.is_(None),
        )
        kb_count = (await self.db.execute(stmt_kb)).scalar() or 0
        if kb_count > 0:
            raise FolderServiceError(
                f"folder 下还有 {kb_count} 个未删的文件, 请先清理",
                status_code=400,
            )

        folder.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.commit()
        logger.info(f"[FolderService.soft_delete_folder] id={folder.id}")
        return True

    async def restore_folder(
        self,
        folder_id: int,
        current_user_id: int,
        is_admin: bool = False,
    ) -> Optional[Folder]:
        """恢复被软删的 folder (owner or admin, 3 天保留期内有效)

        v2.13 (2026-07-10): 加 admin 越权支持 (与 soft_delete_folder 对齐)
        """
        stmt = select(Folder).where(Folder.id == folder_id)
        folder = (await self.db.execute(stmt)).scalar_one_or_none()
        if folder is None:
            return None
        # v2.13: admin 可越权恢复 (与 soft_delete_folder 对齐)
        if folder.owner_id != current_user_id and not is_admin:
            return None
        folder.deleted_at = None
        await self.db.commit()
        await self.db.refresh(folder)
        logger.info(f"[FolderService.restore_folder] id={folder.id}")
        return folder

    # ============================================================
    # v2 PR2 回收站列表 (与文件回收站对称)
    # ============================================================

    async def list_trash_folders(
        self,
        *,
        current_user_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> Tuple[List[Folder], int]:
        """v2 PR2: 列回收站中的 folder (deleted_at IS NOT NULL, 仅 owner).

        复用 list_folders + include_deleted=True + owner_id filter, 排序用 deleted_at desc
        (最近删除在前, 与文件回收站一致).
        """
        stmt = select(Folder)
        count_stmt = select(func.count(Folder.id))
        filters = [
            Folder.deleted_at.isnot(None),
            Folder.owner_id == current_user_id,
        ]
        stmt = stmt.where(and_(*filters)).order_by(Folder.deleted_at.desc())
        count_stmt = count_stmt.where(and_(*filters))
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        items_result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = count_result.scalar() or 0
        logger.info(
            f"[FolderService.list_trash_folders] user={current_user_id} total={total}"
        )
        return items, total
