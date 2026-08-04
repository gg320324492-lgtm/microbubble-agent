"""W100 +74 RAG user feedback iteration 单元测试

派工 v6 §1.2 实战: 单元测试 stub Feedback + Knowledge 对象, 不依赖真 DB。
派工 v6 §13.3 仓库实情真查 (类 20.13):
- actual `feedback` 表用 `rating: -1=👎 / 1=👍` 二值 (W98 CHAT-P1-D3)
- 派工 brief 假设 `score < 3` → 实际语义 `rating == -1` (负面)
- 没有 `knowledge_quarantine` 表 → 复用 `Knowledge.meta['feedback_quarantine']`
"""
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import rag_feedback_iteration_service as svc


# ============================================================
# Helpers
# ============================================================


def make_feedback(
    *,
    fid: int,
    rating: int = -1,
    comment: str = "",
    message_id: Optional[int] = None,
):
    obj = SimpleNamespace(
        id=fid,
        rating=rating,
        comment=comment,
        message_id=message_id,
    )
    return obj


class _ResultStub:
    """SQLAlchemy Result stub supporting both ``.scalars().all()`` and ``.scalar_one_or_none()``."""

    def __init__(self, scalars_iter: List = None, scalar_value=None):
        self._scalars_iter = scalars_iter or []
        self._scalar_value = scalar_value

    def scalars(self):
        m = MagicMock()
        m.all.return_value = self._scalars_iter
        m.one_or_none.return_value = None  # unused by code path under test
        return m

    def scalar_one_or_none(self):
        return self._scalar_value


def make_async_db_for_feedback(rows: List, candidate_row=None):
    """AsyncMock returning feedback Result first, then candidate Result.

    Side effect queue is consumed FIFO per ``.execute()`` call.
    """
    db = AsyncMock()
    responses = [
        _ResultStub(scalars_iter=rows),       # feedback select
        _ResultStub(scalar_value=candidate_row),  # candidate select (with embedding)
    ]
    db.execute = AsyncMock(side_effect=lambda *a, **kw: responses.pop(0))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


# ============================================================
# Aggregation: negative feedback → quarantine entry written
# ============================================================


@pytest.mark.asyncio
async def test_aggregator_quarantines_negative_actionable():
    """Actionable negative feedback (rating=-1, comment≥3 chars, message_id) ⇒ quarantine.

    Note: in production the SQL ``rating == -1`` clause already filters positives,
    so we pass only rating=-1 rows to the mock (mimic SQL behavior).
    """
    short_comment = "ok"  # 2 chars — fails _is_actionable
    long_comment_a = "x" * 30  # passes _is_actionable
    long_comment_b = "y" * 25  # passes _is_actionable
    rows = [
        make_feedback(fid=1, rating=-1, comment=long_comment_a, message_id=42),
        make_feedback(fid=2, rating=-1, comment=long_comment_b, message_id=43),
        make_feedback(fid=3, rating=-1, comment="", message_id=44),  # skipped (empty comment)
        make_feedback(fid=4, rating=-1, comment=short_comment, message_id=45),  # skipped (short)
        make_feedback(fid=5, rating=-1, comment=long_comment_a, message_id=None),  # skipped (no msg_id)
    ]
    candidate = SimpleNamespace(id=7, meta={}, embedding=[0.1, 0.2])
    db = make_async_db_for_feedback(rows, candidate_row=candidate)

    result = await svc.aggregate_negative_feedback(db=db)

    assert result["scanned"] == 5
    assert result["negative"] == 2  # only rows 1, 2 are actionable
    assert result["skipped_empty_comment"] == 2  # row 3 + row 4
    assert result["skipped_no_message"] == 1  # row 5
    assert result["quarantined"] == 1
    assert "feedback_quarantine" in candidate.meta
    entry = candidate.meta["feedback_quarantine"][0]
    assert entry["negative_count"] == 2
    assert len(entry["sample_comments"]) == 2
    assert entry["affected_message_ids"] == [42, 43]


# ============================================================
# Threshold: rating == 1 always skipped; rating == -1 retained if has comment
# ============================================================


@pytest.mark.asyncio
async def test_threshold_rating_negative_only():
    """rating==1 rows would be filtered upstream by ``WHERE rating == -1``.

    The mock passes an empty row set to simulate that the SQL already removed
    positives. Result: scanned=0, no quarantine.
    """
    rows = []  # SQL filter already removed rating=1 rows
    db = make_async_db_for_feedback(rows, candidate_row=None)

    result = await svc.aggregate_negative_feedback(db=db)

    assert result["scanned"] == 0
    assert result["negative"] == 0
    assert result["quarantined"] == 0


# ============================================================
# Empty / no-actionable case
# ============================================================


@pytest.mark.asyncio
async def test_aggregator_no_actionable_short_circuits():
    """All negative rows lack actionable attributes ⇒ no quarantine write."""
    rows = [
        make_feedback(fid=20, rating=-1, comment="", message_id=None),  # both filters trip
    ]
    db = make_async_db_for_feedback(rows, candidate_row=None)

    result = await svc.aggregate_negative_feedback(db=db)

    assert result["negative"] == 0
    assert result["quarantined"] == 0
    assert result["triage_keywords"] == []
    assert db.commit.await_count == 0


# ============================================================
# Helpers: _is_actionable, _extract_quarantined_keywords
# ============================================================


def test_is_actionable_filters_short_comments():
    assert not svc._is_actionable(None)
    assert not svc._is_actionable("")
    assert not svc._is_actionable("a")  # 1 char < 3
    assert not svc._is_actionable("ok")  # 2 chars after strip
    assert not svc._is_actionable("  ok   ")  # strip → "ok" 2 chars
    assert not svc._is_actionable("   ab ")  # strip → "ab" 2 chars
    assert svc._is_actionable("useful comment")  # 14 chars passes
    assert svc._is_actionable("  yes good  ")  # strip → "yes good" 8 chars
    assert not svc._is_actionable("       ")  # all whitespace
    assert not svc._is_actionable("\n\t  ")  # all whitespace chars


def test_extract_quarantined_keywords_caps_results():
    """Keyword extractor returns at most 20 tokens, weighted by frequency."""
    text = ["formula missing", "formula absent", "formula formula formula", "slow"]
    kw = svc._extract_quarantined_keywords(text)
    assert isinstance(kw, list)
    assert len(kw) <= 20
    # 'formula' appears 5 times across 3 rows → should be in top tokens
    assert "formula" in kw


def test_extract_quarantined_keywords_empty_input():
    assert svc._extract_quarantined_keywords([]) == []
    assert svc._extract_quarantined_keywords([""]) == []
