"""RAGEvaluationReport 模型 — PR5 离线批量评估报告 (W91 +0)

设计 (RAG 工业级 v1.1 §3.2 PR5 + 派工 brief §2):
- 离线批量评估报告 (区别于 RAGEvaluation 在线单条评估)
- 字段: eval_time / ground_truth_total / ndcg_at_10 / mrr / hit_rate / per_question_json
- per_question_json: List[Dict] per-question 详细结果 (id / question / retrieved_ids / relevant / score / mrr)
- created_at: TimestampMixin

Anchor (派工 v11 段 11 类 20 #24 错配):
- 与 RAGEvaluation (online 评估 rag_evaluations 表) 互补, 不替代
- rag_evaluations: 单条 query 在线评估 (query/answer/context/4 RAGAS 指标)
- rag_eval_reports: 批量离线报告 (eval_time/ground_truth_total/NDCG@10/MRR/hit_rate/per_question_json)

alembic 090 (派工 v11 段 1):
- 接 ('089_gin_trgm_tsvector',)
- 089 = PR3 merge commit a000d0bf2
- CREATE TABLE IF NOT EXISTS rag_eval_reports (idempotent guard 087/088/089 模式)

errata (PR5 path correction):
- 文件名错配: 派工 brief `pwa/src/pages/admin/RAGEvalPanel.tsx` → 实际 `web/src/views/admin/RAGEvalPanel.vue`
- 类 20 #24 brief 错配据实上报, v1.2 §11.2 修正路径
"""
from sqlalchemy import (
    Column, Integer, Float, DateTime, Text, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import TimestampMixin


class RAGEvaluationReport(Base, TimestampMixin):
    """RAG 离线批量评估报告 — PR5 (W91 +0)

    与 RAGEvaluation (online 单条) 的区别:
    - RAGEvaluation: query → 评估 → 保存 4 RAGAS 指标 (online 实时)
    - RAGEvaluationReport: 批量 ground_truth → 全跑 → 聚合 NDCG@10/MRR/hit_rate/per_question_json (offline)

    字段:
    - eval_time: 评估执行时间 (batch 入口时间)
    - ground_truth_total: ground-truth 题库总数 (与 per_question_json 题数对齐)
    - ndcg_at_10: NDCG@10 0-1 (越大召回率越好)
    - mrr: Mean Reciprocal Rank 0-1 (首个相关结果排名倒数取均)
    - hit_rate: 命中率 0-1 (top-K 至少命中 1 条的比例)
    - per_question_json: List[Dict] per-question 详细结果 (id / question / retrieved_ids / relevant / score / mrr)
    - created_at: TimestampMixin (派工 v11 §F 字段)
    """
    __tablename__ = "rag_eval_reports"

    id = Column(Integer, primary_key=True, index=True)
    eval_time = Column(DateTime, nullable=False, server_default="now()")
    ground_truth_total = Column(Integer, nullable=False, default=0)
    ndcg_at_10 = Column(Float, nullable=True)
    mrr = Column(Float, nullable=True)
    hit_rate = Column(Float, nullable=True)
    per_question_json = Column(JSONB, nullable=True)  # List[Dict] per-question 详细

    __table_args__ = (
        CheckConstraint(
            "ground_truth_total >= 0",
            name="ck_rag_eval_reports_gt_total",
        ),
        CheckConstraint(
            "ndcg_at_10 IS NULL OR (ndcg_at_10 >= 0 AND ndcg_at_10 <= 1)",
            name="ck_rag_eval_reports_ndcg_range",
        ),
        CheckConstraint(
            "mrr IS NULL OR (mrr >= 0 AND mrr <= 1)",
            name="ck_rag_eval_reports_mrr_range",
        ),
        CheckConstraint(
            "hit_rate IS NULL OR (hit_rate >= 0 AND hit_rate <= 1)",
            name="ck_rag_eval_reports_hit_rate_range",
        ),
        Index("ix_rag_eval_reports_eval_time", "eval_time"),
    )
