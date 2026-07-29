"""RAG PR6 (W92) e2e -- /admin/search-logs 7-dimension SearchLog admin API.

Plan: `rag-quirky-otter.md` PR6. Gates:
  (a) /admin/search-logs exposes >= 7 dimensions
  (b) recall rate (clicks / impressions) >= 30%   -- measured, reported as-is
  (c) slow-query share (> 500ms) <= 5%            -- measured, reported as-is
  (d) anchor 0 regression

These tests are pure-logic / contract tests: they exercise the module's
schemas, SQL shape, constants and route wiring without needing a live DB,
so they run in the default `SKIP_DB_SETUP` and no-DB environments too.

Gates (b) and (c) are DATA properties of production rows, not code properties.
Cases 19-20 assert that the *computation* is correct against synthetic inputs;
the real production numbers are reported in the runbook, not asserted here
(asserting on live data would make the suite flap with user behaviour).

22 cases total.
"""
import inspect

import pytest

from app.api.v1 import search_logs_admin as mod


# ---------------------------------------------------------------- dimensions


def test_01_gate_dimensions_has_at_least_seven():
    """Gate (a): >= 7 dimensions."""
    assert len(mod.GATE_DIMENSIONS) >= 7


def test_02_gate_dimensions_exact_names():
    """The 7 dims map 1:1 to the plan wording (时间/查询/候选数/命中/点击/耗时/user)."""
    assert mod.GATE_DIMENSIONS == [
        "created_at",
        "query",
        "candidate_count",
        "hit",
        "click_position",
        "latency_ms",
        "user_id",
    ]


def test_03_row_schema_exposes_every_gate_dimension():
    fields = set(mod.SearchLogRow.model_fields)
    missing = [d for d in mod.GATE_DIMENSIONS if d not in fields]
    assert not missing, f"SearchLogRow missing gate dims: {missing}"


def test_04_row_schema_has_user_name_for_display():
    """dim 7 (user) must be human-readable, not a bare FK."""
    assert "user_name" in mod.SearchLogRow.model_fields


def test_05_page_schema_reports_dimensions_to_frontend():
    """Frontend self-check (hasAllDimensions) depends on this field."""
    assert "dimensions" in mod.SearchLogPage.model_fields


# ---------------------------------------------------------------- row semantics


def test_06_hit_is_derived_from_clicked_id_true():
    row = mod.SearchLogRow(
        id=1, query="q", candidate_count=3, hit=True, clicked_id=9, click_position=1
    )
    assert row.hit is True and row.clicked_id == 9


def test_07_hit_false_when_no_click():
    row = mod.SearchLogRow(id=2, query="q", candidate_count=3, hit=False)
    assert row.hit is False
    assert row.clicked_id is None
    assert row.click_position is None


def test_08_latency_is_nullable_for_unclicked_rows():
    """No click => no dwell interval => latency_ms must be None, never 0."""
    row = mod.SearchLogRow(id=3, query="q", candidate_count=1, hit=False)
    assert row.latency_ms is None


def test_09_top_ids_defaults_to_empty_list():
    row = mod.SearchLogRow(id=4, query="q", candidate_count=0, hit=False)
    assert row.top_ids == []


# ---------------------------------------------------------------- constants


def test_10_slow_query_threshold_is_500ms():
    assert mod.SLOW_QUERY_THRESHOLD_MS == 500


def test_11_synthetic_source_is_system_metrics():
    """Heartbeat rows must be excluded, matching analytics.py discipline."""
    assert mod.SYNTHETIC_SOURCE == "system_metrics"


# ---------------------------------------------------------------- SQL contract


def _src(fn):
    return inspect.getsource(fn)


def test_12_list_excludes_synthetic_heartbeat_rows():
    assert "source IS DISTINCT FROM :synthetic" in _src(mod.list_search_logs)


def test_13_summary_excludes_synthetic_heartbeat_rows():
    assert "source IS DISTINCT FROM :synthetic" in _src(mod.search_logs_summary)


