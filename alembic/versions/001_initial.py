"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # members
    op.create_table(
        'members',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('username', sa.String(50), unique=True, index=True),
        sa.Column('password_hash', sa.String(200)),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('grade', sa.String(20)),
        sa.Column('research_area', sa.String(100)),
        sa.Column('skills', sa.ARRAY(sa.String())),
        sa.Column('wechat_id', sa.String(100)),
        sa.Column('wechat_nickname', sa.String(100)),
        sa.Column('wechat_remark', sa.String(100)),
        sa.Column('personal_wechat_id', sa.String(100)),
        sa.Column('wechat_mobile', sa.String(20)),
        sa.Column('email', sa.String(100)),
        sa.Column('phone', sa.String(20)),
        sa.Column('avatar', sa.String(500)),
        sa.Column('bio', sa.Text()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('role', sa.String(20), default='member'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # projects
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('research_area', sa.String(100)),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('start_date', sa.Date()),
        sa.Column('end_date', sa.Date()),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('members', sa.ARRAY(sa.Integer())),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # meetings
    op.create_table(
        'meetings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime()),
        sa.Column('location', sa.String(200)),
        sa.Column('meeting_url', sa.String(500)),
        sa.Column('meeting_id', sa.String(100)),
        sa.Column('transcript', sa.JSON()),
        sa.Column('summary', sa.Text()),
        sa.Column('key_points', sa.ARRAY(sa.String())),
        sa.Column('decisions', sa.ARRAY(sa.String())),
        sa.Column('status', sa.String(20), default='scheduled'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # tasks
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('assignee_id', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id')),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('status', sa.String(20), default='todo'),
        sa.Column('priority', sa.String(10), default='medium'),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('due_date', sa.DateTime()),
        sa.Column('started_at', sa.DateTime()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('source', sa.String(50)),
        sa.Column('meeting_id', sa.Integer(), sa.ForeignKey('meetings.id')),
        sa.Column('tags', sa.ARRAY(sa.String())),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # task_dependencies
    op.create_table(
        'task_dependencies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('depends_on_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
    )

    # meeting_participants
    op.create_table(
        'meeting_participants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('meeting_id', sa.Integer(), sa.ForeignKey('meetings.id'), nullable=False),
        sa.Column('member_id', sa.Integer(), sa.ForeignKey('members.id'), nullable=False),
        sa.Column('role', sa.String(20), default='participant'),
    )

    # milestones
    op.create_table(
        'milestones',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('due_date', sa.Date()),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('status', sa.String(20), default='pending'),
    )

    # knowledge (must come after pgvector extension)
    op.create_table(
        'knowledge',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(50)),
        sa.Column('tags', sa.ARRAY(sa.String())),
        sa.Column('source', sa.String(500)),
        sa.Column('source_type', sa.String(50)),
        sa.Column('embedding', Vector(768)),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('members.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # reminders
    op.create_table(
        'reminders',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('remind_at', sa.DateTime(), nullable=False),
        sa.Column('remind_type', sa.String(20), default='wechat'),
        sa.Column('status', sa.String(20), default='pending'),
        sa.Column('sent_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('reminders')
    op.drop_table('knowledge')
    op.drop_table('milestones')
    op.drop_table('meeting_participants')
    op.drop_table('task_dependencies')
    op.drop_table('tasks')
    op.drop_table('meetings')
    op.drop_table('projects')
    op.drop_table('members')
