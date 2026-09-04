"""收藏个人化 + 文件名搜索 trgm 索引 (批次① B6, 2026-09-05)

1. 新表 drive_file_stars (file_id × member_id 唯一) — Knowledge.is_starred
   全局限列退役为 legacy, 收藏改 per-user 关系 (背景见 app/models/drive_file_star.py)。
2. 存量回填: is_starred=true 的 drive 行按其 created_by 各生成一条个人收藏,
   时间 COALESCE(starred_at, created_at); created_by NULL 的脏行跳过 (无主可归)。
   ON CONFLICT DO NOTHING 保证重复执行/并发回填幂等。
3. B6 文件名搜索: knowledge.file_name 加 pg_trgm GIN 部分索引
   (WHERE storage_mode='drive', 网盘文件名中缀 ILIKE 高频; 066/089 同款先例,
   扩展 CREATE EXTENSION IF NOT EXISTS 幂等兜底)。

Revision ID: 134_drive_file_stars
Revises: 133_single_team_workspace
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

revision = "134_drive_file_stars"
down_revision = "133_single_team_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. drive_file_stars 表 (约束/索引名与模型 __table_args__ 逐字一致) ──
    op.create_table(
        "drive_file_stars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "starred_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("file_id", "member_id", name="uq_drive_file_stars"),
    )
    # 本人收藏夹分页主路径 (member_id 等值 + starred_at DESC 翻页)
    op.create_index(
        "ix_dfs_member_starred",
        "drive_file_stars",
        ["member_id", sa.text("starred_at DESC")],
        unique=False,
    )
    # 列表端点按本页 file_ids 批量反查收藏集合
    op.create_index("ix_dfs_file", "drive_file_stars", ["file_id"], unique=False)

    # ── 2. 存量 is_starred 回填给 created_by (老"全局限收藏"降级为"创建人的个人收藏") ──
    op.execute(
        """
        INSERT INTO drive_file_stars (file_id, member_id, starred_at)
        SELECT id, created_by, COALESCE(starred_at, created_at)
        FROM knowledge
        WHERE is_starred = true
          AND storage_mode = 'drive'
          AND created_by IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # ── 3. B6 文件名中缀搜索 GIN trgm 部分索引 (网盘行专属, KB 行 search_text 已有 089) ──
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_file_name_trgm
        ON knowledge USING gin (file_name gin_trgm_ops)
        WHERE storage_mode = 'drive'
        """
    )


def downgrade() -> None:
    # 逆序: 先删 B6 索引, 再删收藏关系 (回填行随之消失, 但 legacy is_starred 列
    # 未被本迁移改过, 回滚后全局收藏语义自动恢复), 最后删表。pg_trgm 扩展不回滚
    # (066/089 已服务其他表, 与 089 down 口径一致)。
    op.execute("DROP INDEX IF EXISTS ix_knowledge_file_name_trgm")
    op.drop_index("ix_dfs_file", table_name="drive_file_stars")
    op.drop_index("ix_dfs_member_starred", table_name="drive_file_stars")
    op.drop_table("drive_file_stars")
