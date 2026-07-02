"""v2026-06-29: #043 账号持久化聊天历史 (chat_sessions / chat_messages / chat_shares)

Revision ID: 039_chat_history
Revises: 038_tpl_cloned_from
Create Date: 2026-06-29

背景:
- 用户原始需求: 每个人与小气助手的对话的聊天记录要跟随账号一直记住 (ChatGPT/Doubao 模式)
- 当前实现: 前端 100% localStorage (chat_sessions_v3 + chat_msgs_<sid>), per-browser 不跨账号
- 后端: Redis agent_session:{sid}:msgs 有持久化但无 user_id 反查, chat_stream() 流式场景不写

设计决策:
- PostgreSQL 三表 (chat_sessions / chat_messages / chat_shares) + JSONB 存 rich_blocks / tool_trace / metadata
- session_id 沿用前端 user_<ts>_<rand> 格式 (24 字符内), 保持 localStorage 兼容
- user_id CASCADE 删除 (用户销户时连带清会话)
- session_id CASCADE 删除 (会话删除时连带清消息 + 分享链接)
- shared_by SET NULL (分享者销户后保留链接)
- 软删除 (deleted_at) + 30 天 Celery beat 物理清除 (与 Task 模式对齐)

新增 3 表 + 13 索引:
- chat_sessions: 8 列 + 4 索引
- chat_messages: 12 列 + 5 索引 (含幂等键 client_msg_id 索引)
- chat_shares: 8 列 + 3 索引
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "039_chat_history"
down_revision: Union[str, None] = "037_knowledge_meta_jsonb"  # 2026-07-03 跳过 038_tpl_cloned_from (模板管理已删除)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== 1. chat_sessions 表 ====================
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default="新对话"),
        sa.Column("preview", sa.Text(), nullable=True, server_default=""),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tags", sa.ARRAY(sa.String()), nullable=False, server_default=sa.text("ARRAY[]::varchar[]")),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # 索引
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_is_pinned", "chat_sessions", ["is_pinned"])
    op.create_index("ix_chat_sessions_is_archived", "chat_sessions", ["is_archived"])
    op.create_index("ix_chat_sessions_deleted_at", "chat_sessions", ["deleted_at"])
    op.create_index("ix_chat_sessions_user_active", "chat_sessions", ["user_id", "is_archived", "last_message_at"])
    op.create_index("ix_chat_sessions_user_pinned", "chat_sessions", ["user_id", "is_pinned"])

    # ==================== 2. chat_messages 表 ====================
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rich_blocks", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tool_trace", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_partial", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("client_msg_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    # 索引
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_is_partial", "chat_messages", ["is_partial"])
    op.create_index("ix_chat_messages_is_deleted", "chat_messages", ["is_deleted"])
    op.create_index("ix_chat_messages_client_msg_id", "chat_messages", ["client_msg_id"])
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"])
    op.create_index("ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"])
    op.create_index("ix_chat_messages_session_partial", "chat_messages", ["session_id", "is_partial"])

    # ==================== 3. chat_shares 表 ====================
    op.create_table(
        "chat_shares",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shared_by", sa.Integer(), sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("permission", sa.String(20), nullable=False, server_default="read"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    # 索引
    op.create_index("ix_chat_shares_session_id", "chat_shares", ["session_id"])
    op.create_index("ix_chat_shares_expires_at", "chat_shares", ["expires_at"])
    op.create_index("ix_chat_shares_created_at", "chat_shares", ["created_at"])


def downgrade() -> None:
    # 反序删除
    op.drop_index("ix_chat_shares_created_at", table_name="chat_shares")
    op.drop_index("ix_chat_shares_expires_at", table_name="chat_shares")
    op.drop_index("ix_chat_shares_session_id", table_name="chat_shares")
    op.drop_table("chat_shares")

    op.drop_index("ix_chat_messages_session_partial", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_client_msg_id", table_name="chat_messages")
    op.drop_index("ix_chat_messages_is_deleted", table_name="chat_messages")
    op.drop_index("ix_chat_messages_is_partial", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_user_pinned", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_active", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_deleted_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_is_archived", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_is_pinned", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
