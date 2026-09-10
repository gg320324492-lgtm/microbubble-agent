# -*- coding: utf-8 -*-
"""Streaming-7B ASR 客户端 (app 容器侧) — 调用 host:8006 流式服务

约定:
  - 输入 wav bytes (16kHz mono)
  - 服务不可用/超时/出错一律抛 GPUASRError, 由 asr.py 回退 SenseVoice
  - 服务的显存说明: Streaming-7B 常驻 ~16GB; 与 meeting_worker 并存时
    meeting worker OOM 会自动回退 SenseVoice (安全降级), 但建议二者择一常驻
"""
import json
import time
import wave
from io import BytesIO

import httpx
import numpy as np


class GPUStreamingError(Exception):
    pass


def _wav_to_f32_pcm(wav_bytes: bytes) -> bytes:
    with wave.open(BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())
    if sr != 16000 or ch != 1 or sw != 2:
        raise GPUStreamingError(f"期望 16kHz mono 16bit wav, 得到 {sr}Hz/{ch}ch/{sw*8}bit")
    pcm = np.frombuffer(raw, dtype=np.int16).astype("<f4") / 32768.0
    return pcm.astype("<f4").tobytes()


async def transcribe_pcm(wav_bytes: bytes, base_url: str,
                         timeout: float = 600) -> str:
    """整段转写: POST f32 PCM → {"text", "chunks"}"""
    pcm = _wav_to_f32_pcm(wav_bytes)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/transcribe", content=pcm,
            headers={"Content-Type": "application/octet-stream"})
    r.raise_for_status()
    return r.json().get("text", "")


async def healthy(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{base_url.rstrip('/')}/healthz")
            return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False
