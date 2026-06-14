"""Reminder v2 策略：ack/snooze 状态机 + 11AM 单一窗口

2026-06-15 任务提醒体系全面优化：
- 赵航佳抱怨半夜收微信提醒（痛点 1）→ 所有 reminder 统一在 11:00 AM 北京时间窗口发送
- 杜同贺多次发"收到"但小气助手仍推（痛点 2）→ 新增 'acknowledged' 状态

本迁移为 reminders 表加 6 列（ack/snooze 状态机 + 批次日期 + 策略版本），
为 members 表加 1 个 JSON 列（用户通知偏好）。

新列全 nullable（除 policy_version 有 server_default='2'），
老 reminder 数据自动落默认值，无需数据迁移。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "019_reminder_v2"
down_revision: Union[str, None] = "018_meet_tp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. reminders 表加 6 列
    op.add_column(
        "reminders",
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("acknowledged_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_reminder_acknowledged_by",
        "reminders",
        "members",
        ["acknowledged_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "reminders",
        sa.Column("ack_channel", sa.String(20), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("snoozed_until", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("reminder_batch_date", sa.String(10), nullable=True),
    )
    op.add_column(
        "reminders",
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="2"),
    )

    # 2. 索引（ack/snooze 状态查询 + 批次聚合）
    op.create_index("idx_reminder_ack_at", "reminders", ["acknowledged_at"])
    op.create_index(
        "idx_reminder_batch_date", "reminders", ["reminder_batch_date"]
    )
    op.create_index(
        "idx_reminder_snoozed_until", "reminders", ["snoozed_until"]
    )

    # 3. members 表加 JSON 通知偏好列
    op.add_column(
        "members",
        sa.Column("notification_preferences", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("members", "notification_preferences")

    op.drop_index("idx_reminder_snoozed_until", "reminders")
    op.drop_index("idx_reminder_batch_date", "reminders")
    op.drop_index("idx_reminder_ack_at", "reminders")

    op.drop_column("reminders", "policy_version")
    op.drop_column("reminders", "reminder_batch_date")
    op.drop_column("reminders", "snoozed_until")
    op.drop_column("reminders", "ack_channel")
    op.drop_constraint(
        "fk_reminder_acknowledged_by", "reminders", type_="foreignkey"
    )
    op.drop_column("reminders", "acknowledged_by")
    op.drop_column("reminders", "acknowledged_at")
