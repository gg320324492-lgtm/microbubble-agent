"""Unit tests for the pending knowledge Celery processor (no real DB/LLM)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.celery import celery_app
from app.services import knowledge_polling_service as polling


class FakeScalarResult:
    def __init__(self, *, rows=None, scalar=0):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        result = MagicMock()
        result.all.return_value = self._rows
        return result

    def scalar_one(self):
        return self._scalar


def knowledge(kid, status="pending"):
    return SimpleNamespace(
        id=kid,
        title=f"title-{kid}",
        content=f"content-{kid}",
        analysis_status=status,
        quality_score=None,
        summary=None,
        category=None,
        topic=None,
        tags=None,
        key_concepts=None,
        entities=None,
        related_topics=None,
        knowledge_type=None,
    )


def make_db(rows, remaining=0):
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            FakeScalarResult(rows=rows),
            FakeScalarResult(scalar=remaining),
        ]
    )
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def analysis():
    return {
        "summary": "summary",
        "category": "论文",
        "tags": ["bubble"],
        "key_concepts": ["mass transfer"],
        "related_topics": ["ozone"],
    }


@pytest.mark.asyncio
async def test_process_pending_basic(monkeypatch, analysis):
    row = knowledge(1)
    db = make_db([row], remaining=0)
    analyze = AsyncMock(return_value=analysis)
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", analyze)

    stats = await polling.process_pending_knowledge(db=db)

    assert stats == {"processed": 1, "succeeded": 1, "failed": 0, "remaining": 0}
    assert row.analysis_status == "done"
    assert row.quality_score == 1.0
    db.commit.assert_awaited_once()
    analyze.assert_awaited_once_with("title-1", "content-1")


@pytest.mark.asyncio
async def test_process_pending_empty(monkeypatch):
    db = make_db([], remaining=0)
    analyze = AsyncMock()
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", analyze)

    stats = await polling.process_pending_knowledge(db=db)

    assert stats == {"processed": 0, "succeeded": 0, "failed": 0, "remaining": 0}
    analyze.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_pending_partial_failure(monkeypatch, analysis):
    first, second = knowledge(1), knowledge(2)
    db = make_db([first, second], remaining=1)
    analyze = AsyncMock(side_effect=[analysis, RuntimeError("down"), RuntimeError("down"), RuntimeError("down")])
    sleep = AsyncMock()
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", analyze)

    stats = await polling.process_pending_knowledge(db=db, sleep=sleep)

    assert stats == {"processed": 2, "succeeded": 1, "failed": 1, "remaining": 1}
    assert first.analysis_status == "done"
    assert second.analysis_status == "pending"
    assert analyze.await_count == 4
    assert sleep.await_count == 2
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_pending_limit(monkeypatch):
    db = make_db([], remaining=7)
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", AsyncMock())

    stats = await polling.process_pending_knowledge(limit=500, db=db)

    statement = db.execute.await_args_list[0].args[0]
    assert "LIMIT :param_1" in str(statement)
    assert statement._limit_clause.value == polling.MAX_LIMIT
    assert stats["remaining"] == 7


@pytest.mark.asyncio
async def test_process_pending_skip_already_done(monkeypatch):
    stale_row = knowledge(3, status="done")
    db = make_db([stale_row], remaining=0)
    analyze = AsyncMock()
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", analyze)

    stats = await polling.process_pending_knowledge(db=db)

    assert stats["processed"] == 0
    analyze.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_failure_retries_with_exponential_backoff(monkeypatch, analysis):
    row = knowledge(4)
    db = make_db([row], remaining=0)
    analyze = AsyncMock(side_effect=[TimeoutError("first"), TimeoutError("second"), analysis])
    sleep = AsyncMock()
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", analyze)

    stats = await polling.process_pending_knowledge(db=db, sleep=sleep)

    assert stats["succeeded"] == 1
    assert [call.args[0] for call in sleep.await_args_list] == [0.25, 0.5]


def test_celery_task_and_beat_are_registered():
    task_name = "app.services.knowledge_polling_service.process_pending_knowledge_task"
    assert task_name in celery_app.tasks
    schedule = celery_app.conf.beat_schedule["process-pending-knowledge"]
    assert schedule["task"] == task_name
    assert schedule["schedule"] == 300.0


def test_zero_limit_does_not_fetch_rows(monkeypatch):
    """The explicit safety stop still reports remaining queue depth."""
    db = MagicMock()
    db.execute = AsyncMock(return_value=FakeScalarResult(scalar=9))
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", AsyncMock())

    stats = __import__("asyncio").run(polling.process_pending_knowledge(limit=0, db=db))

    assert stats == {"processed": 0, "succeeded": 0, "failed": 0, "remaining": 9}
    assert db.execute.await_count == 1
