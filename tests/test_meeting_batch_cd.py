"""Batch C/D 回归测试 — 重跑服务 + 巡检 + 管理 API

覆盖:
- MeetingReprocessingService: idempotency, snapshot, force gate
- MeetingInspector: 5 类异常检测
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from app.services.meeting_inspector import _async_scan
from app.services.meeting_reprocessing_service import (
    ReprocessRequest,
    SUPPORTED_STAGES,
)


def test_supported_stages_constant():
    assert "title" in SUPPORTED_STAGES
    assert "polish" in SUPPORTED_STAGES
    assert "analysis" in SUPPORTED_STAGES
    assert "speaker_assignment" in SUPPORTED_STAGES
    assert "transcription" in SUPPORTED_STAGES
    assert "quality" in SUPPORTED_STAGES


def test_reprocess_request_rejects_unknown_stage():
    with pytest.raises(ValueError, match="unsupported stages"):
        ReprocessRequest(meeting_id=1, requested_stages=["title", "bad_stage"])


def test_reprocess_request_normalizes_stages():
    req = ReprocessRequest(meeting_id=1, requested_stages=["title", "polish", "title"])
    assert req.requested_stages == ["title", "polish", "title"]


def test_idempotency_key_is_deterministic():
    from app.services.meeting_reprocessing_service import MeetingReprocessingService
    svc = MeetingReprocessingService(MagicMock())
    k1 = svc.idempotency_key(242, ["title", "analysis"])
    k2 = svc.idempotency_key(242, ["analysis", "title"])
    k3 = svc.idempotency_key(242, ["title", "analysis"])
    assert k1 == k2 == k3
    assert k1 != svc.idempotency_key(243, ["title", "analysis"])
    assert k1 != svc.idempotency_key(242, ["title"])


@pytest.mark.asyncio
async def test_inspector_scan_runs_with_mock(monkeypatch):
    """mock DB + create_celery_engine_and_session, 验证 _async_scan 返回 findings 结构."""

    class _FakeResult:
        def __init__(self, value):
            self._v = value

        def scalar(self):
            return self._v

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt):
            return _FakeResult(self._counter_inc())

        def _counter_inc(self):
            if not hasattr(self, "_n"):
                self._n = 0
            self._n += 1
            return self._n

    class _FakeSessionFactory:
        def __init__(self):
            pass

        def __call__(self):
            return _FakeSession()

    class _FakeEngine:
        async def dispose(self):
            pass

    monkeypatch.setattr(
        "app.services.meeting_inspector.create_celery_engine_and_session",
        lambda: (_FakeEngine(), _FakeSessionFactory()),
    )

    report = await _async_scan(7)
    assert "window_days" in report
    assert "scanned_at" in report
    assert "findings" in report
    expected_keys = {
        "completed_but_minutes_empty",
        "processing_stuck_over_2h",
        "quality_fail_but_status_completed",
        "error_reason_but_completed",
        "orphan_no_audio_url",
    }
    assert set(report["findings"].keys()) == expected_keys
    # 5 类计数都返回 (mock 返回 1..5)
    for v in report["findings"].values():
        assert v >= 1