"""Batch E-3 重跑服务幂等键测试

- 1h 内同 stages 重跑: 直接复用 run, 跳过执行
- 1h 内不同 stages: 重新发起
- 跨会议: 独立
- force=true: 跳过复用
- transcription stage: 必须 force=true
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.meeting_reprocessing_service import (
    MeetingReprocessingService,
    ReprocessRequest,
)


def _make_meeting():
    m = SimpleNamespace(
        id=242,
        title="T", summary=None, key_points=None, decisions=None,
        transcript_polished=[{"speaker": "张三", "text": "你好", "ts": 0}],
        transcript=[{"speaker": "张三", "text": "你好", "start": 0}],
        speaker_mapping={}, speaker_stats=None, error_reason=None,
        status="completed",
    )
    return m


def _make_existing_run(idempotency_key=None, started_at=None, status="success"):
    r = SimpleNamespace(
        id=99,
        meeting_id=242,
        overall_status=status,
        started_at=started_at or __import__("datetime").datetime.now(),
        metrics={"idempotency_key": idempotency_key} if idempotency_key else {},
    )
    return r


def _make_async_db():
    """返回 AsyncMock 形式的 db session, 支持 await commit/flush/add 等."""
    db = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


def test_request_validates_stages():
    with pytest.raises(ValueError):
        ReprocessRequest(meeting_id=1, requested_stages=["invalid_stage"])


def test_idempotency_key_stable_across_stage_order():
    svc = MeetingReprocessingService(MagicMock())
    k1 = svc.idempotency_key(242, ["title", "analysis", "polish"])
    k2 = svc.idempotency_key(242, ["polish", "analysis", "title"])
    assert k1 == k2


def test_idempotency_key_differs_per_meeting():
    svc = MeetingReprocessingService(MagicMock())
    assert svc.idempotency_key(242, ["title"]) != svc.idempotency_key(243, ["title"])


@pytest.mark.asyncio
async def test_reuse_run_when_key_matches_and_recent():
    svc = MeetingReprocessingService(MagicMock())
    from datetime import datetime, timezone

    req = ReprocessRequest(
        meeting_id=242, requested_stages=["title", "analysis"], force=False
    )
    matching = _make_existing_run(idempotency_key=svc.idempotency_key(242, ["analysis", "title"]))

    with patch.object(svc, "get_meeting", AsyncMock(return_value=_make_meeting())), \
         patch.object(svc, "find_recent_successful_run", AsyncMock(return_value=matching)):
        result = await svc.execute(req)

    assert result.reused is True
    assert result.run_id == 99
    assert "title" in result.completed_stages


@pytest.mark.asyncio
async def test_no_reuse_when_keys_differ():
    db = _make_async_db()
    svc = MeetingReprocessingService(db)
    req = ReprocessRequest(
        meeting_id=242, requested_stages=["title"], force=False
    )
    with patch.object(svc, "get_meeting", AsyncMock(return_value=_make_meeting())), \
         patch.object(svc, "find_recent_successful_run", AsyncMock(return_value=None)):
        with patch.object(svc, "start_reprocess_run",
                          AsyncMock(return_value=(MagicMock(id=200, metrics={}, overall_status="", finished_at=None,
                                                            error_summary=None, warning_count=0), False))):
            with patch.object(svc, "_run_stage", AsyncMock(side_effect=NotImplementedError("not impl in test"))):
                with patch.object(svc, "snapshot_derived_fields", AsyncMock(return_value={})):
                    result = await svc.execute(req)
    assert result.reused is False


@pytest.mark.asyncio
async def test_transcription_requires_force():
    svc = MeetingReprocessingService(_make_async_db())
    req = ReprocessRequest(
        meeting_id=242, requested_stages=["transcription"], force=False
    )
    with patch.object(svc, "get_meeting", AsyncMock(return_value=_make_meeting())):
        result = await svc.execute(req)
    assert result.reused is False
    assert any("transcription" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_force_skips_reuse():
    db = _make_async_db()
    svc = MeetingReprocessingService(db)
    req = ReprocessRequest(
        meeting_id=242, requested_stages=["title"], force=True
    )
    matching = _make_existing_run(idempotency_key=svc.idempotency_key(242, ["title"]))
    with patch.object(svc, "get_meeting", AsyncMock(return_value=_make_meeting())), \
         patch.object(svc, "find_recent_successful_run", AsyncMock(return_value=matching)):
        with patch.object(svc, "start_reprocess_run",
                          AsyncMock(return_value=(MagicMock(id=300, metrics={}, overall_status="", finished_at=None,
                                                            error_summary=None, warning_count=0), False))):
            with patch.object(svc, "_run_stage", AsyncMock(side_effect=NotImplementedError)):
                with patch.object(svc, "snapshot_derived_fields", AsyncMock(return_value={})):
                    result = await svc.execute(req)
    assert result.reused is False
    assert result.run_id == 300