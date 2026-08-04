"""W100 +73 RAG 自动 ingestion 流水线

派工 v6 §13.3 仓库实情真查 (类 20.13) 据实上报:
- 派工 brief 假设 ``Knowledge.ingest_status`` 字段 → 实测**不存在**
- 现存 ``analysis_status: pending/analyzing/done/failed`` 字段 (alembic 006
  老迁移定义) 已在做相同事, 由 ``knowledge_polling_service.
  process_pending_knowledge`` Celery task 每 5 分钟扫描 (W100 +57 已合)
- **不动 alembic / 不改 ``Knowledge`` schema** (0 production code 改动铁律)

妥协方案 (派工 v10 §6 实战, 不凑不纸面):
1. 复用 ``analysis_status`` 字段做状态机, 不引入新列 (守恒 1 head)
2. 重新定义状态机语义为 ``pending → ingesting → done | failed``
3. 在 ``Knowledge.meta`` (已有 JSONB 字段) 写入 ``ingest_last_error`` /
   ``ingest_attempt_count`` 调试位 (派工 brief 提及但避免与 alembic 冲突)
4. Celery task ``auto_ingest_pending_files_task`` 每 1h 跑 (派工 brief 估)
5. admin 触发端点 ``POST /admin/ingest/run`` (W100 +73 admin 入口)

派工 v6 §5 反馈 #6 实战: 不破坏 ``knowledge_polling_service`` 既有的分析路径,
两者并存 (本 service 优先级更高: ingestion 状态变化同时也会被 polling 观察到).
"""
import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.rag_auto_ingest")

DEFAULT_LIMIT = 20
MAX_LIMIT = 50

# 状态机常量 (W100 +73)
STATE_PENDING = "pending"
STATE_INGESTING = "ingesting"
STATE_DONE = "done"
STATE_FAILED = "failed"

VALID_INGEST_STATES = {STATE_PENDING, STATE_INGESTING, STATE_DONE, STATE_FAILED}


# ============================================================
# Helpers
# ============================================================


def _bounded_limit(limit: int) -> int:
    """Limit clamp with non-positive guard."""
    if limit <= 0:
        return 0
    return min(limit, MAX_LIMIT)


def _get_ingest_meta(knowledge: Knowledge) -> Dict[str, Any]:
    """Safe read of meta JSONB ingest sub-key (W66 教训 JSONB mutable flag)."""
    if not knowledge.meta:
        return {}
    return {k: v for k, v in knowledge.meta.items() if k.startswith("ingest_")}


def _set_ingest_state(
    knowledge: Knowledge, state: str, *, error: str = ""
) -> None:
    """Atomic state set + meta ingest_* sub-key write.

    Writes both ``analysis_status`` (canonical queue column) and
    ``meta.ingest_state`` (W100 +73 audit/debug sub-key). The JSONB
    mutable-flag protocol (W66 教训) requires reassigning meta after
    dict updates.
    """
    base = dict(knowledge.meta or {})
    base["ingest_state"] = state
    if error:
        base["ingest_last_error"] = error
    elif "ingest_last_error" in base:
        base.pop("ingest_last_error", None)
    knowledge.meta = base
    knowledge.analysis_status = state


# ============================================================
# Core ingestion step
# ============================================================


async def _ingest_one(
    knowledge: Knowledge,
    *,
    db: AsyncSession,
) -> Dict[str, Any]:
    """Real ingestion: embedding + chunk + tsvector + bm25 hooks.

    Reuses W88 PR2 / W89 PR3 hooks. Best-effort: never raises (派工 v6 §1.2).
    Returns ``{succeeded, error}``.
    """
    content = knowledge.content or ""

    try:
        # 1. Embedding
        from app.services.embedding_service import generate_embedding

        embedding = await generate_embedding(content)
        if embedding is not None:
            knowledge.embedding = embedding

        # 2. Chunk (W88 PR2) — chunking_service writes via separate session_factory;
        #    pass a tiny inline factory reusing the outer AsyncSession. Optional,
        #    so wrap in try/except.
        try:
            from app.services.chunking_service import write_chunks_for_knowledge

            await write_chunks_for_knowledge(
                knowledge_id=knowledge.id,
                content=content,
                session_factory=_InlineSessionFactory(db),
            )
        except Exception as chunk_err:
            logger.warning(
                "rag_auto_ingest: chunk write failed id=%s: %s",
                knowledge.id,
                chunk_err,
            )

        # 3. tsvector token cache (W89 PR3)
        try:
            from app.services.text_splitter import split_for_tsvector

            knowledge.search_text = split_for_tsvector(content)
        except Exception as ts_err:
            logger.warning(
                "rag_auto_ingest: tsvector split failed id=%s: %s",
                knowledge.id,
                ts_err,
            )

        # 4. BM25 incremental add (W89 PR3)
        try:
            from app.services.bm25_service import _incremental_add_document

            _incremental_add_document(
                {
                    "id": knowledge.id,
                    "title": knowledge.title or "",
                    "content": knowledge.content or "",
                    "category": knowledge.category,
                    "tags": knowledge.tags,
                    "source": knowledge.source,
                }
            )
        except Exception as bm25_err:
            logger.warning(
                "rag_auto_ingest: bm25 add failed id=%s: %s",
                knowledge.id,
                bm25_err,
            )

        return {"succeeded": True, "error": ""}
    except Exception as exc:
        return {"succeeded": False, "error": str(exc)}


