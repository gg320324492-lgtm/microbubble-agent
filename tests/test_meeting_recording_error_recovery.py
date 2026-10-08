"""tests/test_meeting_recording_error_recovery.py

2026-10-08 主指挥复验修正: 会议 255 孤儿误杀后的补录链路守卫单测。

背景 (Phase 3 阻塞点):
    orphan_meeting_cleanup 把会议 255 误判 status='error' 后, 用户要用手机自带
    录音器补录 m4a。补录链路是:
        PUT  /api/v1/meetings/{id}/audio-chunk        (分片上传)
        POST /api/v1/meetings/{id}/chunks/reset       (复位服务端已有分片)
        POST /api/v1/meetings/{id}/merge-chunks?mode=raw (字节拼接)
        POST /api/v1/meetings/{id}/reprocess          (error → processing + Celery)
    而 `useMeetingAudioUpload.js:109` 的 uploadBlobInSlices() **第一步就是调
    chunks/reset** —— 若 reset 的状态守卫仍硬性要求 'recording', 这条链第一步就
    400, Phase 3 直接卡死。

覆盖 (主指挥复验发现的缺陷 3 + 缺陷 4):
- audio-chunk   : status='error' → 放行 (P0-4 扩展)
- audio-chunk   : status='processing'/'completed'/'scheduled' → 仍 400 (原守卫初衷)
- chunks/reset  : status='error' → 放行 (缺陷 3 修正)
- chunks/reset  : status='recording' → 放行 (老行为不变)
- chunks/reset  : status='processing'/'completed' → 仍 400 (会毁掉已有成果, 必须挡)
- reprocess     : status='error' + 有音频 → 200 + status 改 processing + 触发 Celery
- reprocess     : status='error' + 无音频 → 400 (先补传再 reprocess)
- reprocess     : status != 'error' → 400 (幂等, 不重复触发流水线)
- reprocess     : 越权 (created_by != current_user) → 403
- reprocess     : audit action 必须是 VALID_ACTIONS 白名单里的 'meeting_reprocess'
                  (缺陷 4: 'meeting_reprocess_user_initiated' 会 fallback 成 'read')

铁律: SKIP_DB_SETUP=1 mock, 不依赖数据库, 5s 内跑完
"""
import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _make_db_with_meeting(meeting_obj):
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=meeting_obj)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result_mock)
    db.commit = AsyncMock(return_value=None)
    return db


def _make_meeting(**overrides):
    m = MagicMock()
    m.id = 255
    m.created_by = 58
    m.status = "error"
    m.last_chunk_index = -1
    m.total_chunks = 0
    m.upload_status = "pending"
    m.audio_url = None
    m.error_reason = None
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


def _make_upload_file(data: bytes = b"x" * 1024):
    f = MagicMock()
    f.read = AsyncMock(return_value=data)
    f.content_type = "audio/mp4"
    return f


def _user(uid=58):
    u = MagicMock()
    u.id = uid
    return u


# ============================================================================
# audio-chunk 状态守卫 (P0-4 扩展)
# ============================================================================


class TestAudioChunkStatusGuard:
    @pytest.mark.parametrize("status", ["recording", "error"])
    async def test_recording_and_error_both_allowed(self, status):
        """P0-4: audio-chunk 接受 recording + error (补录链路第一步)"""
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status=status, last_chunk_index=-1, total_chunks=0)
        db = _make_db_with_meeting(meeting)

        with patch.object(mr, "chunked_upload_service") as mock_svc:
            mock_svc.save_chunk = AsyncMock(return_value=None)
            res = await mr.upload_audio_chunk(
                meeting_id=255,
                chunk_index=0,
                file=_make_upload_file(),
                current_user=_user(58),
                db=db,
            )
        assert res["chunk_index"] == 0
        mock_svc.save_chunk.assert_awaited_once()

    @pytest.mark.parametrize("status", ["processing", "completed", "scheduled"])
    async def test_other_statuses_still_rejected(self, status):
        """processing/completed 代表流水线在跑或已有成果, 补传会污染"""
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status=status)
        db = _make_db_with_meeting(meeting)

        with patch.object(mr, "chunked_upload_service") as mock_svc:
            mock_svc.save_chunk = AsyncMock(return_value=None)
            with pytest.raises(HTTPException) as exc:
                await mr.upload_audio_chunk(
                    meeting_id=255,
                    chunk_index=0,
                    file=_make_upload_file(),
                    current_user=_user(58),
                    db=db,
                )
        assert exc.value.status_code == 400

    async def test_cross_user_still_403(self):
        """越权守卫不受本次放宽影响"""
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="error", created_by=58)
        db = _make_db_with_meeting(meeting)

        with pytest.raises(HTTPException) as exc:
            await mr.upload_audio_chunk(
                meeting_id=255,
                chunk_index=0,
                file=_make_upload_file(),
                current_user=_user(99),
                db=db,
            )
        assert exc.value.status_code == 403


