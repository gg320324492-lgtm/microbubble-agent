"""会议音频归档服务

职责：累积 WS 期间的 PCM 流，WS 关闭时 ffmpeg 转 opus + 上传 MinIO + 写 Meeting 字段。
"""
import asyncio
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting import Meeting
from app.services.file_service import FileService

logger = logging.getLogger("microbubble.audio_archive")

MIN_PCM_BYTES_FOR_ARCHIVE = 1000  # 太短不存档


class AudioArchiveWriter:
    """每条 WS 一个实例，累积 PCM 流"""

    def __init__(self, meeting_id: int, file_service: FileService):
        self.meeting_id = meeting_id
        self.fs = file_service
        self._pcm_buffer = bytearray()
        self._start_time: Optional[float] = None
        self._closed = False

    def feed_pcm(self, pcm_int16: bytes):
        """WS 接收每个 PCM chunk 时调用"""
        if self._closed:
            return
        if self._start_time is None:
            self._start_time = time.time()
        self._pcm_buffer.extend(pcm_int16)

    async def finalize(self, db: AsyncSession) -> dict:
        """
        WS 关闭时调用：
        1. 写临时 WAV 文件
        2. ffmpeg 转 opus
        3. 上传 MinIO
        4. 写 Meeting.audio_archive_url 等字段
        5. 清理临时文件
        """
        self._closed = True
        if len(self._pcm_buffer) < MIN_PCM_BYTES_FOR_ARCHIVE:
            return {"skipped": "too_short"}

        pcm_path = None
        opus_path = None
        try:
            # 1. 写临时 PCM
            with tempfile.NamedTemporaryFile(suffix='.pcm', delete=False, dir='/tmp') as pcm_f:
                pcm_f.write(self._pcm_buffer)
                pcm_path = pcm_f.name

            # 2. ffmpeg 转 opus
            opus_path = pcm_path.replace('.pcm', '.opus')
            try:
                await asyncio.to_thread(_ffmpeg_to_opus, pcm_path, opus_path)
            except FileNotFoundError:
                logger.error("ffmpeg 未安装，跳过音频归档")
                return {"skipped": "ffmpeg_unavailable"}
            except subprocess.CalledProcessError as e:
                logger.error(f"ffmpeg 转码失败: {e}")
                return {"skipped": "ffmpeg_failed"}

            # 3. 读 opus bytes
            with open(opus_path, 'rb') as f:
                opus_bytes = f.read()

            # 4. 上传 MinIO（固定路径 meetings/{id}/audio.opus）
            object_name = f"meetings/{self.meeting_id}/audio.opus"
            result = await self.fs.upload_to_path(
                object_name, opus_bytes, content_type="audio/ogg"
            )

            # 5. 写 Meeting 字段
            result_db = await db.execute(select(Meeting).where(Meeting.id == self.meeting_id))
            meeting = result_db.scalar_one_or_none()
            if meeting:
                meeting.audio_archive_url = result["url"]
                meeting.audio_duration_seconds = len(self._pcm_buffer) / (16000 * 2)  # 16kHz int16 mono
                meeting.audio_size_bytes = result["size"]
                meeting.audio_archived_at = datetime.now(timezone.utc)
                meeting.audio_archived = True
                await db.commit()

            return {
                "audio_archive_url": result["url"],
                "audio_duration_seconds": meeting.audio_duration_seconds if meeting else None,
                "audio_size_bytes": result["size"],
            }
        finally:
            # 6. 清理临时文件
            for path in (pcm_path, opus_path):
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {path}: {e}")


def _ffmpeg_to_opus(input_pcm: str, output_opus: str):
    """同步 ffmpeg 调用：16kHz s16le mono → opus @ 32kbps"""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "s16le",
        "-ar", "16000",
        "-ac", "1",
        "-i", input_pcm,
        "-c:a", "libopus",
        "-b:a", "32k",
        output_opus,
    ], check=True, capture_output=True)
