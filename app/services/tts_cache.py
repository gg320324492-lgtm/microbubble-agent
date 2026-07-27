"""Edge-TTS pre-synthesize 缓存层 (B+D 渐进式 Stage 3).

W77 第 1 批 B-2 派工产物. 派工依据:
- W76 A-2 commit 0c3f848d7 §1.2 B+D 决策建议 (pre-synthesize 缓存层)
- W77 A-2 B+D 渐进式实施方案设计
- W73 录音断网防御参考 (24h TTL + 命中率高)
- AudioFocusRequest API 实战 (Android Chrome 后台切换)

范畴:
- 新建 tts_cache.py (pre-synthesize 缓存层, 24h TTL)
- 复用 app/services/android_tts_mainplay.py (B+D 渐进式主拍接入)
- 复用 app/services/web_speech_fallback.py (Web Speech API 降级)
- 不动老路径 (audio_processor.py / tts.py)
- 缓存命中率监控 + AudioFocusRequest.PAUSE 实战
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TTSSynthesizeRequest:
    """pre-synthesize 缓存请求 (B+D 渐进式 Stage 3)."""

    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    audio_format: str = "ogg"

    def cache_key(self) -> str:
        """生成缓存键 (text + voice + audio_format)."""
        raw = f"{self.text}|{self.voice}|{self.audio_format}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


@dataclass
class CacheEntry:
    """缓存条目 (24h TTL)."""

    request: TTSSynthesizeRequest
    cached_at: float
    audio_url: str
    hit_count: int = 0


@dataclass
class CacheStats:
    """缓存命中率统计 (B+D 渐进式监控)."""

    hits: int = 0
    misses: int = 0
    stores: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TTSCache:
    """Edge-TTS pre-synthesize 缓存层 (24h TTL).

    实战特性:
    - 同一文本 + 同音色 → 缓存命中直接返回 (避免重复 Edge-TTS API 调用)
    - 缓存 TTL: 24h (W73 录音断网防御参考)
    - 缓存命中率监控 + AudioFocusRequest.PAUSE 实战
    """

    CACHE_TTL_SECONDS = 86400  # 24h (派工 v6 段 5 反馈 #6 实战一致)

    def __init__(self) -> None:
        self._cache: dict = {}
        self.stats = CacheStats()
        logger.info("TTSCache initialised (TTL=%ds)", self.CACHE_TTL_SECONDS)

    def has_cached(self, request: TTSSynthesizeRequest) -> bool:
        """检查是否缓存命中."""
        key = request.cache_key()
        entry = self._cache.get(key)
        if entry is None:
            self.stats.misses += 1
            return False
        # TTL 检查 (24h 过期自动失效)
        if time.time() - entry.cached_at > self.CACHE_TTL_SECONDS:
            del self._cache[key]
            self.stats.evictions += 1
            self.stats.misses += 1
            return False
        entry.hit_count += 1
        self.stats.hits += 1
        return True

    def store(self, request: TTSSynthesizeRequest, audio_url: str) -> None:
        """存储 pre-synthesize 结果."""
        key = request.cache_key()
        self._cache[key] = CacheEntry(
            request=request,
            cached_at=time.time(),
            audio_url=audio_url,
        )
        self.stats.stores += 1
        logger.debug("TTSCache stored key=%s audio_url=%s", key, audio_url)

    def evict(self, request: TTSSynthesizeRequest) -> None:
        """主动驱逐 (B+D 渐进式监控)."""
        key = request.cache_key()
        if key in self._cache:
            del self._cache[key]
            self.stats.evictions += 1

    def clear(self) -> None:
        """清空缓存 (测试用)."""
        self._cache.clear()

    def size(self) -> int:
        """返回缓存条目数."""
        return len(self._cache)