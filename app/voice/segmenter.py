"""实时音频段满检测器

职责：根据静音时长或最大累积时长判断是否触发"段满"。
设计：纯字节级计算，无 ML 依赖，无单例状态污染。
"""
import logging

logger = logging.getLogger("microbubble.segmenter")

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2  # int16
SILENCE_AMPLITUDE_THRESHOLD = 500  # int16 振幅低于此值视为静音


class LiveSegmenter:
    """
    段满检测器。检测条件：
    1. 连续静音 > silence_threshold_ms（默认 1500ms）
    2. 累积长度 > max_segment_ms（默认 8000ms）强制触发
    """

    def __init__(
        self,
        silence_threshold_ms: int = 1500,
        max_segment_ms: int = 8000,
        sample_rate: int = SAMPLE_RATE,
    ):
        self._silence_threshold_bytes = int(
            sample_rate * BYTES_PER_SAMPLE * silence_threshold_ms / 1000
        )
        self._max_bytes = int(sample_rate * BYTES_PER_SAMPLE * max_segment_ms / 1000)
        self._silence_bytes = 0
        self._buffer = bytearray()

    def feed(self, pcm_int16: bytes) -> bool:
        """
        喂入一段 PCM 数据。返回 True 表示应该触发段满处理。
        """
        if not pcm_int16:
            return False

        is_silent = self._is_silent(pcm_int16)
        self._buffer.extend(pcm_int16)

        if is_silent:
            self._silence_bytes += len(pcm_int16)
        else:
            self._silence_bytes = 0

        return (
            self._silence_bytes >= self._silence_threshold_bytes
            or len(self._buffer) >= self._max_bytes
        )

    def drain(self) -> bytes:
        """取出并清空缓冲区"""
        data = bytes(self._buffer)
        self._buffer.clear()
        self._silence_bytes = 0
        return data

    def _is_silent(self, pcm_int16: bytes) -> bool:
        """检测 PCM 数据是否静音（平均振幅 < 阈值）"""
        if not pcm_int16:
            return True
        num_samples = len(pcm_int16) // BYTES_PER_SAMPLE
        if num_samples == 0:
            return True
        # 计算绝对值之和
        total = 0
        for i in range(0, len(pcm_int16), BYTES_PER_SAMPLE):
            sample = int.from_bytes(pcm_int16[i : i + BYTES_PER_SAMPLE], "little", signed=True)
            total += abs(sample)
        avg = total / num_samples
        return avg < SILENCE_AMPLITUDE_THRESHOLD
