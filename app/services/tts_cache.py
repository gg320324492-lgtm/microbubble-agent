"""TTS pre-synthesize 缓存层 (W77 第 1 批 B-1)

W76 A-2 §1.2 D 选项核心
依据: W73 录音断网防御参考 + Edge-TTS API 复用减少

缓存策略:
- key = sha256(text|voice)[:16]
- TTL = 24h (86400s, W73 reference)
- 存储: 内存 dict (主路径), Redis 可选 (W77 B-1 协调)
- value: {audio_url, text, voice, created_at}

监控:
- 命中率 (hits / (hits + misses))
- 过期清理 (lazy + max_size)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger("microbubble.tts_cache")


@dataclass
class TTSCacheEntry:
    """TTS pre-synthesize 缓存条目"""
    key: str
    audio_url: str
    text: str
    voice: str
    created_at_ms: int
    ttl_seconds: int


@dataclass
class TTSCacheStoreConfig:
    """TTS 缓存 store 配置"""
    ttl_seconds: int = 86400       # 24h
    max_size: int = 10_000         # 1 万条目上限
    enable_metrics: bool = True


class TTSCacheStore:
    """TTS pre-synthesize 缓存 store

    实战角色:
    1. Edge-TTS 成功后写入 (供下次命中)
    2. 命中时跳过 Edge-TTS 直接返回 audio_url
    3. 过期 lazy 清理 (get 时检查)
    """

    def __init__(self, config: Optional[TTSCacheStoreConfig] = None) -> None:
        self._config = config or TTSCacheStoreConfig()
        self._store: Dict[str, TTSCacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[TTSCacheEntry]:
        """查询缓存; 过期 lazy 清理; 命中后返回"""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        now_ms = int(time.time() * 1000)
        age_ms = now_ms - entry.created_at_ms
        if age_ms > entry.ttl_seconds * 1000:
            self._store.pop(key, None)
            self._misses += 1
            self._evictions += 1
            return None
        self._hits += 1
        return entry

    def put(self, key: str, *, audio_url: str, text: str, voice: str) -> TTSCacheEntry:
        """写入缓存 (含 LRU 简化: 超 max_size 时清最旧 10%)"""
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
        return entry

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
        return evict_count

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
    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def metrics(self) -> Dict[str, Any]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "size": self.size,
            "evictions": self._evictions,
            "max_size": self._config.max_size,
        }


def build_tts_cache_store(
    ttl_seconds: int = 86400,
    max_size: int = 10_000,
) -> TTSCacheStore:
    return TTSCacheStore(
        config=TTSCacheStoreConfig(
            ttl_seconds=ttl_seconds,
            max_size=max_size,
        )
    )
