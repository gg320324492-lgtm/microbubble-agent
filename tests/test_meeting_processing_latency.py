"""meeting_processing_stages.latency_ms 语义守卫 (类 20.220)

背景 (2026-10-13, 会议 256 全流程验收):
`latency_ms` 名义上是"阶段耗时", 实测却是**落库调用本身**的耗时
(downloading 18ms / transcribing 59ms / 声纹 4ms), 而阶段真实耗时是
60s / 603s / 117s —— 拿它做耗时监控会得到完全错误的结论。

根因不在字段语义 (`MeetingProcessingService.finish_stage` 一直按
`finished_at - started_at` 算, 是对的), 而在**调用方**:
`post_meeting_tasks._persist_stage` 是"阶段跑完之后"才被调用的,
它现场调 start_stage + finish_stage, 两次紧挨着, 中间只隔两次 DB round-trip。

本文件钉住这个不变量, 防止将来有人把透传改回去 (那不会报任何错,
只会让 latency_ms 重新变成几十毫秒 —— 典型的"看起来在工作")。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.meeting_processing_service import MeetingProcessingService, _now
from app.services.post_meeting_tasks import _persist_stage


def _svc() -> tuple[MeetingProcessingService, MagicMock]:
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return MeetingProcessingService(db), db


# ==========================================================================
# start_stage: started_at 透传
# ==========================================================================

def test_start_stage_uses_supplied_started_at():
    """传了 started_at 就必须用它, 不能被 _now() 覆盖。"""
    svc, _db = _svc()
    t0 = _now() - timedelta(seconds=603)

    row = _run(svc.start_stage(MagicMock(id=1), "transcribing", started_at=t0))

    assert row.started_at == t0
    # 类 20.220: 若实现里写回 _now(), 这里会差 603 秒
    assert abs((_now() - row.started_at).total_seconds() - 603) < 2


def test_start_stage_defaults_to_now_when_omitted():
    """不传时保持原行为 (向后兼容, reprocessing 调用方不受影响)。"""
    svc, _db = _svc()
    row = _run(svc.start_stage(MagicMock(id=1), "polish"))
    assert abs((_now() - row.started_at).total_seconds()) < 5


# ==========================================================================
# finish_stage: latency_ms = finished_at - started_at
# ==========================================================================

def test_finish_stage_latency_is_real_stage_duration():
    svc, _db = _svc()
    t0 = _now() - timedelta(seconds=60)
    row = _run(svc.start_stage(MagicMock(id=1), "downloading_audio", started_at=t0))

    _run(svc.finish_stage(row, status="success"))

    assert row.latency_ms == pytest.approx(60_000, abs=2_000)
    assert row.latency_ms > 1_000  # 不再是"落库耗时"那个量级


def test_finish_stage_never_negative():
    """started_at 晚于 finished_at (时钟回拨/上游传错) 时钳到 0, 不写负数。"""
    svc, _db = _svc()
    row = _run(svc.start_stage(MagicMock(id=1), "x", started_at=_now() + timedelta(hours=1)))
    _run(svc.finish_stage(row, status="success"))
    assert row.latency_ms == 0


# ==========================================================================
# _persist_stage: 阶段开工时刻必须透传下去 (本次修复的核心)
# ==========================================================================

def test_persist_stage_threads_started_at_to_service():
    """调用方掐的表必须一路传到 start_stage —— 这是修复的判据。"""
    t0 = _now() - timedelta(seconds=117)
    proc_svc = MagicMock()
    proc_svc.db = MagicMock()
    proc_svc.db.commit = AsyncMock()
    proc_svc.start_stage = AsyncMock(side_effect=lambda run, stage, **kw: MagicMock(kw))
    proc_svc.finish_stage = AsyncMock()

    _run(_persist_stage(proc_svc, MagicMock(), "identifying_speakers", "success", started_at=t0))

    assert proc_svc.start_stage.await_args.kwargs.get("started_at") == t0


def test_persist_stage_without_started_at_keeps_legacy_behaviour():
    """不传 started_at 时不得硬造时间戳 (service 内部 fallback 到 _now())。"""
    proc_svc = MagicMock()
    proc_svc.db = MagicMock()
    proc_svc.db.commit = AsyncMock()
    proc_svc.start_stage = AsyncMock(side_effect=lambda run, stage, **kw: MagicMock(kw))
    proc_svc.finish_stage = AsyncMock()

    _run(_persist_stage(proc_svc, MagicMock(), "ai_polish", "skipped"))

    assert proc_svc.start_stage.await_args.kwargs.get("started_at") is None


def test_persist_stage_is_best_effort():
    """DB 炸了不许把主流程带崩 (原有契约, 防止有人顺手加 raise)。"""
    proc_svc = MagicMock()
    proc_svc.db = MagicMock()
    proc_svc.db.commit = AsyncMock(side_effect=RuntimeError("db down"))
    proc_svc.start_stage = AsyncMock(side_effect=lambda run, stage, **kw: MagicMock(kw))
    proc_svc.finish_stage = AsyncMock()

    _run(_persist_stage(proc_svc, MagicMock(), "storing_results", "success"))  # 不抛即通过


# ==========================================================================
# 时钟一致性 (类 20.221: DB 存 UTC)
# ==========================================================================

def test_stage_now_is_naive_utc():
    """_now() 必须是 naive UTC —— 带 tzinfo 会与 DB 列 (timestamp w/o tz) 对不上。"""
    assert _now().tzinfo is None
    assert isinstance(_now(), datetime)


def _run(coro):
    """极简 async runner (避免引 pytest-asyncio 依赖)。"""
    import asyncio

    return asyncio.run(coro)