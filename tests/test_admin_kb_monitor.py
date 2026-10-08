"""Unit tests for the KB monitor admin API (no real DB).

回归锚点: 2026-10-09 类 20.219 同源第 5 例 — admin 面板的队列深度 / 重试中 / 失败列表
原先只按 analysis_status 过滤, 把 storage_mode='drive' 的行也算进去。

为什么这会造成真告警而不是无害噪声:
  1. ``app/models/knowledge.py:26`` 的 ``analysis_status`` 默认值是 ``"pending"``;
  2. ``app/services/drive_service.py`` 的 6 条建行路径 (普通上传 / 秒传 / 新版本 /
     上传会话完成) **都不显式设置 analysis_status** → 每个网盘文件都落 pending;
  3. 但第 3/4 例修复后, ``rag_auto_ingest_service`` 与 ``knowledge_polling_service``
     已按 storage_mode=='kb' 硬过滤 → **drive 行永远不会被 claim**。

于是修复前 admin 看到的 queue_depth / retrying / failures 每传一个网盘文件 +1 且永远
drain 不掉; failures 列表还会诱导 admin 对着一批永远不会被 claim 的行反复人工重提。

断言策略 (照 ``tests/test_knowledge_polling.py`` 的做法): 捕获 ``db.execute`` 实际收到
的 statement / SQL 文本再渲染, **不在测试里重建一遍 select** —— 重建的副本在服务退回
pre-fix 后依然全绿, 等于没写 (见 test_service_revert_makes_these_red 的变异证据)。
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql.elements import TextClause

from app.api.v1 import admin_kb_monitor as monitor


# ============================================================
# Fakes
# ============================================================


class FakeResult:
    """Stands in for an AsyncSession result for all 4 consumption shapes used here.

    The monitor reads results four different ways: ``scalar_one()`` (counters),
    ``scalars().all()`` (failures list), and bare iteration (raw-SQL row tuples).
    """

    def __init__(self, *, rows=(), scalar=0):
        self._rows = list(rows)
        self._scalar = scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        inner = MagicMock()
        inner.all.return_value = self._rows
        return inner

    def __iter__(self):
        return iter(self._rows)


def _db_with(results: list[FakeResult]) -> MagicMock:
    """A db whose ``execute`` returns ``results`` in call order and records calls.

    Each endpoint gets its own queue: the monitor reads results four different
    ways (``scalar_one`` / ``scalars().all`` / bare iteration), so a shared pool
    would hand a tuple where a row object is expected.
    """
    db = MagicMock()
    db.execute = AsyncMock(side_effect=list(results))
    db.commit = AsyncMock()
    return db


def overview_db(*, queue=0, retrying=0):
    """Overview runs 4 queries in order: status_counts, queue_depth, retrying, trend."""
    return _db_with(
        [
            FakeResult(rows=[("done", 5), ("pending", 2)]),
            FakeResult(scalar=queue),
            FakeResult(scalar=retrying),
            FakeResult(rows=[(datetime(2026, 1, 1, 12), 4, 3, 1)]),
        ]
    )


def queue_depth_db(*, rows=(("pending", 0), ("analyzing", 0))):
    """The queue-depth endpoint runs exactly 1 query (its own GROUP BY)."""
    return _db_with([FakeResult(rows=list(rows))])


def failures_db(*, rows=()):
    """The failures endpoint runs exactly 1 query and reads ``scalars().all()``."""
    return _db_with([FakeResult(rows=list(rows))])


# ============================================================
# Rendering helpers — always render what the service ACTUALLY executed
# ============================================================


def render_call(call) -> tuple[str, dict]:
    """Return ``(sql, params)`` for one captured ``db.execute`` call.

    Handles both statement shapes the monitor uses:
      * raw ``text()`` → a TextClause (no .compile()), SQL is ``str()`` and the
        values live in the second positional arg (the params dict);
      * ORM ``select()`` → compiled with literal_binds so the filter is visible.
    """
    stmt, params = call.args[0], (call.args[1] if len(call.args) > 1 else {})
    if isinstance(stmt, TextClause):
        return str(stmt), dict(params)
    return str(stmt.compile(compile_kwargs={"literal_binds": True})), dict(params)


def render_all(db) -> list[tuple[str, dict]]:
    return [render_call(c) for c in db.execute.await_args_list]


def predicates_of(sql: str) -> list[str]:
    """Split the WHERE clause on AND, so we can count/inspect real predicates."""
    where = sql.split("WHERE", 1)[1]
    for terminator in ("ORDER BY", "GROUP BY", "LIMIT"):
        where = where.split(terminator, 1)[0]
    return [p.strip() for p in where.split(" AND ") if p.strip()]


async def call_overview(db, hours=24):
    return await monitor.kb_monitor_overview(
        hours=hours, current_user=None, db=db
    )


async def call_queue_depth(db):
    return await monitor.kb_monitor_queue_depth(current_user=None, db=db)


# ============================================================
# 1. overview: status_counts (raw SQL, #1)
# ============================================================


@pytest.mark.asyncio
async def test_overview_status_counts_sql_filters_drive_rows():
    """ingested/done/failed/status_counts 共用这一条, 分母口径必须与分子一致。"""
    db = overview_db()
    await call_overview(db)

    sql, params = render_all(db)[0]
    assert "storage_mode" in sql, "status_counts 未带 storage_mode 过滤"
    assert "storage_mode = :ingestable_storage_mode" in sql
    assert params["ingestable_storage_mode"] == "kb", (
        f"绑定值应为 INGESTABLE_STORAGE_MODE, 实得 {params.get('ingestable_storage_mode')!r}"
    )
    assert "created_at >= :cutoff" in sql, "原有时间窗条件不应丢失"


@pytest.mark.asyncio
async def test_overview_status_counts_does_not_drop_the_window_param():
    """回归: 补 storage_mode 时不能把 cutoff 顺手挤掉 (params 是同一 dict)。"""
    db = overview_db()
    await call_overview(db)

    _, params = render_all(db)[0]
    assert "cutoff" in params


# ============================================================
# 2. overview: queue_depth (ORM, #2)
# ============================================================


@pytest.mark.asyncio
async def test_overview_queue_depth_filters_drive_rows():
    db = overview_db()
    await call_overview(db)

    sql, _ = render_all(db)[1]
    assert "storage_mode = 'kb'" in sql
    assert "analysis_status IN ('pending', 'analyzing')" in sql
    assert len(predicates_of(sql)) == 2, f"期望 2 个谓词, 实得 {predicates_of(sql)}"


@pytest.mark.asyncio
async def test_overview_queue_depth_number_comes_from_the_filtered_statement():
    """钉住下标对齐: admin 看到的 queue_depth 必须取自**带过滤**的那条 count。

    防的是「把 4 条查询重排 / 少加一条」后 scalar 恰好从未过滤的语句取值。
    """
    db = overview_db(queue=7)
    payload = await call_overview(db)

    sql, _ = render_all(db)[1]
    assert "storage_mode = 'kb'" in sql
    assert payload["queue_depth"] == 7


# ============================================================
# 3. overview: retrying (ORM, #3)
# ============================================================


@pytest.mark.asyncio
async def test_overview_retrying_filters_drive_rows():
    db = overview_db()
    await call_overview(db)

    sql, _ = render_all(db)[2]
    assert "storage_mode = 'kb'" in sql
    assert "analysis_status = 'pending'" in sql
    assert len(predicates_of(sql)) == 3, f"期望 3 个谓词 (状态+滞留+storage_mode), 实得 {predicates_of(sql)}"


# ============================================================
# 4. overview: trend (raw SQL, #4)
# ============================================================


@pytest.mark.asyncio
async def test_overview_trend_filters_drive_rows():
    """前端 KbMonitorView.vue L171 用 trend.failed / trend.ingested 算失败率。"""
    db = overview_db()
    await call_overview(db)

    sql, params = render_all(db)[3]
    assert "storage_mode = :ingestable_storage_mode" in sql
    assert params["ingestable_storage_mode"] == "kb"
    assert "date_trunc" in sql, "趋势聚合不应被改写"


@pytest.mark.asyncio
async def test_overview_trend_keeps_the_status_filters_inside_aggregate():
    """FILTER 子句是 done/failed 的来源, 补 storage_mode 时不能碰掉。"""
    db = overview_db()
    await call_overview(db)

    sql, _ = render_all(db)[3]
    assert "analysis_status = 'done'" in sql
    assert "analysis_status = 'failed'" in sql


# ============================================================
# 5. queue-depth endpoint (raw SQL, #5)
# ============================================================


@pytest.mark.asyncio
async def test_queue_depth_endpoint_filters_drive_rows():
    db = queue_depth_db()
    await call_queue_depth(db)

    sql, params = render_all(db)[0]
    assert "storage_mode = :ingestable_storage_mode" in sql
    assert params["ingestable_storage_mode"] == "kb"
    assert "analysis_status IN ('pending', 'analyzing')" in sql


@pytest.mark.asyncio
async def test_queue_depth_eta_derives_from_the_filtered_count():
    """eta_minutes 是 queue_depth 的派生量 —— 深度错了 ETA 就永远归不了零。"""
    db = queue_depth_db(rows=[("pending", 100)])
    payload = await call_queue_depth(db)

    sql, _ = render_all(db)[0]
    assert "storage_mode = :ingestable_storage_mode" in sql
    assert payload["queue_depth"] == 100
    assert payload["eta_minutes"] > 0


# ============================================================
# 6. failures endpoint (ORM, #6) — 两个分支都要过滤
# ============================================================


@pytest.mark.asyncio
async def test_failures_include_stuck_filters_drive_rows():
    db = failures_db()
    await monitor.kb_monitor_failures(
        limit=50, include_stuck=True, current_user=None, db=db
    )

    sql, _ = render_all(db)[0]
    assert "storage_mode = 'kb'" in sql, "失败列表含 drive 行 = 假告警, admin 会反复重提死行"
    assert "analysis_status = 'failed'" in sql
    assert "analysis_status = 'pending'" in sql


@pytest.mark.asyncio
async def test_failures_failed_only_branch_also_filters_drive_rows():
    """include_stuck=False 走 else 分支 —— 补过滤加在分支之后, 覆盖两条路径。"""
    db = failures_db()
    await monitor.kb_monitor_failures(
        limit=50, include_stuck=False, current_user=None, db=db
    )

    sql, _ = render_all(db)[0]
    assert "storage_mode = 'kb'" in sql
    assert "analysis_status IN ('failed')" in sql


@pytest.mark.asyncio
async def test_failures_filter_sits_outside_the_or_group():
    """storage_mode 必须 AND 在 OR 组**外面**。

    正确形状: ``WHERE (failed OR (pending AND 滞留)) AND storage_mode='kb'``
    若整段被括号吞成 ``WHERE (failed OR ... OR storage_mode='kb')``, drive 的 failed
    行仍会漏进来 —— 这是补 AND 谓词时最常见的括号错误, 所以显式钉住。
    """
    import re

    db = failures_db()
    await monitor.kb_monitor_failures(
        limit=50, include_stuck=True, current_user=None, db=db
    )

    sql, _ = render_all(db)[0]
    # 注意: 必须只看 WHERE —— select(Knowledge) 展开的列清单里本来就有一列 storage_mode,
    # 全串计数会把「多了一列」误判成「谓词重复」。
    where = sql.split("WHERE", 1)[1].split("ORDER BY", 1)[0]
    assert where.count("storage_mode") == 1, f"WHERE 中 storage_mode 应恰好 1 次, 实得 {where}"
    # 顶层 AND: 前面是 AND 而不是左括号
    assert re.search(
        r"\)\s+AND\s+knowledge\.storage_mode\s*=\s*'kb'", where
    ), f"storage_mode 应作为顶层 AND 谓词接在 OR 组之后, 实得 WHERE: {where}"
    assert not re.search(
        r"\(\s*knowledge\.storage_mode", where
    ), "storage_mode 落在了括号内 —— 会被 OR 语义吞掉, drive 行漏进来"


# ============================================================
# 单例真相: 常量必须 import 复用, 不能复制第二份
# ============================================================


def test_monitor_reuses_the_shared_ingest_constant_not_a_copy():
    from app.services import rag_auto_ingest_service as rag

    assert monitor.INGESTABLE_STORAGE_MODE is rag.INGESTABLE_STORAGE_MODE
    assert monitor.INGESTABLE_STORAGE_MODE == "kb"


def test_ingestable_kb_clause_targets_the_knowledge_model():
    """clause 必须作用于 Knowledge (不是别的表) —— raw SQL 那几条则按表名 knowledge 写。"""
    from sqlalchemy.dialects import postgresql

    compiled = str(
        monitor._ingestable_kb_clause().compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "storage_mode = 'kb'" in compiled
    assert "knowledge" in compiled, "clause 应作用于 Knowledge 模型对应的表"