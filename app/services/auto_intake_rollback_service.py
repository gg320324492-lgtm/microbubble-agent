"""AutoIntakeRollbackService — W68 第 10 批 B-3 业务核心 (2026-07-24)

设计要点:
- 不直接调 save_to_kb 重跑 (那是 save_to_kb_service 的职责)
- 本 service 维护**生命周期**: 失败 → 24h 后重试 → 3 次后永久挂起 → 转人工
- 与 Celery task 严格分离: service 同步 (业务逻辑), task 异步 (Celery 调度)

核心方法:
1. should_retry(rejected_id) -> bool
   - 24h 是否到 + retry_count < 3 + permanent_suspended=false
2. mark_permanent_suspend(rejected_id)
   - 写 knowledge_pending_review + 标记 permanent_suspended=True + 删 rejected (保留 7 天审计)
3. get_failure_rate(days=7) -> float
   - (rejected_count / total_attempts) 最近 7d
4. schedule_retry(rejected_id, delay_seconds=86400)
   - 重排 next_retry_at + 触发 retry_rejected_kb_intake_task (apply_async count)
5. record_failure(qa_id, failed_gate, error_msg, ...)
   - 5 道防线任一失败 → 写 knowledge_rejected (幂等 upsert)

设计纪律:
- 同步 API (无 async, 无 Celery import) → 业务层与调度层完全解耦
- service 函数签名接 (db: AsyncSession, ...) → 跨 event loop 安全
- 所有错误 best-effort try/except + logger.error → 不阻塞调用方
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.knowledge_rejected import (
    GATE_GRAYSCALE,
    GATE_INTAKE_FLAG,
    GATE_INTENT,
    GATE_SCORE,
    GATE_CONTENT,
    KnowledgePendingReview,
    KnowledgeRejected,
    VALID_FAILED_GATES,
)

logger = logging.getLogger("microbubble.auto_intake_rollback")

# 重试间隔 (24h, 与 W68 派工 prompt 24h 间隔对齐)
RETRY_INTERVAL_SECONDS = 24 * 3600

# 最大重试次数 (3 次, 第 4 次仍失败 → 永久挂起转人工)
MAX_RETRY_COUNT = 3

# 默认统计窗口 (7 天, 与 W62 D2 observer 周期对齐)
DEFAULT_FAILURE_RATE_DAYS = 7

# 告警阈值 (失败率 20%)
FAILURE_RATE_ALERT_THRESHOLD = 0.20

# error_msg 最大长度 (防超长污染, 与 alembic 066 Text 列一致)
ERROR_MSG_MAX_LENGTH = 500


def _to_naive_datetime(dt: datetime) -> datetime:
    """tz-aware → naive 转换 (CLAUDE.md 2026-06-05 教训: DB 存 naive, 必须 replace)

    Args:
        dt: tz-aware 或 naive datetime

    Returns:
        naive datetime (与 DB 列兼容)
    """
    if dt.tzinfo is None:
        return dt
    return dt.replace(tzinfo=None)


def _now_naive() -> datetime:
    """返回 naive UTC 时间 (DB DateTime 列兼容)"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AutoIntakeRollbackService:
    """qa-bench 自动入库失败回滚 / 重试 / 永久挂起业务核心

    与 Celery task 严格分离:
    - service (本类): 纯业务逻辑, 同步 API, 接 db session
    - task (auto_intake_rollback_tasks.py): Celery 调度 + asyncio.run 入口
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============ 5 道防线失败的入口 (save_to_kb_service 调用) ============

    async def record_failure(
        self,
        *,
        qa_id: str,
        failed_gate: str,
        error_msg: Optional[str] = None,
        question: Optional[str] = None,
        content: Optional[str] = None,
        score: Optional[int] = None,
        intent: Optional[str] = None,
        extra: Optional[dict] = None,
        created_by: Optional[int] = None,
    ) -> Optional[KnowledgeRejected]:
        """5 道防线任一失败 → 写 knowledge_rejected (幂等 upsert by qa_id)

        Args:
            qa_id: qa-bench 业务 ID (S-001 格式)
            failed_gate: 5 道防线哪一道失败 (GATE_* 常量)
            error_msg: 错误详情 (前 500 字符)
            question / content / score / intent: 冗余存储 (避免回查 onebyone_log)
            extra: JSONB 额外元数据 (灰度档 / 调用方 / request_id)
            created_by: 用户 ID (NULL = 系统自动入库)

        Returns:
            KnowledgeRejected 实例 (新创建或更新失败原因) / None (非法 gate)

        幂等策略:
        - ON CONFLICT (qa_id) DO UPDATE: 同一题多次失败不重复创建行
        - failed_gate 不变 → 仅更新 error_msg / updated_at
        - failed_gate 改变 (如 score fail → grayscale fail) → 更新 failed_gate + error_msg
        - retry_count / next_retry_at / permanent_suspended 由 task 维护, 不在这里 reset

        设计要点:
        - 这是 B-3 失败的**单一入口**, save_to_kb_service 5 道防线失败时调
        - 不直接调 Celery (避免同步任务内嵌 Celery), 写完 next_retry_at 即可, task 会扫到
        """
        if failed_gate not in VALID_FAILED_GATES:
            logger.error(
                f"record_failure: invalid failed_gate={failed_gate!r} "
                f"qa_id={qa_id!r}, valid={VALID_FAILED_GATES}"
            )
            return None

        # error_msg 截断 (防超长污染)
        if error_msg and len(error_msg) > ERROR_MSG_MAX_LENGTH:
            error_msg = error_msg[:ERROR_MSG_MAX_LENGTH] + "...[truncated]"

        # 首次失败 next_retry_at = now + 24h (B-3 retry task 扫到)
        next_retry = _to_naive_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=RETRY_INTERVAL_SECONDS)
        )

        # 幂等 upsert (qa_id UNIQUE)
        stmt = (
            pg_insert(KnowledgeRejected)
            .values(
                qa_id=qa_id,
                question=question,
                content=content,
                score=score,
                intent=intent,
                failed_gate=failed_gate,
                error_msg=error_msg,
                extra=extra,
                retry_count=0,
                next_retry_at=next_retry,
                permanent_suspended=False,
                created_by=created_by,
            )
            .on_conflict_do_update(
                index_elements=["qa_id"],
                set_=dict(
                    question=question,
                    content=content,
                    score=score,
                    intent=intent,
                    failed_gate=failed_gate,
                    error_msg=error_msg,
                    extra=extra,
                    # next_retry_at 不重置 (保持首次 24h 后节奏)
                    # permanent_suspended 不重置 (已挂起的不会再激活)
                    updated_at=_now_naive(),
                ),
            )
            .returning(KnowledgeRejected)
        )
        result = await self.db.execute(stmt)
        rejected = result.scalar_one()
        await self.db.commit()

        logger.info(
            f"📝 [rejected] recorded failure qa_id={qa_id!r} gate={failed_gate!r} "
            f"next_retry={next_retry.isoformat()}"
        )
        return rejected

    # ============ 重试决策 (Celery task 调用) ============

    async def should_retry(self, rejected_id: int) -> bool:
        """检查是否能重试: 24h 是否到 + retry_count < 3 + permanent_suspended=false

        Args:
            rejected_id: knowledge_rejected.id

        Returns:
            True if 可以重试 / False if 已挂起/超次/未到时间

        设计要点:
        - 同步决策 (无副作用), Celery task 调后决定是否真跑 save_to_kb 重试
        - 24h 边界: now >= next_retry_at 才允许 (避免提前跑)
        """
        result = await self.db.execute(
            select(KnowledgeRejected).where(KnowledgeRejected.id == rejected_id)
        )
        rejected = result.scalar_one_or_none()
        if not rejected:
            logger.warning(f"should_retry: rejected_id={rejected_id} not found")
            return False

        if rejected.permanent_suspended:
            logger.debug(f"should_retry: id={rejected_id} already suspended, skip")
            return False

        if rejected.retry_count >= MAX_RETRY_COUNT:
            logger.debug(f"should_retry: id={rejected_id} retry_count={rejected.retry_count} >= {MAX_RETRY_COUNT}, skip")
            return False

        if rejected.next_retry_at is None:
            # 没排期 = 不重试 (灰度 = 0 等场景)
            return False

        # 24h 边界: now >= next_retry_at 才允许
        now = _now_naive()
        if now < rejected.next_retry_at:
            logger.debug(
                f"should_retry: id={rejected_id} next_retry={rejected.next_retry_at.isoformat()} "
                f"now={now.isoformat()} not yet"
            )
            return False

        return True

    async def schedule_retry(
        self,
        rejected_id: int,
        *,
        delay_seconds: int = RETRY_INTERVAL_SECONDS,
    ) -> Optional[KnowledgeRejected]:
        """重排 next_retry_at (延迟入队) + retry_count++

        Args:
            rejected_id: knowledge_rejected.id
            delay_seconds: 距下次重试秒数 (默认 24h)

        Returns:
            更新后的 KnowledgeRejected / None (已挂起/超次)

        设计要点:
        - Celery task 跑完一次 retry (无论成功失败) 都调本方法排下次
        - 成功 → 删 rejected 行 (本方法不负责, 由调用方)
        - 失败 → 重排 24h 后再试, retry_count++
        - retry_count 达到 MAX_RETRY_COUNT → 调 mark_permanent_suspend 转人工
        """
        result = await self.db.execute(
            select(KnowledgeRejected).where(KnowledgeRejected.id == rejected_id)
        )
        rejected = result.scalar_one_or_none()
        if not rejected:
            logger.warning(f"schedule_retry: rejected_id={rejected_id} not found")
            return None

        if rejected.permanent_suspended:
            logger.warning(f"schedule_retry: id={rejected_id} already suspended, skip")
            return None

        new_retry_count = rejected.retry_count + 1
        new_next_retry = _to_naive_datetime(
            datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        )

        # retry_count 已达上限 → 永久挂起
        if new_retry_count > MAX_RETRY_COUNT:
            logger.warning(
                f"schedule_retry: id={rejected_id} retry_count={new_retry_count} "
                f"> MAX_RETRY_COUNT={MAX_RETRY_COUNT}, suspending"
            )
            await self.mark_permanent_suspend(rejected_id)
            return None

        # 正常重排
        rejected.retry_count = new_retry_count
        rejected.next_retry_at = new_next_retry
        await self.db.commit()

        logger.info(
            f"🔄 [rejected] scheduled retry id={rejected_id} qa_id={rejected.qa_id!r} "
            f"retry_count={new_retry_count} next_retry={new_next_retry.isoformat()}"
        )
        return rejected

    async def mark_permanent_suspend(
        self,
        rejected_id: int,
        *,
        review_notes: Optional[str] = None,
    ) -> Optional[KnowledgePendingReview]:
        """3 次失败 → 永久挂起 + 写 knowledge_pending_review

        Args:
            rejected_id: knowledge_rejected.id
            review_notes: 审计备注 (默认: 自动 retry 3 次失败)

        Returns:
            KnowledgePendingReview 实例 / None (未找到 rejected)

        设计要点:
        - 写 knowledge_pending_review (人工审阅, review_status=pending)
        - 标记 knowledge_rejected.permanent_suspended=True (Celery 不再扫)
        - 不删 rejected 行 (保留 7 天审计追溯 + total_attempts 计数)
        - FK rejected_id SET NULL 兜底 (删 rejected 不影响 pending_review)

        幂等: 已 permanent_suspended=True → 直接返回已有 pending_review (不重复写)
        """
        result = await self.db.execute(
            select(KnowledgeRejected).where(KnowledgeRejected.id == rejected_id)
        )
        rejected = result.scalar_one_or_none()
        if not rejected:
            logger.warning(f"mark_permanent_suspend: rejected_id={rejected_id} not found")
            return None

        if rejected.permanent_suspended:
            # 已挂起, 查现有 pending_review
            existing = await self.db.execute(
                select(KnowledgePendingReview).where(
                    KnowledgePendingReview.qa_id == rejected.qa_id
                )
            )
            return existing.scalar_one_or_none()

        # 1) 写 knowledge_pending_review (幂等: qa_id UNIQUE)
        notes = review_notes or f"自动入库 3 次失败, 转人工审阅 (gate={rejected.failed_gate})"
        pending_stmt = (
            pg_insert(KnowledgePendingReview)
            .values(
                rejected_id=rejected.id,
                qa_id=rejected.qa_id,
                question=rejected.question,
                content=rejected.content,
                score=rejected.score,
                intent=rejected.intent,
                failed_gate=rejected.failed_gate,
                last_error_msg=rejected.error_msg,
                review_status="pending",
                total_attempts=rejected.retry_count + 1,  # 1 首次 + 3 retry
                review_notes=notes,
            )
            .on_conflict_do_update(
                index_elements=["qa_id"],
                set_=dict(
                    last_error_msg=rejected.error_msg,
                    total_attempts=rejected.retry_count + 1,
                    updated_at=_now_naive(),
                ),
            )
            .returning(KnowledgePendingReview)
        )
        pending_result = await self.db.execute(pending_stmt)
        pending = pending_result.scalar_one()

        # 2) 标记 rejected.permanent_suspended=True
        rejected.permanent_suspended = True
        rejected.next_retry_at = None  # 不再排期
        await self.db.commit()

        logger.warning(
            f"🚫 [rejected] permanent suspend id={rejected_id} qa_id={rejected.qa_id!r} "
            f"attempts={rejected.retry_count + 1} → knowledge_pending_review id={pending.id}"
        )
        return pending

    # ============ 健康监控 (daily task 调用) ============

    async def get_failure_rate(self, days: int = DEFAULT_FAILURE_RATE_DAYS) -> dict:
        """统计最近 N 天失败率 (用于 daily health check + 告警)

        Args:
            days: 统计窗口 (默认 7 天)

        Returns:
            dict: {
                "window_days": int,
                "rejected_count": int (新增 rejected 行数),
                "pending_review_count": int (新增 pending_review 行数),
                "total_attempts": int (rejected 累计 attempts, 含 retry),
                "failure_rate": float (0-1, rejected_count / (rejected_count + 假设成功基线)),
                "alert_threshold": float (默认 0.20),
                "should_alert": bool (failure_rate > threshold),
            }

        设计要点:
        - 失败率 = rejected_count / (rejected_count + 假设成功基线)
        - 假设成功基线: 用 knowledge 表新增条目 (source_type='auto_expansion') 作分母
          (存粹 rejected_count 无法反映真实失败率)
        - 失败率 > 20% → 触发告警 (call kb_intake_alert_service.send_alert)
        """
        cutoff = _to_naive_datetime(datetime.now(timezone.utc) - timedelta(days=days))

        # 1) 最近 N 天 rejected 行数
        rejected_result = await self.db.execute(
            select(func.count(KnowledgeRejected.id)).where(
                KnowledgeRejected.created_at >= cutoff
            )
        )
        rejected_count = int(rejected_result.scalar_one() or 0)

        # 2) 最近 N 天 pending_review 行数
        pending_result = await self.db.execute(
            select(func.count(KnowledgePendingReview.id)).where(
                KnowledgePendingReview.created_at >= cutoff
            )
        )
        pending_count = int(pending_result.scalar_one() or 0)

        # 3) 成功基线: knowledge 表新增 source_type='auto_expansion' 行数
        #    (延迟 import 避免循环依赖)
        from app.models.knowledge import Knowledge

        knowledge_result = await self.db.execute(
            select(func.count(Knowledge.id)).where(
                and_(
                    Knowledge.created_at >= cutoff,
                    Knowledge.source_type == "auto_expansion",
                )
            )
        )
        success_count = int(knowledge_result.scalar_one() or 0)

        # 4) 失败率 = rejected / (rejected + success), 避免除零
        total_attempts = rejected_count + success_count
        if total_attempts == 0:
            failure_rate = 0.0
        else:
            failure_rate = rejected_count / total_attempts

        should_alert = failure_rate > FAILURE_RATE_ALERT_THRESHOLD

        return {
            "window_days": days,
            "rejected_count": rejected_count,
            "pending_review_count": pending_count,
            "success_count": success_count,
            "total_attempts": total_attempts,
            "failure_rate": failure_rate,
            "alert_threshold": FAILURE_RATE_ALERT_THRESHOLD,
            "should_alert": should_alert,
        }

    async def list_pending_retries(
        self,
        *,
        limit: int = 100,
    ) -> list[KnowledgeRejected]:
        """列出可重试候选 (Celery task 调度入口)

        Args:
            limit: 最多返回多少行 (默认 100)

        Returns:
            list[KnowledgeRejected] - 按 next_retry_at ASC 排序

        设计要点:
        - partial index WHERE permanent_suspended=false 已覆盖
        - 只返回 next_retry_at <= now 的 (到期可重试)
        - 不返回已永久挂起的
        - 不返回 retry_count >= MAX_RETRY_COUNT 的 (Belt+Suspenders)
        """
        now = _now_naive()
        result = await self.db.execute(
            select(KnowledgeRejected)
            .where(
                and_(
                    KnowledgeRejected.permanent_suspended == False,  # noqa: E712
                    KnowledgeRejected.retry_count < MAX_RETRY_COUNT,
                    KnowledgeRejected.next_retry_at <= now,
                )
            )
            .order_by(KnowledgeRejected.next_retry_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_permanent_suspended_old(
        self,
        *,
        retention_days: int = 7,
    ) -> int:
        """物理删除 N 天前永久挂起的 rejected 行 (审计追溯后清理)

        Args:
            retention_days: 保留天数 (默认 7 天, 与 chat_history cleanup 对齐)

        Returns:
            删除行数

        设计要点:
        - 只删 permanent_suspended=True + created_at < cutoff 的
        - knowledge_pending_review.rejected_id FK SET NULL (不级联删)
        - Celery beat 每天跑一次 (与 health_check 错峰 12h)
        """
        cutoff = _to_naive_datetime(
            datetime.now(timezone.utc) - timedelta(days=retention_days)
        )
        result = await self.db.execute(
            delete(KnowledgeRejected).where(
                and_(
                    KnowledgeRejected.permanent_suspended == True,  # noqa: E712
                    KnowledgeRejected.created_at < cutoff,
                )
            )
        )
        await self.db.commit()
        deleted = result.rowcount or 0
        if deleted > 0:
            logger.warning(
                f"🗑️ [rejected] physical cleanup: {deleted} old permanent-suspended rows "
                f"(retention={retention_days}d, cutoff={cutoff.isoformat()})"
            )
        return deleted