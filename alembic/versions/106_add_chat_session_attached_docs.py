"""W-N-G+ / W2 +N #P5: 附加文档持久化迁移 (跨 session 复用)

新增:
1. chat_session_attached_documents 表
   - 用户 × 文档 多对多绑定
   - 跨 session 复用 (类似 ChatGPT Project Memory)
   - 唯一约束 (user_id, knowledge_id) 保证幂等

2. chat_messages.attached_knowledge_ids JSONB 列
   - 记录本次消息引用的附件 ID 列表
   - 用于审计 + UI 标注 "本回答引用了 [257] ..."

设计要点:
- IF NOT EXISTS / IF EXISTS 兼容 idempotent 重跑 (W73 铁律)
- 默认值 '[]' 避免 NULL 处理
- 不索引: 用户级附加文档数量小 (硬上限 8)
"""
from alembic import op
import sqlalchemy as sa


revision = "106_add_chat_session_attached_docs"
down_revision = "105_fix_drift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 新增 chat_session_attached_documents 表 (用户级全局附加)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_session_attached_documents (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL
                REFERENCES members(id) ON DELETE CASCADE,
            knowledge_id INTEGER NOT NULL
                REFERENCES knowledge(id) ON DELETE CASCADE,
            attached_at TIMESTAMP WITHOUT TIME ZONE
                NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_chat_session_attached_user_doc
                UNIQUE (user_id, knowledge_id)
        );
    """)
    # 索引: 按 user 查全局附加列表 (高频, 每次 chat_stream 都查)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chat_session_attached_user
            ON chat_session_attached_documents (user_id);
    """)

    # 2. chat_messages 加 attached_knowledge_ids JSONB 列 (审计)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='chat_messages'
                  AND column_name='attached_knowledge_ids'
            ) THEN
                ALTER TABLE chat_messages
                ADD COLUMN attached_knowledge_ids JSONB
                NOT NULL DEFAULT '[]'::jsonb;
            END IF;
        END$$;
    """)
    # GIN 索引: 按附加文档 ID 查历史消息 (审计场景: 用户问"我之前用 [257] 引用过的回答有哪些")
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chat_messages_attached_knowledge_ids
            ON chat_messages USING gin (attached_knowledge_ids);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_messages_attached_knowledge_ids;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='chat_messages'
                  AND column_name='attached_knowledge_ids'
            ) THEN
                ALTER TABLE chat_messages
                DROP COLUMN attached_knowledge_ids;
            END IF;
        END$$;
    """)
    op.execute("DROP INDEX IF EXISTS ix_chat_session_attached_user;")
    op.execute("DROP TABLE IF EXISTS chat_session_attached_documents;")