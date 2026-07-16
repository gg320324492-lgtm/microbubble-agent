"""Add user_agent column to meetings table (2026-07-16)

Reason: 会议 207 在 HarmonyOS ArkWeb 失败, 事后无法反推设备类型。
修复: meetings 表加 user_agent VARCHAR(500) 列, start-recording route 接收
   User-Agent header 落库, orphan_meeting_cleanup error_reason 拼 UA 片段。

down_revision: 059_drop_audio_archive_columns
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "060_meeting_user_agent"
down_revision: Union[str, None] = "059_drop_audio_archive_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("user_agent", sa.String(length=500), nullable=True),
    )
    # 索引有助于 orphan cleanup 按 UA 排查 (虽然不大, 但常查)
    op.create_index(
        "ix_meetings_user_agent",
        "meetings",
        ["user_agent"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_meetings_user_agent", table_name="meetings")
    op.drop_column("meetings", "user_agent")
