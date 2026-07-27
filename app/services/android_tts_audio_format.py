"""Android Chrome audio-format negotiation for Edge-TTS output."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AndroidAudioFormat:
    name: str
    mime_type: str
    sample_rate_hz: int | None
    native: bool = True


ANDROID_EDGE_TTS_FORMATS = {
    "mp3": AndroidAudioFormat("mp3", "audio/mpeg", 24_000),
    "wav": AndroidAudioFormat("wav", "audio/wav", 16_000),
    "ogg": AndroidAudioFormat("ogg", 'audio/ogg; codecs="vorbis"', None),
    "aac": AndroidAudioFormat("aac", "audio/aac", None),
}


class AndroidTTSAudioFormatPolicy:
    """Keep all four Android-native formats; never apply the iOS OGG fallback."""

    @staticmethod
    def can_play_type_probe() -> str:
        return "new Audio().canPlayType('audio/ogg; codecs=\"vorbis\"')"

    def select(self, requested: str, can_play_type: str = "probably") -> AndroidAudioFormat:
        key = requested.lower().lstrip(".")
        if key not in ANDROID_EDGE_TTS_FORMATS:
            raise ValueError(f"unsupported Android Chrome TTS format: {requested}")
        if key == "ogg" and can_play_type not in {"maybe", "probably"}:
            raise RuntimeError("Android Chrome reports no OGG Vorbis support")
        return ANDROID_EDGE_TTS_FORMATS[key]
