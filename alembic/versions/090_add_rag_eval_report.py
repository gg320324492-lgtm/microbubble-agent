"""add rag_eval_reports 离线批量评估报告 (PR5 W91 +1)

PR5 RAGEvaluator 真召回率激活:
- 离线批量评估报告表 (区别于 RAGEvaluation 在线单条)
- 字段: eval_time / ground_truth_total / ndcg_at_10 / mrr / hit_rate / per_question_json
- per_question_json: JSONB List[Dict] per-question 详细 (id/question/retrieved_ids/relevant/score/mrr)

idempotent guard (沿用 087/088/089 模式):
- CREATE TABLE IF NOT EXISTS rag_eval_reports (...)

down_revision 接续关系 (派工 v11 段 1):
- 接 ('089_gin_trgm_tsvector',)
- 089 = PR3 merge commit a000d0bf2 (anchors 444)

Why new table (派工 v11 §2 路径错配据实):
- 已有 RAGEvaluation (online 单条) + rag_evaluations 表 (lifespan create_all, 0 alembic migration)
- PR5 新增 RAGEvaluationReport (offline 批量) + rag_eval_reports 表 (alembic 090)
- 字段完全不同: online 4 RAGAS 指标 vs offline NDCG@10/MRR/hit_rate + per_question_json
- 关系: 互补, 非替代 (RAGEvaluation 单条 + RAGEvaluationReport 批量聚合)

errata (PR5 path correction, 类 20 #24 brief 错配):
- 派工 brief 路径 pwa/src/pages/admin/RAGEvalPanel.tsx → 实际 web/src/views/admin/RAGEvalPanel.vue
- v1.2 §11.2 修正路径, PR6 模式对齐

Revision ID: 090_add_rag_eval_report
Revises: 089_gin_trgm_tsvector
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "090_add_rag_eval_report"
down_revision = "089_gin_trgm_tsvector"
branch_labels = None
depends_on = None


def upgrade():
    # 1. CREATE TABLE IF NOT EXISTS rag_eval_reports (idempotent guard)
    # pg_statistic 显式列: id / eval_time / ground_truth_total / ndcg_at_10 / mrr / hit_rate / per_question_json / created_at / updated_at
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_eval_reports (
            id SERIAL PRIMARY KEY,
            eval_time TIMESTAMP NOT NULL DEFAULT now(),
            ground_truth_total INTEGER NOT NULL DEFAULT 0,
            ndcg_at_10 DOUBLE PRECISION,
            mrr DOUBLE PRECISION,
            hit_rate DOUBLE PRECISION,
            per_question_json JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        );
    """
    )

    # 2. CheckConstraint ck_rag_eval_reports_gt_total (ground_truth_total >= 0)
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_rag_eval_reports_gt_total') THEN "
        "ALTER TABLE rag_eval_reports "
        "ADD CONSTRAINT ck_rag_eval_reports_gt_total "
        "CHECK (ground_truth_total >= 0); "
        "END IF; END$$;"
    )

    # 3. CheckConstraint ck_rag_eval_reports_ndcg_range (0 <= ndcg_at_10 <= 1)
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_rag_eval_reports_ndcg_range') THEN "
        "ALTER TABLE rag_eval_reports "
        "ADD CONSTRAINT ck_rag_eval_reports_ndcg_range "
        "CHECK (ndcg_at_10 IS NULL OR (ndcg_at_10 >= 0 AND ndcg_at_10 <= 1)); "
        "END IF; END$$;"
    )

    # 4. CheckConstraint ck_rag_eval_reports_mrr_range (0 <= mrr <= 1)
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_rag_eval_reports_mrr_range') THEN "
        "ALTER TABLE rag_eval_reports "
        "ADD CONSTRAINT ck_rag_eval_reports_mrr_range "
        "CHECK (mrr IS NULL OR (mrr >= 0 AND mrr <= 1)); "
        "END IF; END$$;"
    )

    # 5. CheckConstraint ck_rag_eval_reports_hit_rate_range (0 <= hit_rate <= 1)
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_rag_eval_reports_hit_rate_range') THEN "
        "ALTER TABLE rag_eval_reports "
        "ADD CONSTRAINT ck_rag_eval_reports_hit_rate_range "
        "CHECK (hit_rate IS NULL OR (hit_rate >= 0 AND hit_rate <= 1)); "
        "END IF; END$$;"
    )

    # 6. Index ix_rag_eval_reports_eval_time (按时间排序查询)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rag_eval_reports_eval_time "
        "ON rag_eval_reports (eval_time);"
    )


def downgrade():
    # DROP TABLE 自动级联所有 index + constraint
    op.execute("DROP TABLE IF EXISTS rag_eval_reports CASCADE;")
