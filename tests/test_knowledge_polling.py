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


def knowledge(kid, status="pending", storage_mode="kb"):
    return SimpleNamespace(
        id=kid,
        title=f"title-{kid}",
        content=f"content-{kid}",
        analysis_status=status,
        storage_mode=storage_mode,
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


# ============================================================
# storage_mode 过滤 (2026-10-09 类 20.219 同源第 4 例修复)
#
# 回归证据: 修复前本服务只按 analysis_status='pending' 选行, 会把 drive 行的
# 占位正文 "[drive upload] <file_name>" 喂给 llm_analysis_service 烧真实 LLM
# 调用, 产出的 summary/category/tags 全是基于文件名占位串的垃圾。以下 case
# 从「生成了什么 SQL」+「LLM 被喂了什么」两个层面钉死过滤器。
# ============================================================


def _render(stmt) -> str:
    """Render a captured SQLAlchemy statement with literal bind values."""
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


async def _captured_select_sql(monkeypatch) -> str:
    """Run the real service on an empty batch and return its ACTUAL select SQL.

    Deliberately captures ``db.execute``'s argument instead of rebuilding the
    statement here: a hand-rebuilt copy keeps passing even after the service
    stops calling the shared clause (caught by mutation test).
    """
    db = make_db([], remaining=0)
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", AsyncMock())
    await polling.process_pending_knowledge(limit=20, db=db)
    return _render(db.execute.await_args_list[0].args[0])


@pytest.mark.asyncio
async def test_polling_select_filters_out_drive_rows(monkeypatch):
    sql = await _captured_select_sql(monkeypatch)
    assert "storage_mode" in sql, "select 未带 storage_mode 过滤 —— drive 占位正文会被送去分析"
    assert f"storage_mode = {polling.INGESTABLE_STORAGE_MODE!r}" in sql
    assert "analysis_status = 'pending'" in sql, "原有 analysis_status 条件不应丢失"


@pytest.mark.asyncio
async def test_polling_select_has_exactly_two_predicates(monkeypatch):
    """过滤器必须真的多出一个谓词, 而不只是 SQL 里出现了 storage_mode 字样。"""
    sql = await _captured_select_sql(monkeypatch)
    where_clause = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    predicates = [p.strip() for p in where_clause.split("AND") if p.strip()]
    assert len(predicates) == 2, f"期望 2 个谓词 (analysis_status + storage_mode), 实得 {predicates}"
    assert any("storage_mode" in p for p in predicates)


def test_polling_reuses_the_rag_ingest_clause_not_a_copy():
    """常量与 helper 必须是同一个对象, 不能是复制粘贴的第二份 (会漂移)。"""
    from app.services import rag_auto_ingest_service as rag

    assert polling._ingestable_rows_clause is rag._ingestable_rows_clause
    assert polling.INGESTABLE_STORAGE_MODE is rag.INGESTABLE_STORAGE_MODE
    assert polling.INGESTABLE_STORAGE_MODE == "kb"


@pytest.mark.asyncio
async def test_drive_row_reaching_the_loop_is_skipped(monkeypatch):
    """即使 drive 行侥幸进了 pending 列表 (竞态/陈旧结果), 也不能被送去分析。"""
    drive_row = knowledge(7, storage_mode="drive")
    kb_row = knowledge(8, storage_mode="kb")
    db = make_db([drive_row, kb_row], remaining=1)
    analyze = AsyncMock(return_value={"summary": "s"})
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", analyze)

    stats = await polling.process_pending_knowledge(db=db)

    assert stats["processed"] == 1
    # drive 行一次 LLM 都没被调用, 只有 kb 行被分析
    analyze.assert_awaited_once_with("title-8", "content-8")
    assert drive_row.analysis_status == "pending", "drive 行不得被标记 done"
    assert kb_row.analysis_status == "done"


@pytest.mark.asyncio
async def test_remaining_count_uses_the_same_filter_as_the_select(monkeypatch):
    """remaining 必须与选行同口径, 否则 admin 看到的队列深度永远降不下来。"""
    db = make_db([], remaining=3)
    monkeypatch.setattr(polling.llm_analysis_service, "analyze_content", AsyncMock())

    await polling.process_pending_knowledge(db=db)

    count_sql = _render(db.execute.await_args_list[1].args[0])
    assert "storage_mode = 'kb'" in count_sql
    assert "analysis_status = 'pending'" in count_sql