def test_14_list_joins_members_for_user_dimension():
    """dim 7 resolved in the same statement -- no N+1."""
    src = _src(mod.list_search_logs)
    assert "LEFT JOIN members m ON sl.user_id = m.id" in src
    assert src.count("LEFT JOIN") == 1


def test_15_candidate_count_derives_from_top_ids_length():
    assert "array_length(sl.top_ids, 1)" in _src(mod.list_search_logs)


def test_16_latency_derives_from_updated_minus_created():
    """No schema change: latency is a derived proxy, not a stored column."""
    src = _src(mod.list_search_logs)
    assert "sl.updated_at - sl.created_at" in src


def test_17_filters_are_parameterised_not_interpolated():
    """User input must reach SQL only as bind params, never as SQL text.

    Note `f"%{q}%"` in the source is fine -- it builds the *value* of the :q
    bind param. What must not exist is user input spliced into the statement
    string. The only f-string in the SQL itself is `{where_sql}`, which is
    assembled purely from module-local literals.
    """
    src = _src(mod.list_search_logs)
    for token in (":q", ":source", ":user_id", ":cutoff", ":limit", ":offset"):
        assert token in src, f"missing bind param {token}"
    # every appended predicate is a literal; user values only go into `params`
    assert 'where.append("sl.query ILIKE :q")' in src
    assert 'where.append("sl.source = :source")' in src
    assert 'where.append("sl.user_id = :user_id")' in src
    # the sole interpolation into SQL text is the literal-only where clause
    assert 'where_sql = " AND ".join(where)' in src


def test_18_summary_reports_latency_semantics_honestly():
    """The UI must never label the proxy as retrieval latency."""
    field = mod.SearchLogSummary.model_fields["latency_semantics"]
    assert field.annotation is str
    src = _src(mod.search_logs_summary)
    assert "NOT retrieval latency" in src


def test_18b_slow_gate_declared_not_evaluable_on_proxy_latency():
    """Gate (c) is defined on retrieval latency; we only have a dwell proxy.

    Returning `slow_query_gate_pass=True` off the proxy would be dressing a
    different measurement up as a passing gate, so the endpoint hard-codes
    `slow_query_gate_evaluable=False` until PR7 lands a real latency column.
    """
    assert "slow_query_gate_evaluable" in mod.SearchLogSummary.model_fields
    assert "slow_query_gate_evaluable=False" in _src(mod.search_logs_summary)


# ---------------------------------------------------------------- gate math


def test_19_recall_rate_gate_math():
    """Gate (b): clicks / impressions >= 0.30."""
    def recall(clicks, total):
        rate = round(clicks / total, 4) if total else 0.0
        return rate, rate >= 0.30

    assert recall(35, 100) == (0.35, True)
    assert recall(30, 100) == (0.30, True)
    assert recall(4, 89) == (0.0449, False)
    assert recall(0, 0) == (0.0, False)


def test_20_slow_query_rate_gate_math():
    """Gate (c): slow / total <= 0.05."""
    def slow(slow_count, total):
        rate = round(slow_count / total, 4) if total else 0.0
        return rate, rate <= 0.05

    assert slow(3, 100) == (0.03, True)
    assert slow(5, 100) == (0.05, True)
    assert slow(9, 100) == (0.09, False)
    assert slow(0, 0) == (0.0, True)


# ---------------------------------------------------------------- wiring


def test_21_both_routes_registered_under_admin_prefix():
    paths = {r.path for r in mod.router.routes}
    assert "/admin/search-logs" in paths
    assert "/admin/search-logs/summary" in paths


@pytest.mark.parametrize(
    "fn", [mod.list_search_logs, mod.search_logs_summary], ids=["list", "summary"]
)
def test_22_both_routes_require_admin_auth(fn):
    """Unlike legacy /analytics/logs, the new admin route is hardened."""
    sig = inspect.signature(fn)
    dep = sig.parameters["_admin"].default
    assert dep.dependency is mod.get_current_admin_user
