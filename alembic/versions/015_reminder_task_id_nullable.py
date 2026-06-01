"""Make reminders.task_id nullable

Wave 3a fix: create_meeting_with_reminder 创建 target_type='meeting' Reminder
时 task_id 留空（关联 meeting 而非 task）。原 NOT NULL 约束会导致 INSERT 失败。
"""
from alembic import op
import sqlalchemy as sa


revision = "015_reminder_task_id_nullable"
down_revision = "014_reminder_meeting"


def upgrade():
    op.alter_column("reminders", "task_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("reminders", "task_id", existing_type=sa.Integer(), nullable=False)
