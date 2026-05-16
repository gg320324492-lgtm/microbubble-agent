"""说话人识别模块 - 用于区分不同说话人"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class SpeakerProfile:
    """说话人档案"""
    id: str
    name: str
    embedding: Optional[np.ndarray] = None


class SpeakerDetector:
    """说话人识别器"""

    def __init__(self):
        self.speakers: Dict[str, SpeakerProfile] = {}
        self.current_speaker: Optional[str] = None
        self._model = None
        self._initialized = False

    def _init_model(self):
        """初始化模型（延迟加载）"""
        if self._initialized:
            return

        try:
            # 这里可以加载 pyannote-audio 等说话人识别模型
            # 由于需要较大依赖，暂时使用简化的实现
            print("说话人识别模块初始化（简化模式）")
            self._initialized = True
        except Exception as e:
            print(f"说话人识别模型加载失败: {e}")

    def register_speaker(self, name: str, audio_samples: List[bytes] = None) -> str:
        """
        注册说话人

        Args:
            name: 说话人姓名
            audio_samples: 音频样本列表（用于提取声纹特征）

        Returns:
            说话人ID
        """
        speaker_id = f"speaker_{len(self.speakers) + 1}"

        profile = SpeakerProfile(
            id=speaker_id,
            name=name,
            embedding=None  # TODO: 从音频样本提取声纹特征
        )

        self.speakers[speaker_id] = profile
        return speaker_id

    async def identify(self, audio_data: bytes) -> str:
        """
        识别说话人

        Args:
            audio_data: 音频数据

        Returns:
            说话人名称
        """
        self._init_model()

        # 简化实现：返回当前说话人或"未知"
        if self.current_speaker:
            speaker = self.speakers.get(self.current_speaker)
            if speaker:
                return speaker.name

        return "未知"

    async def identify_segments(self, audio_segments: List[bytes]) -> List[str]:
        """
        识别多个音频片段的说话人

        Args:
            audio_segments: 音频片段列表

        Returns:
            说话人名称列表
        """
        results = []
        for segment in audio_segments:
            speaker = await self.identify(segment)
            results.append(speaker)
        return results

    def set_current_speaker(self, speaker_id: str):
        """设置当前说话人"""
        if speaker_id in self.speakers:
            self.current_speaker = speaker_id

    def get_speaker_name(self, speaker_id: str) -> str:
        """获取说话人名称"""
        speaker = self.speakers.get(speaker_id)
        return speaker.name if speaker else "未知"

    def get_all_speakers(self) -> List[Dict]:
        """获取所有注册的说话人"""
        return [
            {"id": s.id, "name": s.name}
            for s in self.speakers.values()
        ]

    def clear(self):
        """清除所有说话人"""
        self.speakers.clear()
        self.current_speaker = None


class SimpleSpeakerDiarization:
    """
    简化的说话人分离实现

    基于音量和静音检测的简单说话人切换检测
    """

    def __init__(self, silence_threshold: float = 0.01, min_silence_ms: int = 500):
        self.silence_threshold = silence_threshold
        self.min_silence_ms = min_silence_ms
        self.segments = []
        self.current_segment_start = 0
        self.current_speaker = 0

    def process_audio(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict]:
        """
        处理音频数据，检测说话人切换

        Args:
            audio_data: 音频数据（归一化到[-1, 1]）
            sample_rate: 采样率

        Returns:
            分段结果列表
        """
        # 计算每帧的音量
        frame_size = int(sample_rate * 0.03)  # 30ms帧
        hop_size = frame_size // 2

        segments = []
        is_speech = False
        silence_start = 0
        speaker_id = 0

        for i in range(0, len(audio_data) - frame_size, hop_size):
            frame = audio_data[i:i + frame_size]
            energy = np.sqrt(np.mean(frame ** 2))

            if energy > self.silence_threshold:
                if not is_speech:
                    # 开始说话
                    is_speech = True
                    silence_duration = (i - silence_start) / sample_rate * 1000

                    # 如果静音时间足够长，认为切换了说话人
                    if silence_duration > self.min_silence_ms and segments:
                        speaker_id = (speaker_id + 1) % 2  # 简单切换

                    segment_start = i / sample_rate

            else:
                if is_speech:
                    # 结束说话
                    is_speech = False
                    silence_start = i

                    segments.append({
                        "start": segment_start,
                        "end": i / sample_rate,
                        "speaker": f"说话人{speaker_id + 1}"
                    })

        return segments


# 全局实例
speaker_detector = SpeakerDetector()
