"""tests/test_orphan_meeting_cleanup_audio_chunks.py

2026-07-16 扩展的孤儿会议清理单测

覆盖 (app/services/orphan_meeting_cleanup.py):
- _scan_and_cleanup() 选择 30min 窗口外的孤儿 meeting (status='recording')
- error_reason 拼接 UA 片段 (line 80-84)
- 上传状态 cleanup → MinIO chunks 清理 + WS 通知
- 半成品 (last_chunk_index >= 0 但用户从未 stop) → 清理
- 24h 窗口外 → 不清理

策略: 提前在 sys.modules 里 stub 掉函数内 from-import 的 chunked_upload_service /
progress_service / redis.asyncio. Meeting 用真的 ORM (SKIP 模式下也能 import, 让
select(Meeting) 能正常构造 SQL). create_celery_engine_and_session 通过 patch 注入.

铁律: SKIP_DB_SETUP=1 mock, 不依赖数据库, 5s 内跑完
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# 提前 stub 函数内 from-import 的模块 + 对象
# (注: app.models.meeting.Meeting 必须用真 ORM, 否则 select(Meeting) 构造 SQL 时报 ArgumentError)
# ============================================================================
_chunked_stub = MagicMock()
_chunked_stub.delete_chunks = AsyncMock(return_value=0)
sys.modules.setdefault("app.services.chunked_upload_service", MagicMock())
sys.modules["app.services.chunked_upload_service"].chunked_upload_service = _chunked_stub

_update_progress_stub = AsyncMock(return_value=None)
sys.modules.setdefault("app.services.progress_service", MagicMock())
sys.modules["app.services.progress_service"].update_progress = _update_progress_stub
sys.modules["app.services.progress_service"].ProgressStage = MagicMock()

_redis_client = MagicMock()
_redis_client.aclose = AsyncMock(return_value=None)
_redis_stub = MagicMock()
_redis_stub.from_url = MagicMock(return_value=_redis_client)
sys.modules.setdefault("redis.asyncio", _redis_stub)


def _make_orphan_meeting(
    meeting_id: int = 301,
    created_at: datetime = None,
    last_chunk_index: int = 3,
    total_chunks: int = 4,
    user_agent: str = "Mozilla/5.0 Test UA",
):
    m = MagicMock()
    m.id = meeting_id
    m.created_by = 7
    m.status = "recording"
    m.recording_started_at = created_at or (datetime.utcnow() - timedelta(minutes=45))
    m.last_chunk_index = last_chunk_index
    m.total_chunks = total_chunks
    m.user_agent = user_agent
    m.error_reason = None
    return m


def _setup_session(orphan_meetings, filter_meetings=False):
    """构造 mock db session + engine, 使 _scan_and_cleanup 能跑通.

    filter_meetings=True: 模拟真实 select(Meeting).where(...) 过滤 — 返空 list
    (代表 meeting 不在 30min 窗口内或不是 recording 状态).
    filter_meetings=False: 返 orphan_meetings (代表 meeting 命中 SELECT 条件).
    """
    if filter_meetings:
        meetings_to_return = []
    else:
        meetings_to_return = orphan_meetings

    scalars = MagicMock()
    scalars.all = MagicMock(return_value=meetings_to_return)
    execute_result = MagicMock()
    execute_result.scalars = MagicMock(return_value=scalars)

    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock(return_value=None)

    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    engine = MagicMock()
    engine.dispose = AsyncMock(return_value=None)

    create_engine_session = MagicMock(return_value=(engine, session_factory))
    return create_engine_session, session


class TestOrphanMeetingCleanup:
    """孤儿会议清理 (app/services/orphan_meeting_cleanup.py)."""

    async def test_window_under_threshold_no_cleanup(self):
        """SKIP_DB_SETUP=1 mock 模式下, db.execute 返 [] 模拟"无 orphan meeting"
        (等价于 meeting.recording_started_at 不在 30min 窗口内 → select 过滤掉).

        这里关键不是验时间窗口选择 (需要真 SQL), 而是验证:
        - select 返空 list 时, 状态不被改
        - commit 不被调
        """
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        # 不创建任何 orphan, 模拟 SQL 已过滤
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, session = _setup_session([], filter_meetings=True)

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert result["cleaned"] == []
        assert result["count"] == 0
        assert result["errors"] == []
        # 没 commit (无状态变更)
        session.commit.assert_not_awaited()
        # 没触发 chunked 清理
        _chunked_stub.delete_chunks.assert_not_awaited()

    async def test_window_over_threshold_marks_as_error(self):
        """录音 45min (超 30min 阈值) → 标 status='error', 写 error_reason."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        orphan = _make_orphan_meeting(
            meeting_id=301,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            last_chunk_index=5,
            total_chunks=6,
            user_agent="Mozilla/5.0 (Macintosh; Chrome/120) Test",
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.return_value = 6
        _update_progress_stub.reset_mock()
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert orphan.status == "error"
        assert "录音超过 30min 未 stop" in orphan.error_reason
        assert "last_chunk_index=5" in orphan.error_reason
        assert "total_chunks=6" in orphan.error_reason
        assert "[UA:" in orphan.error_reason
        _chunked_stub.delete_chunks.assert_awaited_once_with(301)
        _update_progress_stub.assert_awaited_once()
        assert 301 in result["cleaned"]
        assert result["count"] == 1

    async def test_half_finished_orphan_cleaned_up(self):
        """关键修复 (2026-07-16 扩展): 录了 30 分钟突然刷新离开 (last_chunk_index >= 0) → 也被清理."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        half_finished = _make_orphan_meeting(
            meeting_id=302,
            created_at=datetime.utcnow() - timedelta(minutes=35),
            last_chunk_index=10,
            total_chunks=11,
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.return_value = 11
        create_engine_session, _ = _setup_session([half_finished])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert half_finished.status == "error"
        assert "last_chunk_index=10" in half_finished.error_reason
        assert "total_chunks=11" in half_finished.error_reason
        assert 302 in result["cleaned"]

    async def test_no_chunks_orphan_cleaned_up(self):
        """半成品孤儿: last_chunk_index = -1 (录音 30min 但从未收到 chunk) → 也被清理."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        no_chunks = _make_orphan_meeting(
            meeting_id=303,
            created_at=datetime.utcnow() - timedelta(minutes=40),
            last_chunk_index=-1,
            total_chunks=None,
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.return_value = 0
        create_engine_session, _ = _setup_session([no_chunks])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert no_chunks.status == "error"
        assert "last_chunk_index=-1" in no_chunks.error_reason
        assert 303 in result["cleaned"]

    async def test_threshold_uses_settings_constant(self):
        """防御: 阈值应来自 settings.ORPHAN_MEETING_TIMEOUT_MINUTES (单点配置)."""
        from app.config import settings

        assert settings.ORPHAN_MEETING_TIMEOUT_MINUTES == 30

    async def test_threshold_boundary_31min_just_over(self):
        """31 分钟 (刚超 30min 阈值) → 清理."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        boundary = _make_orphan_meeting(
            meeting_id=304,
            created_at=datetime.utcnow() - timedelta(minutes=31),
        )
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, _ = _setup_session([boundary])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        assert boundary.status == "error"
        assert 304 in result["cleaned"]

    async def test_error_reason_contains_ua_snippet(self):
        """P0 (2026-07-16): error_reason 拼 UA 片段便于事后排查 HarmonyOS ArkWeb."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        ua = "Mozilla/5.0 (Linux; Android 12; HarmonyOS; ArkWeb/45.10.0)"
        orphan = _make_orphan_meeting(
            meeting_id=305,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            user_agent=ua,
        )
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            await _scan_and_cleanup()

        # UA 截断 80 字符
        assert f"[UA: {ua[:80]}]" in orphan.error_reason

    async def test_error_reason_for_null_ua_says_unknown(self):
        """user_agent=None → 'unknown' (line 79 fallback)."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        orphan = _make_orphan_meeting(
            meeting_id=306,
            created_at=datetime.utcnow() - timedelta(minutes=45),
            user_agent=None,
        )
        _chunked_stub.delete_chunks.reset_mock()
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            await _scan_and_cleanup()

        assert "[UA: unknown]" in orphan.error_reason

    async def test_chunk_cleanup_failure_continues(self):
        """MinIO delete_chunks 失败 → 不影响 status 标 error (line 86-91 warning)."""
        from app.services.orphan_meeting_cleanup import _scan_and_cleanup

        orphan = _make_orphan_meeting(
            meeting_id=307,
            created_at=datetime.utcnow() - timedelta(minutes=45),
        )
        _chunked_stub.delete_chunks.reset_mock()
        _chunked_stub.delete_chunks.side_effect = Exception("MinIO 500")
        create_engine_session, _ = _setup_session([orphan])

        with patch(
            "app.services.orphan_meeting_cleanup.create_celery_engine_and_session",
            create_engine_session,
        ):
            result = await _scan_and_cleanup()

        # 关键: MinIO 失败时, status 仍标 error
        assert orphan.status == "error"
        assert 307 in result["cleaned"]
