"""v2026-07-01: 课题组网盘 v2 PR1 分享链接密码（提取码）

Revision ID: 042_drive_share_password
Revises: 041_drive_share_download_count
Create Date: 2026-07-01

新增列 (Knowledge 表):
- share_password VARCHAR(64) NULL
    - NULL = 公开分享 (无密码)
    - 非 NULL = SHA256 hex hash (64 字符) 4-8 位数字提取码
    - 计划文档原列宽 VARCHAR(8) 仅够 4 位明文, 违背"哈希存储"承诺
      改 VARCHAR(64) 兼容 SHA256 hex, 语义不变
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "042_drive_share_password"
down_revision: Union[str, None] = "041_drive_share_download_count"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge",
        sa.Column("share_password", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge", "share_password")
