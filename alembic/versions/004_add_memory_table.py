"""add memories table

Revision ID: 004
Revises: 003
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'memories',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('memory_type', sa.String(20), nullable=False),
        sa.Column('key', sa.String(200), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', sa.LargeBinary(), nullable=True),
        sa.Column('importance', sa.Float(), server_default='1.0'),
        sa.Column('access_count', sa.Integer(), server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('source_session', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_memories_user_type', 'memories', ['user_id', 'memory_type'])
    op.create_index('ix_memories_user_active', 'memories', ['user_id', 'is_active'])


def downgrade() -> None:
    op.drop_index('ix_memories_user_active')
    op.drop_index('ix_memories_user_type')
    op.drop_table('memories')
