"""VAD (Voice Activity Detection) — silero-vad 封装

将连续音频流切割为有意义的语音片段，过滤静音/噪音。
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("microbubble.vad")

# silero-vad 采样率固定为 16000
SAMPLE_RATE = 16000


class VADEngine:
    """silero-vad 语音活动检测器"""

    def __init__(self, threshold: float = 0.6, min_speech_ms: int = 400, min_silence_ms: int = 400):
        self.threshold = threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self._model = None
        self._reset_state()

    def _reset_state(self):
        """重置 VAD 状态"""
        self._state = None
        self._triggered = False
        self._temp_end = 0
        self._current_sample = 0
        self._speech_samples = np.array([], dtype=np.float32)
        self._speech_probs: list[float] = []

    def _load_model(self):
        """延迟加载 silero-vad 模型"""
        if self._model is not None:
            return
        try:
            import torch
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self._get_speech_timestamps = utils[0]
            self._model = model
            logger.info("silero-vad 模型加载完成")
        except Exception as e:
            logger.error(f"silero-vad 加载失败: {e}")
            raise

    def process_chunk(self, audio_chunk: np.ndarray) -> Optional[np.ndarray]:
        """处理一个音频块，返回完整语音段（如果有）。

        Args:
            audio_chunk: float32 numpy 数组，16kHz 单声道，值范围 [-1, 1]

        Returns:
            检测到的语音段 float32 数组，或 None（尚无完整语音段）
        """
        self._load_model()

        # 累积音频
        self._speech_samples = np.concatenate([self._speech_samples, audio_chunk])

        # 至少需要 0.5 秒音频才开始检测
        if len(self._speech_samples) < SAMPLE_RATE * 0.5:
            return None

        # 转换为 torch tensor
        import torch
        audio_tensor = torch.from_numpy(self._speech_samples.copy())

        # 获取语音时间戳
        try:
            speeches = self._get_speech_timestamps(
                audio_tensor,
                self._model,
                threshold=self.threshold,
                min_speech_duration_ms=self.min_speech_ms,
                min_silence_duration_ms=self.min_silence_ms,
                return_seconds=False,
            )
        except Exception:
            return None

        if not speeches:
            # 保留最后 1 秒以检测跨块边界语音
            keep = min(len(self._speech_samples), SAMPLE_RATE)
            self._speech_samples = self._speech_samples[-keep:]
            return None

        # 取第一个语音段
        first_speech = speeches[0]
        start_sample = first_speech["start"]
        end_sample = first_speech["end"]

        # 确保 end_sample 不超出数组范围
        end_sample = min(end_sample, len(self._speech_samples))

        segment = self._speech_samples[start_sample:end_sample].copy()

        # 移除已处理的部分，保留剩余部分用于后续检测
        remain_start = min(end_sample + int(SAMPLE_RATE * 0.2), len(self._speech_samples))
        self._speech_samples = self._speech_samples[remain_start:]

        # 验证语音段长度
        if len(segment) < SAMPLE_RATE * 0.3:  # 短于 300ms
            return None

        return segment

    def reset(self):
        """重置 VAD 状态"""
        self._reset_state()


# 全局懒加载默认 VAD（向后兼容）
# 优先使用 per-instance：调用方自行创建 VADEngine()，避免共享状态。
# 此处保留 get_vad_engine() 工厂仅为平滑过渡旧引用；
# 不再在 import 时实例化（避免 module-level 单例误用）。
_default_vad: Optional[VADEngine] = None


def get_vad_engine() -> VADEngine:
    """懒加载全局默认 VAD（向后兼容）"""
    global _default_vad
    if _default_vad is None:
        _default_vad = VADEngine()
    return _default_vad
