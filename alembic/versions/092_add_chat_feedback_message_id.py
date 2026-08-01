"""add chat feedback message_id link (CHAT-P1-D3 W98)

W98 CHAT-P1-D3 用户反馈闭环 (CHAT-P0-A 历史闭环后第二阶段):
- feedback.message_id 列 (FK chat_messages.id, CASCADE), 把反馈与持久化的 AI 回复关联
- ix_feedback_message_id 索引 (按消息查反馈, 防 N+1)
- feedback 已存在 (alembic 005), 本迁移仅加列不重建表

消息反馈 vs session 反馈:
- 老 feedback session_id + rating + comment, 只能绑 session 级评价
- 新加 message_id 后可绑具体 AI 回复, 用于:
  (a) P1 e2e 跨回复质量回归 (按 message_id diff)
  (b) qa-bench D9 评分系统联合 (反馈作为 ground-truth hint)
  (c) KB auto-intake rollback 通路 (收到 👎 反馈 → 反查 knowledge_id + 熔断)

下接 091_add_kg_entity, 上启 093_add_search_log_answer_rating

派工前提铁律 12 第 9 条: 0 production code 改动例外必含派工批文 (主拍 CHAT-P1-D3 派工已批)
派工前提铁律 12 第 11 条: alembic 并行 agent 串单链 — 092 独立 down_revision="091_add_kg_entity"
派工前提铁律 12 第 6 条: idempotent guard (DO $$ IF NOT EXISTS) 防止多次重跑

Revision ID: 092_add_chat_feedback_message_id
Revises: 091_add_kg_entity
Create Date: 2026-08-01
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "092_add_chat_feedback_message_id"
down_revision = "091_add_kg_entity"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 加 message_id 列 (BigInt, FK chat_messages.id CASCADE, nullable=True)
    # idempotent guard (087/088/089/090/091 模式)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'feedback' AND column_name = 'message_id'
            ) THEN
                ALTER TABLE feedback ADD COLUMN message_id BIGINT;
            END IF;
        END$$;
        """
    )

    # 2. 幂等 FK 约束 (chat_messages.id, CASCADE), 仅当 FK 缺失时补齐
    # 注意: 必须先 add column 后 add constraint, 故分两步
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_feedback_message_id'
            ) THEN
                ALTER TABLE feedback
                ADD CONSTRAINT fk_feedback_message_id
                FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE;
            END IF;
        END$$;
        """
    )

    # 3. 索引 (按 message_id 查反馈, 前端 / 异步可能按消息聚合)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_feedback_message_id "
        "ON feedback (message_id);"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_feedback_message_id;")
    op.execute(
        "ALTER TABLE feedback DROP CONSTRAINT IF EXISTS fk_feedback_message_id;"
    )
    op.execute("ALTER TABLE feedback DROP COLUMN IF EXISTS message_id;")
