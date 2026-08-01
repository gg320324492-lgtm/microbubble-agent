"""add search_logs.answer_rating (CHAT-P1-D3 W98)

W98 CHAT-P1-D3 用户反馈闭环 analytics 维度:
- search_logs.answer_rating 列 (Integer, nullable=True; -1=👎 / 1=👍 / NULL=未反馈)
- 与 feedback.message_id 协同: 前端 POST /chat/feedback 同步触发
  POST /analytics/search-event (rating 落 search_logs) — 双写便于按时间维度聚合
- 0 写入 feedback 表聚合 = 严格的评价事件; search_logs.answer_rating 仅辅助分析

后端 POST /api/v1/chat/feedback 调用流程:
  1. 落 feedback 表 (rating + comment + message_id 关联)
  2. 同步写 search_logs.answer_rating (同用户 + 同 message 时 closest event 取最新)
  3. /api/v1/analytics/stats?days=7 返回 by_rating 分组 (👍%/👎%/未反馈%)

下接 092_add_chat_feedback_message_id (W98 CHAT-P1-D3 派工 v1 链)
091 → 092 → 093 串单链 (派工 v11 段 1 串单链纪律)

派工前提铁律 12 第 9 条: production code 改动例外已批 (POST /chat/feedback API + 同步写 search_logs)
派工前提铁律 12 第 6 条: idempotent guard (DO $$ IF NOT EXISTS) 防止多次重跑

Revision ID: 093_add_search_log_answer_rating
Revises: 092_add_chat_feedback_message_id
Create Date: 2026-08-01
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "093_add_search_log_answer_rating"
down_revision = "092_add_chat_feedback_message_id"
branch_labels = None
depends_on = None


def upgrade():
    # 1. 加 answer_rating 列 (Integer, nullable=True)
    # idempotent guard (087/088/089/090/091/092 模式)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'search_logs' AND column_name = 'answer_rating'
            ) THEN
                ALTER TABLE search_logs ADD COLUMN answer_rating INTEGER;
            END IF;
        END$$;
        """
    )

    # 2. 索引 (by_rating 聚合主查询路径: WHERE answer_rating IS NOT NULL GROUP BY ...)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_search_logs_answer_rating "
        "ON search_logs (answer_rating);"
    )

    # 3. CHECK 约束 (-1/1/NULL 仅三态)
    # 注意: NULL 不受 CHECK 约束, 仅 NOT NULL 值受 → answer_rating IN (-1, 1)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_search_logs_answer_rating'
            ) THEN
                ALTER TABLE search_logs
                ADD CONSTRAINT ck_search_logs_answer_rating
                CHECK (answer_rating IS NULL OR answer_rating IN (-1, 1));
            END IF;
        END$$;
        """
    )


def downgrade():
    op.execute(
        "ALTER TABLE search_logs DROP CONSTRAINT IF EXISTS ck_search_logs_answer_rating;"
    )
    op.execute("DROP INDEX IF EXISTS ix_search_logs_answer_rating;")
    op.execute("ALTER TABLE search_logs DROP COLUMN IF EXISTS answer_rating;")
