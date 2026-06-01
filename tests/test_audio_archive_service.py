"""测试 audio_archive_service

设计原则：
- 不依赖真实 ffmpeg：通过 patch 替换 _ffmpeg_to_opus
- 不依赖真实 MinIO：mock file_service
- 不依赖真实 DB：mock AsyncSession
- 在 SKIP_DB_SETUP=1 下可运行
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.audio_archive_service import AudioArchiveWriter


def test_feed_pcm_accumulates():
    """feed_pcm 累积 PCM bytes"""
    fs = MagicMock()
    writer = AudioArchiveWriter(meeting_id=1, file_service=fs)
    writer.feed_pcm(b"\x00\x00" * 100)
    writer.feed_pcm(b"\x01\x00" * 100)
    assert len(writer._pcm_buffer) == 400


@pytest.mark.asyncio
async def test_finalize_too_short_skips():
    """< 1000 bytes 跳过"""
    fs = MagicMock()
    writer = AudioArchiveWriter(meeting_id=1, file_service=fs)
    writer.feed_pcm(b"\x00\x00" * 100)  # 200 bytes
    db = MagicMock()
    result = await writer.finalize(db)
    assert result.get("skipped") == "too_short"
    fs.upload_to_path.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_writes_meeting_fields():
    """finalize 上传 MinIO + 写 Meeting 字段"""
    fs = MagicMock()
    fs.upload_to_path = AsyncMock(return_value={
        "object_name": "meetings/1/audio.opus",
        "size": 5000,
        "content_type": "audio/ogg",
        "url": "/microbubble/meetings/1/audio.opus",
    })

    writer = AudioArchiveWriter(meeting_id=1, file_service=fs)
    # 喂入足够 PCM 触发归档
    writer.feed_pcm(b"\x00\x00" * 5000)  # 10000 bytes

    # mock meeting 对象
    meeting = MagicMock()
    meeting.audio_archive_url = None
    meeting.audio_duration_seconds = None
    meeting.audio_size_bytes = None
    meeting.audio_archived_at = None
    meeting.audio_archived = False

    db = MagicMock()
    # mock db.execute 返回 meeting
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = meeting
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    # mock ffmpeg subprocess（避免实际调用 ffmpeg）
    # 写一个真实的临时文件以让 open() 成功
    import tempfile
    import os

    real_tmpdir = tempfile.mkdtemp()
    pcm_path = os.path.join(real_tmpdir, "test.pcm")
    opus_path = pcm_path.replace(".pcm", ".opus")
    with open(pcm_path, "wb") as f:
        f.write(b"\x00" * 100)
    with open(opus_path, "wb") as f:
        f.write(b"\x00" * 50)

    def fake_ffmpeg(input_pcm, output_opus):
        # 在调用时把临时文件复制到预期的输出路径
        with open(input_pcm, "rb") as src, open(output_opus, "wb") as dst:
            dst.write(src.read())

    with patch("app.services.audio_archive_service._ffmpeg_to_opus", side_effect=fake_ffmpeg), \
         patch("app.services.audio_archive_service.tempfile.NamedTemporaryFile") as mock_ntf, \
         patch("app.services.audio_archive_service.os.path.exists", return_value=True), \
         patch("app.services.audio_archive_service.os.unlink"):
        # 让 NamedTemporaryFile 创建在我们控制的真实路径
        mock_file = MagicMock()
        mock_file.name = pcm_path
        mock_ntf.return_value.__enter__.return_value = mock_file
        mock_ntf.return_value.__exit__.return_value = False

        result = await writer.finalize(db)

    # 验证：upload_to_path 被调用，meeting 字段被设置
    fs.upload_to_path.assert_called_once()
    assert meeting.audio_archive_url is not None
    assert meeting.audio_archived is True
    db.commit.assert_called_once()
