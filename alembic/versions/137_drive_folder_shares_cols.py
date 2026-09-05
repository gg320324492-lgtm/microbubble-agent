"""批次⑩.9 drive_folder_shares 补列 (2026-09-05)

W72 第 2 批 B-1 给 DriveFolderShare 模型加了 password_hash / max_downloads /
download_count 三列, 但对应迁移未在主链执行 (本库建表停留在早期版本) →
文件夹分享创建 INSERT 命中 UndefinedColumnError (前端表现为 创建失败 404/500)。
本迁移幂等补齐三列 (ADD COLUMN IF NOT EXISTS)。

Revision ID: 137_drive_folder_shares_cols
Revises: 136_member_folder_file_attribution
Create Date: 2026-09-05
"""
from alembic import op

revision = "137_drive_folder_shares_cols"
down_revision = "136_member_folder_file_attribution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE drive_folder_shares ADD COLUMN IF NOT EXISTS password_hash VARCHAR(128)")
    op.execute("ALTER TABLE drive_folder_shares ADD COLUMN IF NOT EXISTS max_downloads INTEGER")
    op.execute(
        "ALTER TABLE drive_folder_shares "
        "ADD COLUMN IF NOT EXISTS download_count INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE drive_folder_shares DROP COLUMN IF EXISTS download_count")
    op.execute("ALTER TABLE drive_folder_shares DROP COLUMN IF EXISTS max_downloads")
    op.execute("ALTER TABLE drive_folder_shares DROP COLUMN IF EXISTS password_hash")
