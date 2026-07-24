"""W68 第 10 批 B-4: KB 闭环 audit log + 关联 link 表 (2026-07-24)

## 背景

qa-bench 自动入库 (save_to_kb.py + 5 道防线) 之前是**单点写入**:
- 写入 KB → 跑 LLM 分析 (analysis_status=done) → 后续无关联/抽检/告警闭环
- 缺 5 步 pipeline (入库 → poll → intent_classify → 标注 → 抽检) 的状态记录
- 缺 KB 之间的相似度关联 (top-3 vector search → kb_links 表)

本 PR 引入 2 张表 (同 migration):
1. **kb_closed_loop_log** — 每条 KB 在 5 个 stage 的状态/耗时/错误 (audit trail)
2. **kb_links** — KB 之间通过 vector similarity 建立的关联 (knowledge_id_a + knowledge_id_b + score)

## 字段设计

### kb_closed_loop_log
- knowledge_id: FK to knowledge.id (CASCADE), 关联的 KB 行
- stage: enum (intake/poll/intent_classify/labeling/sample_check), 5 步
- status: enum (pending/success/failed/skipped), 每步状态
- duration_ms: 该 stage 耗时 (ms), 用于 SLA 监控
- error_message: 失败原因 (status=failed 时填), 用于告警
- meta_data JSONB: stage 特定扩展数据 (灰度 hash / intent / 关联 KB id / 抽检员 id)
- created_at: 该 stage 记录创建时间 (单条 KB 同 stage 可多次失败重试)

### kb_links
- knowledge_id_a + knowledge_id_b: FK to knowledge.id (CASCADE), 两端 KB
- similarity_score: 0..1 (pgvector 余弦相似度)
- link_type: auto (vector 自动算) | manual (人工补) | derived (后续 entity 共现衍生)
- UNIQUE (knowledge_id_a, knowledge_id_b): 同对 KB 只算 1 次 (避免重复)

## 依赖

- knowledge 表必须存在 (FK)
- knowledge_extractions 表已存在 (073 关联表 service 复用 vector search)

## 下接

- W68 第 10 批 B-4 service 层: kb_closed_loop_service / kb_intent_classifier / kb_linker_service
- W69 第 1 批第 5+ agent: 跑 kb_closed_loop_log 报告 + 抽检 dashboard

## 回滚

DROP TABLE kb_links, kb_closed_loop_log (FK CASCADE 兜底)

## 实施纪律

- 0 production code 改动铁律 (W68 第 10 批): 本表 + 配套 service 全部新增, 不动老路径
- W68 第 3 批串单链纪律: down_revision 接 065_push_subscriptions (B-3 后续 PR 部署后再调)
- 0-N 关系, 不冗余 stage 维度 (避免枚举膨胀)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "072_kb_closed_loop"
down_revision: Union[str, None] = "065_push_subscriptions"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ===== kb_closed_loop_log =====
    op.create_table(
        "kb_closed_loop_log",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "knowledge_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stage", sa.String(20), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("meta_data", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
            index=True,
        ),
    )
    # 复合索引: 按 KB + stage 查; 按 stage + status + time 监控告警
    op.create_index(
        "idx_kb_loop_log_kb_stage",
        "kb_closed_loop_log",
        ["knowledge_id", "stage"],
    )
    op.create_index(
        "idx_kb_loop_log_stage_status_time",
        "kb_closed_loop_log",
        ["stage", "status", "created_at"],
    )

    # ===== kb_links =====
    op.create_table(
        "kb_links",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "knowledge_id_a",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "knowledge_id_b",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column(
            "link_type",
            sa.String(20),
            nullable=False,
            server_default="auto",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # 同对 KB (无论 a/b 顺序) 只算 1 次 → service 层强制 knowledge_id_a < b
        sa.UniqueConstraint(
            "knowledge_id_a", "knowledge_id_b", name="uq_kb_link_pair"
        ),
    )
    op.create_index(
        "idx_kb_link_a_score",
        "kb_links",
        ["knowledge_id_a", "similarity_score"],
    )
    op.create_index(
        "idx_kb_link_b_score",
        "kb_links",
        ["knowledge_id_b", "similarity_score"],
    )


def downgrade() -> None:
    # 顺序: kb_links → kb_closed_loop_log (无强依赖, 顺序不重要)
    op.drop_index("idx_kb_link_b_score", table_name="kb_links")
    op.drop_index("idx_kb_link_a_score", table_name="kb_links")
    op.drop_table("kb_links")
    op.drop_index("idx_kb_loop_log_stage_status_time", table_name="kb_closed_loop_log")
    op.drop_index("idx_kb_loop_log_kb_stage", table_name="kb_closed_loop_log")
    op.drop_table("kb_closed_loop_log")