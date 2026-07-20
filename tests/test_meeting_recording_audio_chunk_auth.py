"""tests/test_meeting_recording_audio_chunk_auth.py

2026-07-16 录音全链路加固: audio-chunk 越权守卫单测

覆盖 (app/api/v1/meeting_recording.py line 100-147 upload_audio_chunk):
- 同用户 (created_by == current_user.id) → 200
- 跨用户 (created_by != current_user.id) → 403
- meeting 不存在 → 404
- meeting.status != "recording" → 400
- chunk 文件为空 → 400
- chunk 落库字段: last_chunk_index 原子取最大 / total_chunks 累加 / upload_status="uploading"

铁律: SKIP_DB_SETUP=1 mock, 不依赖数据库, 5s 内跑完
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# TestAudioChunkAuthGuard
# ============================================================================


class TestAudioChunkAuthGuard:
    """audio-chunk 端点越权守卫 (line 122-124)."""

    def _make_db_with_meeting(self, meeting_obj):
        """构造 mock DB, db.execute 回 scalar_one_or_none 返给定 meeting."""
        result_mock = MagicMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=meeting_obj)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock(return_value=None)
        return db

    def _make_upload_file(self, data: bytes = b"x" * 100, content_type: str = "audio/webm"):
        f = MagicMock()
        f.read = AsyncMock(return_value=data)
        f.content_type = content_type
        return f

    # -- 跨用户 → 403 ----------------------------------------------------

    async def test_cross_user_chunk_upload_returns_403(self):
        """meeting.created_by=7, current_user.id=99 → 403 越权."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "recording"
        db = self._make_db_with_meeting(meeting)

        current_user = MagicMock()
        current_user.id = 99

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=0,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 403
        assert "仅创建者" in str(exc.value.detail)

    # -- 同用户 → 200 -----------------------------------------------------

    async def test_same_user_chunk_upload_returns_200(self):
        """meeting.created_by=7, current_user.id=7 → 200, 落库字段正确."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "recording"
        meeting.last_chunk_index = -1
        meeting.total_chunks = 0
        meeting.upload_status = "pending"
        db = self._make_db_with_meeting(meeting)

        current_user = MagicMock()
        current_user.id = 7

        # mock chunked_upload_service.save_chunk
        with patch.object(mr_module, "chunked_upload_service") as mock_svc:
            mock_svc.save_chunk = AsyncMock(return_value=None)
            result = await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=0,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )

        assert result["chunk_index"] == 0
        assert result["last_chunk_index"] == 0
        assert result["total_chunks"] == 1
        # 原子累加字段
        assert meeting.last_chunk_index == 0
        assert meeting.total_chunks == 1
        assert meeting.upload_status == "uploading"
        # commit 应被调用一次
        db.commit.assert_awaited_once()

    # -- meeting 不存在 → 404 --------------------------------------------

    async def test_nonexistent_meeting_returns_404(self):
        """db.scalar_one_or_none() = None → 404."""
        from app.api.v1 import meeting_recording as mr_module
        from fastapi import HTTPException

        db = self._make_db_with_meeting(None)
        current_user = MagicMock()
        current_user.id = 7

        with pytest.raises(HTTPException) as exc:
            await mr_module.upload_audio_chunk(
                meeting_id=999,
                chunk_index=0,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 404
        assert "会议不存在" in str(exc.value.detail)

    # -- 状态错 (status=processing) → 400 --------------------------------

    async def test_non_recording_status_returns_400(self):
        """meeting.status='processing' (已 merge) 阻止再上传 chunk."""
        from app.api.v1 import meeting_recording as mr_module
        from fastapi import HTTPException

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "processing"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        with pytest.raises(HTTPException) as exc:
            await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=0,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 400
        assert "录音状态" in str(exc.value.detail)

    async def test_cancelled_status_returns_400(self):
        """meeting.status='error' (cancel-recording 后) 阻止再上传 chunk."""
        from app.api.v1 import meeting_recording as mr_module
        from fastapi import HTTPException

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "error"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        with pytest.raises(HTTPException) as exc:
            await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=0,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 400

    # -- chunk 空 → 400 ----------------------------------------------------

    async def test_empty_chunk_returns_400(self):
        """file.read() = b'' → 400 (前端停止后续 chunk)."""
        from app.api.v1 import meeting_recording as mr_module
        from fastapi import HTTPException

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "recording"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        with pytest.raises(HTTPException) as exc:
            await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=0,
                file=self._make_upload_file(data=b""),
                current_user=current_user,
                db=db,
            )
        assert exc.value.status_code == 400
        assert "chunk 为空" in str(exc.value.detail)

    # -- 乱序到达保留最大值 (line 136) ------------------------------------

    async def test_out_of_order_chunk_preserves_max_last_chunk_index(self):
        """chunk_index=5 先到, chunk_index=2 后到, last_chunk_index 应保持 5."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "recording"
        meeting.last_chunk_index = 5
        meeting.total_chunks = 6
        meeting.upload_status = "uploading"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        with patch.object(mr_module, "chunked_upload_service") as mock_svc:
            mock_svc.save_chunk = AsyncMock(return_value=None)
            # 后到的 chunk_index=2, 不应覆盖
            result = await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=2,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )

        # last_chunk_index 保留 5
        assert meeting.last_chunk_index == 5
        assert result["last_chunk_index"] == 5
        # total_chunks 仍累加 (后到达也计数)
        assert meeting.total_chunks == 7

    async def test_chunk_with_last_index_none_takes_new_value(self):
        """meeting.last_chunk_index = None (旧数据) → 新 chunk_index 直接写入."""
        from app.api.v1 import meeting_recording as mr_module

        meeting = MagicMock()
        meeting.id = 100
        meeting.created_by = 7
        meeting.status = "recording"
        meeting.last_chunk_index = None
        meeting.total_chunks = None
        meeting.upload_status = "pending"
        db = self._make_db_with_meeting(meeting)
        current_user = MagicMock()
        current_user.id = 7

        with patch.object(mr_module, "chunked_upload_service") as mock_svc:
            mock_svc.save_chunk = AsyncMock(return_value=None)
            result = await mr_module.upload_audio_chunk(
                meeting_id=100,
                chunk_index=3,
                file=self._make_upload_file(),
                current_user=current_user,
                db=db,
            )

        assert meeting.last_chunk_index == 3
        assert meeting.total_chunks == 1  # None or 0 → 1


# 阻止 pytest 跳过 async 测试
import pytest