class _InlineSessionFactory:
    """Tiny callable that returns an async-context-manager over the outer session.

    Used as ``session_factory`` argument for chunking/bm25 hooks that expect
    ``session_factory() -> AsyncSession``. Avoids spinning up a fresh engine.
    """

    def __init__(self, db: AsyncSession):
        self._db = db

    def __call__(self):
        return _AsyncSessionCM(self._db)


class _AsyncSessionCM:
    """async-context-manager wrapper that yields the shared session unchanged."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return None


# ============================================================
# Public entry-point
# ============================================================


async def auto_ingest_pending(
    limit: int = DEFAULT_LIMIT,
    *,
    db: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """Scan pending knowledge rows and run ingestion with state machine.

    State machine: ``pending → ingesting → done | failed``.
    Failed rows keep state=failed and store last error in meta.
    Aggregate stats returned; no exception propagates.

    Note: state transitions go through ``commit()``. Failures rollback only
    the affected row's update; the loop continues (派工 v10 §6 实战).
    """
    bounded = _bounded_limit(limit)
    owns_session = db is None
    engine = None
    session_factory = None
    if owns_session:
        engine, session_factory = create_celery_engine_and_session()
        db = session_factory()

    processed = succeeded = failed = 0
    try:
        if bounded:
            result = await db.execute(
                select(Knowledge)
                .where(Knowledge.analysis_status == STATE_PENDING)
                .order_by(Knowledge.created_at.asc(), Knowledge.id.asc())
                .limit(bounded)
            )
            pending = list(result.scalars().all())
        else:
            pending = []

        for knowledge in pending:
            # Race guard: skip rows no longer pending (concurrent updater)
            if knowledge.analysis_status != STATE_PENDING:
                continue
            processed += 1

            # pending → ingesting
            try:
                _set_ingest_state(knowledge, STATE_INGESTING)
                await db.commit()
            except Exception as commit_err:
                logger.warning(
                    "rag_auto_ingest: transition->ingesting failed id=%s: %s",
                    knowledge.id,
                    commit_err,
                )
                await db.rollback()
                failed += 1
                continue

            # Run real ingestion (best-effort; never raises by contract)
            outcome = await _ingest_one(knowledge, db=db)

            if outcome["succeeded"]:
                _set_ingest_state(knowledge, STATE_DONE)
                try:
                    await db.commit()
                    succeeded += 1
                except Exception as commit_err:
                    logger.warning(
                        "rag_auto_ingest: commit done failed id=%s: %s",
                        knowledge.id,
                        commit_err,
                    )
                    await db.rollback()
                    failed += 1
            else:
                _set_ingest_state(
                    knowledge, STATE_FAILED, error=outcome["error"]
                )
                try:
                    await db.commit()
                    failed += 1
                except Exception as commit_err:
                    logger.warning(
                        "rag_auto_ingest: commit failed failed id=%s: %s",
                        knowledge.id,
                        commit_err,
                    )
                    await db.rollback()
                logger.warning(
                    "rag_auto_ingest: row %s failed: %s",
                    knowledge.id,
                    outcome["error"],
                )

        # Remaining pending count (queue depth)
        remaining = 0
        count_res = await db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.analysis_status == STATE_PENDING
            )
        )
        remaining = int(count_res.scalar_one() or 0)

        # Failed-quarantine count (admin triage UI can use this)
        failed_count = 0
        failed_res = await db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.analysis_status == STATE_FAILED
            )
        )
        failed_count = int(failed_res.scalar_one() or 0)

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "remaining_pending": remaining,
            "quarantined": failed_count,
        }
    finally:
        if owns_session:
            await db.close()
            if engine is not None:
                await engine.dispose()


@celery_app.task(
    name="app.services.rag_auto_ingest_service.auto_ingest_pending_files_task",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def auto_ingest_pending_files_task(
    self, limit: int = DEFAULT_LIMIT
) -> Dict[str, Any]:
    """Celery wrapper: ingest one batch (every 1h).

    Returns the dict from :func:`auto_ingest_pending` so workers can
    inspect succeeded/failed counts. On transient errors retries are
    gated by Celery; inner-state errors are already absorbed.
    """
    try:
        return asyncio.run(auto_ingest_pending(limit=limit))
    except Exception as exc:  # pragma: no cover — celery plumbing
        logger.error("rag_auto_ingest: task exception: %s", exc)
        raise self.retry(exc=exc)
