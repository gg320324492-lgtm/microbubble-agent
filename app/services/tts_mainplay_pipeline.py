"""Edge-TTS B+D 组合渐进式跨平台整合平台 (W78 第 1 批 B-1).

派工 v4 铁律 3 真验证 3 步:
1. A-2 W77 commit 44cf83581 docs/w77-1st-batch-a2-edge-tts-bd-plan-2026-07-28.md §5.3 W78 B-1
2. W77 B-1 commit bedcd4594 (ios_tts_mainplay.py) + W77 B-2 commit cc3326409 (android_tts_mainplay.py)
3. app/services/audio_processor.py (195 行 VAD) + app/voice/tts.py (110 行 Edge-TTS) 老链路 — 不动

依据: W76 A-2 commit 0c3f848d7 §3 B+D 决策 + 派工 v6 段 5 反馈 #6 渐进式实战

=== 本模块解决的问题 ===

W77 B-1 (iOS Safari) 与 W77 B-2 (Android Chrome) 各自独立落地了一套主拍接入,
调用方签名完全不同:

    # W77 B-1 iOS
    adapter.play(text, voice, prefer_cached=True) -> MainplayResult(backend_used=MainplayBackend)
    # W77 B-2 Android
    mainplay.execute(MainplayRequest(...))        -> MainplayDecision(route=MainplayRoute)

前端 / Agent 侧要接 TTS 必须自己判平台 + 写两套分支。本模块提供**单一入口**:

    pipeline = build_tts_mainplay_pipeline()
    result = pipeline.synthesize("会议纪要已生成", user_agent=request_ua)

平台判定 + 音频格式差异 (iOS MP3 降级 / Android OGG Vorbis 原生) + 缓存 key
归一 + 类 20.13 真生产 key 守门全部收敛在这里, 两个老 adapter 一行不改。

=== 5 阶段实战 (A-2 §5.3 W78 B-1) ===

1. **Edge-TTS 渐进式**  — 委派 W77 B-1 IOSSafariMainplayAdapter / W77 B-2 AndroidTTSMainplay
2. **Web Speech API 降级** — 委派各平台原生 speechSynthesis (iOS / Android 各自 handler)
3. **pre-synthesize 缓存** — 跨平台 + 跨音色统一 store (24h TTL, key 含 audio_format)
4. **跨平台整合** — Platform 判定 + backend 归一 + fallback_chain 归一
5. **监控容错** — hit_rate / P95 / 8 件套监控接入点 + 优雅降级到用户提示

=== 类 20.13 真生产 key 守门 ===

Edge-TTS 真生产 key **不在 W78 B-1 自动启用** — 由 W78-B-2 单独拍板。
本模块 `PipelineConfig.production_key_enabled` 默认 False (沙箱), 沙箱下即使平台
adapter 判定走 Edge-TTS 路径, `_apply_prod_key_gate` 也会改判为 Web Speech 原生降级
(无真 key 时 Edge-TTS 必然失败, 提前改判避免用户等 5s timeout)。

范畴: app/services/ 新建 (0 production code 改动铁律例外 1 已批)
不修改: audio_processor.py / app/voice/tts.py / ios_tts_mainplay.py / android_tts_mainplay.py
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# W77 B-1 iOS Safari 主拍接入 (不改, 仅委派)
from app.services.ios_tts_mainplay import (
    IOSSafariMainplayAdapter,
    MainplayBackend as IOSBackend,
    MainplayConfig as IOSConfig,
)

# W77 B-2 Android Chrome 主拍接入 (不改, 仅委派)
from app.services.android_tts_mainplay import (
    AndroidTTSMainplay,
    MainplayRequest as AndroidRequest,
    MainplayRoute as AndroidRoute,
)

# 跨平台统一缓存 store (W77 B-1 + W78 B-1 合并, W83 B-2 P1-1 收敛)
from app.services.tts_cache import TTSCacheStore, build_tts_cache_store

logger = logging.getLogger("microbubble.tts_mainplay_pipeline")


class Platform(str, Enum):
    """目标平台 (W76 B-1/B-2 4 维度实战覆盖的两个平台)."""

    IOS_SAFARI = "ios_safari"
    ANDROID_CHROME = "android_chrome"
    UNKNOWN = "unknown"


class PipelineBackend(str, Enum):
    """归一后的 backend (iOS MainplayBackend + Android MainplayRoute 统一投影)."""

    EDGE_TTS = "edge_tts"          # B 选项主路径 (真生产 key 启用后)
    WEB_SPEECH = "web_speech"      # D 选项浏览器原生降级
    CACHE = "cache"                # D 选项 pre-synthesize 缓存命中
    NONE = "none"                  # 全部失败 → 用户友好提示


class PipelineStage(str, Enum):
    """5 阶段常量 (A-2 §5.3 W78 B-1)."""

    EDGE_TTS_PROGRESSIVE = "edge_tts_progressive"
    WEB_SPEECH_FALLBACK = "web_speech_fallback"
    PRE_SYNTHESIZE_CACHE = "pre_synthesize_cache"
    CROSS_PLATFORM_UNIFY = "cross_platform_unify"
    MONITORING_FAULT_TOLERANCE = "monitoring_fault_tolerance"


# 平台 → Edge-TTS 交付音频格式 (W76 B-1 iOS OGG→MP3 降级 / W76 B-2 Android OGG 原生保留)
PLATFORM_AUDIO_FORMAT: Dict[Platform, str] = {
    Platform.IOS_SAFARI: "mp3",
    Platform.ANDROID_CHROME: "ogg",
    Platform.UNKNOWN: "mp3",
}


@dataclass
class PipelineConfig:
    """跨平台整合配置."""

    # 阶段 1 Edge-TTS 渐进式
    edge_tts_enabled: bool = True
    # 阶段 2 Web Speech API 降级
    web_speech_enabled: bool = True
    # 阶段 3 pre-synthesize 缓存
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400          # 24h (W73 录音断网防御参考)
    cache_max_size: int = 10_000
    # 类 20.13: 真生产 key 主拍由 W78-B-2 单独拍板, W78 B-1 不自动启用
    production_key_enabled: bool = False
    # 阶段 5 监控
    enable_monitoring: bool = True
    cache_p95_budget_ms: float = 50.0       # 缓存命中 SLA


@dataclass
class PipelineResult:
    """跨平台整合执行结果 (归一后的对外契约)."""

    platform: Platform
    backend_used: PipelineBackend
    passed: bool
    audio_format: str
    cache_key: str
    fallback_chain: List[str] = field(default_factory=list)
    audio_url: Optional[str] = None
    native_state: Optional[str] = None       # 平台 adapter 原始状态 (可追溯)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """阶段 5 监控指标."""

    calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    edge_tts_used: int = 0
    web_speech_used: int = 0
    exhausted: int = 0
    prod_key_gate_downgrades: int = 0
    max_cache_hit_ms: float = 0.0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
            "edge_tts_used": self.edge_tts_used,
            "web_speech_used": self.web_speech_used,
            "exhausted": self.exhausted,
            "prod_key_gate_downgrades": self.prod_key_gate_downgrades,
            "max_cache_hit_ms": self.max_cache_hit_ms,
        }


class TTSMainplayPipeline:
    """Edge-TTS B+D 组合渐进式跨平台整合平台.

    统一调用接口:
        pipeline.synthesize(text, voice=..., platform=..., user_agent=...)

    渐进式保证 (派工 v6 段 5 反馈 #6):
    - W77 B-1 ios_tts_mainplay.py 一行不改 (20/20 e2e 保持)
    - W77 B-2 android_tts_mainplay.py 一行不改 (20/20 e2e 保持)
    - audio_processor.py / app/voice/tts.py 老 TTS 链路一行不改
    """

    # 类 20.13 实战: 真生产 key 主拍由 W78-B-2 单独拍板 (与 Android 侧常量语义一致)
    PROD_KEY_AUTO_ENABLE = False

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        cache_store: Optional[TTSCacheStore] = None,
        ios_adapter: Optional[IOSSafariMainplayAdapter] = None,
        android_adapter: Optional[AndroidTTSMainplay] = None,
    ) -> None:
        self._config = config or PipelineConfig()
        # 跨平台 + 跨音色统一缓存 (cache key 含 platform audio_format, 防 iOS 拿到 OGG)
        self._cache = cache_store or build_tts_cache_store(
            ttl_seconds=self._config.cache_ttl_seconds,
            max_size=self._config.cache_max_size,
        )
        # 平台 adapter 的 cache 关掉 — 缓存统一在 pipeline 层, 避免双层计数污染 hit_rate
        self._ios = ios_adapter or IOSSafariMainplayAdapter(
            config=IOSConfig(
                edge_tts_enabled=self._config.edge_tts_enabled,
                web_speech_enabled=self._config.web_speech_enabled,
                cache_enabled=False,
                production_key_enabled=self._config.production_key_enabled,
            ),
        )
        self._android = android_adapter or AndroidTTSMainplay()
        self.metrics = PipelineMetrics()
        logger.info(
            "TTSMainplayPipeline initialised (B+D 渐进式, production_key_enabled=%s, "
            "类 20.13 真生产 key 主拍 W78-B-2 单独拍板)",
            self._config.production_key_enabled,
        )

    # ── 阶段 4: 跨平台整合 ────────────────────────────────────────

    @staticmethod
    def detect_platform(user_agent: Optional[str]) -> Platform:
        """从 UA 判定平台 (与 web/src/composables/useIsMobile.js UA 兜底同源思路).

        判定顺序要点: Android 必须先判 — Android Chrome 的 UA 同时含 "Safari",
        先判 iOS 会把 Android 误判成 iOS Safari。
        """
        if not user_agent:
            return Platform.UNKNOWN
        ua = user_agent.lower()
        if "android" in ua:
            return Platform.ANDROID_CHROME
        if ("iphone" in ua or "ipad" in ua or "ipod" in ua) and "safari" in ua:
            return Platform.IOS_SAFARI
        return Platform.UNKNOWN

    def cache_key(self, text: str, voice: str, audio_format: str) -> str:
        """统一缓存 key — 含 audio_format, 防跨平台格式串味 (iOS MP3 vs Android OGG)."""
        raw = f"{text.strip().lower()}|{voice.strip().lower()}|{audio_format.lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    # ── 类 20.13 真生产 key 守门 ──────────────────────────────────

    def _apply_prod_key_gate(self, backend: PipelineBackend) -> PipelineBackend:
        """沙箱模式下 Edge-TTS 改判为 Web Speech 原生降级.

        真生产 key 未拍板 (W78-B-2) 时无有效凭证, Edge-TTS 必然 timeout 失败。
        提前改判避免用户白等 edge_tts_timeout_ms, 同时保持 Web Speech 可用性。
        """
        if backend is not PipelineBackend.EDGE_TTS:
            return backend
        if self._config.production_key_enabled:
            return backend
        self.metrics.prod_key_gate_downgrades += 1
        if not self._config.web_speech_enabled:
            return PipelineBackend.NONE
        return PipelineBackend.WEB_SPEECH

    # ── 平台委派 (阶段 1 + 阶段 2) ────────────────────────────────

    _IOS_BACKEND_MAP: Dict[IOSBackend, PipelineBackend] = {
        IOSBackend.EDGE_TTS_PRIMARY: PipelineBackend.EDGE_TTS,
        IOSBackend.WEB_SPEECH_FALLBACK: PipelineBackend.WEB_SPEECH,
        IOSBackend.CACHE_PRE_SYNTHESIZED: PipelineBackend.CACHE,
        IOSBackend.NONE: PipelineBackend.NONE,
    }

    _ANDROID_ROUTE_MAP: Dict[AndroidRoute, PipelineBackend] = {
        AndroidRoute.EDGE_TTS: PipelineBackend.EDGE_TTS,
        AndroidRoute.WEB_SPEECH_API: PipelineBackend.WEB_SPEECH,
        AndroidRoute.PRE_SYNTHESIZED_CACHE: PipelineBackend.CACHE,
        AndroidRoute.USER_PROMPT: PipelineBackend.NONE,
    }

    def _delegate_ios(self, text: str, voice: str) -> tuple:
        """委派 W77 B-1 IOSSafariMainplayAdapter (prefer_cached=False, 缓存在 pipeline 层)."""
        native = self._ios.play(text=text, voice=voice, prefer_cached=False)
        backend = self._IOS_BACKEND_MAP.get(native.backend_used, PipelineBackend.NONE)
        return backend, native.state.value, dict(native.metadata)

    def _delegate_android(
        self,
        text: str,
        voice: str,
        *,
        user_gesture: bool,
        visible: bool,
        audio_focus_score: float,
    ) -> tuple:
        """委派 W77 B-2 AndroidTTSMainplay (cache_hit=False, 缓存在 pipeline 层)."""
        decision = self._android.execute(
            AndroidRequest(
                text=text,
                voice=voice,
                audio_format=PLATFORM_AUDIO_FORMAT[Platform.ANDROID_CHROME],
                user_gesture=user_gesture,
                visible=visible,
                audio_focus_score=audio_focus_score,
                cache_hit=False,
                web_speech_available=self._config.web_speech_enabled,
            )
        )
        backend = self._ANDROID_ROUTE_MAP.get(decision.route, PipelineBackend.NONE)
        meta = {
            "android_reason": decision.reason,
            "android_fallback_chain": list(decision.fallback_chain),
            "retry_after_seconds": decision.retry_after_seconds,
        }
        return backend, decision.route.value, meta

    # ── 统一入口 ──────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        *,
        platform: Optional[Platform] = None,
        user_agent: Optional[str] = None,
        user_gesture: bool = True,
        visible: bool = True,
        audio_focus_score: float = 1.0,
        prefer_cached: bool = True,
    ) -> PipelineResult:
        """B+D 组合渐进式跨平台统一合成入口.

        阶段顺序:
        1. pre-synthesize 缓存命中 → 立即返回 (阶段 3, P95 < 50ms)
        2. 平台 adapter 委派 (阶段 1 Edge-TTS 渐进式 + 阶段 2 Web Speech 降级)
        3. 类 20.13 真生产 key 守门改判 (沙箱 Edge-TTS → Web Speech)
        4. Edge-TTS 成功 → 回写缓存 (供下次命中)
        5. 全部失败 → 用户友好提示 (阶段 5 优雅降级)
        """
        started = time.monotonic()
        self.metrics.calls += 1

        resolved = platform or self.detect_platform(user_agent)
        audio_format = PLATFORM_AUDIO_FORMAT[resolved]
        key = self.cache_key(text, voice, audio_format)
        chain: List[str] = [PipelineStage.CROSS_PLATFORM_UNIFY.value]

        if not text or not text.strip():
            return PipelineResult(
                platform=resolved,
                backend_used=PipelineBackend.NONE,
                passed=False,
                audio_format=audio_format,
                cache_key=key,
                fallback_chain=chain,
                duration_ms=(time.monotonic() - started) * 1000,
                metadata={"error": "empty_text"},
            )

        # 阶段 3: pre-synthesize 缓存查询 (跨平台 + 跨音色)
        if self._config.cache_enabled and prefer_cached:
            cached = self._cache.get(key)
            chain.append(PipelineStage.PRE_SYNTHESIZE_CACHE.value)
            if cached is not None:
                self.metrics.cache_hits += 1
                elapsed = (time.monotonic() - started) * 1000
                self.metrics.max_cache_hit_ms = max(self.metrics.max_cache_hit_ms, elapsed)
                return PipelineResult(
                    platform=resolved,
                    backend_used=PipelineBackend.CACHE,
                    passed=True,
                    audio_format=audio_format,
                    cache_key=key,
                    fallback_chain=chain,
                    audio_url=cached.audio_url,
                    native_state="cache_hit_playing",
                    duration_ms=elapsed,
                    metadata={
                        "hit": True,
                        "ttl_seconds": cached.ttl_seconds,
                        "within_p95_budget": elapsed <= self._config.cache_p95_budget_ms,
                    },
                )
            self.metrics.cache_misses += 1

        # 阶段 1 + 阶段 2: 平台 adapter 委派
        if resolved is Platform.ANDROID_CHROME:
            backend, native_state, native_meta = self._delegate_android(
                text,
                voice,
                user_gesture=user_gesture,
                visible=visible,
                audio_focus_score=audio_focus_score,
            )
        else:
            # iOS Safari + UNKNOWN 都走 iOS adapter (MP3 最保守, 兼容面最广)
            backend, native_state, native_meta = self._delegate_ios(text, voice)
        chain.append(PipelineStage.EDGE_TTS_PROGRESSIVE.value)

        # 类 20.13 守门: 沙箱模式 Edge-TTS → Web Speech 原生降级
        gated = self._apply_prod_key_gate(backend)
        if gated is not backend:
            native_meta["prod_key_gate"] = (
                f"{backend.value} → {gated.value} (production_key_enabled=False, W78-B-2 待拍板)"
            )
            backend = gated

        if backend is PipelineBackend.WEB_SPEECH:
            chain.append(PipelineStage.WEB_SPEECH_FALLBACK.value)
            self.metrics.web_speech_used += 1
            return PipelineResult(
                platform=resolved,
                backend_used=backend,
                passed=True,
                audio_format=audio_format,
                cache_key=key,
                fallback_chain=chain,
                audio_url=None,
                native_state=native_state,
                duration_ms=(time.monotonic() - started) * 1000,
                metadata=native_meta,
            )

        if backend is PipelineBackend.EDGE_TTS:
            self.metrics.edge_tts_used += 1
            audio_url = f"blob:edge-tts/{key}.{audio_format}"
            # 阶段 3 回写: 供下次命中 (24h TTL)
            if self._config.cache_enabled:
                self._cache.put(key, audio_url=audio_url, text=text, voice=voice)
                chain.append(PipelineStage.PRE_SYNTHESIZE_CACHE.value)
            return PipelineResult(
                platform=resolved,
                backend_used=backend,
                passed=True,
                audio_format=audio_format,
                cache_key=key,
                fallback_chain=chain,
                audio_url=audio_url,
                native_state=native_state,
                duration_ms=(time.monotonic() - started) * 1000,
                metadata=native_meta,
            )

        if backend is PipelineBackend.CACHE:
            # 平台 adapter 自报缓存命中 (pipeline 缓存已关, 理论不进; 保留归一分支)
            return PipelineResult(
                platform=resolved,
                backend_used=backend,
                passed=True,
                audio_format=audio_format,
                cache_key=key,
                fallback_chain=chain,
                native_state=native_state,
                duration_ms=(time.monotonic() - started) * 1000,
                metadata=native_meta,
            )

        # 阶段 5: 全部失败 → 用户友好提示 (优雅降级, 不抛异常打断业务)
        self.metrics.exhausted += 1
        chain.append(PipelineStage.MONITORING_FAULT_TOLERANCE.value)
        native_meta["user_message"] = "TTS 暂时不可用, 请稍后重试或检查网络"
        return PipelineResult(
            platform=resolved,
            backend_used=PipelineBackend.NONE,
            passed=False,
            audio_format=audio_format,
            cache_key=key,
            fallback_chain=chain,
            native_state=native_state,
            duration_ms=(time.monotonic() - started) * 1000,
            metadata=native_meta,
        )

    # ── 阶段 5: 监控接入点 ────────────────────────────────────────

    def monitoring_snapshot(self) -> Dict[str, Any]:
        """监控快照 (scripts/monitor-edge-tts.sh 消费).

        接入既有监控件: W73 B-2 4 类 hot-fix + W74 D-1 多租户 + W75 B-3 webhook
        + W77 B-3 真支付 → 本模块补齐 TTS 维度。
        """
        return {
            "pipeline": self.metrics.as_dict(),
            "cache_store": self._cache.metrics(),
            "production_key_enabled": self._config.production_key_enabled,
            "prod_key_decision": "W78-B-2 单独拍板 (类 20.13, 不在 W78 B-1 自动启用)",
            "cache_p95_budget_ms": self._config.cache_p95_budget_ms,
            "cache_p95_within_budget": (
                self.metrics.max_cache_hit_ms <= self._config.cache_p95_budget_ms
            ),
        }

    def prewarm(
        self,
        text: str,
        voice: str,
        *,
        platform: Platform,
        audio_url: str,
    ) -> str:
        """pre-synthesize 预热 (批量离线合成后回填缓存), 返回 cache key."""
        audio_format = PLATFORM_AUDIO_FORMAT[platform]
        key = self.cache_key(text, voice, audio_format)
        self._cache.put(key, audio_url=audio_url, text=text, voice=voice)
        return key


def build_tts_mainplay_pipeline(
    config: Optional[PipelineConfig] = None,
) -> TTSMainplayPipeline:
    """工厂函数: 构建跨平台 B+D 组合渐进式整合平台."""
    return TTSMainplayPipeline(config=config)
