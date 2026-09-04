"""Folder 服务 (PR2.2)

负责 folders 表的 CRUD 操作 + 嵌套深度校验 + 可见性继承。

核心规则:
- 嵌套深度 ≤ 5 (PR1 用户决策, 防 UI 渲染崩溃)
- 可见性继承: 子文件夹 visibility 必须 ≤ 父 (同 drive_service 规则)
- 物化路径 path='/1/4/7/' 形式自动维护, 便于 O(子项数) 列出子节点
- 软删除: deleted_at=NOW → Celery beat 3 天后物理清除 (PR1.2 复用 drive 清理)
- 2026-09 单一团队空间: owner_id 仅作创建人溯源, 不再是权限门
  (任何登录成员可在任意 folder 下建子夹/改名/移动/删除);
  visibility='private' 已在 create/update 收口点强制改写为 'team' (私有概念退役)。
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, select, func, update
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
            owner_id: 创建人溯源 (非权限, 2026-09 单一团队空间)
            parent_id: 父 folder id (None = 顶级)
            visibility: team/public (默认 team; private 退役 → 强制改写 team)
        Returns: Folder 对象 (path/depth 已自动维护)
        Raises: FolderServiceError on depth/visibility 违规
        """
        if not name or len(name) > 200:
            raise FolderServiceError(f"文件夹名长度非法: '{name[:20]}...'", status_code=400)
        if visibility not in VISIBILITY_ORDER:
            raise FolderServiceError(f"非法 visibility: {visibility}", status_code=400)
        # 2026-09 单一团队空间: private 概念退役, create 收口点强制改写为 team (不报错兼容老客户端)
        if visibility == "private":
            logger.warning(
                "[FolderService.create_folder] visibility='private' 已退役, 强制改写为 'team' "
                f"(name='{name}', owner_id={owner_id})"
            )
            visibility = "team"

        # 父 folder 校验
        parent: Optional[Folder] = None
        if parent_id is not None:
            parent = await self.get_folder(parent_id)
            if parent is None:
                raise FolderServiceError(f"父文件夹 id={parent_id} 不存在", status_code=400)
            # 2026-09 单一团队空间: 不再校验 parent.owner_id == owner_id (owner 仅溯源)
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
            # 2026-09 单一团队空间: 新建顶级文件夹自动归入团队默认盘
            is_team_default=(parent_id is None),
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
        """列 folder (2026-09 单一团队空间: 全部 folder 对全员可见)

        Args:
            current_user_id: 保留参数 (兼容老调用方签名), 已不再用于 private 过滤
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

        # 2026-09 单一团队空间: 删除 "private folder 仅 owner 可见" 隐私边界
        # (create/update 收口点已禁止新 private folder, 存量由迁移 133 翻 team)

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

    async def get_folder_children_stats(
        self,
        folder_id: int,
    ) -> dict:
        """返 folder 下未删子 folder + 文件数

        v2.14 (2026-07-10): smart confirm 前置, 避免用户撞 422 后才知道有子。
        Returns: {"folder_count": int, "file_count": int}
        """
        from app.models.knowledge import Knowledge

        # 子 folder 数 (排除已软删)
        stmt_folder = select(func.count(Folder.id)).where(
            Folder.parent_id == folder_id,
            Folder.deleted_at.is_(None),
        )
        folder_count = (await self.db.execute(stmt_folder)).scalar() or 0

        # 网盘文件数 (storage_mode='drive', 排除已软删)
        # 注: 知识库条目 (storage_mode='kb') 不算"folder 下文件", 跳过
        stmt_file = select(func.count(Knowledge.id)).where(
            Knowledge.folder_id == folder_id,
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "drive",
        )
        file_count = (await self.db.execute(stmt_file)).scalar() or 0

        return {"folder_count": folder_count, "file_count": file_count}

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

        2026-09 单一团队空间: 任何成员可改任意 folder (owner_id 仅溯源)。

        - rename: 任意成员可改
        - move (parent_id): 需重新算 depth + path, 校验父不超深度
        - change visibility: 校验 ≤ 当前父 folder visibility + 子 folder visibility 兼容
          (private 退役, 收口点强制改写 team)

        Returns: 更新后的 Folder, None = folder 不存在
        """
        folder = await self.get_folder(folder_id)
        if folder is None:
            return None

        if name is not None:
            if not name or len(name) > 200:
                raise FolderServiceError(f"文件夹名长度非法: '{name[:20]}...'", status_code=400)
            folder.name = name

        if visibility is not None:
            if visibility not in VISIBILITY_ORDER:
                raise FolderServiceError(f"非法 visibility: {visibility}", status_code=400)
            # 2026-09 单一团队空间: update 收口点 private → team 强制改写
            if visibility == "private":
                logger.warning(
                    "[FolderService.update_folder] visibility='private' 已退役, 强制改写为 "
                    f"'team' (folder_id={folder_id})"
                )
                visibility = "team"
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
            # 2026-09 单一团队空间: move 不再校验 new_parent.owner_id (owner 仅溯源)
            # 不能 move 到自己的子 folder (防环)
            if new_parent is not None and self._is_descendant_of(new_parent, folder):
                raise FolderServiceError(
                    f"不能将 folder 移动到自己的子 folder (会形成环)",
                    status_code=400,
                )
            # 重新算 depth
            new_depth = self._compute_depth(new_parent.depth if new_parent else None)
            # 批次① B4: 旧实现只校验被移动 folder 自身落点深度, 子树整体平移后
            # 最深 descendant 可能穿透 MAX_FOLDER_DEPTH (5 层上限名存实亡)。
            # 真校验 = 新落点 + 子树相对深度偏移 仍 ≤ 上限 (含自身, 覆盖老 check)。
            subtree_max_depth = await self._subtree_max_depth(folder)
            projected_max = new_depth + (subtree_max_depth - folder.depth)
            if projected_max > MAX_FOLDER_DEPTH:
                raise FolderServiceError(
                    f"移动后子树最深将达 {projected_max} 层, 超过 {MAX_FOLDER_DEPTH} 层上限",
                    status_code=400,
                )
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

    async def _subtree_max_depth(self, folder: Folder) -> int:
        """folder 子树 (含自身, 排除已软删) 的最大 depth — B4 move 校验用

        物化 path 前缀一把抓 (与 soft_delete_folder 级联同款遍历, O(子树行数));
        已软删后代不计 (restore 后其深度会随 _rebuild_subtree_path 重算, 且删除中
        的行不应阻塞移动决策)。
        """
        stmt = select(func.max(Folder.depth)).where(
            Folder.path.like(f"{folder.path}%"),
            Folder.deleted_at.is_(None),
        )
        max_depth = (await self.db.execute(stmt)).scalar()
        # 兜底: 极端脏数据 (自身行不在 LIKE 结果里) 至少保证自身深度
        return max_depth if max_depth is not None else folder.depth

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
        recursive: bool = False,
    ) -> dict | bool:
        """软删除 folder (2026-09 单一团队空间: 任何成员可删任意 folder)

        设 deleted_at=NOW(), 3 天后 Celery beat 物理清除

        Args:
            folder_id: 目标 folder
            current_user_id: 当前用户
            is_admin: admin 越权标识
            recursive: True = 级联删整棵子树 (folder + 全部子 folder + 全部子文件
                       一起进回收站, 30 天保留期可整体 restore).
                       False = 硬性 422 (旧行为, 留给"误删防护"场景).

        Returns:
            bool: 仅当 recursive=False 且成功 (向后兼容 v2.13/v2.14)
            dict: recursive=True 时返 {"deleted_folders": int, "deleted_files": int,
                                       "deleted_folder_ids": list[int]}

        Raises:
            FolderServiceError(404): folder 真不存在
            FolderServiceError(400, recursive=False): folder 下还有未删子 folder/file

        2026-07-10 v2.13: 加 is_admin 越权支持 (对齐 CLAUDE.md 任务权限模型
        "任务: 创建人/负责人/管理员可删除" 的 admin 跨越规则)

        2026-07-11 v2.16: 加 recursive=True 级联软删除 — 用户决策"有子文件夹
        也可以直接删除" (前端 smart confirm 2 按钮分流)。设计:
        - 用 Folder.path 物化路径 '/1/4/7/' → UPDATE ... WHERE path LIKE ?
          一次抓 subtree 所有 folder id (避免 N+1 递归)
        - Knowledge 同步 UPDATE (storage_mode='drive' 才级联, KB 不动)
        - 单事务: 失败整体 rollback (防半删)
        - deleted_folder_ids 给前端 import 用 restore all
        """
        folder = await self.get_folder(folder_id)
        if folder is None:
            # folder 真不存在 → 调用方映射 404
            return False
        # 2026-09 单一团队空间: 任何成员可软删任意 folder
        # (is_admin 参数保留兼容签名, 不再用于 owner 门禁)

        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        if not recursive:
            # === 旧行为 (PR1 铁律: skip 非空 folder) ===
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

            folder.deleted_at = now_naive
            await self.db.commit()
            logger.info(f"[FolderService.soft_delete_folder] id={folder.id}")
            return True

        # === v2.16 级联软删除 (recursive=True) ===
        # 1. 收集子树 folder ids (含自己) — 用物化 path LIKE 一把抓
        # path 形如 '/1/4/7/' → 找所有 path 以 '/1/4/7/' 开头的 (自身 + 后代)
        # 已软删的不算, 避免 restore 后 parent 软删导致二次"激活"
        subtree_stmt = select(Folder.id).where(
            Folder.path.like(f"{folder.path}%"),
            Folder.deleted_at.is_(None),
        )
        subtree_ids = [row[0] for row in (await self.db.execute(subtree_stmt)).all()]

        if not subtree_ids:
            # 边界: self 已被删 (软删但 fetchTree 可能仍能拿到 if include_deleted=False 时不会)
            # 安全起见, 单独软删 self
            subtree_ids = [folder.id]

        # 2. 原子软删所有 subtree folders (一次 UPDATE)
        stmt_upd_folder = update(Folder).where(
            Folder.id.in_(subtree_ids),
        ).values(
            deleted_at=now_naive,
            updated_at=now_naive,
        )
        folder_result = await self.db.execute(stmt_upd_folder)

        # 3. 级联软删所有 subtree knowledge (drive 文件)
        #   - storage_mode='drive' 才动, 'kb' 是知识库条目 (KB 不归文件夹管理)
        #   - deleted_at=now 而非 None, restore 时可恢复整棵子树
        #   - 批次① B3: 与 drive_service.soft_delete_file (L832) 对称补快照 —
        #     旧实现级联删的行 original_parent_id/original_path 恒 NULL, 回收站 UI
        #     无法显示原位置, 且夹在回收期内被物理删后单文件 restore 只能掉根目录。
        #     UPDATE...FROM folders 把各自所在 folder 的 path 一并快照。
        from app.models.knowledge import Knowledge
        # UPDATE...FROM (PG): 目标列引用其他表列 → folders 自动进 FROM,
        # 再显式 where 关联条件; 不用 .select_from (ORM-enabled update 生成式方法面窄)
        stmt_upd_kb = update(Knowledge).where(
            Knowledge.folder_id.in_(subtree_ids),
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "drive",
        ).values(
            deleted_at=now_naive,
            original_parent_id=Knowledge.folder_id,
            original_path=Folder.path,
        ).where(Folder.id == Knowledge.folder_id)
        file_result = await self.db.execute(stmt_upd_kb)

        await self.db.commit()

        deleted_folders = folder_result.rowcount or 0
        deleted_files = file_result.rowcount or 0
        logger.info(
            f"[FolderService.soft_delete_folder] CASCADE id={folder.id} path='{folder.path}' "
            f"deleted_folders={deleted_folders} deleted_files={deleted_files} "
            f"subtree_ids={subtree_ids[:10]}{'...' if len(subtree_ids) > 10 else ''}"
        )
        return {
            "deleted_folders": deleted_folders,
            "deleted_files": deleted_files,
            "deleted_folder_ids": subtree_ids,
        }

    async def restore_folder(
        self,
        folder_id: int,
        current_user_id: int,
        is_admin: bool = False,
    ) -> Optional[dict]:
        """恢复被软删的 folder — 批次① B1 级联对称恢复 (2026-09 单一团队空间: 任何成员可恢复)

        真 bug 背景: soft_delete_folder(recursive=True) 给整棵子树 (folder + drive
        Knowledge) 写**同一个** now_naive 时间戳级联软删, 但旧 restore 只复活单个夹
        → 用户从回收站恢复"组会PPT"后得到空夹, 48 个子夹 + 276 条文件"消失"在垃圾桶。

        方案 (级联批时间戳对称判据):
        - batch_ts = folder.deleted_at; 子树行 (path LIKE + deleted_at 非空) 中
          deleted_at >= batch_ts - 5s 容差 的视为**同一次级联删**, 一并复活。
        - 更早时间戳的行 = 单独删除的 (级联删会跳过已删行, 两者时间戳必不同批),
          不复活 — 保持"单独删子夹先进回收站"的用户意图 (对称性: 删 A 又单独删 B,
          restore A 只回来 A 批)。
        - Knowledge 侧同判据 (folder_id IN 复活夹集合 + deleted_at 同批), 并清
          B3 快照列 (folder_id 从未改过, 夹已复活 → 落点天然正确, 快照完成使命)。
        - 5s 容差: 级联用同一 Python datetime 对象写所有行 (理论差 0), 容差只防
          时钟抖动/未来改成分批 commit; 两次独立用户操作间隔 >> 5s。

        current_user_id / is_admin 参数保留兼容签名, 不再用于 owner 门禁。

        Returns:
            None = folder 真不存在 (caller 映射 404)
            dict = {"folder": Folder, "restored_folders": int, "restored_files": int}
                   (未删时幂等返计数 0/0)
        """
        stmt = select(Folder).where(Folder.id == folder_id)
        folder = (await self.db.execute(stmt)).scalar_one_or_none()
        if folder is None:
            return None
        if folder.deleted_at is None:
            # 幂等 no-op: 未删的夹"恢复" = 什么都不做
            return {"folder": folder, "restored_folders": 0, "restored_files": 0}

        batch_ts = folder.deleted_at
        cutoff = batch_ts - timedelta(seconds=5)

        # 1. 子树 folder 中属于本次级联批的行 (含自己 — path 前缀匹配自身)
        subtree_stmt = select(Folder.id).where(
            Folder.path.like(f"{folder.path}%"),
            Folder.deleted_at.isnot(None),
            Folder.deleted_at >= cutoff,
        )
        subtree_ids = [row[0] for row in (await self.db.execute(subtree_stmt)).all()]
        if folder.id not in subtree_ids:
            # 边界: 自身 path 与行不一致的脏数据也要能把自己捞回来
            subtree_ids.append(folder.id)

        # 2. 复活 folder 批
        stmt_upd_folder = update(Folder).where(
            Folder.id.in_(subtree_ids),
        ).values(deleted_at=None, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        folder_result = await self.db.execute(stmt_upd_folder)

        # 3. 复活同批 drive 文件 (kb 条目级联删时就没动过, 这里同样不碰)
        from app.models.knowledge import Knowledge
        stmt_upd_kb = update(Knowledge).where(
            Knowledge.folder_id.in_(subtree_ids),
            Knowledge.deleted_at.isnot(None),
            Knowledge.deleted_at >= cutoff,
            Knowledge.storage_mode == "drive",
        ).values(
            deleted_at=None,
            original_parent_id=None,   # B3 快照清理: 夹已复活, folder_id 落点不变即正确
            original_path=None,
        )
        file_result = await self.db.execute(stmt_upd_kb)

        await self.db.commit()
        await self.db.refresh(folder)

        restored_folders = folder_result.rowcount or 0
        restored_files = file_result.rowcount or 0
        logger.info(
            f"[FolderService.restore_folder] CASCADE id={folder.id} path='{folder.path}' "
            f"restored_folders={restored_folders} restored_files={restored_files} "
            f"batch_ts={batch_ts.isoformat()}"
        )
        return {
            "folder": folder,
            "restored_folders": restored_folders,
            "restored_files": restored_files,
        }

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
        """v2 PR2: 列回收站中的 folder (deleted_at IS NOT NULL, 全组共享垃圾桶).

        2026-09 单一团队空间: 不再按 owner 过滤 (与文件回收站对齐)。
        复用 list_folders + include_deleted=True, 排序用 deleted_at desc
        (最近删除在前, 与文件回收站一致).
        """
        stmt = select(Folder)
        count_stmt = select(func.count(Folder.id))
        filters = [
            Folder.deleted_at.isnot(None),
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
