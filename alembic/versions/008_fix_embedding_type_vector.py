"""fix embedding type LargeBinary → Vector(768)

Revision ID: 008
Revises: 007
Create Date: 2026-05-26

Knowledge 表 DB 已是 vector(768)（001 迁移），仅 ORM 模型纠正。
Memory 表 DB 是 LargeBinary，需要 ALTER COLUMN。
"""

revision = '008_fix_embedding'
down_revision = '007'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade():
    # Knowledge: bytea → vector(768)，无已有数据直接转换
    op.execute(
        "ALTER TABLE knowledge ALTER COLUMN embedding TYPE vector(768) USING embedding::text::vector(768)"
    )
    # Memories: bytea → vector(768)
    op.execute(
        "ALTER TABLE memories ALTER COLUMN embedding TYPE vector(768) USING embedding::text::vector(768)"
    )


def downgrade():
    op.execute("ALTER TABLE knowledge ALTER COLUMN embedding TYPE bytea USING embedding::text::bytea")
    op.execute("ALTER TABLE memories ALTER COLUMN embedding TYPE bytea USING embedding::text::bytea")
