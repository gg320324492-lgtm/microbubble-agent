"""W86 mini-11 B analytics heartbeat end-to-end contract tests."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.analytics import get_stats, list_recent_logs
from app.core.celery import celery_app
from app.services.analytics_tasks import analytics_heartbeat


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


def test_analytics_heartbeat_writes_system_metrics_row():
    db = MagicMock()
    db.commit = AsyncMock()
    engine = MagicMock()
    engine.dispose = AsyncMock()
    session_factory = MagicMock(return_value=_AsyncContext(db))

    with patch(
        "app.services.analytics_tasks.create_celery_engine_and_session",
        return_value=(engine, session_factory),
    ):
        result = analytics_heartbeat.run()

    assert result == {"status": "ok", "source": "system_metrics"}
    db.add.assert_called_once()
    log = db.add.call_args.args[0]
    assert log.query == "system_health_check"
    assert log.source == "system_metrics"
    assert log.top_ids == []
    assert log.user_id == 1
    assert log.created_at.tzinfo == timezone.utc
    db.commit.assert_awaited_once()
    engine.dispose.assert_awaited_once()


def test_celery_beat_registers_analytics_heartbeat_every_five_minutes():
    entry = celery_app.conf.beat_schedule["analytics-heartbeat-every-5-min"]
    assert entry["task"] == "app.services.analytics_tasks.analytics_heartbeat"
    assert entry["schedule"] == 300.0
    assert "app.services.analytics_tasks" in celery_app.conf.imports


class _Result:
    def __init__(self, rows=None, one=None):
        self.rows = rows or []
        self.one = one

    def fetchone(self):
        return self.one

    def __iter__(self):
        return iter(self.rows)


@pytest.mark.asyncio
async def test_stats_queries_exclude_system_metrics():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            _Result(one=(2, 1, 1.0, 1)),
            _Result(rows=[("model", 2, 1)]),
            _Result(rows=[("knowledge_search", 2, 1)]),
            _Result(rows=[]),
            _Result(rows=[(datetime(2026, 7, 29).date(), 2, 1)]),
        ]
    )

    stats = await get_stats(days=7, db=db)

    assert stats["total_searches"] == 2
    assert "system_metrics" not in stats["by_source"]
    sql_texts = [str(call.args[0]) for call in db.execute.await_args_list]
    assert len(sql_texts) == 5
    assert all("system_metrics" in sql for sql in sql_texts)


@pytest.mark.asyncio
async def test_logs_include_system_metrics_rows():
    heartbeat = SimpleNamespace(
        id=331,
        query="system_health_check",
        embedding_model="Qwen/Qwen3-Embedding-0.6B",
        top_ids=[],
        clicked_id=None,
        click_position=None,
        session_id=None,
        source="system_metrics",
        created_at=datetime.now(timezone.utc),
    )
    scalars = MagicMock()
    scalars.all.return_value = [heartbeat]
    result = MagicMock()
    result.scalars.return_value = scalars
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    payload = await list_recent_logs(limit=50, source=None, db=db)

    assert payload["total"] == 1
    assert payload["items"][0]["source"] == "system_metrics"
    assert payload["items"][0]["query"] == "system_health_check"
