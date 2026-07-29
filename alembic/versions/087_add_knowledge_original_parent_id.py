"""add knowledge.original_parent_id for W85 hot-fix (PR5 trash 路径快照补齐)

W85 hot-fix 2026-07-29:
- 根因: alembic 080_drive_chunked_uploads.py upgrade() 加 original_parent_id + original_path 列
- alembic rebase (W72 第 2 批 B-3 串单链) 中该列被 down 后未重新 up
- ORM app/models/knowledge.py:77 仍声明该列, 但 SQL knowledge 表无此列
- 后果: /api/v1/knowledge?page=1&page_size=20 返 500 UndefinedColumnError
       /api/v1/drive/files 同源 500

W78 第 11 批 alembic rebase 纪律 (派工前提铁律 12 第 11 条):
- down_revision 必须接最新 head 086_backfill_drive_file_versions
- 部署前必跑 alembic chain verify, 必须 1 head

派工前提铁律 12 第 5 条: 实施前必先 information_schema 实查
派工前提铁律 12 第 9 条: 0 production code 例外必含派工批文 (主拍决策已批 hot-fix)

idempotent guard: DO $$ ... IF NOT EXISTS ... 防止 hot-fix 重跑副作用

Revision ID: 087_add_knowledge_original_parent_id
Revises: 086_backfill_drive_file_versions
Create Date: 2026-07-29
"""
from alembic import op


revision = "087_add_knowledge_original_parent_id"
down_revision = "086_backfill_drive_file_versions"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 加 original_parent_id 列 (idempotent guard)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'knowledge' AND column_name = 'original_parent_id'
            ) THEN
                ALTER TABLE knowledge ADD COLUMN original_parent_id INTEGER;
            END IF;
        END$$;
    """
    )
    # 2. 加 original_path 列 (idempotent guard) — 与 080 同步, 但仅在缺失时补齐
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'knowledge' AND column_name = 'original_path'
            ) THEN
                ALTER TABLE knowledge ADD COLUMN original_path VARCHAR(1000);
            END IF;
        END$$;
    """
    )
    # 3. 加 index (可选, 与 080 一致)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_original_parent_id "
        "ON knowledge (original_parent_id);"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_knowledge_original_parent_id;")
    op.execute("ALTER TABLE knowledge DROP COLUMN IF EXISTS original_path;")
    op.execute("ALTER TABLE knowledge DROP COLUMN IF EXISTS original_parent_id;")