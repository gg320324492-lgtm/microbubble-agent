"""语音合成模块 - 基于 Edge-TTS"""

import logging
import edge_tts
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


# 2026-06-13 修复：edge-tts 6.1.9 的 TrustedClientToken 已过期，
# Microsoft Edge TTS readaloud 端点返回 403 Forbidden。
# 升级到 edge-tts 7.2.8 后修复（新版更新了 internal UA + endpoint 配置）。
# 之前用 monkey-patch 替换硬编码 UA 的方案不再需要（保留在 git history 中备查）。


class TextToSpeech:
    """语音合成服务"""

    VOICES = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",
        "xiaoyi": "zh-CN-XiaoyiNeural",
        "yunxi": "zh-CN-YunxiNeural",
        "yunjian": "zh-CN-YunjianNeural",
        "yunxia": "zh-CN-YunxiaNeural",
        "xiaomeng": "zh-CN-XiaomengNeural",
        "xiaochen": "zh-CN-XiaochenNeural",
        "xiaohan": "zh-CN-XiaohanNeural",
        "xiaomo": "zh-CN-XiaomoNeural",
        "xiaorui": "zh-CN-XiaoruiNeural",
        "xiaoshuang": "zh-CN-XiaoshuangNeural",
        "xiaoyan": "zh-CN-XiaoyanNeural",
        "xiaozhen": "zh-CN-XiaozhenNeural",
        "yunfeng": "zh-CN-YunfengNeural",
        "yunhao": "zh-CN-YunhaoNeural",
        "yunyang": "zh-CN-YunyangNeural",
    }

    def __init__(self):
        self.default_voice = self.VOICES["xiaoxiao"]

    async def synthesize(
        self,
        text: str,
        voice: str = "xiaoxiao",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> bytes:
        """文字转语音

        失败时记 logger（含 voice + text_len）便于排查。
        """
        voice_id = self.VOICES.get(voice, voice)
        if voice_id not in self.VOICES.values():
            voice_id = self.default_voice

        communicate = edge_tts.Communicate(
            text=text, voice=voice_id,
            rate=rate, volume=volume, pitch=pitch,
        )

        audio_data = b""
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
        except Exception as e:
            logger.error(
                f"TTS 合成失败: {type(e).__name__}: {e} | "
                f"voice={voice_id} text_len={len(text)}",
                exc_info=True,
            )
            raise

        if not audio_data:
            logger.warning(f"TTS 返回空音频: voice={voice_id} text_len={len(text)}")

        return audio_data

    async def synthesize_stream(
        self,
        text: str,
        voice: str = "xiaoxiao",
        rate: str = "+0%",
        volume: str = "+0%",
    ) -> AsyncGenerator[bytes, None]:
        voice_id = self.VOICES.get(voice, voice)
        if voice_id not in self.VOICES.values():
            voice_id = self.default_voice

        communicate = edge_tts.Communicate(
            text=text, voice=voice_id, rate=rate, volume=volume
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    def get_voice_options(self) -> list:
        return [
            {"value": "xiaoxiao", "label": "晓晓（温柔女声）", "gender": "female"},
            {"value": "xiaoyi", "label": "晓伊（活泼女声）", "gender": "female"},
            {"value": "yunxi", "label": "云希（阳光男声）", "gender": "male"},
            {"value": "yunjian", "label": "云健（稳重男声）", "gender": "male"},
            {"value": "yunyang", "label": "云扬（专业男声）", "gender": "male"},
            {"value": "xiaomeng", "label": "晓梦（甜美女声）", "gender": "female"},
        ]


# 全局实例
tts_service = TextToSpeech()