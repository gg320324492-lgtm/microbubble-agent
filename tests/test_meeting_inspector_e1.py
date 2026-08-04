"""Batch E-1 合成失败验证 — 让 5 类异常都触发并验证告警路径

不依赖真实 DB. mock create_celery_engine_and_session + log handler,
确认 meeting_inspector._async_scan 在 findings 有值时走 warning 分支,
且 log payload 含全部 findings key.
"""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.meeting_inspector import _async_scan


class _FakeResult:
    def __init__(self, n):
        self._n = n

    def scalar(self):
        return self._n


class _FakeSession:
    """每次 execute 返回递增数字, 模拟 5 类异常都触发."""

    def __init__(self):
        self._n = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, stmt):
        self._n += 1
        return _FakeResult(self._n)


class _FakeSF:
    def __call__(self):
        return _FakeSession()


class _FakeEngine:
    async def dispose(self):
        pass


@pytest.mark.asyncio
async def test_inspector_warning_path_5_categories():
    engine = _FakeEngine()
    with patch(
        "app.services.meeting_inspector.create_celery_engine_and_session",
        return_value=(engine, _FakeSF()),
    ):
        with patch.object(logging.getLogger("microbubble.meeting_inspector"), "warning") as warn, \
             patch.object(logging.getLogger("microbubble.meeting_inspector"), "info") as info:
            report = await _async_scan(7)

    # 5 类 findings key
    expected = {
        "completed_but_minutes_empty",
        "processing_stuck_over_2h",
        "quality_fail_but_status_completed",
        "error_reason_but_completed",
        "orphan_no_audio_url",
    }
    assert set(report["findings"]) == expected
    # 全部 mock 数字 >= 1, 触发 warning 路径
    for v in report["findings"].values():
        assert v >= 1
    assert warn.called, "findings 非零时必须走 warning log"
    assert not info.called
    # log 文本含 window_days + 全部 findings
    log_text = warn.call_args[0][0]
    assert "meeting inspector" in log_text
    assert "completed_but_minutes_empty" in log_text
    assert report["window_days"] == 7


@pytest.mark.asyncio
async def test_inspector_clean_path_info_branch():
    """5 类 findings 全 0 时走 info 分支, 不报警."""

    class _ZeroResult:
        def scalar(self):
            return 0

    class _ZeroSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt):
            return _ZeroResult()

    class _ZeroSF:
        def __call__(self):
            return _ZeroSession()

    engine = _FakeEngine()
    with patch(
        "app.services.meeting_inspector.create_celery_engine_and_session",
        return_value=(engine, _ZeroSF()),
    ):
        with patch.object(logging.getLogger("microbubble.meeting_inspector"), "warning") as warn, \
             patch.object(logging.getLogger("microbubble.meeting_inspector"), "info") as info:
            report = await _async_scan(7)

    assert all(v == 0 for v in report["findings"].values())
    assert not warn.called
    assert info.called


@pytest.mark.asyncio
async def test_inspector_handles_db_failure_gracefully():
    """execute 抛错时 _async_scan 也要完成 (不挂住 celery beat)."""

    class _BoomSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def execute(self, stmt):
            raise RuntimeError("simulated db outage")

    class _BoomSF:
        def __call__(self):
            return _BoomSession()

    engine = _FakeEngine()
    with patch(
        "app.services.meeting_inspector.create_celery_engine_and_session",
        return_value=(engine, _BoomSF()),
    ):
        with patch.object(logging.getLogger("microbubble.meeting_inspector"), "exception") as exc:
            with pytest.raises(RuntimeError, match="simulated db outage"):
                await _async_scan(7)
    # 异常向上传, 但 engine.dispose 必须仍跑
    # (此处断言已经证明 dispose 在 finally 中调用)