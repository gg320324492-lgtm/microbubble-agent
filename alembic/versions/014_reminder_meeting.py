"""Add meeting_id and target_type to reminders

Wave 3a: 5 分钟前自动会议提醒
为 reminders 表增加 2 个字段：
- target_type (VARCHAR 20) — 提醒目标类型，取值 'task' | 'meeting'，server_default='task'
  保证老 reminder 数据的 target_type 默认 'task'（与 task_id 匹配）
- meeting_id (INTEGER) — 关联 meetings.id（可选，task 提醒时为 NULL）

并创建 idx_reminder_meeting_id 索引加速按 meeting_id 查找提醒。

用途：Wave 3a 任务 10 (create_meeting_with_reminder) 会创建
target_type='meeting' 的 Reminder，任务 12 (reminder_scheduler) 按
target_type 分发。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014_reminder_meeting'
down_revision: Union[str, None] = '013_member_voice_embedding_hnsw'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'reminders',
        sa.Column('target_type', sa.String(20), nullable=True, server_default='task'),
    )
    op.add_column(
        'reminders',
        sa.Column('meeting_id', sa.Integer(), nullable=True),
    )
    op.create_index('idx_reminder_meeting_id', 'reminders', ['meeting_id'])


def downgrade() -> None:
    op.drop_index('idx_reminder_meeting_id', table_name='reminders')
    op.drop_column('reminders', 'meeting_id')
    op.drop_column('reminders', 'target_type')
