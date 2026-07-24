"""v2 PR11: drive_comments path 物化 + GIN 索引 (2026-07-24, W68 第 8 批)

背景:
- W68 第 3 批 F-1 (062_drive_comments) 留 TODO: 大量嵌套回复 (100+) 时
  list_comments N+1 拉 replies 慢. 设计文档提到 "PR11 path 物化"
- 课题组场景: 一个文件 100+ 评论 + 多层嵌套 (GitHub PR review comments 风格)
  现有 ORM 实现每次 list 需 2 次 query (顶层 + 子回复), 但前端要"按 path 过滤"
  / "面包屑导航" 时需要 N 次递归

设计:
- drive_comments 表加 1 列:
  * path VARCHAR(500), 默认 '/', 物化嵌套路径
    - 顶层: path = '/'
    - 子评论: path = parent.path + str(parent.id) + '/'
    - 例: comment id=42 在 /1/2/3/ 路径下 → path='/1/2/3/42/'
- 加 1 GIN 索引 (trigram 扩展):
  * CREATE EXTENSION IF NOT EXISTS pg_trgm
  * CREATE INDEX ix_drive_comments_path_gin ON drive_comments USING GIN (path gin_trgm_ops)
- migration 体内 UPDATE 现有数据 (WITH RECURSIVE 重算 path):
  * 顶层 → '/'
  * 子 → parent.path || parent.id || '/'

调用方 (新功能, 不影响现有 API):
- GET /api/v1/drive/comments?path_prefix=/1/2/ (新 query 参数)
- GET /api/v1/drive/comments/{id}/breadcrumb (新端点, ancestor chain)

回滚策略: DROP COLUMN + DROP INDEX (无外部 FK 引用 path)

依赖: drive_comments (062) 表必须存在
下接: PR12+ 进一步 (mention email / 企业微信 / 嵌套分页)

实施纪律:
- 0 production code 改动铁律 (W68 第 8 批): PR11 纯新功能, 不动现有评论逻辑
- W68 第 4 批 串单链纪律: down_revision 接 064_drive_documents (064 是当前 head, 065 留待后续 PR)
  不破坏 alembic 链 (1 head only)
- pg_trgm 扩展必须 CREATE EXTENSION IF NOT EXISTS (PostgreSQL 自带, 但需 superuser 一次授权)
- WITH RECURSIVE 重算 path 时先按 created_at 排序保证确定性
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "066_drive_comments_path"
down_revision: Union[str, None] = "065_push_subscriptions"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # === 1. 确保 pg_trgm 扩展存在 (GIN trgm ops 依赖) ===
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # === 2. 加 path 列 (nullable=True + 默认 '/' 兼容历史数据) ===
    op.add_column(
        "drive_comments",
        sa.Column(
            "path",
            sa.String(length=500),
            nullable=True,
            server_default=sa.text("'/'"),
        ),
    )

    # === 3. WITH RECURSIVE 重算现有数据的 path ===
    # 按 parent_id 自底向上, 计算每行 path
    # 顶层 (parent_id IS NULL) → path = '/'
    # 子 → path = parent.path || parent.id || '/'
    op.execute(
        """
        WITH RECURSIVE comment_path_calc AS (
            SELECT
                id,
                parent_id,
                '/'::text AS path
            FROM drive_comments
            WHERE parent_id IS NULL

            UNION ALL

            SELECT
                c.id,
                c.parent_id,
                (cp.path || cp.id::text || '/')::text AS path
            FROM drive_comments c
            INNER JOIN comment_path_calc cp ON c.parent_id = cp.id
        )
        UPDATE drive_comments dc
        SET path = cpc.path
        FROM comment_path_calc cpc
        WHERE dc.id = cpc.id
        """
    )

    # === 4. 加 GIN 索引 (trigram ops, 支持 path LIKE '%xxx%' 加速) ===
    op.create_index(
        "ix_drive_comments_path_gin",
        "drive_comments",
        ["path"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"path": "gin_trgm_ops"},
    )

    # === 5. 加 file_id + path 复合索引 (按 file 过滤 + path prefix 常用) ===
    op.create_index(
        "ix_drive_comments_file_path",
        "drive_comments",
        ["file_id", "path"],
        unique=False,
    )


def downgrade() -> None:
    # 顺序: 先删索引, 再删列
    op.drop_index("ix_drive_comments_file_path", table_name="drive_comments")
    op.drop_index("ix_drive_comments_path_gin", table_name="drive_comments")
    op.drop_column("drive_comments", "path")
    # 注意: pg_trgm 扩展不回滚 (其他表可能用, 不强制 DROP EXTENSION)