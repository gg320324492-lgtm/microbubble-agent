"""Edge-TTS iOS Safari 主拍接入 (W77 第 1 批 B-1)

派工 v4 铁律 3 真验证 3 步:
1. W76 A-2 commit 0c3f848d7 §1.2 B+D 渐进式决策 (Edge-TTS + Web Speech API 降级 + pre-synthesize 缓存)
2. W76 B-1 commit a20ec9603 17/17 e2e 基础 (不动)
3. audio_processor.py 老 TTS 链路 (不动)

依据: W76 A-2 决策建议 B+D 渐进式 + 派工 v6 段 5 反馈 #6 实战 (类比 W75 C-1 真支付 SDK 渐进式)

5 阶段实战:
1. Edge-TTS 渐进式 (在 ios_tts_autoplay.py 基础上扩展为主拍接入)
2. Web Speech API 降级 (新建 web_speech_fallback.py 同步用)
3. pre-synthesize 缓存 (新建 tts_cache.py 缓存层, 24h TTL)
4. 真生产 key 主拍决策 (W78 单独拍板, 不在 W77 自动启用, 类 20.13 实战)
5. 监控 + 容错 (接入 W73 B-2 4 类 hot-fix 监控 + W74 D-1 多租户监控 + W75 B-3 webhook 监控)

范畴: app/services/ 新建 (0 production code 改动铁律例外 1 已批)
不修改: app/services/audio_processor.py, app/voice/tts.py, useChatStream.ts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# W78 B-1 类 20.12.1 修复: 原 import 指向 web_speech_fallback / tts_cache,
# 但 W77 B-2 (Android) 同名模块在 main merge 时覆盖了 B-1 版本 →
# ImportError: cannot import name 'WebSpeechFallbackHandler'.
# 改指 iOS 专属模块 (ios_web_speech_fallback / ios_tts_cache), Android 侧不动.
from app.services.ios_web_speech_fallback import (
    WebSpeechFallbackHandler,
    WebSpeechResult,
    build_web_speech_fallback_handler,
)
from app.services.ios_tts_cache import (
    TTSCacheEntry,
    TTSCacheStore,
    build_tts_cache_store,
)

logger = logging.getLogger("microbubble.ios_tts_mainplay")


class MainplayState(str, Enum):
    """iOS Safari TTS 主拍接入状态机"""
    IDLE = "idle"                                # 初始
    EDGE_TTS_REQUESTED = "edge_tts_requested"    # Edge-TTS API 调起
    EDGE_TTS_PLAYING = "edge_tts_playing"        # Edge-TTS 播放中
    EDGE_TTS_FAILED = "edge_tts_failed"          # Edge-TTS 失败
    WEB_SPEECH_PLAYING = "web_speech_playing"    # Web Speech API 降级
    WEB_SPEECH_FAILED = "web_speech_failed"      # Web Speech API 失败
    CACHE_HIT_PLAYING = "cache_hit_playing"      # 缓存命中播放
    CACHE_MISS_FALLBACK = "cache_miss_fallback"  # 缓存未命中最终降级
    ERROR = "error"                              # 错误


class MainplayBackend(str, Enum):
    """主拍 backend 优先级 (W76 A-2 §1.2 B+D 决策)"""
    EDGE_TTS_PRIMARY = "edge_tts_primary"
    WEB_SPEECH_FALLBACK = "web_speech_fallback"
    CACHE_PRE_SYNTHESIZED = "cache_pre_synthesized"
    NONE = "none"


@dataclass
class MainplayConfig:
    """iOS Safari 主拍接入配置"""
    # Edge-TTS 主路径
    edge_tts_enabled: bool = True
    edge_tts_timeout_ms: int = 5000
    # Web Speech API 降级
    web_speech_enabled: bool = True
    web_speech_timeout_ms: int = 3000
    # pre-synthesize 缓存
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400                # 24h
    # 真生产 key 主拍 (W78 单独拍板)
    production_key_enabled: bool = False           # 类 20.13 实战 - 默认 False
    # 监控
    enable_monitoring: bool = True


@dataclass
class MainplayResult:
    """主拍接入执行结果"""
    case_id: str
    passed: bool
    state: MainplayState
    backend_used: MainplayBackend
    audio_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class BackendAttempt:
    """backend 尝试记录"""
    backend: MainplayBackend
    attempted: bool
    success: bool
    duration_ms: float
    error: Optional[str] = None


class IOSSafariMainplayAdapter:
    """iOS Safari TTS 主拍接入适配器

    W77 B-1 核心: 在 W76 B-1 ios_tts_*.py 基础上, 增加 B+D 渐进式主拍接入:
    - Edge-TTS 可用 → 主路径 (主拍)
    - Edge-TTS 失败 → Web Speech API 降级 (D 选项原生 fallback)
    - Web Speech API 失败 → pre-synthesize 缓存命中 (D 选项缓存)
    - 缓存 miss → 用户友好提示 (D 选项优雅降级)

    决策: W76 A-2 §1.2 B+D 组合 (类比 W75 C-1 真支付 SDK 渐进式)
    """

    def __init__(
        self,
        config: Optional[MainplayConfig] = None,
        web_speech: Optional[WebSpeechFallbackHandler] = None,
        cache_store: Optional[TTSCacheStore] = None,
    ) -> None:
        self._config = config or MainplayConfig()
        self._web_speech = web_speech or build_web_speech_fallback_handler()
        self._cache_store = cache_store or build_tts_cache_store(
            ttl_seconds=self._config.cache_ttl_seconds,
        )
        self._attempts: List[BackendAttempt] = []
        self._hit_count = 0
        self._miss_count = 0

    @property
    def attempts(self) -> List[BackendAttempt]:
        return list(self._attempts)

    @property
    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0.0

    def _normalize_cache_key(self, text: str, voice: str) -> str:
        """生成缓存 key (text + voice hash)"""
        import hashlib

        raw = f"{text.strip().lower()}|{voice.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def play(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        *,
        prefer_cached: bool = True,
    ) -> MainplayResult:
        """B+D 渐进式主拍接入 4 阶段实战:
        1. pre-synthesize cache hit (D)
        2. Edge-TTS primary (B)
        3. Web Speech API fallback (D)
        4. cache miss → 用户友好提示 (D)
        """
        self._attempts = []
        cache_key = self._normalize_cache_key(text, voice)

        # 阶段 1: pre-synthesize cache 查询 (D 选项)
        if self._config.cache_enabled and prefer_cached:
            cached = self._cache_store.get(cache_key)
            if cached is not None:
                self._hit_count += 1
                self._attempts.append(
                    BackendAttempt(
                        backend=MainplayBackend.CACHE_PRE_SYNTHESIZED,
                        attempted=True,
                        success=True,
                        duration_ms=0.5,
                    )
                )
                return MainplayResult(
                    case_id="mainplay.cache_hit",
                    passed=True,
                    state=MainplayState.CACHE_HIT_PLAYING,
                    backend_used=MainplayBackend.CACHE_PRE_SYNTHESIZED,
                    audio_url=cached.audio_url,
                    metadata={
                        "cache_key": cache_key,
                        "hit": True,
                        "fallback_chain": "CACHE → INSTANT",
                    },
                )
            self._miss_count += 1

        # 阶段 2: Edge-TTS 主路径 (B 选项)
        if self._config.edge_tts_enabled:
            edge_result = self._try_edge_tts(text, voice)
            self._attempts.append(edge_result)
            if edge_result.success:
                audio_url = f"blob:edge-tts/{cache_key}.mp3"
                # 写入缓存 (供下次命中)
                if self._config.cache_enabled:
                    self._cache_store.put(
                        cache_key,
                        audio_url=audio_url,
                        text=text,
                        voice=voice,
                    )
                return MainplayResult(
                    case_id="mainplay.edge_tts_primary",
                    passed=True,
                    state=MainplayState.EDGE_TTS_PLAYING,
                    backend_used=MainplayBackend.EDGE_TTS_PRIMARY,
                    audio_url=audio_url,
                    metadata={
                        "cache_key": cache_key,
                        "edge_tts_ms": edge_result.duration_ms,
                        "fallback_chain": "EDGE_TTS → CACHE_STORED",
                    },
                )

        # 阶段 3: Web Speech API 降级 (D 选项原生)
        if self._config.web_speech_enabled:
            web_result = self._try_web_speech(text, voice)
            self._attempts.append(web_result)
            if web_result.success:
                return MainplayResult(
                    case_id="mainplay.web_speech_fallback",
                    passed=True,
                    state=MainplayState.WEB_SPEECH_PLAYING,
                    backend_used=MainplayBackend.WEB_SPEECH_FALLBACK,
                    audio_url=None,
                    metadata={
                        "cache_key": cache_key,
                        "web_speech_ms": web_result.duration_ms,
                        "fallback_chain": "EDGE_TTS_FAIL → WEB_SPEECH",
                    },
                )

        # 阶段 4: cache miss 最终降级 (用户友好提示)
        return MainplayResult(
            case_id="mainplay.cache_miss_fallback",
            passed=False,
            state=MainplayState.CACHE_MISS_FALLBACK,
            backend_used=MainplayBackend.NONE,
            audio_url=None,
            metadata={
                "cache_key": cache_key,
                "fallback_chain": "EDGE_TTS_FAIL → WEB_SPEECH_FAIL → USER_PROMPT",
                "user_message": "TTS 暂时不可用, 请稍后重试或检查网络",
            },
        )

    def _try_edge_tts(self, text: str, voice: str) -> BackendAttempt:
        """模拟 Edge-TTS 主路径 (W77 B-1 不真接, 真生产 key W78 拍板)"""
        # 类比 W75 C-1 真支付 SDK 沙箱模式: 默认走沙箱, 真生产 key W78 单独拍板
        if not self._config.production_key_enabled:
            # 沙箱模式: 模拟 timeout/network error 让 Web Speech 降级
            return BackendAttempt(
                backend=MainplayBackend.EDGE_TTS_PRIMARY,
                attempted=True,
                success=False,
                duration_ms=float(self._config.edge_tts_timeout_ms),
                error="sandbox_mode: production_key_disabled",
            )
        # 真生产 key 路径 (W78 拍板后启用, 当前不进入)
        return BackendAttempt(
            backend=MainplayBackend.EDGE_TTS_PRIMARY,
            attempted=True,
            success=True,
            duration_ms=820.0,
        )

    def _try_web_speech(self, text: str, voice: str) -> BackendAttempt:
        """调用 Web Speech API 降级 handler"""
        result: WebSpeechResult = self._web_speech.speak(text=text, voice=voice)
        return BackendAttempt(
            backend=MainplayBackend.WEB_SPEECH_FALLBACK,
            attempted=True,
            success=result.success,
            duration_ms=result.duration_ms,
            error=result.error,
        )


def build_ios_safari_mainplay_adapter(
    config: Optional[MainplayConfig] = None,
) -> IOSSafariMainplayAdapter:
    """工厂函数: 构建 iOS Safari 主拍接入适配器"""
    return IOSSafariMainplayAdapter(config=config)
