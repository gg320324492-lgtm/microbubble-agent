"""add feedback, prompt_templates, custom_instructions

Revision ID: 005
Revises: 004
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # members 表添加 custom_instructions 列
    op.add_column('members', sa.Column('custom_instructions', sa.Text(), nullable=True))

    # 创建 feedback 表
    op.create_table('feedback',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('session_id', sa.String(100)),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text()),
        sa.Column('agent_reply', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # 创建 prompt_templates 表
    op.create_table('prompt_templates',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('version', sa.Integer(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('prompt_templates')
    op.drop_table('feedback')
    op.drop_column('members', 'custom_instructions')
