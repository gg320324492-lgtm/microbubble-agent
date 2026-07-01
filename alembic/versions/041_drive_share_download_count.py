"""v2026-07-01: 课题组网盘 PR2.7 分享链接 + 下载计数

Revision ID: 041_drive_share_download_count
Revises: 040_drive_storage_mode
Create Date: 2026-07-01

新增 3 列 (Knowledge 表):
- download_count (Integer, default 0)         原子计数
- share_token (String(32), unique nullable)   公开分享 token
- share_expires_at (DateTime, nullable)        到期时间

新索引: ix_knowledge_share_token (partial WHERE share_token IS NOT NULL)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "041_drive_share_download_count"
down_revision: Union[str, None] = "040_drive_storage_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge",
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "knowledge",
        sa.Column("share_token", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "knowledge",
        sa.Column("share_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_knowledge_share_token",
        "knowledge",
        ["share_token"],
        unique=True,
        postgresql_where=sa.text("share_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_share_token", table_name="knowledge")
    op.drop_column("knowledge", "share_expires_at")
    op.drop_column("knowledge", "share_token")
    op.drop_column("knowledge", "download_count")