# ============================================================================
# chunks/reset 状态守卫 (主指挥复验缺陷 3 —— Phase 3 直接卡死点)
# ============================================================================


class TestChunksResetStatusGuard:
    @pytest.mark.parametrize("status", ["recording", "error"])
    async def test_recording_and_error_both_allowed(self, status):
        """缺陷 3 修正: uploadBlobInSlices() 第一步调 reset, error 态必须放行"""
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status=status)
        db = _make_db_with_meeting(meeting)

        with patch.object(mr, "chunked_upload_service") as mock_svc:
            mock_svc.delete_chunks = AsyncMock(return_value=3)
            mock_svc.delete_merged = AsyncMock(return_value=0)
            res = await mr.reset_chunks_endpoint(
                meeting_id=255,
                current_user=_user(58),
                db=db,
            )
        assert res["reset"] is True
        assert res["deleted_chunks"] == 3
        mock_svc.delete_chunks.assert_awaited_once_with(255)
        # reset 后字段归零
        assert meeting.last_chunk_index == -1
        assert meeting.total_chunks == 0
        assert meeting.audio_url is None

    @pytest.mark.parametrize("status", ["processing", "completed", "scheduled"])
    async def test_pipeline_statuses_still_rejected(self, status):
        """processing/completed 挡住 —— reset 会毁掉已有成果 (原守卫初衷)"""
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status=status, audio_url="recordings/255/x.m4a")
        db = _make_db_with_meeting(meeting)

        with patch.object(mr, "chunked_upload_service") as mock_svc:
            mock_svc.delete_chunks = AsyncMock(return_value=3)
            with pytest.raises(HTTPException) as exc:
                await mr.reset_chunks_endpoint(
                    meeting_id=255,
                    current_user=_user(58),
                    db=db,
                )
        assert exc.value.status_code == 400
        # 关键: 拒绝时**不能**调 delete_chunks (不能有副作用)
        mock_svc.delete_chunks.assert_not_awaited()
        # 也不能清空 audio_url
        assert meeting.audio_url == "recordings/255/x.m4a"


# ============================================================================
# reprocess 端点 (P0-4 新增)
# ============================================================================


