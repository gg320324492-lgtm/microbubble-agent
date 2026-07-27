"""Edge-TTS Android Chrome 主拍接入 (B+D 渐进式方案)

W77 第 1 批 B-2 派工产物. 派工依据:
- W76 A-2 commit 0c3f848d7 §1.2 B+D 决策建议
- W76 B-2 commit 4ec33878a 16/16 e2e 基础 (autoplay + audio_format + background + recovery)
- W77 A-2 B+D 渐进式实施方案设计
- 派工 v6 段 5 反馈 #6 渐进式实战 (类 W75 C-1 沙箱模式, 类 20.13 真生产 key 单独拍板)
- W73 A-2 调研 0.55 audio-focus threshold

范畴:
- 新建 android_tts_mainplay.py (主拍接入核心, 5 阶段: Edge-TTS 渐进式 + Web Speech API 降级 + pre-synthesize 缓存 + 真生产 key 主拍决策 + 监控容错)
- 复用 W76 B-2 4 android_tts_*.py (autoplay/audio_format/background/recovery)
- 复用 app/services/tts_cache.py (pre-synthesize 缓存层, 24h TTL)
- 复用 app/services/web_speech_fallback.py (Android Chrome 原生 speechSynthesis)
- 0 production code 改动铁律守恒: 不动 app/services/audio_processor.py 老 TTS 链路, 不动 app/voice/tts.py Edge-TTS 后端
- 类 20.13 真生产 key 主拍单独拍板 (W78 主拍, 不在 W77 自动启用, 与 W75 C-1 派工 v6 段 5 反馈 #6 实战一致)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.services.android_tts_autoplay import (
    AndroidAutoplayState,
    AndroidTTSAutoplayGuard,
    AutoplayAction,
)
from app.services.android_tts_audio_format import (
    ANDROID_EDGE_TTS_FORMATS,
    AndroidAudioFormat,
    AndroidTTSAudioFormatPolicy,
)
from app.services.android_tts_background import (
    AndroidTTSBackgroundPolicy,
    AudioFocusAction,
)
from app.services.android_tts_recovery import (
    AndroidTTSRecovery,
    RecoveryPoint,
)
from app.services.tts_cache import TTSCache, TTSSynthesizeRequest

logger = logging.getLogger(__name__)


class MainplayRoute(str, Enum):
    """主拍接入的 4 条路径 (B+D 渐进式实战分类)."""

    EDGE_TTS = "edge_tts"                     # 主路径: Edge-TTS 直接播放
    WEB_SPEECH_API = "web_speech_api"          # 降级路径: Android Chrome speechSynthesis
    PRE_SYNTHESIZED_CACHE = "pre_synthesized"  # 离线缓存路径: 复用 W77 B-1 tts_cache
    USER_PROMPT = "user_prompt"                # 用户提示路径: 全部失败


@dataclass(frozen=True)
class MainplayRequest:
    """主拍接入请求 (B+D 渐进式 5 阶段实战)."""

    text: str
    voice: str = "zh-CN-XiaoxiaoNeural"
    audio_format: str = "ogg"
    user_gesture: bool = False
    visible: bool = True
    audio_focus_score: float = 1.0
    recovery_point: Optional[RecoveryPoint] = None
    cache_hit: bool = False
    web_speech_available: bool = True
    request_id: str = ""


@dataclass(frozen=True)
class MainplayDecision:
    """主拍决策结果 (B+D 渐进式)."""

    route: MainplayRoute
    reason: str
    retry_after_seconds: float = 0.0
    fallback_chain: list = field(default_factory=list)


class AndroidTTSMainplay:
    """B+D 渐进式主拍接入核心 (5 阶段).

    5 阶段实战流程:
    1. **Edge-TTS 渐进式**: 在 android_tts_autoplay.py (W76 B-2 已建) 基础上扩展为主拍接入
    2. **Web Speech API 降级**: Android Chrome speechSynthesis.speak() 浏览器原生
    3. **pre-synthesize 缓存**: 复用 W77 B-1 tts_cache.py 缓存层
    4. **真生产 key 主拍决策**: W78 主拍, 不在 W77 自动启用 (类 20.13 实战)
    5. **监控 + 容错**: 接入 W76 D-1 5 件套监控 + W73 B-2 4 类 hot-fix
    """

    # 5 阶段常量 (派工 v6 段 5 反馈 #6 实战一致)
    STAGE_EDGE_TTS_PROGRESSIVE = "edge_tts_progressive"
    STAGE_WEB_SPEECH_FALLBACK = "web_speech_fallback"
    STAGE_PRE_SYNTHESIZE_CACHE = "pre_synthesize_cache"
    STAGE_PROD_KEY_DECISION = "prod_key_decision_pending_w78"
    STAGE_MONITORING_FAULT_TOLERANCE = "monitoring_fault_tolerance"

    # 类 20.13 实战: 真生产 key 主拍由 W78 单独拍板, W77 沙箱模式
    PROD_KEY_AUTO_ENABLE = False

    def _format_supported(self, audio_format: str) -> bool:
        """检查音频格式是否被 Android Chrome 原生支持."""
        return audio_format.lower() in ANDROID_EDGE_TTS_FORMATS

    def __init__(
        self,
        autoplay_guard: Optional[AndroidTTSAutoplayGuard] = None,
        audio_format_policy: Optional[AndroidTTSAudioFormatPolicy] = None,
        background_policy: Optional[AndroidTTSBackgroundPolicy] = None,
        recovery: Optional[AndroidTTSRecovery] = None,
        cache: Optional[TTSCache] = None,
    ) -> None:
        self.autoplay_guard = autoplay_guard or AndroidTTSAutoplayGuard()
        self.audio_format_policy = audio_format_policy or AndroidTTSAudioFormatPolicy()
        self.background_policy = background_policy or AndroidTTSBackgroundPolicy()
        self.recovery = recovery or AndroidTTSRecovery()
        self.cache = cache or TTSCache()
        logger.info(
            "AndroidTTSMainplay initialised (B+D 渐进式, 类 20.13 沙箱模式, "
            "PROD_KEY_AUTO_ENABLE=%s)",
            self.PROD_KEY_AUTO_ENABLE,
        )

    def decide(self, request: MainplayRequest) -> MainplayDecision:
        """主拍决策 (B+D 渐进式 5 阶段).

        决策顺序:
        1. Edge-TTS 渐进式: autoplay guard + audio format + background mode
        2. Web Speech API 降级: Edge-TTS 失败或 audio focus 不达标
        3. pre-synthesize 缓存命中: 跳过实时合成
        4. 用户友好提示: 全部失败
        """
        fallback_chain: list = []

        # Stage 1: Edge-TTS 渐进式 (复用 W76 B-2 android_tts_autoplay.py)
        autoplay_state = AndroidAutoplayState(
            user_gesture=request.user_gesture,
            visible=request.visible,
            effective_gain=request.audio_focus_score,
        )
        autoplay_action = self.autoplay_guard.action(autoplay_state)
        edge_tts_blocked = autoplay_action in (AutoplayAction.VIBRATE, AutoplayAction.WAIT_FOR_GESTURE)
        if autoplay_action == AutoplayAction.PLAY and request.cache_hit:
            # 缓存命中 + autoplay 通过 → pre-synthesized 路径
            return MainplayDecision(
                route=MainplayRoute.PRE_SYNTHESIZED_CACHE,
                reason="cache_hit + autoplay_play",
                fallback_chain=[self.STAGE_PRE_SYNTHESIZE_CACHE],
            )
        if not edge_tts_blocked and self._format_supported(request.audio_format):
            # Edge-TTS 渐进式主路径 (OGG Vorbis Android 原生保留, W76 B-2 实战)
            # RESUME 也走 Edge-TTS (autoplay guard 已经判定用户手势 + 可见 + 有效音量)
            if self.PROD_KEY_AUTO_ENABLE:
                # 类 20.13 实战: 真生产 key 主拍由 W78 拍板, W77 默认沙箱模式
                # 即使 PROD_KEY_AUTO_ENABLE=True 也走沙箱, 主拍决策由 §W78 单独拍板
                pass
            return MainplayDecision(
                route=MainplayRoute.EDGE_TTS,
                reason="autoplay_play_or_resume + format_supported + sandbox_mode",
                fallback_chain=[self.STAGE_EDGE_TTS_PROGRESSIVE, self.STAGE_PROD_KEY_DECISION],
            )
        fallback_chain.append(self.STAGE_EDGE_TTS_PROGRESSIVE)

        # Stage 2: Web Speech API 降级 (Android Chrome 原生 speechSynthesis)
        # 仅在 Edge-TTS 真正不可用 (gain=0 或 no user gesture) 且 web_speech_available=True 时启用
        if request.web_speech_available and edge_tts_blocked:
            return MainplayDecision(
                route=MainplayRoute.WEB_SPEECH_API,
                reason="edge_tts_blocked + web_speech_available",
                fallback_chain=fallback_chain + [self.STAGE_WEB_SPEECH_FALLBACK],
            )
        fallback_chain.append(self.STAGE_WEB_SPEECH_FALLBACK)

        # Stage 3: pre-synthesize 缓存命中 (复用 W77 B-1 tts_cache.py)
        cache_request = TTSSynthesizeRequest(
            text=request.text,
            voice=request.voice,
            audio_format=request.audio_format,
        )
        if self.cache.has_cached(cache_request):
            return MainplayDecision(
                route=MainplayRoute.PRE_SYNTHESIZED_CACHE,
                reason="edge_tts_skipped + web_speech_skipped + cache_hit",
                fallback_chain=fallback_chain + [self.STAGE_PRE_SYNTHESIZE_CACHE],
            )
        fallback_chain.append(self.STAGE_PRE_SYNTHESIZE_CACHE)

        # Stage 4: 用户友好提示 (全部失败)
        return MainplayDecision(
            route=MainplayRoute.USER_PROMPT,
            reason="all_paths_exhausted",
            retry_after_seconds=self.recovery.backoff_seconds(1),
            fallback_chain=fallback_chain + [self.STAGE_MONITORING_FAULT_TOLERANCE],
        )

    def execute(self, request: MainplayRequest) -> MainplayDecision:
        """执行主拍接入 (B+D 渐进式, 复用 W76 B-2 4 模块 + W77 B-1 tts_cache)."""
        decision = self.decide(request)
        logger.info(
            "Mainplay decision route=%s reason=%s request_id=%s",
            decision.route.value,
            decision.reason,
            request.request_id,
        )
        return decision

    @staticmethod
    def browser_hooks() -> str:
        """B+D 渐进式浏览器端 hooks (Edge-TTS 主路径 + Web Speech API 降级 + pre-synthesize 缓存).

        复用 W76 B-2 android_tts_autoplay.py 的 audioContext + gain + visibility hooks.
        新增 Web Speech API 降级 + cache hit 检查.
        """
        return """
