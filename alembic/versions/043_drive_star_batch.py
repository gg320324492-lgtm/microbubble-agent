"""v2026-07-01: 课题组网盘 v2 PR2 收藏星标 + 批量操作字段

Revision ID: 043_drive_star_batch
Revises: 042_drive_share_password
Create Date: 2026-07-01

新增列 (Knowledge 表):
- is_starred   (Boolean, default false)             收藏标记
- starred_at   (DateTime, nullable)                  收藏时间 (用于 sort by starred_at desc)

新增索引: ix_knowledge_starred (partial WHERE is_starred = true)
复用现有 deleted_at / created_by 索引做 list_trash / list_starred 复合查询

注意: 文件夹 folders 表暂不加星标 (UI 暂未做 folder 收藏; PR2 plan 范围聚焦 file)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "043_drive_star_batch"
down_revision: Union[str, None] = "042_drive_share_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Knowledge 表: is_starred + starred_at
    op.add_column(
        "knowledge",
        sa.Column(
            "is_starred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "knowledge",
        sa.Column("starred_at", sa.DateTime(), nullable=True),
    )
    # partial index: 只索引 starred=true 的行, 节省空间 + 加速 "list_my_starred"
    op.create_index(
        "ix_knowledge_starred",
        "knowledge",
        ["is_starred", "starred_at"],
        postgresql_where=sa.text("is_starred = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_starred", table_name="knowledge")
    op.drop_column("starred_at", "knowledge")
    op.drop_column("is_starred", "knowledge")