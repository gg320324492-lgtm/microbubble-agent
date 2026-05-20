"""语音合成模块 - 基于 Edge-TTS"""

import io
import edge_tts
import asyncio
from typing import Optional, AsyncGenerator

from app.config import settings


class TextToSpeech:
    """语音合成服务"""

    # 可用的中文语音
    VOICES = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",      # 女声，温柔
        "xiaoyi": "zh-CN-XiaoyiNeural",           # 女声，活泼
        "yunxi": "zh-CN-YunxiNeural",             # 男声，阳光
        "yunjian": "zh-CN-YunjianNeural",         # 男声，稳重
        "yunxia": "zh-CN-YunxiaNeural",           # 男声，少年
        "xiaomeng": "zh-CN-XiaomengNeural",       # 女声，甜美
        "xiaochen": "zh-CN-XiaochenNeural",       # 女声，知性
        "xiaohan": "zh-CN-XiaohanNeural",         # 女声，成熟
        "xiaomo": "zh-CN-XiaomoNeural",           # 女声，温柔
        "xiaorui": "zh-CN-XiaoruiNeural",         # 女声，沉稳
        "xiaoshuang": "zh-CN-XiaoshuangNeural",   # 女声，童声
        "xiaoyan": "zh-CN-XiaoyanNeural",         # 女声，干练
        "xiaozhen": "zh-CN-XiaozhenNeural",       # 女声，知性
        "yunfeng": "zh-CN-YunfengNeural",         # 男声，浑厚
        "yunhao": "zh-CN-YunhaoNeural",           # 男声，大气
        "yunyang": "zh-CN-YunyangNeural",         # 男声，专业
    }

    def __init__(self):
        self.default_voice = self.VOICES["xiaoxiao"]

    async def synthesize(
        self,
        text: str,
        voice: str = "xiaoxiao",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz"
    ) -> bytes:
        """
        文字转语音

        Args:
            text: 要转换的文字
            voice: 语音名称，可选值见 VOICES 字典
            rate: 语速，如 "+10%", "-10%"
            volume: 音量，如 "+10%", "-10%"
            pitch: 音调，如 "+10Hz", "-10Hz"

        Returns:
            MP3格式的音频数据
        """
        # 获取语音ID
        voice_id = self.VOICES.get(voice, voice)
        if voice_id not in self.VOICES.values():
            voice_id = self.default_voice

        # 创建通信对象
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            volume=volume,
            pitch=pitch
        )

        # 收集音频数据
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        return audio_data

    async def synthesize_stream(
        self,
        text: str,
        voice: str = "xiaoxiao",
        rate: str = "+0%",
        volume: str = "+0%"
    ) -> AsyncGenerator[bytes, None]:
        """
        流式语音合成

        Args:
            text: 要转换的文字
            voice: 语音名称
            rate: 语速
            volume: 音量

        Yields:
            音频数据块
        """
        voice_id = self.VOICES.get(voice, voice)
        if voice_id not in self.VOICES.values():
            voice_id = self.default_voice

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=rate,
            volume=volume
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]

    def get_voice_options(self) -> list:
        """获取预设的语音选项"""
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
