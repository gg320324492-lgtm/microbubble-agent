"""MiniMax asr-1.0 云端 ASR 服务 — 会议转写后端之一 (2026-11-17).

2026-11-17 评测 (data/tmp/asr_eval_minimax.py, 与 SenseVoice 同集同口径):
  MiniMax asr-1.0 avg CER 0.0888 vs SenseVoice 0.156 → 质量更好, 切为主力。
  本地 VibeVoice-7B / SenseVoice 降级为替补 (GPU 挂/云端失败时回退)。

限制: 单次音频 ≤500s (服务端硬闸), 长音频必须按 ≤480s 切片分批调用再按时间戳拼接。
端点: POST https://api.minimaxi.com/v1/speech_to_text  (multipart: model + file)
返回: {"text": "...", "duration": <sec>, "trace_id": "..."}
"""
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger("microbubble.minimax_asr")

MINIMAX_ASR_URL = "https://api.minimaxi.com/v1/speech_to_text"
# 服务端硬闸 500s; 切 480s 留余量
MAX_CLIP_SEC = 480
REQUEST_TIMEOUT = 600


def _get_api_key() -> str:
    """复用 MiniMax 对话链路同源 key (LLM_OPENAI_COMPAT_API_KEY 优先, 回退 MIMO_API_KEY)。"""
    return (
        getattr(settings, "LLM_OPENAI_COMPAT_API_KEY", "")
        or getattr(settings, "MIMO_API_KEY", "")
        or os.getenv("MINIMAX_ASR_API_KEY", "")
    )


async def check_health() -> bool:
    """key 可用性探测 (不真正转写, 只要有 key 就认为可用)。"""
    return bool(_get_api_key())


async def transcribe_full_audio(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    language: str = "zh",
    on_clip_done=None,
) -> Tuple[List[Dict], Dict]:
    """把整段 PCM 按 ≤480s 切片调 MiniMax asr-1.0, 按顺序拼接时间戳。

    Args:
        pcm_bytes: 16-bit 单声道 PCM 原始字节
        sample_rate: 采样率
        language: 语言 (仅记录, asr-1.0 自动识别)
        on_clip_done: 回调 (done, total) 进度

    Returns:
        (segments, meta)
        segments: [{"text", "start", "end", "clip"}]
        meta: {"clips": N, "backend": "minimax-asr-1.0", "elapsed_sec": ...}
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("MiniMax ASR key 未配置 (LLM_OPENAI_COMPAT_API_KEY/MIMO_API_KEY)")

    import numpy as np

    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
    total_sec = len(pcm) / sample_rate
    clip_samples = MAX_CLIP_SEC * sample_rate
    clips = []
    for start in range(0, len(pcm), clip_samples):
        chunk = pcm[start:start + clip_samples]
        clips.append((start / sample_rate, chunk))
    total_clips = len(clips)

    segments: List[Dict] = []
    t0 = time.time()
    last_err = None
    for idx, (offset_sec, chunk) in enumerate(clips):
        clip_sec = len(chunk) / sample_rate
        if clip_sec < 0.2:
            continue
        # PCM → WAV 容器 (asr-1.0 接受 wav)
        import io
        import wave as wavmod

        buf = io.BytesIO()
        with wavmod.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(chunk.tobytes())
        wav_bytes = buf.getvalue()

        ok = False
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    files = {"file": (f"clip_{idx:03d}.wav", wav_bytes, "audio/wav")}
                    data = {"model": "asr-1.0"}
                    resp = await client.post(
                        MINIMAX_ASR_URL,
                        headers={"Authorization": f"Bearer {api_key}"},
                        files=files,
                        data=data,
                    )
                if resp.status_code == 200:
                    payload = resp.json()
                    text = (payload.get("text") or "").strip()
                    if text:
                        segments.append({
                            "text": text,
                            "start": round(offset_sec, 2),
                            "end": round(offset_sec + clip_sec, 2),
                            "clip": idx,
                        })
                    ok = True
                    break
                # 4xx 除 408/429 不重试
                if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    break
                last_err = f"HTTP {resp.status_code}, attempt {attempt + 1}"
                time.sleep(min(30, 2 ** attempt))
            except Exception as e:
                last_err = f"attempt {attempt + 1}: {e}"
                time.sleep(min(30, 2 ** attempt))
        if not ok and last_err:
            logger.warning(f"[minimax-asr] clip {idx + 1}/{total_clips} 失败: {last_err}")
        if on_clip_done:
            try:
                on_clip_done(idx + 1, total_clips)
            except Exception:
                pass

    meta = {
        "backend": "minimax-asr-1.0",
        "clips": total_clips,
        "failed_clips": sum(1 for _ in range(total_clips)) - len(segments),
        "elapsed_sec": round(time.time() - t0, 1),
        "total_sec": round(total_sec, 1),
        "last_error": last_err,
    }
    logger.info(
        f"[minimax-asr] 完成: {len(segments)} 段文本 / {total_clips} 片, "
        f"{meta['elapsed_sec']}s, last_err={last_err or 'none'}"
    )
    return segments, meta
