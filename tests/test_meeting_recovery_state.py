"""会议录音恢复状态机行为测试（2026-11-16 深度加固）。

禁止源码字符串断言：全部走 evaluate_recovery() 与 API 端点真实行为。
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _meeting(**overrides):
    values = dict(
        status="error",
        audio_url=None,
        last_chunk_index=-1,
        media_duration_seconds=None,
        audio_duration=0,
        upload_status="completed",
        total_chunks=1,
        created_by=58,
        id=278,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _db(meeting):
    result = MagicMock()
    result.scalar_one_or_none.return_value = meeting
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    return db


def _user(uid=58):
    return SimpleNamespace(id=uid)


class TestEvaluateRecoveryMatrix:
    def test_recording(self):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(_meeting(status="recording", last_chunk_index=2))
        assert r["state"] == "recording"
        assert r["recommended_action"] == "resume"
        assert r["can_upload"] and r["can_merge"] and not r["can_reprocess"]

    @pytest.mark.parametrize("status", ["processing", "completed", "scheduled", None])
    def test_non_error_non_recording_closed(self, status):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(_meeting(status=status, audio_url="x.m4a", last_chunk_index=3))
        assert r["recommended_action"] == "none"
        assert not r["can_upload"] and not r["can_merge"] and not r["can_reprocess"]

    def test_error_with_long_audio_reprocess(self):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(
            _meeting(audio_url="recordings/255/merged.m4a", media_duration_seconds=3600)
        )
        assert r["recommended_action"] == "reprocess"
        assert r["can_reprocess"] and not r["can_upload"] and not r["can_merge"]

    def test_error_with_short_audio_reupload(self):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(
            _meeting(audio_url="recordings/278/merged.m4a", media_duration_seconds=4)
        )
        assert r["recommended_action"] == "reupload"
        assert not r["can_reprocess"]
        assert r["can_upload"] and r["can_merge"]

    def test_error_with_audio_duration_none_allows_reprocess(self):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(_meeting(audio_url="recordings/old/merged.m4a"))
        assert r["recommended_action"] == "reprocess"

    def test_error_chunks_only_never_reprocess(self):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(_meeting(last_chunk_index=1))
        assert r["recommended_action"] in ("reupload", "merge_first")
        assert r["can_upload"] and not r["can_reprocess"]

    def test_error_no_audio_no_chunks_reupload(self):
        from app.services.meeting_recovery import evaluate_recovery

        r = evaluate_recovery(_meeting(last_chunk_index=-1))
        assert r["recommended_action"] == "reupload"
        assert r["can_upload"] and not r["can_merge"] and not r["can_reprocess"]


class TestUploadStatusRecovery:
    async def test_returns_recovery_and_duration(self):
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(status="error", audio_url="x.m4a", media_duration_seconds=4)
        res = await mr.get_upload_status(meeting_id=278, current_user=_user(), db=_db(meeting))
        assert res["media_duration_seconds"] == 4
        assert res["recovery"]["recommended_action"] == "reupload"
        assert res["recovery"]["can_reprocess"] is False

    async def test_cross_user_forbidden(self):
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(created_by=58)
        with pytest.raises(HTTPException) as exc:
            await mr.get_upload_status(meeting_id=278, current_user=_user(99), db=_db(meeting))
        assert exc.value.status_code == 403


class TestUploadAudioHardGuard:
    async def test_short_audio_still_cannot_be_overwritten(self):
        """error+短 audio_url：纯函数建议 reupload，但整段覆盖 API 必须拒绝。"""
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(audio_url="recordings/278/merged.m4a", media_duration_seconds=4)
        with patch.object(mr, "file_service") as svc:
            with pytest.raises(HTTPException) as exc:
                await mr.upload_audio(
                    meeting_id=278,
                    file=MagicMock(read=AsyncMock(return_value=b"x")),
                    current_user=_user(),
                    db=_db(meeting),
                )
        assert exc.value.status_code == 400
        svc.upload_file.assert_not_called()


class TestMergeStatusGuard:
    @pytest.mark.parametrize("status", ["processing", "completed"])
    async def test_pipeline_statuses_rejected(self, status):
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(status=status, last_chunk_index=3)
        db = _db(meeting)
        with patch.object(mr, "chunked_upload_service") as svc:
            with pytest.raises(HTTPException) as exc:
                await mr.merge_chunks_endpoint(meeting_id=278, current_user=_user(), db=db)
        assert exc.value.status_code == 400
        svc.merge_chunks.assert_not_called()

    @pytest.mark.parametrize("status", ["recording", "error"])
    async def test_recording_and_error_pass_guard(self, status):
        """只验证守卫放行到后续 chunk 校验，不做真实 merge（无 MinIO）。"""
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(status=status, last_chunk_index=-1)
        with pytest.raises(HTTPException) as exc:
            await mr.merge_chunks_endpoint(meeting_id=278, current_user=_user(), db=_db(meeting))
        assert exc.value.status_code == 400
        assert "无可合并的 chunk" in str(exc.value.detail)


class TestReprocessHardGuards:
    async def test_short_audio_rejected(self):
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(audio_url="recordings/278/merged.m4a", media_duration_seconds=4)
        with pytest.raises(HTTPException) as exc:
            await mr.reprocess_meeting(meeting_id=278, current_user=_user(), db=_db(meeting))
        assert exc.value.status_code == 400
        assert "静音" in str(exc.value.detail)

    async def test_concurrent_claim_conflict(self):
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(audio_url="recordings/278/merged.m4a", media_duration_seconds=3600)
        db = _db(meeting)
        # 第一次 select 返回会议，第二次条件 UPDATE 报告 0 行（被并发请求抢先）
        result = MagicMock()
        result.scalar_one_or_none.return_value = meeting
        claim = MagicMock()
        claim.rowcount = 0
        db.execute = AsyncMock(side_effect=[result, claim])
        with pytest.raises(HTTPException) as exc:
            await mr.reprocess_meeting(meeting_id=278, current_user=_user(), db=db)
        assert exc.value.status_code == 409
        db.commit.assert_not_awaited()


class TestStopRecordingAutoMergeDuration:
    async def test_automerge_probe_failure_fails_loud(self):
        """自动 merge 后 ffprobe 失败 ⇒ 500 且不触发后处理。"""
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(
            status="recording",
            last_chunk_index=1,
            upload_status="uploading",
            audio_url=None,
            recording_started_at=None,
        )
        db = _db(meeting)
        fake_task = MagicMock()
        fake_task.delay = MagicMock()

        with patch.object(mr.chunked_upload_service, "merge_chunks", new=AsyncMock(return_value="merged.m4a")), \
             patch.object(mr.file_service, "download_file", new=AsyncMock(return_value=b"bytes")), \
             patch.object(mr, "ffprobe_duration_async", new=AsyncMock(return_value=None)), \
             patch.dict(sys.modules, {"app.services.post_meeting_tasks": MagicMock(post_meeting_process=fake_task)}):
            with pytest.raises(HTTPException) as exc:
                await mr.stop_recording(meeting_id=278, current_user=_user(), db=db)
        assert exc.value.status_code == 500
        fake_task.delay.assert_not_called()

    async def test_automerge_success_writes_media_duration(self):
        """自动 merge + ffprobe 成功 ⇒ media_duration_seconds 落库且触发后处理。"""
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(
            status="recording",
            last_chunk_index=1,
            upload_status="uploading",
            audio_url=None,
            recording_started_at=None,
            error_reason="old error",
            audio_duration=0,
        )
        db = _db(meeting)
        fake_task = MagicMock()
        fake_task.delay = MagicMock()
        clear_heartbeat = AsyncMock()
        fake_heartbeat_module = MagicMock(clear_recording_heartbeat=clear_heartbeat)

        with patch.object(mr.chunked_upload_service, "merge_chunks", new=AsyncMock(return_value="merged.m4a")), \
             patch.object(mr.file_service, "download_file", new=AsyncMock(return_value=b"bytes")), \
             patch.object(mr, "ffprobe_duration_async", new=AsyncMock(return_value=3723.5)), \
             patch.dict(sys.modules, {
                 "app.services.post_meeting_tasks": MagicMock(post_meeting_process=fake_task),
                 "app.services.recording_heartbeat": fake_heartbeat_module,
             }):
            res = await mr.stop_recording(meeting_id=278, current_user=_user(), db=db)

        assert res["status"] == "processing"
        assert meeting.audio_url == "merged.m4a"
        assert meeting.media_duration_seconds in (3723, 3723.5)
        fake_task.delay.assert_called_once_with(278)
        clear_heartbeat.assert_awaited_once_with(278)


class TestResetHeartbeatCleanup:
    async def test_reset_clears_heartbeat_and_metadata(self):
        from app.api.v1 import meeting_recording as mr

        meeting = _meeting(status="error", audio_url="old.m4a", media_duration_seconds=4)
        meeting.error_reason = "orphan cleanup"
        db = _db(meeting)
        clear_heartbeat = AsyncMock()

        with patch.object(mr, "chunked_upload_service") as svc, patch.dict(
            sys.modules,
            {"app.services.recording_heartbeat": MagicMock(clear_recording_heartbeat=clear_heartbeat)},
        ):
            svc.delete_chunks = AsyncMock(return_value=1)
            svc.delete_merged = AsyncMock(return_value=0)
            res = await mr.reset_chunks_endpoint(meeting_id=278, current_user=_user(), db=db)

        assert res["reset"] is True
        clear_heartbeat.assert_awaited_once_with(278)
        assert meeting.media_duration_seconds is None
        assert meeting.error_reason is None
