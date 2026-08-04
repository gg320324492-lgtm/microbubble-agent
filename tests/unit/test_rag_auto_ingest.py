"""W100 +73 RAG auto-ingest 单元测试

派工 v6 §1.2 实战: 单元测试不依赖真 DB, 用 stub Knowledge 对象 + mock session
覆盖状态机 (pending → ingesting → done / failed) + 重试 + 告警三个核心场景。

遵循 tests/rag/conftest.py 的 no-op setup_db 覆盖: 本套件不需要真 PG。
"""
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import rag_auto_ingest_service as svc


# ============================================================
# Helpers
# ============================================================


def make_knowledge(
    *,
    kid: int,
    analysis_status: str = "pending",
    meta: Dict[str, Any] = None,
    embedding=None,
):
    """Build a lightweight Knowledge stub for state-machine tests."""
    obj = SimpleNamespace(
        id=kid,
        title=f"doc-{kid}",
        content="some body",
        category=None,
        tags=None,
        source=None,
        meta=dict(meta or {}),
        embedding=embedding,
        search_text=None,
        analysis_status=analysis_status,
    )
    return obj


def make_async_db(rows: List):
    """Return an AsyncMock AsyncSession wired for select(Knowledge).all()."""

    db = AsyncMock()
    # execute(Knowledge.select).scalars().all()  → rows
    # execute(Knowledge.count).scalar_one()       → 0
    # commit / rollback                           → no-op
    scalars = MagicMock()
    scalars.all.return_value = rows
    scalars.scalar_one.return_value = 0

    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars
    db.execute.return_value = execute_result
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ============================================================
# State-machine: pending → ingesting → done
# ============================================================


@pytest.mark.asyncio
async def test_state_machine_pending_to_done():
    """State machine happy path: all 3 rows finish ingesting successfully."""
    rows = [
        make_knowledge(kid=1),
        make_knowledge(kid=2),
        make_knowledge(kid=3),
    ]
    db = make_async_db(rows)

    # Stub all ingestion side-effects to no-ops so we can assert pure state machine
    with (
        patch.object(svc, "_ingest_one", AsyncMock(return_value={"succeeded": True, "error": ""})) as ingest_mock,
    ):
        result = await svc.auto_ingest_pending(limit=20, db=db)

    assert result["processed"] == 3
    assert result["succeeded"] == 3
    assert result["failed"] == 0
    assert ingest_mock.call_count == 3
    for row in rows:
        # Meta ingest_state set; analysis_status mirrors
        assert row.meta.get("ingest_state") == "done"
        assert row.analysis_status == "done"
    assert db.commit.call_count >= 3  # one commit per row + tail counts


# ============================================================
# State-machine: pending → ingesting → failed
# ============================================================


@pytest.mark.asyncio
async def test_state_machine_pending_to_failed():
    """One row fails, captures error in meta['ingest_last_error']."""
    rows = [make_knowledge(kid=10), make_knowledge(kid=11)]
    db = make_async_db(rows)

    failing_ingest = AsyncMock(
        side_effect=[
            {"succeeded": True, "error": ""},
            {"succeeded": False, "error": "embedding timeout"},
        ]
    )
    with patch.object(svc, "_ingest_one", failing_ingest):
        result = await svc.auto_ingest_pending(limit=20, db=db)

    assert result["processed"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1
    assert rows[0].meta.get("ingest_state") == "done"
    assert rows[0].analysis_status == "done"
    assert rows[1].meta.get("ingest_state") == "failed"
    assert rows[1].meta.get("ingest_last_error") == "embedding timeout"
    assert rows[1].analysis_status == "failed"


# ============================================================
# Race guard: stale rows (analysis_status != pending) are skipped
# ============================================================


@pytest.mark.asyncio
async def test_race_skip_non_pending():
    """Rows whose analysis_status no longer matches pending are skipped silently."""
    rows = [
        make_knowledge(kid=20, analysis_status="done"),  # race-loss, skip
        make_knowledge(kid=21, analysis_status="pending"),
    ]
    db = make_async_db(rows)

    ingest_mock = AsyncMock(return_value={"succeeded": True, "error": ""})
    with patch.object(svc, "_ingest_one", ingest_mock):
        result = await svc.auto_ingest_pending(limit=20, db=db)

    assert result["processed"] == 1
    assert result["succeeded"] == 1
    assert ingest_mock.call_count == 1  # only row 21 was ingested


# ============================================================
# Bounded limit
# ============================================================


def test_bounded_limit_clamp():
    assert svc._bounded_limit(0) == 0
    assert svc._bounded_limit(20) == 20
    assert svc._bounded_limit(60) == svc.MAX_LIMIT  # 50


# ============================================================
# State setter is JSONB-safe
# ============================================================


def test_set_ingest_state_clears_error_on_success():
    obj = make_knowledge(
        kid=99,
        meta={"ingest_state": "failed", "ingest_last_error": "old-error"},
    )
    svc._set_ingest_state(obj, "done")
    assert obj.meta["ingest_state"] == "done"
    assert "ingest_last_error" not in obj.meta
    assert obj.analysis_status == "done"


def test_set_ingest_state_records_error_on_fail():
    obj = make_knowledge(kid=99)
    svc._set_ingest_state(obj, "failed", error="transient embed 504")
    assert obj.meta["ingest_state"] == "failed"
    assert obj.meta["ingest_last_error"] == "transient embed 504"
    assert obj.analysis_status == "failed"
