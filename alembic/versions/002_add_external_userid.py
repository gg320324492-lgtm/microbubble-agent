"""add external_userid to members

Revision ID: 002
Revises: 001
Create Date: 2026-05-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加微信互通外部用户ID列
    op.add_column('members', sa.Column('external_userid', sa.String(100), nullable=True, comment='微信互通外部用户ID'))


def downgrade() -> None:
    op.drop_column('members', 'external_userid')
