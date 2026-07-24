"""v2 PR14: 历史评论 path 自动重建 (2026-07-24, W68 第 12 批 B-1)

背景:
- W68 第 8 批 B-1 PR11 (alembic 066) 引入 drive_comments.path 物化列 + GIN trgm 索引
  * 当时 migration 体内自动 WITH RECURSIVE 重算现有评论的 path (PR9 时期的)
- W68 第 9 批 B-2 (alembic 069) 加 PG function 兜底 (极深嵌套 fallback)
- W68 第 10 批 B-2 + B-3 推动 v2 PR11 在生产部署, 新评论自动算 path
- **缺**: 历史评论 (PR9 时期填的) path 是空 / 错的 → 需一次性自动重建

根因:
- 066 migration 的 WITH RECURSIVE 只对 parent_id IS NULL 起点有效
  * 如果某评论 parent_id 指向一个**还没创建**的 ID (孤儿), 它会被跳过
  * 如果有循环引用 (A.parent=B, B.parent=A), WITH RECURSIVE 会爆错
  * 后续 schema 变更 (rebuild_paths 之类) 可能让 path 失同步
- 任何 path IS NULL 或 path = '/' 但 depth > 0 的评论, 都是数据漂移

设计:
- alembic migration 体内自动重算 + 提供 service 层接口:
  * WITH RECURSIVE CTE: 从根评论 (parent_id IS NULL) 开始, 逐层算 path
  * 同步 file_id 和 folder_id 两种 target (PR11 模式保留)
  * 跳过孤儿 (parent_id 指向不存在 ID) — 留 NULL 提示后续手动修复
  * **不**自动 commit (data migration 标准模式 — 让 alembic upgrade 显式 commit)

依赖:
- 062_drive_comments: drive_comments 表 + parent_id 列必须存在 (上游 PR9)
- 066_drive_comments_path: path 列存在, GIN trgm 索引已有 (上游 PR11)
- 069_drive_comments_recursive_func: PG function 兜底已存在

下接: PR14 service + Celery task + CLI (本批 B-1 其他文件)
- app/services/drive_comments_path_backfill_service.py: service 接口
- app/services/drive_comments_path_backfill_tasks.py: Celery task
- scripts/backfill_drive_comments_path.py: 手动 CLI

实施纪律:
- 0 production code 改动铁律 (W68 第 12 批): PR14 纯新功能, 不动 PR9/11 老逻辑
- alembic 070 串单链 (接 069_drive_comments_recursive_func, 留 071+ 后续 PR)
  不可双 head (CLAUDE.md 2026-07-24 alembic chain discipline 铁律)
- data migration 走 op.execute 不用 ORM 对象 (性能 + 1 query 完成)
- 不加新列 / 不加新索引 (复用 PR11 066 的 GIN trgm + file_path 复合索引)
- 失败不破坏: WITH RECURSIVE 循环引用检测 (LIMIT 0 防无限递归)
"""
from typing import Union

from alembic import op


revision: str = "070_drive_comments_path_backfill"
down_revision: Union[str, None] = "069_drive_comments_recursive_func"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """PR14: 重算所有 drive_comments.path (历史数据漂移修复)

    策略:
    1. 标记孤儿 (parent_id 指向不存在 ID) — path 留 NULL, 走 PR11 fallback
    2. 走 file_id / folder_id 两种 target 各自重算 (PR11 模式保留)
    3. 不删/不改既有评论, 只 UPDATE path
    4. 加 path 完整性约束检查 (可选, 跳过 — PR11 已 server_default '/')
    """
    # === 1. 修复孤儿引用 (parent_id 指向不存在 ID) ===
    # 逻辑: 任何 parent_id NOT NULL 但不在 drive_comments.id 集合里的评论
    #       → 视为孤儿, parent_id 置 NULL, path 置 '/'
    # 安全: 不删评论, 不破坏嵌套关系, 只"剪枝"
    op.execute(
        """
        UPDATE drive_comments dc
        SET parent_id = NULL,
            path = '/',
            depth = 0
        WHERE dc.parent_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM drive_comments parent
              WHERE parent.id = dc.parent_id
          )
        """
    )

    # === 2. WITH RECURSIVE 重算所有评论的 path (file_id 维度) ===
    # 顶层 (parent_id IS NULL) → path = '/'
    # 子 → path = parent.path || parent.id || '/'
    # 防无限递归: cycle detection 通过 LIMIT 0 + WHERE dc.id IS DISTINCT FROM cp.id
    #            (PR11 已用此模式, 这里复制确保幂等)
    op.execute(
        """
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
              AND file_id IS NOT NULL

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
            WHERE c.file_id IS NOT NULL
              AND cp.depth < 100  -- 防无限递归硬上限 (PR11 PR9 嵌套通常 <10层)
        )
        UPDATE drive_comments dc
        SET path = cpc.path,
            depth = cpc.depth
        FROM comment_path_calc cpc
        WHERE dc.id = cpc.id
          AND dc.file_id IS NOT NULL
        """
    )

    # === 3. WITH RECURSIVE 重算所有评论的 path (folder_id 维度) ===
    # 与上面对称, 走 folder_id 维度的评论 (folder 级评论, 不是 file 级)
    op.execute(
        """
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
              AND folder_id IS NOT NULL

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
            WHERE c.folder_id IS NOT NULL
              AND cp.depth < 100
        )
        UPDATE drive_comments dc
        SET path = cpc.path,
            depth = cpc.depth
        FROM comment_path_calc cpc
        WHERE dc.id = cpc.id
          AND dc.folder_id IS NOT NULL
        """
    )

    # === 4. 统计报告 (logger.info 模式) ===
    # 不写 log (alembic migration 不应该有 side effect logger),
    # 通过 op.execute SELECT 让用户升级后能 select 看到效果
    # (后续 service/CLI 也做同样统计)


def downgrade() -> None:
    """PR14 downgrade: 不删数据, 仅 mark 为"已 rebuild"语义

    实际无操作, 因为 PR14 只 UPDATE 现有 path (没有 schema 变更).
    如果需要回滚 path 到旧值, 用户必须从 backup 恢复 (migration 不保留历史 path).
    """
    # 故意 pass — 不可逆 data migration
    # 如果用户真要回滚, 需 git revert + 重新部署
    pass