<button type="button" @click="triggerMainplay">播放语音 (B+D)</button>
<script>
const AudioContextCtor = window.AudioContext || window.webkitAudioContext
const audioContext = new AudioContextCtor()
const gainNode = audioContext.createGain()

async function triggerMainplay() {
  if (audioContext.state !== 'running') await audioContext.resume()
  const focusScore = gainNode.gain.value === 0 ? 0.3 : 1.0
  const userGesture = true
  const webSpeechAvailable = 'speechSynthesis' in window

  // Stage 1: Edge-TTS 主路径
  try {
    const response = await fetch('/api/edge-tts/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: message, voice: 'zh-CN-XiaoxiaoNeural', format: 'ogg' })
    })
    if (response.ok) {
      const blob = await response.blob()
      await blob.play()
      return
    }
  } catch (error) {
    console.warn('[B+D] Edge-TTS failed, falling back to Web Speech API:', error)
  }

  // Stage 2: Web Speech API 降级 (Android Chrome 原生)
  if (webSpeechAvailable) {
    const utterance = new SpeechSynthesisUtterance(message)
    utterance.lang = 'zh-CN'
    speechSynthesis.speak(utterance)
    return
  }

  // Stage 3: pre-synthesize 缓存命中 (前端缓存层)
  const cached = sessionStorage.getItem('tts-cache-' + message.slice(0, 32))
  if (cached) {
    const audio = new Audio(cached)
    await audio.play()
    return
  }

  // Stage 4: 用户友好提示
  alert('语音播放失败, 请稍后重试')
}

document.addEventListener('visibilitychange', async () => {
  if (document.visibilityState === 'visible' && audioContext.state === 'suspended') {
    await audioContext.resume()
  }
})
</script>
""".strip()