"""录音模块 - 用于会议录制和语音输入"""

import io
import wave
import numpy as np
from datetime import datetime
from app.models.base import utcnow
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum


class RecordingStatus(str, Enum):
    """录音状态"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class AudioConfig:
    """音频配置"""
    sample_rate: int = 16000      # 采样率
    channels: int = 1             # 声道数
    sample_width: int = 2         # 采样宽度（字节）
    chunk_size: int = 1024        # 数据块大小


class AudioRecorder:
    """音频录制器"""

    def __init__(self, config: AudioConfig = None):
        self.config = config or AudioConfig()
        self.status = RecordingStatus.IDLE
        self.audio_buffer = []
        self.start_time = None
        self.on_data_callback: Optional[Callable] = None

    def start(self, on_data: Optional[Callable] = None):
        """
        开始录音

        Args:
            on_data: 数据回调函数，用于实时处理音频数据
        """
        if self.status == RecordingStatus.RECORDING:
            return

        self.audio_buffer = []
        self.start_time = utcnow()
        self.status = RecordingStatus.RECORDING
        self.on_data_callback = on_data

        # 这里会启动实际的录音线程
        # 在Web环境中，录音由前端完成，这里只是管理状态
        print("录音开始")

    def stop(self) -> bytes:
        """
        停止录音

        Returns:
            WAV格式的音频数据
        """
        if self.status != RecordingStatus.RECORDING:
            return b""

        self.status = RecordingStatus.STOPPED

        # 合并音频数据
        audio_data = b"".join(self.audio_buffer)

        # 转换为WAV格式
        wav_data = self._to_wav(audio_data)

        print(f"录音结束，时长: {self.get_duration():.1f}秒")
        return wav_data

    def pause(self):
        """暂停录音"""
        if self.status == RecordingStatus.RECORDING:
            self.status = RecordingStatus.PAUSED
            print("录音暂停")

    def resume(self):
        """恢复录音"""
        if self.status == RecordingStatus.PAUSED:
            self.status = RecordingStatus.RECORDING
            print("录音恢复")

    def add_audio_data(self, data: bytes):
        """添加音频数据"""
        if self.status == RecordingStatus.RECORDING:
            self.audio_buffer.append(data)

            # 调用回调函数
            if self.on_data_callback:
                self.on_data_callback(data)

    def get_duration(self) -> float:
        """获取录音时长（秒）"""
        if not self.start_time:
            return 0.0

        if self.status == RecordingStatus.RECORDING:
            return (utcnow() - self.start_time).total_seconds()

        # 计算缓冲区中的音频时长
        total_bytes = sum(len(chunk) for chunk in self.audio_buffer)
        duration = total_bytes / (
            self.config.sample_rate *
            self.config.channels *
            self.config.sample_width
        )
        return duration

    def get_audio_data(self) -> bytes:
        """获取当前录制的音频数据"""
        return b"".join(self.audio_buffer)

    def clear(self):
        """清空录音缓冲区"""
        self.audio_buffer = []
        self.start_time = None
        self.status = RecordingStatus.IDLE

    def _to_wav(self, audio_data: bytes) -> bytes:
        """将原始音频数据转换为WAV格式"""
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.config.channels)
            wf.setsampwidth(self.config.sample_width)
            wf.setframerate(self.config.sample_rate)
            wf.writeframes(audio_data)

        buffer.seek(0)
        return buffer.read()


class MeetingRecorder:
    """会议录制器"""

    def __init__(self, meeting_id: int):
        self.meeting_id = meeting_id
        self.recorder = AudioRecorder()
        self.transcript = []
        self.start_time = None
        self.participants = []

    async def start_recording(self):
        """开始会议录制"""
        self.start_time = utcnow()
        self.recorder.start(on_data=self._on_audio_data)
        print(f"会议 {self.meeting_id} 开始录制")

    async def stop_recording(self) -> dict:
        """停止会议录制"""
        audio_data = self.recorder.stop()
        end_time = utcnow()

        return {
            "meeting_id": self.meeting_id,
            "start_time": self.start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": (end_time - self.start_time).total_seconds(),
            "audio_size": len(audio_data),
            "transcript": self.transcript
        }

    def _on_audio_data(self, data: bytes):
        """处理音频数据"""
        # 这里可以调用ASR进行实时转写
        pass

    def add_transcript_entry(self, entry: dict):
        """添加转写条目"""
        self.transcript.append({
            **entry,
            "timestamp": utcnow().isoformat()
        })

    def get_transcript_text(self) -> str:
        """获取转写文本"""
        lines = []
        for entry in self.transcript:
            time_str = entry.get("timestamp", "")
            speaker = entry.get("speaker", "未知")
            text = entry.get("text", "")
            lines.append(f"[{time_str}] {speaker}: {text}")
        return "\n".join(lines)


# 录音管理器
class RecorderManager:
    """录音管理器 - 管理多个录音实例"""

    def __init__(self):
        self.recorders = {}
        self.active_meeting_recorder = None

    def create_recorder(self, recorder_id: str) -> AudioRecorder:
        """创建录音器"""
        recorder = AudioRecorder()
        self.recorders[recorder_id] = recorder
        return recorder

    def get_recorder(self, recorder_id: str) -> Optional[AudioRecorder]:
        """获取录音器"""
        return self.recorders.get(recorder_id)

    def remove_recorder(self, recorder_id: str):
        """移除录音器"""
        if recorder_id in self.recorders:
            recorder = self.recorders[recorder_id]
            if recorder.status == RecordingStatus.RECORDING:
                recorder.stop()
            del self.recorders[recorder_id]

    async def start_meeting_recording(self, meeting_id: int) -> MeetingRecorder:
        """开始会议录制"""
        if self.active_meeting_recorder:
            await self.active_meeting_recorder.stop_recording()

        self.active_meeting_recorder = MeetingRecorder(meeting_id)
        await self.active_meeting_recorder.start_recording()
        return self.active_meeting_recorder

    async def stop_meeting_recording(self) -> Optional[dict]:
        """停止会议录制"""
        if self.active_meeting_recorder:
            result = await self.active_meeting_recorder.stop_recording()
            self.active_meeting_recorder = None
            return result
        return None


# 全局实例
recorder_manager = RecorderManager()
