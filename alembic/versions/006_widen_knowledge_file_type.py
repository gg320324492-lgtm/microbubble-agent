"""widen knowledge.file_type from VARCHAR(50) to VARCHAR(200)

Office Open XML MIME types (e.g., .docx = 71 chars) exceed the
previous VARCHAR(50) limit, causing StringDataRightTruncationError.

Revision ID: 006
Revises: 005
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('knowledge', 'file_type',
                    existing_type=sa.String(50),
                    type_=sa.String(200),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('knowledge', 'file_type',
                    existing_type=sa.String(200),
                    type_=sa.String(50),
                    existing_nullable=True)
