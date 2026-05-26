"""fix embedding type LargeBinary → Vector(768)

Revision ID: 008
Revises: 007
Create Date: 2026-05-26

Knowledge 表 DB 已是 vector(768)（001 迁移），仅 ORM 模型纠正。
Memory 表 DB 是 LargeBinary，需要 ALTER COLUMN。
"""

revision = '008_fix_embedding'
down_revision = '007_knowledge_brain'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


def upgrade():
    # Knowledge 表：若列实际是 vector 则此操作为 no-op
    op.execute(
        "ALTER TABLE knowledge ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)"
    )
    # Memory 表：LargeBinary → Vector(768)
    op.execute(
        "ALTER TABLE memory ALTER COLUMN embedding TYPE vector(768) USING NULLIF(embedding::text, '')::vector(768)"
    )


def downgrade():
    op.execute("ALTER TABLE knowledge ALTER COLUMN embedding TYPE bytea USING embedding::text::bytea")
    op.execute("ALTER TABLE memory ALTER COLUMN embedding TYPE bytea USING embedding::text::bytea")
