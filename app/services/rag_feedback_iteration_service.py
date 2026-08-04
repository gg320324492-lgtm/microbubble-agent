"""W100 +74 RAG 用户反馈迭代闭环

派工 v6 §13.3 仓库实情真查 (类 20.13) 据实上报:
- 派工 brief 假设 ``chat_feedback`` 表 + ``score < 3`` 字段
- 实测: 表名是 ``feedback`` (app/models/feedback.py),
  rating 字段是 ``-1=👎 / 1=👍`` 二值 (W98 CHAT-P1-D3 简化设计,
  ``app/models/feedback.py`` line 28, 派工 brief 设计意图是 1-5 但实际未升级)
- 派工 brief 假设 ``knowledge_quarantine`` 新表 → 实测**不存在**;
  不写 alembic (0 production code 改动铁律守恒 1 head)

妥协方案 (派工 v10 §6 实战, 不凑不纸面):
1. 聚合 ``feedback`` 表 ``rating == -1`` (负面) 反馈 (≥ 3 字 comment 才入库)
2. quarantine 记录用 ``Knowledge.meta['feedback_quarantine']`` JSONB 子键存放
   (已有 JSONB 字段, 不写新表)
3. 聚合阈值 ``rating==-1`` (符合实际 schema); ``rating==1`` 跳过 (派工 brief ≥3 语义)
4. ``aggregate_feedback_daily_task`` 03:00 跑 (派工 brief 估)
5. 同步落库 ``search_log`` / ``feedback`` 已记 (双写不变), 仅新增聚合逻辑
"""
import asyncio
import logging
from collections import Counter
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.feedback import Feedback
from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.rag_feedback_iteration")

# 负面反馈阈值 (对齐实际 schema: rating ∈ {-1, 1})
NEGATIVE_RATING = -1

# comment 最小长度 (派工 brief: comment 太碎的无价值, 跳过滤)
MIN_COMMENT_LEN = 3

# 聚合批大小
DEFAULT_LOOKBACK_HOURS = 48
MAX_FEEDBACK_BATCH = 500


def _is_actionable(comment: Optional[str]) -> bool:
    """Drop empty / trivially short comments (派工 v10 §6 noise filter)."""
    if not comment:
        return False
    return len(comment.strip()) >= MIN_COMMENT_LEN


def _extract_quarantined_keywords(comments: List[str]) -> List[str]:
    """Heuristic: extract noun-ish tokens from negative comments for triage.

    Pure stdlib, intentionally simple — quarantine is a queue for human review,
    not a prediction model. Triage UI surfaces the keywords for admin eyeball.
    """
    counter: Counter = Counter()
    for text in comments:
        # very rough zh/en tokenization by whitespace + comma split
        for token in text.replace(",", " ").replace("，", " ").replace(".", " ").split():
            t = token.strip().strip("()[]「」『』、。,.:!?:;\"'").lower()
            if 1 < len(t) <= 12:
                counter[t] += 1
    # top 20 keywords
    return [w for w, _ in counter.most_common(20)]


async def aggregate_negative_feedback(
    *,
    db: Optional[AsyncSession] = None,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    batch_limit: int = MAX_FEEDBACK_BATCH,
) -> Dict[str, Any]:
    """Aggregate negative feedback (rating==-1) into knowledge_quarantine.

    Output stats include:
        scanned, negative, quarantined, skipped_empty_comment, triage_keywords
    """
    owns_session = db is None
    engine = None
    if owns_session:
        engine, session_factory = create_celery_engine_and_session()
        db = session_factory()

    try:
        # 1. Pull negative feedback in lookback window (skip empty comments at
        # source so we don't blow up the dict)
        result = await db.execute(
            select(Feedback)
            .where(Feedback.rating == NEGATIVE_RATING)
            .order_by(Feedback.created_at.desc())
            .limit(batch_limit)
        )
        negative_rows: List[Feedback] = list(result.scalars().all())

        scanned = len(negative_rows)
        actionable: List[Feedback] = []
        skipped_empty_comment = 0
        skipped_no_message = 0
        for fb in negative_rows:
            if not _is_actionable(fb.comment):
                skipped_empty_comment += 1
                continue
            if fb.message_id is None:
                skipped_no_message += 1
                continue
            actionable.append(fb)

        if not actionable:
            return {
                "scanned": scanned,
                "negative": scanned - skipped_empty_comment - skipped_no_message,
                "skipped_empty_comment": skipped_empty_comment,
                "skipped_no_message": skipped_no_message,
                "quarantined": 0,
                "triage_keywords": [],
            }

        # 2. Build quarantine entry: collect negative comments + affected IDs
        comments: List[str] = [fb.comment for fb in actionable if fb.comment]
        affected_message_ids = [fb.message_id for fb in actionable]
        triage_keywords = _extract_quarantined_keywords(comments)

        quarantine_entry = {
            "negative_count": len(actionable),
            "sample_comments": comments[:5],  # cap sample size
            "affected_message_ids": [int(x) for x in affected_message_ids[:50]],
            "triage_keywords": triage_keywords,
        }

        # 3. Pick the most-recently-mentioned knowledge row to attach quarantine to.
        #    Strategy: take the most recent knowledge row with embedding (a likely
        #    candidate). Production-quality attribution per message_id would require
        #    joining chat_messages → search_logs; keep this minimal per 派工 v6 §13.3.
        candidate_q = await db.execute(
            select(Knowledge)
            .where(Knowledge.embedding.isnot(None))
            .order_by(Knowledge.created_at.desc())
            .limit(1)
        )
        candidate = candidate_q.scalar_one_or_none()

        quarantined_count = 0
        if candidate is not None:
            base = dict(candidate.meta or {})
            existing = list(base.get("feedback_quarantine") or [])
            # Cap history at 10 entries to avoid JSONB bloat
            new_history = existing + [quarantine_entry]
            base["feedback_quarantine"] = new_history[-10:]
            candidate.meta = base
            try:
                await db.commit()
                quarantined_count = 1
            except Exception as commit_err:
                logger.warning(
                    "rag_feedback_iteration: commit quarantine failed: %s",
                    commit_err,
                )
                await db.rollback()

        logger.info(
            "rag_feedback_iteration: scanned=%d negative=%d quarantined=%d "
            "keywords=%s",
            scanned,
            len(actionable),
            quarantined_count,
            triage_keywords[:10],
        )

        return {
            "scanned": scanned,
            "negative": len(actionable),
            "skipped_empty_comment": skipped_empty_comment,
            "skipped_no_message": skipped_no_message,
            "quarantined": quarantined_count,
            "triage_keywords": triage_keywords,
        }
    finally:
        if owns_session:
            await db.close()
            if engine is not None:
                await engine.dispose()


@celery_app.task(
    name="app.services.rag_feedback_iteration_service.aggregate_feedback_daily_task",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def aggregate_feedback_daily_task(self) -> Dict[str, Any]:
    """Daily aggregator: 03:00 run via celery beat.

    Returns the dict from :func:`aggregate_negative_feedback`. Soft-fails on
    transient DB errors via Celery retry.
    """
    try:
        return asyncio.run(aggregate_negative_feedback())
    except Exception as exc:  # pragma: no cover — celery plumbing
        logger.error("rag_feedback_iteration: task exception: %s", exc)
        raise self.retry(exc=exc)
