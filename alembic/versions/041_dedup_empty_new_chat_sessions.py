"""v2026-07-01: 清理重复的空"新对话"会话 (chat 重复 bug 数据修复)

Revision ID: 041_dedup_empty_new_chat_sessions
Revises: 040_drive_storage_mode
Create Date: 2026-07-01

背景:
- 用户痛点: 每次登录都创建一个新的"新对话"会话 (前端 3 层 bug 导致)
- 历史数据: DB 中累积了多个标题为"新对话"、0 条消息的会话
- 用户决策: 清理 DB 中堆积的重复空"新对话",每个用户保留最近 1 个

修复:
- 仅删除: title='新对话' AND message_count=0 AND 无 chat_messages AND created_at>30 天前
- 每个用户保留最新 1 个
- 不可逆(用户已确认 destructive 操作)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "041_dedup_empty_sessions"
down_revision: Union[str, None] = "040_drive_storage_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """删除每个用户多于 1 个的空"新对话"会话,保留最近 1 个"""
    conn = op.get_bind()

    # Step 1: 找出每个用户所有"重复"空会话(>=2 个)
    # 按 created_at DESC 排序(最新在前),保留第一个
    dup_users = conn.execute(
        sa.text(
            """
            SELECT user_id, array_agg(id ORDER BY created_at DESC) AS ids
            FROM chat_sessions
            WHERE title = '新对话'
              AND message_count = 0
              AND deleted_at IS NULL
              AND created_at > now() - interval '30 days'
            GROUP BY user_id
            HAVING count(*) > 1
            """
        )
    ).fetchall()

    deleted = 0
    for user_id, ids in dup_users:
        # 保留最新 1 个,删除其余
        for sid in ids[1:]:
            # 二次校验:确认无消息(防止 race condition / 历史数据污染)
            cnt = conn.execute(
                sa.text("SELECT count(*) FROM chat_messages WHERE session_id = :sid"),
                {"sid": sid},
            ).scalar()
            if cnt == 0:
                conn.execute(
                    sa.text("DELETE FROM chat_sessions WHERE id = :sid"),
                    {"sid": sid},
                )
                deleted += 1

    print(f"[dedup] removed {deleted} duplicate empty '新对话' sessions (kept latest 1 per user)")


def downgrade() -> None:
    """不可逆(用户已确认 destructive)"""
    pass
