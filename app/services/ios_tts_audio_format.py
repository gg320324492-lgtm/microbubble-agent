"""iOS Safari 音频格式检测 + 降级 (W76 第 1 批 B-1)

派工 v6 段 5 反馈 #6 渐进式实战 — 不破坏老 TTS 链路
依据: W75 A-2 调研 §2.2 4 case 实战汇总 (commit f538e3cf6)

4 实战 (iOS Safari 音频格式支持):
1. mp3 24kHz — iOS Safari 原生支持, 无降级
2. wav 16kHz — iOS Safari 原生支持, 无降级
3. ogg vorbis — iOS Safari **不支持**, 必降级到 mp3
4. aac — iOS Safari 原生支持, 无降级

格式检测: Audio.canPlayType('audio/ogg; codecs="vorbis"')
范畴: app/services/ 新建 (0 production code 改动铁律守恒)
不修改: app/services/audio_processor.py, app/api/v1/voice.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.ios_tts_audio_format")


class AudioFormat(str, Enum):
    """TTS 输出音频格式"""
    MP3 = "mp3"
    WAV = "wav"
    OGG_VORBIS = "ogg"
    AAC = "aac"


class IOSSupportLevel(str, Enum):
    """iOS Safari 格式支持等级"""
    NATIVE = "native"            # 原生支持
    NEEDS_FALLBACK = "fallback"  # 需降级
    UNSUPPORTED = "unsupported"  # 不支持


@dataclass
class FormatCapability:
    """iOS Safari 格式能力"""
    format: AudioFormat
    mime_type: str
    can_play_type_probe: str   # canPlayType 探针字符串
    ios_support: IOSSupportLevel
    fallback_to: Optional[AudioFormat] = None
    notes: str = ""


# iOS Safari 16+ 格式能力表 (Apple 官方 + 实测)
IOS_SAFARI_FORMAT_CAPABILITIES: Dict[AudioFormat, FormatCapability] = {
    AudioFormat.MP3: FormatCapability(
        format=AudioFormat.MP3,
        mime_type="audio/mpeg",
        can_play_type_probe='audio/mpeg; codecs="mp3"',
        ios_support=IOSSupportLevel.NATIVE,
        notes="iOS Safari 全版本支持 MP3 24kHz mono",
    ),
    AudioFormat.WAV: FormatCapability(
        format=AudioFormat.WAV,
        mime_type="audio/wav",
        can_play_type_probe='audio/wav; codecs="1"',
        ios_support=IOSSupportLevel.NATIVE,
        notes="iOS Safari 全版本支持 WAV 16-bit PCM",
    ),
    AudioFormat.OGG_VORBIS: FormatCapability(
        format=AudioFormat.OGG_VORBIS,
        mime_type="audio/ogg",
        can_play_type_probe='audio/ogg; codecs="vorbis"',
        ios_support=IOSSupportLevel.NEEDS_FALLBACK,
        fallback_to=AudioFormat.MP3,
        notes="iOS Safari 不支持 OGG Vorbis, 必降级到 MP3",
    ),
    AudioFormat.AAC: FormatCapability(
        format=AudioFormat.AAC,
        mime_type="audio/aac",
        can_play_type_probe='audio/aac; codecs="aac"',
        ios_support=IOSSupportLevel.NATIVE,
        notes="iOS Safari 全版本支持 AAC-LC",
    ),
}


@dataclass
class AudioFormatResult:
    """音频格式检测 + 降级结果"""
    case_id: str                              # 2.1 / 2.2 / 2.3 / 2.4
    requested_format: AudioFormat
    ios_support: IOSSupportLevel
    final_format: AudioFormat                 # 降级后格式
    passed: bool
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class IOSSafariAudioFormatHandler:
    """iOS Safari 音频格式检测 + 降级 — 4 case 实战

    派工 v6 段 5 反馈 #6: 渐进式, 不破坏老 TTS 链路
    """

    def __init__(
        self,
        capabilities: Optional[Dict[AudioFormat, FormatCapability]] = None,
    ):
        self.capabilities = capabilities or IOS_SAFARI_FORMAT_CAPABILITIES
        self._play_type_cache: Dict[str, str] = {}

    def probe_can_play_type(self, mime_probe: str) -> str:
        """模拟 Audio.canPlayType() 探针 (沙箱环境)

        真实环境: audio.canPlayType('audio/ogg; codecs="vorbis"')
        iOS Safari 返回 "" (不支持)
        """
        if mime_probe in self._play_type_cache:
            return self._play_type_cache[mime_probe]
        # 沙箱环境基于 capabilities 表判定
        for cap in self.capabilities.values():
            if cap.can_play_type_probe == mime_probe:
                result = (
                    "probably" if cap.ios_support == IOSSupportLevel.NATIVE
                    else ""
                )
                self._play_type_cache[mime_probe] = result
                return result
        return ""

    def detect_format(self, audio_url: str) -> AudioFormat:
        """从 audio URL 推断格式 (基于扩展名 / MIME type)"""
        url_lower = audio_url.lower()
        if url_lower.endswith(".mp3") or "audio/mpeg" in url_lower:
            return AudioFormat.MP3
        if url_lower.endswith(".wav") or "audio/wav" in url_lower:
            return AudioFormat.WAV
        if url_lower.endswith(".ogg") or "audio/ogg" in url_lower:
            return AudioFormat.OGG_VORBIS
        if url_lower.endswith(".aac") or "audio/aac" in url_lower:
            return AudioFormat.AAC
        # 默认 MP3 (Edge-TTS 7.2.8 默认输出)
        return AudioFormat.MP3

    def resolve_format(
        self, requested: AudioFormat,
    ) -> tuple[AudioFormat, IOSSupportLevel]:
        """解析最终格式 (含降级链)

        Returns:
            (final_format, ios_support_level)
        """
        cap = self.capabilities.get(requested)
        if cap is None:
            return AudioFormat.MP3, IOSSupportLevel.NATIVE
        if cap.ios_support == IOSSupportLevel.NATIVE:
            return requested, IOSSupportLevel.NATIVE
        # 需降级 — 沿 fallback_to 链解析
        current = cap
        while current.fallback_to is not None:
            next_fmt = current.fallback_to
            next_cap = self.capabilities.get(next_fmt)
            if next_cap is None:
                break
            if next_cap.ios_support == IOSSupportLevel.NATIVE:
                return next_fmt, IOSSupportLevel.NATIVE
            current = next_cap
        # 全部降级失败, 仍返回原 fallback (前端应报错)
        return (
            cap.fallback_to or AudioFormat.MP3,
            IOSSupportLevel.UNSUPPORTED,
        )

    # ---- 4 case 实战 ----
    def case_2_1_mp3_24khz(self) -> AudioFormatResult:
        """2.1: MP3 24kHz (Edge-TTS 默认) — iOS Safari 原生支持"""
        final, support = self.resolve_format(AudioFormat.MP3)
        return AudioFormatResult(
            case_id="2.1",
            requested_format=AudioFormat.MP3,
            ios_support=support,
            final_format=final,
            passed=support == IOSSupportLevel.NATIVE,
            notes="MP3 24kHz mono, iOS Safari 全版本支持",
        )

    def case_2_2_wav_16khz(self) -> AudioFormatResult:
        """2.2: WAV 16kHz — iOS Safari 原生支持"""
        final, support = self.resolve_format(AudioFormat.WAV)
        return AudioFormatResult(
            case_id="2.2",
            requested_format=AudioFormat.WAV,
            ios_support=support,
            final_format=final,
            passed=support == IOSSupportLevel.NATIVE,
            notes="WAV 16kHz 16-bit PCM, iOS Safari 全版本支持",
        )

    def case_2_3_ogg_vorbis(self) -> AudioFormatResult:
        """2.3: OGG Vorbis — iOS Safari **不支持**, 必降级到 MP3"""
        final, support = self.resolve_format(AudioFormat.OGG_VORBIS)
        return AudioFormatResult(
            case_id="2.3",
            requested_format=AudioFormat.OGG_VORBIS,
            ios_support=support,
            final_format=final,
            passed=final == AudioFormat.MP3,
            notes=f"OGG Vorbis 不支持, 降级到 {final.value}",
            metadata={"fallback_chain": "OGG → MP3"},
        )

    def case_2_4_aac(self) -> AudioFormatResult:
        """2.4: AAC — iOS Safari 原生支持"""
        final, support = self.resolve_format(AudioFormat.AAC)
        return AudioFormatResult(
            case_id="2.4",
            requested_format=AudioFormat.AAC,
            ios_support=support,
            final_format=final,
            passed=support == IOSSupportLevel.NATIVE,
            notes="AAC-LC, iOS Safari 全版本支持",
        )

    def run_all_cases(self) -> List[AudioFormatResult]:
        """运行 4 case 实战 (派工 v10 段 7 实战)"""
        return [
            self.case_2_1_mp3_24khz(),
            self.case_2_2_wav_16khz(),
            self.case_2_3_ogg_vorbis(),
            self.case_2_4_aac(),
        ]


def build_ios_safari_audio_format_handler() -> IOSSafariAudioFormatHandler:
    """工厂函数 (派工 v6 段 5 反馈 #6 渐进式)"""
    return IOSSafariAudioFormatHandler()
