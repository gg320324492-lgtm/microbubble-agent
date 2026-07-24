"""Drive v2 PR14 path backfill service (2026-07-24, W68 第 12 批 B-1)

背景:
- alembic 070 migration 体内自动重算 path (PR11 066 + PR14 修复)
- 但生产部署后可能仍有: 增量评论 path 漂移 (PR11 service 漏算) / 手动改 DB
- service 提供运行时重算入口 (单文件 / 全部 / dry-run)

设计:
- backfill_all_paths(db) -> BackfillResult: 全部 file + folder 维度重算
- backfill_for_file(db, file_id) -> int: 单文件重算 (走 file_id 维度)
- backfill_for_folder(db, folder_id) -> int: 单 folder 重算 (走 folder_id 维度)
- dry_run 默认 True: 调用方必须显式 confirm 才写库 (防误操作)

W68 第 12 批 B-1 纪律:
- 0 production code 改动铁律维持: 纯新功能, 不动 drive_comment_service.py 老逻辑
- 复用 PR11 (066) rebuild_paths 同样的 WITH RECURSIVE 模式
  * 不 import drive_comment_service (避免循环 import, service 间解耦)
- 走 raw SQL via SQLAlchemy text (data migration 性能 + 1 query)
- dry_run 默认: 默认行为不写库, 显式 dry_run=False 才生效
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.drive_comments_path_backfill")


@dataclass
class BackfillResult:
    """PR14 path 重算结果汇总

    Fields:
        total_examined: 扫到的评论总数 (含无变化)
        updated: 实际 UPDATE 成功的行数 (path 变化)
        orphans_fixed: 孤儿引用修复数 (parent_id → NULL)
        dry_run: 是否 dry-run (无写库)
        target: "all" / "file:42" / "folder:3" 描述
    """

    total_examined: int = 0
    updated: int = 0
    orphans_fixed: int = 0
    dry_run: bool = True
    target: str = "all"
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_examined": self.total_examined,
            "updated": self.updated,
            "orphans_fixed": self.orphans_fixed,
            "dry_run": self.dry_run,
            "target": self.target,
            "errors": list(self.errors),
        }


class DriveCommentsPathBackfillService:
    """Drive v2 PR14 path backfill service

    Usage:
        async with AsyncSessionLocal() as db:
            svc = DriveCommentsPathBackfillService(db)
            result = await svc.backfill_all_paths(dry_run=False)
            print(result.to_dict())
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def backfill_all_paths(
        self,
        *,
        dry_run: bool = True,
        fix_orphans: bool = True,
    ) -> BackfillResult:
        """重算所有 drive_comments.path (file + folder 双维度)

        Args:
            dry_run: True = 只统计, 不写库; False = 真更新
            fix_orphans: True = 修复孤儿引用 (parent_id → NULL + path '/')

        Returns:
            BackfillResult 含统计 + 错误列表

        Notes:
            - 双维度 (file_id / folder_id) 各自重算, 与 alembic 070 同步
            - dry_run=True 是默认安全模式
        """
        result = BackfillResult(dry_run=dry_run, target="all")

        # 1. 统计总数
        total = (await self.db.execute(
            text("SELECT COUNT(*) FROM drive_comments")
        )).scalar_one()
        result.total_examined = int(total)

        if dry_run:
            logger.info(
                f"[PR14] dry_run backfill_all_paths: total={result.total_examined}"
            )
            return result

        # 2. 修孤儿
        if fix_orphans:
            orphan_sql = text(
                """
                UPDATE drive_comments dc
                SET parent_id = NULL, path = '/', depth = 0
                WHERE dc.parent_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM drive_comments parent
                      WHERE parent.id = dc.parent_id
                  )
                """
            )
            orphan_result = await self.db.execute(orphan_sql)
            result.orphans_fixed = orphan_result.rowcount or 0

        # 3. file 维度重算 (全部模式, target_val=None)
        file_updated = await self._backfill_dim(target_col="file_id", target_val=None)
        # 4. folder 维度重算 (全部模式, target_val=None)
        folder_updated = await self._backfill_dim(target_col="folder_id", target_val=None)
        result.updated = file_updated + folder_updated

        await self.db.commit()
        logger.info(
            f"[PR14] backfill_all_paths: orphans={result.orphans_fixed} "
            f"updated={result.updated} (file={file_updated} folder={folder_updated})"
        )
        return result

    async def backfill_for_file(
        self,
        file_id: int,
        *,
        dry_run: bool = True,
        fix_orphans: bool = True,
    ) -> int:
        """单文件维度重算 path

        Args:
            file_id: drive file id
            dry_run: True = 只统计, 不写库; False = 真更新
            fix_orphans: True = 修复孤儿引用

        Returns:
            更新行数
        """
        return await self._backfill_target(
            target_col="file_id",
            target_val=file_id,
            dry_run=dry_run,
            fix_orphans=fix_orphans,
        )

    async def backfill_for_folder(
        self,
        folder_id: int,
        *,
        dry_run: bool = True,
        fix_orphans: bool = True,
    ) -> int:
        """单 folder 维度重算 path

        Args:
            folder_id: drive folder id
            dry_run: True = 只统计, 不写库; False = 真更新
            fix_orphans: True = 修复孤儿引用

        Returns:
            更新行数
        """
        return await self._backfill_target(
            target_col="folder_id",
            target_val=folder_id,
            dry_run=dry_run,
            fix_orphans=fix_orphans,
        )

    # === 内部 helper ===

    async def _backfill_target(
        self,
        *,
        target_col: str,
        target_val: int,
        dry_run: bool,
        fix_orphans: bool,
    ) -> int:
        """单 target 重算 (file 或 folder)

        与 PR11 (066) rebuild_paths 逻辑相同, 拆 _backfill_dim 复用
        """
        if dry_run:
            count = (await self.db.execute(
                text(
                    f"SELECT COUNT(*) FROM drive_comments WHERE {target_col} = :target_val"
                ),
                {"target_val": target_val},
            )).scalar_one()
            logger.info(
                f"[PR14] dry_run _backfill_target {target_col}={target_val}: would_update~={count}"
            )
            return 0

        if fix_orphans:
            await self.db.execute(
                text(
                    f"""
                    UPDATE drive_comments dc
                    SET parent_id = NULL, path = '/', depth = 0
                    WHERE dc.{target_col} = :target_val
                      AND dc.parent_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM drive_comments parent
                          WHERE parent.id = dc.parent_id
                      )
                    """
                ),
                {"target_val": target_val},
            )

        return await self._backfill_dim(
            target_col=target_col,
            target_val=target_val,
        )

    async def _backfill_dim(
        self,
        *,
        target_col: str,
        target_val: Optional[int] = None,
    ) -> int:
        """走 WITH RECURSIVE 重算一整个 target_col 维度的 path

        Args:
            target_col: 'file_id' 或 'folder_id'
            target_val: 单 target 模式 = 具体值; 全部模式 = None (走 IS NOT NULL)

        Returns:
            UPDATE 影响的行数
        """
        # 单 target 模式 (target_val 给出) 走 :target_val 占位符;
        # 全部模式 (target_val=None) 走 hardcoded IS NOT NULL
        if target_val is not None:
            base_filter = f"{target_col} = :target_val"
            recursive_filter = f"{target_col} = :target_val"
            params: dict = {"target_val": target_val}
        else:
            base_filter = f"{target_col} IS NOT NULL"
            recursive_filter = f"{target_col} IS NOT NULL"
            params = {}

        sql = text(
            f"""
            WITH RECURSIVE comment_path_calc AS (
                SELECT
                    id,
                    parent_id,
                    file_id,
                    folder_id,
                    '/'::text AS path,
                    0 AS depth
                FROM drive_comments
                WHERE parent_id IS NULL
                  AND {base_filter}

                UNION ALL

                SELECT
                    c.id,
                    c.parent_id,
                    c.file_id,
                    c.folder_id,
                    (cp.path || cp.id::text || '/')::text AS path,
                    cp.depth + 1
                FROM drive_comments c
                INNER JOIN comment_path_calc cp ON c.parent_id = cp.id
                WHERE {recursive_filter}
                  AND cp.depth < 100
            )
            UPDATE drive_comments dc
            SET path = cpc.path,
                depth = cpc.depth
            FROM comment_path_calc cpc
            WHERE dc.id = cpc.id
            """
        )
        result = await self.db.execute(sql, params)
        return int(result.rowcount or 0)
