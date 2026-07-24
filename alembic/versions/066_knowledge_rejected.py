"""knowledge_rejected + knowledge_pending_review 表 (2026-07-24, W68 第 10 批 B-2)

背景:
- qa-bench save_to_kb.py 全自动入库 5 道防线 (score / content / intent / grayscale / intake_flag)
  任一失败: 需要**持久化**记录以便后续重试或人工审阅
- 现有 qa-bench observer JSONL 是短期运行时统计 (数天自动 trim),
  跨周追踪和永久挂起都需要 DB 表
- B-3 (本批同 agent 后续) 在本表上加 retry_count / next_retry_at / permanent_suspended 字段

设计:
- 2 张新表 (同 migration):
  * knowledge_rejected: 失败记录 (qa_id UNIQUE 幂等 + failed_gate 索引 + retry 跟踪)
  * knowledge_pending_review: 永久挂起转人工审阅 (3 次失败后写本表 + 删 rejected)

依赖: members 表 (FK created_by / reviewed_by, SET NULL 防 CASCADE 误删)
下接: B-3 alembic 067_knowledge_rejected_retry 加 retry_count / next_retry_at / permanent_suspended

回滚策略: 直接 DROP TABLE (knowledge_pending_review → knowledge_rejected 顺序, FK 兜底)

实施纪律:
- 0 production code 改动铁律 (W68 第 7 批): 本表 + 配套 service 全部新增, 不动老路径
- W68 第 3 批串单链纪律: down_revision 接 065_push_subscriptions (W68 第 7 批 B-3 后续)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "066_knowledge_rejected"
down_revision: Union[str, None] = "065_push_subscriptions"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1) knowledge_rejected 主表
    op.create_table(
        "knowledge_rejected",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("qa_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("failed_gate", sa.String(length=32), nullable=False),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("extra", JSONB(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("permanent_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    # 索引: qa_id 唯一 (幂等) + failed_gate (失败统计) + permanent_suspended (扫描) + next_retry_at (Celery 调度)
    op.create_index(
        "ix_knowledge_rejected_qa_id", "knowledge_rejected", ["qa_id"], unique=True
    )
    op.create_index(
        "ix_knowledge_rejected_failed_gate", "knowledge_rejected", ["failed_gate"]
    )
    op.create_index(
        "ix_knowledge_rejected_permanent_suspended",
        "knowledge_rejected",
        ["permanent_suspended"],
    )
    op.create_index(
        "ix_knowledge_rejected_next_retry_at",
        "knowledge_rejected",
        ["next_retry_at"],
        postgresql_where=sa.text("permanent_suspended = false"),
    )

    # 2) knowledge_pending_review 永久挂起转人工审阅
    op.create_table(
        "knowledge_pending_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rejected_id", sa.Integer(), nullable=True),
        sa.Column("qa_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("failed_gate", sa.String(length=32), nullable=False),
        sa.Column("last_error_msg", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("total_attempts", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rejected_id"], ["knowledge_rejected.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["members.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_pending_review_qa_id", "knowledge_pending_review", ["qa_id"], unique=True
    )
    op.create_index(
        "ix_knowledge_pending_review_review_status",
        "knowledge_pending_review",
        ["review_status"],
    )


def downgrade() -> None:
    # 反向顺序: 先删有 FK 引用的 pending_review, 再删 rejected
    op.drop_index(
        "ix_knowledge_pending_review_review_status", table_name="knowledge_pending_review"
    )
    op.drop_index(
        "ix_knowledge_pending_review_qa_id", table_name="knowledge_pending_review"
    )
    op.drop_table("knowledge_pending_review")

    op.drop_index(
        "ix_knowledge_rejected_next_retry_at", table_name="knowledge_rejected"
    )
    op.drop_index(
        "ix_knowledge_rejected_permanent_suspended", table_name="knowledge_rejected"
    )
    op.drop_index(
        "ix_knowledge_rejected_failed_gate", table_name="knowledge_rejected"
    )
    op.drop_index(
        "ix_knowledge_rejected_qa_id", table_name="knowledge_rejected"
    )
    op.drop_table("knowledge_rejected")