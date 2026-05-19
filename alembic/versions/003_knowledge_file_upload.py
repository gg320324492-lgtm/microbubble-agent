"""add file columns to knowledge

Revision ID: 003
Revises: 002
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('knowledge', sa.Column('file_path', sa.String(500), nullable=True))
    op.add_column('knowledge', sa.Column('file_name', sa.String(200), nullable=True))
    op.add_column('knowledge', sa.Column('file_type', sa.String(50), nullable=True))
    op.add_column('knowledge', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('knowledge', 'summary')
    op.drop_column('knowledge', 'file_type')
    op.drop_column('knowledge', 'file_name')
    op.drop_column('knowledge', 'file_path')