class TestReprocessEndpoint:
    async def test_error_with_audio_triggers_celery(self):
        """error + 有音频 → status 改 processing + post_meeting_process.delay"""
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(
            status="error", last_chunk_index=3, total_chunks=4, audio_url="recordings/255/merged.m4a"
        )
        db = _make_db_with_meeting(meeting)

        fake_task = MagicMock()
        fake_task.delay = MagicMock()

        with patch.dict(
            sys.modules,
            {"app.services.post_meeting_tasks": MagicMock(post_meeting_process=fake_task)},
        ):
            with patch("app.services.audit_service.AuditService.log", new=AsyncMock()):
                res = await mr.reprocess_meeting(
                    meeting_id=255, current_user=_user(58), db=db
                )
        assert res["status"] == "processing"
        assert meeting.status == "processing"
        assert meeting.error_reason is None
        fake_task.delay.assert_called_once_with(255)

    async def test_error_with_chunks_only_no_audio_url_ok(self):
        """只有分片没有 audio_url 也应放行 (merge 后才有 audio_url)"""
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="error", last_chunk_index=2, audio_url=None)
        db = _make_db_with_meeting(meeting)
        fake_task = MagicMock()
        fake_task.delay = MagicMock()

        with patch.dict(
            sys.modules,
            {"app.services.post_meeting_tasks": MagicMock(post_meeting_process=fake_task)},
        ):
            with patch("app.services.audit_service.AuditService.log", new=AsyncMock()):
                res = await mr.reprocess_meeting(
                    meeting_id=255, current_user=_user(58), db=db
                )
        assert res["status"] == "processing"

    async def test_error_without_audio_returns_400(self):
        """0 分片 + 无 audio_url → 400, 提示先补传"""
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="error", last_chunk_index=-1, audio_url=None)
        db = _make_db_with_meeting(meeting)

        with pytest.raises(HTTPException) as exc:
            await mr.reprocess_meeting(meeting_id=255, current_user=_user(58), db=db)
        assert exc.value.status_code == 400
        assert "audio-chunk" in str(exc.value.detail)

    @pytest.mark.parametrize("status", ["recording", "processing", "completed"])
    async def test_non_error_status_idempotent_400(self, status):
        """非 error 态 → 400 幂等, 不重复触发流水线"""
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status=status, last_chunk_index=1, audio_url="x.m4a")
        db = _make_db_with_meeting(meeting)

        with pytest.raises(HTTPException) as exc:
            await mr.reprocess_meeting(meeting_id=255, current_user=_user(58), db=db)
        assert exc.value.status_code == 400

    async def test_cross_user_403(self):
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="error", created_by=58, last_chunk_index=1, audio_url="x")
        db = _make_db_with_meeting(meeting)

        with pytest.raises(HTTPException) as exc:
            await mr.reprocess_meeting(meeting_id=255, current_user=_user(99), db=db)
        assert exc.value.status_code == 403

    async def test_audit_action_in_valid_actions_whitelist(self):
        """缺陷 4: action 必须是 VALID_ACTIONS 白名单值, 否则 fallback 'read' 语义丢失"""
        from app.api.v1 import meeting_recording as mr
        from app.services.audit_service import VALID_ACTIONS

        assert "meeting_reprocess" in VALID_ACTIONS
        # 端点源码里硬编码的 action 字符串必须就是白名单里的那个
        import inspect
        src = inspect.getsource(mr.reprocess_meeting)
        assert 'action="meeting_reprocess"' in src
        # 老代码用的非白名单值不能残留
        assert "meeting_reprocess_user_initiated" not in src


# ============================================================================
# recording-presence 端点 (P0-1 后端配套)
# ============================================================================


class TestRecordingPresenceEndpoint:
    async def test_presence_written_when_recording(self):
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="recording")
        db = _make_db_with_meeting(meeting)

        res = await mr.recording_presence(
            meeting_id=255, current_user=_user(58), db=db
        )
        assert res["presence_recorded"] is True
        assert meeting.recording_presence_at is not None
        db.commit.assert_awaited_once()

    async def test_presence_idempotent_when_not_recording(self):
        """非录音态幂等返回, 不抛错 (fetch catch 静默失败)"""
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="error", recording_presence_at=None)
        db = _make_db_with_meeting(meeting)

        res = await mr.recording_presence(
            meeting_id=255, current_user=_user(58), db=db
        )
        assert res["presence_recorded"] is False
        assert meeting.recording_presence_at is None
        db.commit.assert_not_awaited()

    async def test_presence_cross_user_403(self):
        from fastapi import HTTPException
        from app.api.v1 import meeting_recording as mr

        meeting = _make_meeting(status="recording", created_by=58)
        db = _make_db_with_meeting(meeting)

        with pytest.raises(HTTPException) as exc:
            await mr.recording_presence(meeting_id=255, current_user=_user(99), db=db)
        assert exc.value.status_code == 403