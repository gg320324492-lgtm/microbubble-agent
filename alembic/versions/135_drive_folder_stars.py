"""批次⑩ 文件夹收藏 + 人名文件夹归属/时间数据修正 (2026-09-05)

1. 新表 drive_folder_stars (folder_id × member_id 唯一) — 文件夹收藏 per-user
   关系 (与 134 drive_file_stars 同构, 设计动因见 app/models/drive_folder_star.py)。
2. 数据修正 (用户 2026-09-05 拍板): 团队共享盘下以成员姓名命名的文件夹,
   owner 原为建盘人 (owner_id=1 王天志), 直接改为对应成员本人;
   created_at/updated_at 同步刷为迁移执行日 (该批文件夹视为当日归档)。
   幂等: 重跑时 owner_id 已相等, UPDATE 命中 0 行。

Revision ID: 135_drive_folder_stars
Revises: 134_drive_file_stars
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

revision = "135_drive_folder_stars"
down_revision = "134_drive_file_stars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. drive_folder_stars 表 (约束/索引名与模型 __table_args__ 逐字一致) ──
    op.create_table(
        "drive_folder_stars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
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
        sa.UniqueConstraint("folder_id", "member_id", name="uq_drive_folder_stars"),
    )
    op.create_index(
        "ix_dfos_member_starred",
        "drive_folder_stars",
        ["member_id", sa.text("starred_at DESC")],
        unique=False,
    )
    op.create_index("ix_dfos_folder", "drive_folder_stars", ["folder_id"], unique=False)

    # ── 2. 人名文件夹归属/时间修正: owner → 同名成员, 时间 → 迁移执行日 ──
    op.execute(
        """
        UPDATE folders f
        SET owner_id = m.id, created_at = now(), updated_at = now()
        FROM members m
        WHERE f.name = m.name
          AND f.deleted_at IS NULL
          AND f.owner_id <> m.id
          AND f.parent_id IN (SELECT id FROM folders WHERE is_team_default)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_dfos_folder", table_name="drive_folder_stars")
    op.drop_index("ix_dfos_member_starred", table_name="drive_folder_stars")
    op.drop_table("drive_folder_stars")
