"""Web Speech API 降级 handler (W77 第 1 批 B-1)

iOS Safari 原生 speechSynthesis 降级方案
依据: W76 A-2 §1.2 D 选项原生 fallback + W76 A-2 §3.2 方案 B 渐进式

iOS Safari 原生 Web Speech API:
- speechSynthesis.speak(utterance) 无需后端 API 调用
- 零网络依赖 (Edge-TTS 失败时立即可用)
- 受限: 音色少 (vs Edge-TTS ~300 音色), 停顿/语速参数精度差
- 优势: iOS Safari 原生支持, 不需任何后端凭证

W77 B-1 + A-2 协调: A-2 提供后端 Edge-TTS 入参适配
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("microbubble.web_speech_fallback")


class WebSpeechBackend(str, Enum):
    """Web Speech API backend 选项"""
    NATIVE_SPEECH_SYNTHESIS = "native_speech_synthesis"
    POLYFILLED = "polyfilled"
    DISABLED = "disabled"


@dataclass
class WebSpeechConfig:
    """Web Speech API 降级配置"""
    enable_native_speak: bool = True
    enable_voices_picking: bool = True
    default_lang: str = "zh-CN"
    timeout_ms: int = 3000
    fallback_voice: str = "default"


@dataclass
class WebSpeechResult:
    """Web Speech API 执行结果"""
    success: bool
    duration_ms: float
    voice_used: Optional[str] = None
    lang_used: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WebSpeechFallbackHandler:
    """iOS Safari 原生 Web Speech API 降级 handler

    职责:
    1. 包装 speechSynthesis.speak()
    2. 兜底音色选择 (iOS Safari 音色列表有限)
    3. 提供模拟执行结果 (用于 e2e 测试)
    """

    def __init__(self, config: Optional[WebSpeechConfig] = None) -> None:
        self._config = config or WebSpeechConfig()
        self._voices_seen: Dict[str, int] = {}

    def speak(self, text: str, voice: Optional[str] = None) -> WebSpeechResult:
        """降级到 Web Speech API speak()

        沙箱模式: 模拟 iOS Safari 原生 speechSynthesis 行为
        生产模式: 调用 speechSynthesis.speak() 真原生 API
        """
        start = time.monotonic()
        if not self._config.enable_native_speak:
            return WebSpeechResult(
                success=False,
                duration_ms=(time.monotonic() - start) * 1000,
                error="web_speech_disabled",
            )
        if not text.strip():
            return WebSpeechResult(
                success=False,
                duration_ms=(time.monotonic() - start) * 1000,
                error="empty_text",
            )

        # 模拟执行 (e2e 沙箱; 真生产将由前端调用)
        voice_used = voice or self._config.fallback_voice
        self._voices_seen[voice_used] = self._voices_seen.get(voice_used, 0) + 1
        elapsed_ms = (time.monotonic() - start) * 1000 + 50.0  # base 50ms

        return WebSpeechResult(
            success=True,
            duration_ms=elapsed_ms,
            voice_used=voice_used,
            lang_used=self._config.default_lang,
            metadata={
                "backend": WebSpeechBackend.NATIVE_SPEECH_SYNTHESIS.value,
                "text_length": len(text),
            },
        )

    def list_voices(self) -> Dict[str, int]:
        return dict(self._voices_seen)


def build_web_speech_fallback_handler(
    config: Optional[WebSpeechConfig] = None,
) -> WebSpeechFallbackHandler:
    return WebSpeechFallbackHandler(config=config)
