"""音频处理服务 — WebM 转 WAV + 离线 VAD 分段

用于录音机模式的后处理：将完整录音切割为有意义的语音片段。
"""

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import List

import numpy as np

logger = logging.getLogger("microbubble.audio_processor")

SAMPLE_RATE = 16000


@dataclass
class AudioSegment:
    """音频片段"""
    audio: np.ndarray      # float32 PCM, 16kHz mono
    start_time: float      # 起始时间（秒）
    end_time: float        # 结束时间（秒）


class AudioProcessor:
    """音频格式转换 + 离线 VAD 分段"""

    async def convert_webm_to_wav(self, webm_data: bytes) -> np.ndarray:
        """WebM/Opus → 16kHz mono float32 PCM（通过 ffmpeg）

        Args:
            webm_data: WebM 格式的音频字节

        Returns:
            float32 numpy 数组，16kHz 单声道，值范围 [-1, 1]
        """
        def _convert():
            import subprocess
            import wave

            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f_in:
                f_in.write(webm_data)
                input_path = f_in.name

            output_path = input_path.replace('.webm', '.wav')
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', input_path,
                    '-ar', str(SAMPLE_RATE),
                    '-ac', '1',
                    '-f', 'wav',
                    output_path
                ], capture_output=True, check=True, timeout=300)

                with wave.open(output_path, 'rb') as wf:
                    pcm_bytes = wf.readframes(wf.getnframes())
                    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                return audio
            finally:
                try:
                    os.unlink(input_path)
                except OSError:
                    pass
                try:
                    os.unlink(output_path)
                except OSError:
                    pass

        return await asyncio.to_thread(_convert)

    def segment_audio(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> List[AudioSegment]:
        """用 VAD 将完整音频切割为语音段（离线模式）

        直接调用 silero-vad 的 get_speech_timestamps 对整段音频检测，
        比逐块 process_chunk 更准确。

        Args:
            audio: float32 numpy 数组，16kHz 单声道
            sample_rate: 采样率（默认 16000）

        Returns:
            AudioSegment 列表，每段包含音频数据和时间戳
        """
        import torch

        # 加载 silero-vad
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        get_speech_timestamps = utils[0]

        # 转为 tensor
        audio_tensor = torch.from_numpy(audio.copy())

        # 获取语音时间戳
        speeches = get_speech_timestamps(
            audio_tensor,
            model,
            threshold=0.5,
            min_speech_duration_ms=500,
            min_silence_duration_ms=300,
            return_seconds=False,
            sampling_rate=sample_rate,
        )

        if not speeches:
            # 没有检测到语音，返回整段
            logger.warning("VAD 未检测到语音，返回整段音频")
            return [AudioSegment(
                audio=audio,
                start_time=0,
                end_time=len(audio) / sample_rate,
            )]

        # 合并相邻过近的语音段（间隔 < 1s 的合并）
        merged = [speeches[0]]
        for seg in speeches[1:]:
            gap_samples = seg["start"] - merged[-1]["end"]
            if gap_samples < sample_rate * 1.0:  # 间隔 < 1s，合并
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg)

        # 切割
        segments = []
        for seg in merged:
            start = seg["start"]
            end = min(seg["end"], len(audio))
            segment_audio = audio[start:end]

            if len(segment_audio) < sample_rate * 0.3:  # 跳过 < 300ms 的段
                continue

            segments.append(AudioSegment(
                audio=segment_audio,
                start_time=start / sample_rate,
                end_time=end / sample_rate,
            ))

        logger.info(f"VAD 分段完成: {len(segments)} 段（原始 {len(speeches)} 段，合并后 {len(merged)} 段）")
        return segments

    async def convert_and_segment(self, webm_data: bytes) -> tuple[np.ndarray, List[AudioSegment], int]:
        """一步完成：WebM → PCM + VAD 分段

        Returns:
            (audio_pcm, segments, sample_rate)
        """
        audio_pcm = await self.convert_webm_to_wav(webm_data)
        segments = self.segment_audio(audio_pcm, SAMPLE_RATE)
        return audio_pcm, segments, SAMPLE_RATE


audio_processor = AudioProcessor()
