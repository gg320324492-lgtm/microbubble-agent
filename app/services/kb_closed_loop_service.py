"""KB closed loop — 5 步 pipeline (W68 第 10 批 B-4, 2026-07-24)

## 背景

qa-bench 自动入库 (save_to_kb.py + 5 道防线) 之后:
- 写入 KB → 跑 LLM 分析 (analysis_status=done) → 后续无关联/抽检/告警闭环
- 缺 5 步 pipeline (入库 → poll → intent_classify → 标注 → 抽检) 的状态记录
- 缺 KB 之间的相似度关联 (top-3 vector search → kb_links 表)
- 缺失败告警 + audit log

本服务实现完整 5 步 pipeline, 每步写一行 `kb_closed_loop_log` (5 stage × N 状态).
所有中间失败都不抛异常 (best-effort), 仅写 status=failed + error_message 留给告警/dashboard.

## 5 步 pipeline

| # | stage | 任务 | 调用方 | 失败兜底 |
|---|-------|------|--------|----------|
| 1 | intake | 调 save_qa_to_kb (B-2) 写入 KB | save_to_kb_service | 跳过整个 pipeline |
| 2 | poll | 等 1h 后看业务影响 (KB 是否被检索/引用) | knowledge_polling_service | poll 失败标 skipped |
| 3 | intent_classify | LLM 标 intent (meeting/task/knowledge/...) | kb_intent_classifier | < 0.7 标 unclassified |
| 4 | labeling | 自动填 tags/category + 关联已有 KB (top-3) | kb_linker_service | 单条失败不影响其他 |
| 5 | sample_check | 按 5% 概率抽检 + 人工 review | sample_check_worker | 抽中无人 review 时留 unclassified |

## 调用方

- qa-bench 自动入库 save_to_kb.py → 入库后调 `run_closed_loop(knowledge_id)`
- admin dashboard 可手动重跑 (`/api/v1/admin/kb-closed-loop/{id}/rerun`)

## 设计要点

1. **每步独立 try/except** — 单步失败不影响其他 stage, 全部走 best-effort
2. **完整 audit trail** — 5 步每步写 1 行 `kb_closed_loop_log`, 含 duration_ms
3. **跨 event loop 安全** — db session 通过参数注入 (CLAUDE.md 519/527 行铁律)
4. **pipeline 顺序严格** — intake → poll → intent_classify → labeling → sample_check
5. **失败告警** — Celery beat 监控 stage + status + time, 失败率 > 阈值触发 admin 通知

## 纪律

- 0 production code 改动铁律 (W68 第 10 批): 本服务 + 配套表全部新增, 不动老路径
- 跨 event loop 安全: db session 通过参数注入, 不在模块顶部创建
- 不吞异常: try/except 必须 logger.error + 写 log, 不静默吞 (W68 第 5 批教训)
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_closed_loop_log import (
    KbClosedLoopLog,
    STAGE_INTAKE,
    STAGE_INTENT_CLASSIFY,
    STAGE_LABELING,
    STAGE_POLL,
    STAGE_SAMPLE_CHECK,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    VALID_STAGES,
)
from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.kb_closed_loop_service")


# ============== 配置常量 ==============

# 抽检比例 (5%, 与 plan 一致)
DEFAULT_SAMPLE_CHECK_RATIO = 0.05

# poll 等待时间 (1h = 3600s, 与 plan 一致)
DEFAULT_POLL_WAIT_SECONDS = 3600

# 闭环整体 SLA (ms), 超过视为超时
DEFAULT_CLOSED_LOOP_TIMEOUT_MS = 60_000

# intent classify 默认 confidence 阈值
DEFAULT_INTENT_THRESHOLD = 0.7


# ============== 枚举 ==============

class ClosedLoopStage(str, Enum):
    """5 步 pipeline 阶段 (与 model 字段保持一致)"""

    INTAKE = STAGE_INTAKE
    POLL = STAGE_POLL
    INTENT_CLASSIFY = STAGE_INTENT_CLASSIFY
    LABELING = STAGE_LABELING
    SAMPLE_CHECK = STAGE_SAMPLE_CHECK


class ClosedLoopStatus(str, Enum):
    """stage 状态 (与 model 字段保持一致)"""

    PENDING = STATUS_PENDING
    SUCCESS = STATUS_SUCCESS
    FAILED = STATUS_FAILED
    SKIPPED = STATUS_SKIPPED


# pipeline 顺序 (强制)
PIPELINE_ORDER: List[ClosedLoopStage] = [
    ClosedLoopStage.INTAKE,
    ClosedLoopStage.POLL,
    ClosedLoopStage.INTENT_CLASSIFY,
    ClosedLoopStage.LABELING,
    ClosedLoopStage.SAMPLE_CHECK,
]


# ============== 数据类 ==============

@dataclass
class StageResult:
    """单步 stage 执行结果"""

    stage: ClosedLoopStage
    status: ClosedLoopStatus
    duration_ms: int
    error_message: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None


@dataclass
class ClosedLoopResult:
    """完整 pipeline 执行结果 (5 步汇总)"""

    knowledge_id: int
    stages: List[StageResult] = field(default_factory=list)
    overall_status: ClosedLoopStatus = ClosedLoopStatus.PENDING
    total_duration_ms: int = 0

    @property
    def failed_stages(self) -> List[StageResult]:
        return [s for s in self.stages if s.status == ClosedLoopStatus.FAILED]

    @property
    def is_success(self) -> bool:
        return self.overall_status == ClosedLoopStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "overall_status": self.overall_status.value,
            "total_duration_ms": self.total_duration_ms,
            "stages": [
                {
                    "stage": s.stage.value,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "error_message": s.error_message,
                }
                for s in self.stages
            ],
            "failed_count": len(self.failed_stages),
        }


# ============== audit log writer ==============

async def _write_log(
    db: AsyncSession,
    *,
    knowledge_id: int,
    stage: ClosedLoopStage,
    status: ClosedLoopStatus,
    duration_ms: Optional[int] = None,
    error_message: Optional[str] = None,
    meta_data: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """写一行 kb_closed_loop_log (audit)

    失败也不抛异常 (best-effort), 写 log 失败时仅 logger.warning 兜底.
    """
    try:
        entry = KbClosedLoopLog(
            knowledge_id=knowledge_id,
            stage=stage.value,
            status=status.value,
            duration_ms=duration_ms,
            error_message=error_message,
            meta_data=meta_data,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry.id
    except Exception as exc:
        logger.warning(
            "kb_closed_loop_service 写 log 失败 knowledge_id=%s stage=%s status=%s: %s",
            knowledge_id, stage.value, status.value, exc,
        )
        try:
            await db.rollback()
        except Exception:
            pass
        return None


# ============== 5 步 stage 实现 ==============

async def _stage_intake(
    db: AsyncSession,
    knowledge_id: int,
    *,
    intake_hook: Optional[Callable[[AsyncSession, int], Awaitable[Dict[str, Any]]]] = None,
) -> StageResult:
    """Stage 1: 入库确认 (B-2 save_qa_to_kb 已写, 这里确认存在 + 状态)"""
    started = time.monotonic()
    try:
        kb = await db.get(Knowledge, knowledge_id)
        if kb is None:
            return StageResult(
                stage=ClosedLoopStage.INTAKE,
                status=ClosedLoopStatus.FAILED,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_message=f"Knowledge id={knowledge_id} 不存在, 无法入闭环",
            )

        # 调可选 hook (B-2 save_qa_to_kb 在 save_to_kb.py 已跑, 这里不重复)
        meta: Dict[str, Any] = {"kb_id": kb.id, "analysis_status": kb.analysis_status}
        if intake_hook is not None:
            try:
                hook_result = await intake_hook(db, knowledge_id)
                if isinstance(hook_result, dict):
                    meta.update(hook_result)
            except Exception as hook_exc:
                logger.warning("kb_closed_loop intake_hook 失败: %s", hook_exc)

        return StageResult(
            stage=ClosedLoopStage.INTAKE,
            status=ClosedLoopStatus.SUCCESS,
            duration_ms=int((time.monotonic() - started) * 1000),
            meta_data=meta,
        )
    except Exception as exc:
        logger.error("kb_closed_loop intake 失败: %s", exc, exc_info=True)
        return StageResult(
            stage=ClosedLoopStage.INTAKE,
            status=ClosedLoopStatus.FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_message=f"{exc.__class__.__name__}: {exc}",
        )


async def _stage_poll(
    db: AsyncSession,
    knowledge_id: int,
    *,
    poll_wait_seconds: int = DEFAULT_POLL_WAIT_SECONDS,
) -> StageResult:
    """Stage 2: poll 业务影响 (KB 是否被检索/引用)

    真业务 impact 需要等 1h 让 qa-bench / 用户实际用 KB → 简单做法是:
    - 立即检查: KB 是否已有引用次数 (knowledge_extractions.count + memory.count)
    - 真 1h 后跑: Celery delayed task, 本函数只占位 + 标 success (留给后续 PR 接 Celery countdown)

    本期实现: 占位, 立刻标 success (留 hook 给 Celery beat 重跑)
    """
    started = time.monotonic()
    try:
        kb = await db.get(Knowledge, knowledge_id)
        if kb is None:
            return StageResult(
                stage=ClosedLoopStage.POLL,
                status=ClosedLoopStatus.FAILED,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_message="KB 不存在, 无法 poll",
            )

        # 占位统计: 当前 KB 的 extractions 数 (后续可加 search log 计数)
        from app.models.knowledge_multimodal import KnowledgeExtraction
        from sqlalchemy import func as sql_func

        cnt_result = await db.execute(
            select(sql_func.count(KnowledgeExtraction.id)).where(
                KnowledgeExtraction.knowledge_id == knowledge_id,
                KnowledgeExtraction.is_active.is_(True),
            )
        )
        extractions_count = int(cnt_result.scalar_one() or 0)

        meta: Dict[str, Any] = {
            "extractions_count": extractions_count,
            "poll_wait_seconds": poll_wait_seconds,
            "poll_mode": "placeholder",  # 真异步 poll 留待 Celery delayed task
        }
        return StageResult(
            stage=ClosedLoopStage.POLL,
            status=ClosedLoopStatus.SUCCESS,
            duration_ms=int((time.monotonic() - started) * 1000),
            meta_data=meta,
        )
    except Exception as exc:
        logger.error("kb_closed_loop poll 失败: %s", exc, exc_info=True)
        return StageResult(
            stage=ClosedLoopStage.POLL,
            status=ClosedLoopStatus.FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_message=f"{exc.__class__.__name__}: {exc}",
        )


async def _stage_intent_classify(
    db: AsyncSession,
    knowledge_id: int,
    *,
    threshold: float = DEFAULT_INTENT_THRESHOLD,
) -> StageResult:
    """Stage 3: intent_classify (调 kb_intent_classifier)"""
    started = time.monotonic()
    try:
        from app.services.kb_intent_classifier import (
            build_classifier_from_settings,
            classify_intent,
        )

        kb = await db.get(Knowledge, knowledge_id)
        if kb is None:
            return StageResult(
                stage=ClosedLoopStage.INTENT_CLASSIFY,
                status=ClosedLoopStatus.FAILED,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_message="KB 不存在, 无法 classify",
            )

        text = f"{kb.title}\n{(kb.content or '')[:1000]}"
        classifier = build_classifier_from_settings()
        classification = await classify_intent(
            text,
            classifier=classifier,
            threshold=threshold,
        )

        if not classification.is_classified:
            # < 0.7 → unclassified, 但 stage 仍标 success (人工 review 流程)
            return StageResult(
                stage=ClosedLoopStage.INTENT_CLASSIFY,
                status=ClosedLoopStatus.SUCCESS,
                duration_ms=int((time.monotonic() - started) * 1000),
                meta_data={
                    **classification.to_log_metadata(),
                    "needs_human_review": True,
                },
            )

        # 标 KB 的 knowledge_type 字段 (复用 LLM analysis 字段)
        try:
            kb.knowledge_type = classification.intent.value
            await db.commit()
        except Exception as kb_exc:
            logger.warning(
                "kb_closed_loop 写 KB.knowledge_type 失败: %s", kb_exc,
            )
            await db.rollback()

        return StageResult(
            stage=ClosedLoopStage.INTENT_CLASSIFY,
            status=ClosedLoopStatus.SUCCESS,
            duration_ms=int((time.monotonic() - started) * 1000),
            meta_data=classification.to_log_metadata(),
        )
    except Exception as exc:
        logger.error("kb_closed_loop intent_classify 失败: %s", exc, exc_info=True)
        return StageResult(
            stage=ClosedLoopStage.INTENT_CLASSIFY,
            status=ClosedLoopStatus.FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_message=f"{exc.__class__.__name__}: {exc}",
        )


async def _stage_labeling(
    db: AsyncSession,
    knowledge_id: int,
    *,
    top_k: int = 3,
) -> StageResult:
    """Stage 4: 标注 (自动填 tags/category + 关联已有 KB)"""
    started = time.monotonic()
    try:
        from app.services.kb_linker_service import (
            build_linker_summary,
            link_kb_to_top_k,
            KbLinkerError,
        )

        # 跑 top-3 关联
        try:
            links = await link_kb_to_top_k(db, knowledge_id, top_k=top_k)
            linker_summary = build_linker_summary(links)
        except KbLinkerError as kb_exc:
            # KB 无 embedding 是预期 (新入库 KB embedding 可能延迟生成)
            return StageResult(
                stage=ClosedLoopStage.LABELING,
                status=ClosedLoopStatus.SKIPPED,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_message=str(kb_exc),
                meta_data={"reason": "no_embedding"},
            )

        meta: Dict[str, Any] = {
            **linker_summary,
            "top_k": top_k,
        }
        return StageResult(
            stage=ClosedLoopStage.LABELING,
            status=ClosedLoopStatus.SUCCESS,
            duration_ms=int((time.monotonic() - started) * 1000),
            meta_data=meta,
        )
    except Exception as exc:
        logger.error("kb_closed_loop labeling 失败: %s", exc, exc_info=True)
        return StageResult(
            stage=ClosedLoopStage.LABELING,
            status=ClosedLoopStatus.FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_message=f"{exc.__class__.__name__}: {exc}",
        )


async def _stage_sample_check(
    db: AsyncSession,
    knowledge_id: int,
    *,
    sample_ratio: float = DEFAULT_SAMPLE_CHECK_RATIO,
    seed: Optional[int] = None,
) -> StageResult:
    """Stage 5: 抽检 (按 sample_ratio 概率抽中, 标记 needs_review)

    算法:
    - hash(knowledge_id + YYYYMMDD) % 100 < sample_ratio * 100 → 抽中
    - 抽中 → 标 KB.needs_review=True + needs_human_review=True
    - 未抽中 → 标 skipped (不抽检)

    与 B-3 (auto_intake_rollback) 5% 抽检对齐, 同 hash 种子保证同一 KB 同一天只抽 1 次.
    """
    started = time.monotonic()
    try:
        from app.models.knowledge import Knowledge as KnowledgeModel
        import hashlib

        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        seed_str = f"{knowledge_id}:{today}:{seed if seed is not None else ''}"
        digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100  # 0..99

        threshold_pct = int(sample_ratio * 100)
        sampled = bucket < threshold_pct

        meta: Dict[str, Any] = {
            "sample_ratio": sample_ratio,
            "bucket": bucket,
            "threshold_pct": threshold_pct,
            "sampled": sampled,
        }

        if not sampled:
            return StageResult(
                stage=ClosedLoopStage.SAMPLE_CHECK,
                status=ClosedLoopStatus.SKIPPED,
                duration_ms=int((time.monotonic() - started) * 1000),
                meta_data=meta,
            )

        # 抽中 → 标 KB.needs_review
        kb = await db.get(KnowledgeModel, knowledge_id)
        if kb is None:
            return StageResult(
                stage=ClosedLoopStage.SAMPLE_CHECK,
                status=ClosedLoopStatus.FAILED,
                duration_ms=int((time.monotonic() - started) * 1000),
                error_message="KB 不存在, 无法标 needs_review",
            )
        kb.needs_review = True
        await db.commit()
        meta["needs_human_review"] = True
        return StageResult(
            stage=ClosedLoopStage.SAMPLE_CHECK,
            status=ClosedLoopStatus.SUCCESS,
            duration_ms=int((time.monotonic() - started) * 1000),
            meta_data=meta,
        )
    except Exception as exc:
        logger.error("kb_closed_loop sample_check 失败: %s", exc, exc_info=True)
        return StageResult(
            stage=ClosedLoopStage.SAMPLE_CHECK,
            status=ClosedLoopStatus.FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_message=f"{exc.__class__.__name__}: {exc}",
        )


# ============== 主入口: 跑完整 pipeline ==============

async def run_closed_loop(
    db: AsyncSession,
    knowledge_id: int,
    *,
    sample_ratio: float = DEFAULT_SAMPLE_CHECK_RATIO,
    intent_threshold: float = DEFAULT_INTENT_THRESHOLD,
    top_k: int = 3,
    poll_wait_seconds: int = DEFAULT_POLL_WAIT_SECONDS,
    intake_hook: Optional[Callable[[AsyncSession, int], Awaitable[Dict[str, Any]]]] = None,
) -> ClosedLoopResult:
    """跑完整 5 步 pipeline

    Args:
        db: AsyncSession (调用方注入)
        knowledge_id: 主 KB id
        sample_ratio: 抽检比例 (默认 0.05)
        intent_threshold: intent classify 阈值 (默认 0.7)
        top_k: 关联 KB 数 (默认 3)
        poll_wait_seconds: poll 等待时间 (占位, 留 Celery 后续接入)
        intake_hook: 可选 B-2 intake 回调 (本阶段不传)

    Returns:
        ClosedLoopResult (5 步 stage + overall_status)
    """
    pipeline_start = time.monotonic()
    stages: List[StageResult] = []

    # 严格按 PIPELINE_ORDER 顺序执行, 单步失败不影响其他 stage (best-effort)
    stage_fns = [
        lambda: _stage_intake(db, knowledge_id, intake_hook=intake_hook),
        lambda: _stage_poll(db, knowledge_id, poll_wait_seconds=poll_wait_seconds),
        lambda: _stage_intent_classify(db, knowledge_id, threshold=intent_threshold),
        lambda: _stage_labeling(db, knowledge_id, top_k=top_k),
        lambda: _stage_sample_check(db, knowledge_id, sample_ratio=sample_ratio),
    ]

    for stage_enum, fn in zip(PIPELINE_ORDER, stage_fns):
        result = await fn()
        stages.append(result)
        # 写 audit log (best-effort, 不阻塞 pipeline)
        await _write_log(
            db,
            knowledge_id=knowledge_id,
            stage=result.stage,
            status=result.status,
            duration_ms=result.duration_ms,
            error_message=result.error_message,
            meta_data=result.meta_data,
        )

    total_ms = int((time.monotonic() - pipeline_start) * 1000)
    # overall: 全 success → success, 否则 failed (但单步 status 各自记录)
    has_failed = any(s.status == ClosedLoopStatus.FAILED for s in stages)
    overall = ClosedLoopStatus.FAILED if has_failed else ClosedLoopStatus.SUCCESS

    return ClosedLoopResult(
        knowledge_id=knowledge_id,
        stages=stages,
        overall_status=overall,
        total_duration_ms=total_ms,
    )


# ============== 工具: 失败告警查询 ==============

async def get_failure_rate(
    db: AsyncSession,
    *,
    stage: Optional[ClosedLoopStage] = None,
    hours: int = 24,
) -> Dict[str, Any]:
    """最近 N 小时 stage 失败率 (供 dashboard 告警)

    Returns:
        {
            "total": int, "failed": int, "skipped": int, "success": int,
            "failure_rate": float, "stage": str | None
        }
    """
    from datetime import timedelta

    from sqlalchemy import func as sql_func

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    stmt = select(
        KbClosedLoopLog.status,
        sql_func.count(KbClosedLoopLog.id),
    ).where(KbClosedLoopLog.created_at >= cutoff)

    if stage is not None:
        stmt = stmt.where(KbClosedLoopLog.stage == stage.value)

    stmt = stmt.group_by(KbClosedLoopLog.status)

    result = await db.execute(stmt)
    counts: Dict[str, int] = {}
    for status, cnt in result.all():
        counts[status] = int(cnt)

    total = sum(counts.values())
    failed = counts.get(STATUS_FAILED, 0)
    return {
        "total": total,
        "failed": failed,
        "skipped": counts.get(STATUS_SKIPPED, 0),
        "success": counts.get(STATUS_SUCCESS, 0),
        "failure_rate": round(failed / total, 3) if total > 0 else 0.0,
        "stage": stage.value if stage else None,
        "hours": hours,
    }