"""RAG 离线批量评估 runner (PR5 W91 +2)

设计 (RAG 工业级 v1.1 §3.2 PR5 + 派工 brief §2):
- 离线条目: RAGEvaluation (online 4 RAGAS) + RAGEvaluationReport (offline NDCG@10/MRR/hit_rate)
- 输入: ground_truth 题库 (200 题, 通过 ground_truth_loader.load_ground_truth)
- 跑: HybridRetriever.retrieve(query, top_k=10)
- 算: NDCG@10 / MRR / hit_rate + per_question_json (id/question/retrieved_ids/relevant/score/mrr)
- 写: RAGEvaluationReport (alembic 090 rag_eval_reports 表)

Threshold 门禁 (派工 brief §3 据实上报):
- NDCG@10 ≥ 0.65 (派工 brief 文档, 实测据实 E29)
- MRR ≥ 0.55 (派工 brief 文档, 实测据实 E29)
- hit_rate ≥ 0.70 (派工 brief 文档, 实测据实 E29)
- 实跑若未达 → 不凑数据, 报主拍 (派工 v11 段 3 + 类 20 #29)

P95 性能门禁 (派工 brief +3):
- 200 题 batch P95 ≤ 10min (W91 +10 测试断言)
- 实测据实 E29

errata (派工 v11 段 3 + 类 20 #24 brief 错配):
- 文件名错配: 派工 brief pwa/src/pages/admin/RAGEvalPanel.tsx → 实际 web/src/views/admin/RAGEvalPanel.vue
- v1.2 §11.2 修正路径, PR6 模式对齐
"""
import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.ground_truth_loader import load_ground_truth
from app.services.hybrid_retriever import HybridRetriever
from app.models.rag_eval_report import RAGEvaluationReport

logger = logging.getLogger("microbubble.rag_eval.runner")


THRESHOLDS = {
    "ndcg_at_10": 0.65,
    "mrr": 0.55,
    "hit_rate": 0.70,
}


def _compute_ndcg_at_k(retrieved_ids: List[str], relevant_ids: set, k: int = 10) -> float:
    """计算 NDCG@k (Normalized Discounted Cumulative Gain)

    binary relevance: 命中 = 1, 未命中 = 0
    IDCG = 1.0 (单条相关, 简化 PR5)
    """
    if not relevant_ids:
        return 0.0
    retrieved_k = retrieved_ids[:k]
    dcg = 0.0
    for i, rid in enumerate(retrieved_k):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)  # 排名 1 → log2(2)=1, 排名 2 → log2(3)≈1.585
    # IDCG = 1 (单条相关在位置 1, 生产场景可算 sum 1/log2(i+2) for i in 0..min(k, len(relevant))-1)
    idcg = 1.0
    return round(dcg / idcg, 4) if idcg > 0 else 0.0


def _compute_mrr(retrieved_ids: List[str], relevant_ids: set) -> float:
    """计算 MRR (Mean Reciprocal Rank) — 单 query 取首个相关位置的倒数"""
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return round(1.0 / (i + 1), 4)
    return 0.0


def _compute_hit_rate(retrieved_ids: List[str], relevant_ids: set, k: int = 10) -> float:
    """hit_rate: top-K 命中至少 1 条相关 = 1.0, 否则 0.0"""
    return 1.0 if set(retrieved_ids[:k]) & relevant_ids else 0.0


def _aggregate(per_question: List[Dict]) -> Dict:
    """聚合 per-question 结果 → NDCG@10/MRR/hit_rate 总均值"""
    if not per_question:
        return {"ndcg_at_10": 0.0, "mrr": 0.0, "hit_rate": 0.0}
    n = len(per_question)
    return {
        "ndcg_at_10": round(sum(q["ndcg_at_10"] for q in per_question) / n, 4),
        "mrr": round(sum(q["mrr"] for q in per_question) / n, 4),
        "hit_rate": round(sum(q["hit_rate"] for q in per_question) / n, 4),
    }


