"""TTS pre-synthesize 缓存层 — 跨平台统一 (W77 B-1 + W78 B-1 合并, W83 B-2 P1-1 收敛)

W77 第 1 批 B-2 + W78 B-1 派工产物 (W83 B-2 P1-1 统一):
- W76 A-2 commit 0c3f848d7 §1.2 B+D 决策建议 (pre-synthesize 缓存层)
- W77 A-2 B+D 渐进式实施方案设计
- W73 录音断网防御参考 (24h TTL + 命中率高)
- AudioFocusRequest API 实战 (Android Chrome 后台切换)

范畴:
- 统一 iOS / Android 双端 TTS 缓存 store (W77 B-2 tts_cache.py + W78 B-1 ios_tts_cache.py 合并)
- 复用 app/services/android_tts_mainplay.py (B+D 渐进式主拍接入)
- 复用 app/services/web_speech_fallback.py (Web Speech API 降级)
- 不动老路径 (audio_processor.py / tts.py)
- 缓存命中率监控 + AudioFocusRequest.PAUSE 实战
- W83 B-2 P1-1: 删除 ios_tts_cache.py, 全部归入本模块, TTSCacheStore 为跨平台统一 API

历史拆分根因:
- W78 B-1 类 20.12.1 修复: 原 tts_cache.py 与 W77 B-2 (Android) 同名模块在 main merge 时互相覆盖
  (B-2 后 merge 胜出), 导致 ios_tts_mainplay.py 的 TTSCacheStore ImportError.
- W83 B-2 P1-1 拆除: 派工前提铁律已确认 (W82 B-2 拦截 #16 实战) — 双端 API 物理隔离, 合并安全

缓存策略:
- key = sha256(text|voice|audio_format)[:16] (Android 侧约定)
- TTL = 24h (86400s, W73 reference)
- 存储: 内存 dict (主路径), max_size = 10000 (W78 B-1 LRU 约定)
- value: {audio_url, text, voice, created_at, ttl_seconds}

监控:
- 命中率 (hits / (hits + misses))
- 过期清理 (lazy + max_size LRU eviction)
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# --- Android 侧 TTSSynthesizeRequest (W77 B-2 保留, 跨平台统一) ---

@dataclass(frozen=True)
class TTSSynthesizeRequest:
    """pre-synthesize 缓存请求 (B+D 渐进式 Stage 3, 跨平台统一).

    W77 B-2 Android 侧原始约定; W83 B-2 P1-1 升级为跨平台统一契约.
    """

    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    audio_format: str = "ogg"

    def cache_key(self) -> str:
        """生成缓存键 (text + voice + audio_format)."""
        raw = f"{self.text}|{self.voice}|{self.audio_format}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


# --- iOS 侧 TTSCacheEntry (W78 B-1 保留, 跨平台统一) ---

@dataclass
class TTSCacheEntry:
    """TTS pre-synthesize 缓存条目 (跨平台统一)."""
    key: str
    audio_url: str
    text: str
    voice: str
    created_at_ms: int
    ttl_seconds: int


@dataclass
class TTSCacheStoreConfig:
    """TTS 缓存 store 配置 (W78 B-1, W83 B-2 P1-1 跨平台统一)."""
    ttl_seconds: int = 86400       # 24h
    max_size: int = 10_000         # 1 万条目上限
    enable_metrics: bool = True


@dataclass
class TTSCacheStats:
    """W77 B-2 兼容 CacheStats (W83 B-2 P1-1 持久化 stats 字段).

    AndroidTTSMainplay 接口依赖此 struct 的字段访问: cache.stats.misses/hits 等.
    必须与 TTSCacheStore._hits/_misses/_evictions 保持同步 (在 get/put/evict/clear 中累加).
    """
    hits: int = 0
    misses: int = 0
    stores: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class TTSCacheStore:
    """TTS pre-synthesize 缓存 store (跨平台统一, W83 B-2 P1-1)

    实战角色:
    1. Edge-TTS 成功后写入 (供下次命中)
    2. 命中时跳过 Edge-TTS 直接返回 audio_url
    3. 过期 lazy 清理 (get 时检查)
    4. LRU 简化: 超 max_size 时清最旧 10%

    W77 B-2 (Android) 旧 TTSCache 类的超集:
    - 已包含 has_cached / store / evict / clear / size 接口的等价能力
    - 包含 metrics (hits / misses / hit_rate / evictions)
    - 跨平台: iOS + Android 统一使用 TTSCacheStore

    注: W77 B-2 旧 TTSCache class 已删除 (W83 B-2 P1-1, 改为 thin wrapper 委派给 TTSCacheStore)
    """

    CACHE_TTL_SECONDS = 86400  # 24h (派工 v6 段 5 反馈 #6 实战一致)

    def __init__(self, config: Optional[TTSCacheStoreConfig] = None) -> None:
        self._config = config or TTSCacheStoreConfig()
        self._store: Dict[str, TTSCacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._stats = TTSCacheStats()  # W77 B-2 兼容 stats 字段
        logger.info("TTSCacheStore initialised (TTL=%ds, max_size=%d)", self._config.ttl_seconds, self._config.max_size)

    # --- 跨平台统一 API (W78 B-1 稳定 API + W77 B-2 接口) ---

    def get(self, key: str) -> Optional[TTSCacheEntry]:
        """查询缓存; 过期 lazy 清理; 命中后返回."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            self._stats.misses += 1
            return None
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - entry.created_at_ms
        if age_ms > entry.ttl_seconds * 1000:
            self._store.pop(key, None)
            self._misses += 1
            self._stats.misses += 1
            self._evictions += 1
            self._stats.evictions += 1
            return None
        self._hits += 1
        self._stats.hits += 1
        return entry

    def put(self, key: str, *, audio_url: str, text: str, voice: str) -> TTSCacheEntry:
        """写入缓存 (含 LRU 简化: 超 max_size 时清最旧 10%)."""
        if len(self._store) >= self._config.max_size:
            self._evict_oldest(percent=10)
        entry = TTSCacheEntry(
            key=key,
            audio_url=audio_url,
            text=text,
            voice=voice,
            created_at_ms=int(time.time() * 1000),
            ttl_seconds=self._config.ttl_seconds,
        )
        self._store[key] = entry
        self._stats.stores += 1
        return entry

    # --- W77 B-2 (Android) 兼容 API (thin wrapper 委派) ---

    def has_cached(self, request: TTSSynthesizeRequest) -> bool:
        """检查是否缓存命中 (W77 B-2 兼容 API)."""
        key = request.cache_key()
        entry = self.get(key)
        if entry is None:
            return False
        return True

    def store(self, request: TTSSynthesizeRequest, audio_url: str) -> None:
        """存储 pre-synthesize 结果 (W77 B-2 兼容 API)."""
        self.put(
            request.cache_key(),
            audio_url=audio_url,
            text=request.text,
            voice=request.voice,
        )

    def evict(self, request: TTSSynthesizeRequest) -> None:
        """主动驱逐 (W77 B-2 兼容 API)."""
        key = request.cache_key()
        if key in self._store:
            del self._store[key]
            self._evictions += 1
            self._stats.evictions += 1

    def clear(self) -> None:
        """清空缓存 (测试用)."""
        self._store.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._stats = TTSCacheStats()

    def size(self) -> int:
        """返回缓存条目数 (W77 B-2 兼容 API)."""
        return len(self._store)

    def _evict_oldest(self, percent: int = 10) -> int:
        if not self._store:
            return 0
        evict_count = max(1, len(self._store) * percent // 100)
        sorted_keys = sorted(
            self._store.keys(),
            key=lambda k: self._store[k].created_at_ms,
        )
        for k in sorted_keys[:evict_count]:
            self._store.pop(k, None)
        self._evictions += evict_count
        self._stats.evictions += evict_count
        return evict_count

    # --- 监控指标 (W78 B-1 跨平台统一) ---

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> "TTSCacheStats":
        """W77 B-2 兼容 stats 字段 (兼容旧 AndroidTTSMainplay 接口)."""
        return self._stats

    @property
    def size_count(self) -> int:
        """W78 B-1 size 计数 (跨平台统一, 区别于 W77 B-2 size() 方法)."""
        return len(self._store)

    def metrics(self) -> Dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "size": self.size_count,
            "evictions": self._evictions,
            "max_size": self._config.max_size,
        }


# --- W77 B-2 兼容 TTSCache 别名 (W83 B-2 P1-1 thin wrapper) ---

class TTSCache(TTSCacheStore):
    """W77 B-2 (Android) 兼容别名 — 已 deprecated, 但保留避免破坏 import.

    W83 B-2 P1-1 派工依据: android_tts_mainplay.py 第 45 行 import 已迁移到 TTSCacheStore,
    本别名仅防御性保留. 后续 W84 batch 清理.
    """

    def __init__(self) -> None:
        super().__init__()


# --- W78 B-1 builder ---

def build_tts_cache_store(
    ttl_seconds: int = 86400,
    max_size: int = 10_000,
) -> TTSCacheStore:
    """W78 B-1 builder 函数 (跨平台统一)."""
    return TTSCacheStore(
        config=TTSCacheStoreConfig(
            ttl_seconds=ttl_seconds,
            max_size=max_size,
        )
    )
