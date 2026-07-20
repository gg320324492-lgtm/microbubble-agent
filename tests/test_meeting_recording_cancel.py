"""tests/test_meeting_recording_cancel.py

2026-07-16 + 2026-07-20 P0 录音 cancel-recording 端点单测

覆盖 (app/api/v1/meeting_recording.py line 327-378 cancel_recording):
- 同用户 (created_by == current_user.id) → cancelled:True, status='error'
- 跨用户 (created_by != current_user.id) → 403
- meeting 不存在 → 404
- 幂等: 第二次调用 (status 已是 'error') → cancelled:False 不抛错
- 幂等: status='processing' / 'stopped' 等非 recording 状态 → cancelled:False
- P0 字段清空: audio_url / last_chunk_index / total_chunks / upload_status='cancelled'
- error_reason 写入 (用于事后排查)

铁律: SKIP_DB_SETUP=1 mock, 不依赖数据库, 5s 内跑完
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# TestCancelRecording
# ============================================================================


class TestCancelRecording:
    """cancel-recording 端点 (line 327-378) — 2026-07-16 加 + 2026-07-20 P0 增强."""

    def _make_db_with_meeting(self, meeting_obj):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=meeting_obj)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock(return_value=None)
        db.refresh = AsyncMock(return_value=None)
        return db

    # -- 同用户 → cancelled:True -----------------------------------------

    async def test_same_user_cancel_recording_succeeds(self):
        """recording → error, audio_url / last_chunk_index / total_chunks 清空."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "recording"
        meeting.audio_url = "recordings/200/chunks/chunk_00003.webm"
        meeting.last_chunk_index = 3
        meeting.total_chunks = 4
        meeting.upload_status = "uploading"
        meeting.error_reason = None
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        result = await mr_module.cancel_recording(
            meeting_id=200,
            current_user=current_user,
            db=db,
        )

        assert result["cancelled"] is True
        assert result["id"] == 200
        assert result["status"] == "error"
        assert result.get("audio_url_cleared") is True
        # 关键字段清空 (P0 修复: 防 MeetingDetailView AudioPlayer 永久 404)
        assert meeting.audio_url is None
        assert meeting.last_chunk_index == -1
        assert meeting.total_chunks is None
        assert meeting.upload_status == "cancelled"
        assert meeting.status == "error"
        # error_reason 写入
        assert "录音启动失败已取消" in meeting.error_reason
        db.commit.assert_awaited_once()

    # -- 跨用户 → 403 -----------------------------------------------------

    async def test_cross_user_cancel_recording_returns_403(self):
        """meeting.created_by=7, current_user.id=99 → 403."""
        from app.api.v1 import meeting_recording as mr_module
        from fastapi import HTTPException

        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "recording"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 99

        with pytest.raises(HTTPException) as exc:
            await mr_module.cancel_recording(
                meeting_id=200,
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 403
        assert "仅创建者" in str(exc.value.detail)

    # -- meeting 不存在 → 404 -------------------------------------------

    async def test_nonexistent_meeting_cancel_returns_404(self):
        from app.api.v1 import meeting_recording as mr_module
        from fastapi import HTTPException

        db = self._make_db_with_meeting(None)
        current_user = MagicMock()
        current_user.id = 7

        with pytest.raises(HTTPException) as exc:
            await mr_module.cancel_recording(
                meeting_id=999,
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 404

    # -- 幂等: 第二次 cancel (status=error) → cancelled:False --------------

    async def test_second_cancel_when_already_error_returns_false(self):
        """第一次 cancel 后 status='error', 第二次 cancel 走幂等路径 (cancelled:False, 不抛错)."""
        from app.api.v1 import meeting_recording as mr_module

        # 模拟已被取消的会议
        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "error"  # 已是 error 状态
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        result = await mr_module.cancel_recording(
            meeting_id=200,
            current_user=current_user,
            db=db,
        )

        assert result["cancelled"] is False
        assert result["status"] == "error"
        # 幂等路径: 不应 commit (没有状态变更)
        db.commit.assert_not_awaited()

    async def test_cancel_when_processing_returns_false(self):
        """status='processing' (已 stop-recording 触发了后处理) → 幂等返 cancelled:False."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "processing"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        result = await mr_module.cancel_recording(
            meeting_id=200,
            current_user=current_user,
            db=db,
        )

        assert result["cancelled"] is False
        assert result["status"] == "processing"
        db.commit.assert_not_awaited()

    # -- audio_url 清空 (P0 防 MinIO 404 孤儿) ----------------------------

    async def test_cancel_clears_audio_url_field(self):
        """P0 验证: audio_url 必须置 None (即使录音从未 chunk, 也防御性清空)."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "recording"
        meeting.audio_url = None  # 录音从未收到任何 chunk, audio_url 仍是 None
        meeting.last_chunk_index = -1
        meeting.total_chunks = None
        meeting.upload_status = "pending"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        result = await mr_module.cancel_recording(
            meeting_id=200,
            current_user=current_user,
            db=db,
        )

        # 关键: 即使 audio_url 本来就是 None, 也要把 upload_status 改成 cancelled
        # 让前端不再走"该字段存在但 MinIO 404"的孤儿状态
        assert meeting.audio_url is None
        assert meeting.upload_status == "cancelled"
        assert meeting.last_chunk_index == -1
        assert meeting.total_chunks is None
        assert result["cancelled"] is True

    async def test_cancel_clears_last_chunk_index_and_total_chunks(self):
        """P0: last_chunk_index / total_chunks 也必须清空, 防孤儿 chunk 数据."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "recording"
        meeting.audio_url = "recordings/200/chunks/chunk_00000.webm"
        meeting.last_chunk_index = 5  # 已收到 6 个 chunk (0..5)
        meeting.total_chunks = 6
        meeting.upload_status = "uploading"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        await mr_module.cancel_recording(
            meeting_id=200,
            current_user=current_user,
            db=db,
        )

        assert meeting.last_chunk_index == -1
        assert meeting.total_chunks is None
        assert meeting.upload_status == "cancelled"

    # -- status 字段终态 -------------------------------------------------

    async def test_cancel_transitions_recording_to_error(self):
        """状态机: recording → error, 不应回到 recording/processing/stopped."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 200
        meeting.created_by = 7
        meeting.status = "recording"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        result = await mr_module.cancel_recording(
            meeting_id=200,
            current_user=current_user,
            db=db,
        )

        # 终态 = error (Celery 60min 后自动清理)
        assert meeting.status == "error"
        assert result["status"] == "error"