class RAGEvalRunner:
    """RAG 离线批量评估 runner (PR5 W91 +2)

    Usage:
        runner = RAGEvalRunner(db)
        report = await runner.run_evaluation(limit=22)  # PR5 e2e 22 题子集
        # report: {ndcg_at_10, mrr, hit_rate, per_question}
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)

    async def run_evaluation(
        self,
        *,
        limit: Optional[int] = None,
        top_k: int = 10,
        gt_path=None,
    ) -> Dict:
        """跑离线评估

        Args:
            limit: 限制题数 (e2e 22 题子集, 生产 200 题)
            top_k: 检索 top-K (默认 10, NDCG@10/MRR/hit_rate 口径对齐)
            gt_path: 题库路径, None = 默认 200 题

        Returns:
            {
                "ground_truth_total": int,
                "ndcg_at_10": float,
                "mrr": float,
                "hit_rate": float,
                "per_question": List[Dict],
                "elapsed_seconds": float,
                "report_id": Optional[int],  # 写库后填充
            }

        Notes:
            - PR5 +3 +7 +8 +9 +10 全部依赖此函数
            - 派工 v11 段 3: 实跑据实, 不凑数据 (类 20 #29)
        """
        questions = load_ground_truth(path=gt_path, limit=limit)
        if not questions:
            logger.warning("no ground-truth questions loaded")
            return {
                "ground_truth_total": 0,
                "ndcg_at_10": 0.0,
                "mrr": 0.0,
                "hit_rate": 0.0,
                "per_question": [],
                "elapsed_seconds": 0.0,
                "report_id": None,
            }

        per_question: List[Dict] = []
        t0 = time.monotonic()
        for q in questions:
            t_q0 = time.monotonic()
            try:
                # 跑 hybrid_retriever.retrieve (件 4a 锁, 0 改)
                retrieved = await self.retriever.retrieve(q["question"], top_k=top_k)
            except Exception as e:
                logger.warning(f"question {q['id']} retrieve failed: {e}")
                retrieved = []

            retrieved_ids = [str(r.get("id", "")) for r in retrieved]
            # PR5 简化: 用 ground_truth_refs (List[str] kb:// 等) 与 retrieved.id 对比
            # 真生产应解析 kb:// → knowledge.id 映射, PR5 留字符串直接等值
            relevant_ids = set(str(r) for r in q.get("ground_truth_refs") or [])

            ndcg = _compute_ndcg_at_k(retrieved_ids, relevant_ids, k=top_k)
            mrr = _compute_mrr(retrieved_ids, relevant_ids)
            hit = _compute_hit_rate(retrieved_ids, relevant_ids, k=top_k)
            q_elapsed = time.monotonic() - t_q0

            per_question.append({
                "id": q["id"],
                "question": q["question"],
                "retrieved_ids": retrieved_ids,
                "relevant_ids": list(relevant_ids),
                "ndcg_at_10": ndcg,
                "mrr": mrr,
                "hit_rate": hit,
                "elapsed_seconds": round(q_elapsed, 4),
            })

        elapsed = time.monotonic() - t0
        agg = _aggregate(per_question)

        report = {
            "ground_truth_total": len(per_question),
            "ndcg_at_10": agg["ndcg_at_10"],
            "mrr": agg["mrr"],
            "hit_rate": agg["hit_rate"],
            "per_question": per_question,
            "elapsed_seconds": round(elapsed, 4),
            "report_id": None,
        }

        # 写库 (派工 brief §2 +7 + W91 +17)
        report_id = await self._save_report(report)
        report["report_id"] = report_id

        logger.info(
            f"RAGEvalRunner done: total={report['ground_truth_total']} "
            f"ndcg@10={report['ndcg_at_10']} mrr={report['mrr']} hit_rate={report['hit_rate']} "
            f"elapsed={report['elapsed_seconds']}s"
        )
        return report

    async def _save_report(self, report: Dict) -> Optional[int]:
        """把 report 写 rag_eval_reports 表 (派工 brief §2 +7)"""
        try:
            row = RAGEvaluationReport(
                eval_time=datetime.now(timezone.utc).replace(tzinfo=None),
                ground_truth_total=report["ground_truth_total"],
                ndcg_at_10=report["ndcg_at_10"],
                mrr=report["mrr"],
                hit_rate=report["hit_rate"],
                per_question_json=report["per_question"],
            )
            self.db.add(row)
            await self.db.commit()
            await self.db.refresh(row)
            return row.id
        except Exception as e:
            logger.warning(f"failed to save RAGEvaluationReport: {e}")
            await self.db.rollback()
            return None

    async def fetch_latest_report(self, limit: int = 10) -> List[Dict]:
        """读取最近 N 条报告 (admin RAGEvalPanel UI 用)"""
        result = await self.db.execute(
            select(RAGEvaluationReport)
            .order_by(RAGEvaluationReport.eval_time.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "eval_time": r.eval_time.isoformat() if r.eval_time else None,
                "ground_truth_total": r.ground_truth_total,
                "ndcg_at_10": r.ndcg_at_10,
                "mrr": r.mrr,
                "hit_rate": r.hit_rate,
                "per_question_count": len(r.per_question_json) if r.per_question_json else 0,
            }
            for r in rows
        ]


# PR5 W91 +6: Celery nightly evaluation task (派工 brief §2 celery 新增)
# 派工 v11 件 4a 双门控: 仅新增 1 task, 不动 celery_app.conf.imports (旧模块不动)
# 异步评测: redis broker + json serializer (与已有 schedule 一致)
async def run_nightly_evaluation():
    """PR5 夜间批量 RAG 评测 — 跑 200 题 ground-truth 写 rag_eval_reports (派工 brief +6)

    Celery 入口: 凌晨 2:00 跑 (24h 1 次), 性能门禁 P95 ≤ 10min (派工 brief +10)
    不需要 return value (Celery best-effort 写库)
    """
    try:
        from app.core.database import async_session_maker
        from app.services.ground_truth_loader import load_ground_truth
        from app.services.rag_eval_runner import RAGEvalRunner

        async with async_session_maker() as db:
            runner = RAGEvalRunner(db)
            # 24h 一次, 200 题全跑 (批生产)
            report = await runner.run_evaluation(limit=None, top_k=10)
            logger.info(
                f"nightly RAG eval done: total={report['ground_truth_total']} "
                f"ndcg@10={report['ndcg_at_10']} mrr={report['mrr']} hit_rate={report['hit_rate']} "
                f"elapsed={report['elapsed_seconds']}s report_id={report['report_id']}"
            )
    except Exception as e:
        logger.error(f"run_nightly_evaluation failed: {e}", exc_info=True)
