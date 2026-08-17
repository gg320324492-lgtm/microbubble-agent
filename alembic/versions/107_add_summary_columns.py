"""alembic migration 2026-08-17 #Step14: chat_messages.summary 列

Plan v1 Step 14 - session summary 落库 (chat_messages.summary 列)

设计:
- 0 业务代码改动: 仅 schema 层 (新列 nullable, 老数据 nullable ok)
- 写入路径: 后续 SSE done 事件触发后 fire-and-forget 异步 LLM 压缩 (P2 留口)
- 读取路径: 跨 session 召回时按 summary 搜 (后续 P2 留口)

回滚路径简单: alembic downgrade() 直接 drop_column (无 FK 引用)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "107_add_summary_columns"
down_revision = "106_add_chat_session_attached_docs"  # 当前 main HEAD
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加 chat_messages.summary + key_topics 列 (P2 启用时用)"""
    op.add_column(
        "chat_messages",
        sa.Column("summary", sa.Text(), nullable=True,
                  comment="2026-08-17 #Step14: assistant message 完成后异步 LLM 压缩"),
    )
    op.add_column(
        "chat_messages",
        sa.Column("key_topics", sa.ARRAY(sa.String(50)), nullable=True,
                  server_default="{}",
                  comment="2026-08-17 #Step14: 提取的 3-5 个关键词, 跨 session 检索用"),
    )
    # GIN 索引支持 key_topics 数组查询
    op.create_index(
        "idx_chat_messages_key_topics_gin",
        "chat_messages",
        ["key_topics"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """回滚: drop index + drop columns"""
    op.drop_index("idx_chat_messages_key_topics_gin", table_name="chat_messages")
    op.drop_column("chat_messages", "key_topics")
    op.drop_column("chat_messages", "summary")
