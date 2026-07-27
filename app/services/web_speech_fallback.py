"""Web Speech API 降级路径 (Android Chrome 原生 speechSynthesis).

W77 第 1 批 B-2 派工产物. 派工依据:
- W76 A-2 commit 0c3f848d7 §1.2 B+D 决策建议 (Web Speech API 降级路径)
- W77 A-2 B+D 渐进式实施方案设计
- 派工 v6 段 5 反馈 #6 渐进式实战

范畴:
- 新建 web_speech_fallback.py (Web Speech API 浏览器原生降级)
- 复用 app/services/android_tts_mainplay.py (B+D 渐进式主拍接入)
- 不动老路径 (audio_processor.py / tts.py)
- Android Chrome 80+ 原生 speechSynthesis.speak() 支持, 端到端降级
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class WebSpeechEvent(str, Enum):
    """Web Speech API 事件类型 (Android Chrome 原生)."""

    START = "start"
    END = "end"
    ERROR = "error"
    PAUSE = "pause"
    RESUME = "resume"
    MARK = "mark"
    BOUNDARY = "boundary"


@dataclass(frozen=True)
class WebSpeechConfig:
    """Web Speech API 配置 (Android Chrome 兼容)."""

    lang: str = "zh-CN"
    voice_name: str = ""           # 空字符串使用默认音色
    rate: float = 1.0               # 0.1 - 10.0
    pitch: float = 1.0              # 0.0 - 2.0
    volume: float = 1.0             # 0.0 - 1.0


@dataclass(frozen=True)
class WebSpeechResult:
    """Web Speech API 降级结果."""

    triggered: bool
    reason: str
    fallback_to_cache: bool = False


class WebSpeechFallback:
    """Android Chrome Web Speech API 降级路径 (B+D 渐进式 Stage 2).

    实战特性:
    - speechSynthesis.speak() 浏览器原生 API, 无需服务端合成
    - Android Chrome 80+ 完整支持
    - 监听 start/end/error/pause/resume 事件
    - 失败自动降级到 pre-synthesize 缓存
    """

    # Android Chrome 支持的 zh-CN 音色 (W73 A-2 调研)
    SUPPORTED_ZH_VOICES = (
        "Google 普通话（中国大陆）",
        "Google 中国国语",
    )

    def __init__(self, config: Optional[WebSpeechConfig] = None) -> None:
        self.config = config or WebSpeechConfig()
        logger.info(
            "WebSpeechFallback initialised (lang=%s, voice=%s)",
            self.config.lang,
            self.config.voice_name or "default",
        )

    def should_use(self, web_speech_available: bool, audio_focus_score: float) -> bool:
        """判定是否使用 Web Speech API 降级路径."""
        return web_speech_available and audio_focus_score > 0.0

    def synthesize(self, text: str) -> WebSpeechResult:
        """调用 Web Speech API 合成语音 (Android Chrome 浏览器端).

        注: 实际调用发生在浏览器端 (AndroidChrome), Python 端仅返回配置.
        """
        if not text or not text.strip():
            return WebSpeechResult(triggered=False, reason="empty_text")
        return WebSpeechResult(
            triggered=True,
            reason="web_speech_api_dispatch",
            fallback_to_cache=False,
        )

    @staticmethod
    def browser_hooks() -> str:
        """浏览器端 Web Speech API hooks (Android Chrome 原生)."""
        return """
function fallbackToWebSpeech(text) {
  if (!('speechSynthesis' in window)) return false
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0
  utterance.pitch = 1.0
  utterance.volume = 1.0

  utterance.addEventListener('start', () => console.info('[WebSpeech] start'))
  utterance.addEventListener('end', () => console.info('[WebSpeech] end'))
  utterance.addEventListener('error', (e) => {
    console.error('[WebSpeech] error', e.error)
    fallbackToCache(text)
  })

  speechSynthesis.speak(utterance)
  return true
}

async function fallbackToCache(text) {
  const cached = sessionStorage.getItem('tts-cache-' + text.slice(0, 32))
  if (cached) {
    const audio = new Audio(cached)
    await audio.play()
    return true
  }
  return false
}
""".strip()