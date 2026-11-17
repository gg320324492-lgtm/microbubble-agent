"""MiniMax asr-1.0 云端 ASR 服务 — 会议转写后端之一 (2026-11-17).

2026-11-17 评测 (data/tmp/asr_eval_minimax.py, 与 SenseVoice 同集同口径):
  MiniMax asr-1.0 avg CER 0.0888 vs SenseVoice 0.156 → 质量更好, 切为主力。
  本地 VibeVoice-7B / SenseVoice 降级为替补 (GPU 挂/云端失败时回退)。

限制: 单次音频 ≤500s (服务端硬闸), 长音频必须按 ≤480s 切片分批调用再按时间戳拼接。
端点: POST https://api.minimaxi.com/v1/speech_to_text  (multipart: model + file)
返回: {"text": "...", "duration": <sec>, "trace_id": "..."}
"""
import asyncio
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
    audio_pcm,
    sample_rate: int = 16000,
    language: str = "zh",
    on_clip_done=None,
) -> Tuple[List[Dict], Dict]:
    """把整段音频按 ≤480s 切片调 MiniMax asr-1.0, 按顺序拼接时间戳。

    Args:
        audio_pcm: **float32 numpy 数组, 取值 -1..1** (与 audio_processor 同约定);
                   也兼容 bytes(按 int16 解释, 仅调试用)
        sample_rate: 采样率
        language: 语言 (仅记录, asr-1.0 自动识别)
        on_clip_done: 回调 (done, total) 进度

    Returns:
        (segments, meta)
        segments: [{"text", "start", "end", "clip"}]
        meta: {"clips": N, "backend": "minimax-asr-1.0", "elapsed_sec": ...}

    ⚠️ 2026-11-17 实锤: 会议 259 首跑 15 个切片全部返回空文本 —— 原因是把
    float32(-1..1) 的字节按 int16 解释 ⇒ 全是噪声。**必须**按 float32 处理。
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("MiniMax ASR key 未配置 (LLM_OPENAI_COMPAT_API_KEY/MIMO_API_KEY)")

    import numpy as np

    if isinstance(audio_pcm, (bytes, bytearray)):
        # 兼容旧调用: 按 int16 解释 (调用方须自行保证)
        pcm = np.frombuffer(bytes(audio_pcm), dtype=np.int16).astype(np.float32) / 32768.0
    else:
        pcm = np.asarray(audio_pcm, dtype=np.float32)
        if pcm.ndim > 1:
            pcm = pcm.reshape(-1)
        peak = float(np.max(np.abs(pcm))) if pcm.size else 0.0
        if peak > 1.5:
            # 传进来的其实是 int16 量级 (|x| 最大 32768), 归一化到 -1..1
            pcm = np.clip(pcm / 32768.0, -1.0, 1.0)
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
        # float32(-1..1) → int16, 与 app/services/post_meeting_tasks.py::_numpy_to_wav_bytes 同约定
        pcm_int16 = (chunk * 32768.0).clip(-32768, 32767).astype(np.int16)
        with wavmod.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_int16.tobytes())
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


# ============================================================================
# 2026-11-17: VAD 分段模式（推荐）—— 每段 VAD 音频单独送云端
# ----------------------------------------------------------------------------
# 片级(480s)模式虽然请求少，但返回的是整片文本、无句级时间戳 ⇒ 声纹按近似区间
# 切音频 ⇒ 会议 259 实测"未识别说话人"从 2.9% 升到 45.1%。
# VAD 分段模式下每段 3–30 秒，时间戳就是声学边界，声纹可正常切音频。
# 代价：请求数从 15 涨到数百，用并发（默认 6）压到 1–2 分钟。
# ============================================================================
SEGMENT_CONCURRENCY = 3  # 2026-11-17 实测: 6 并发触发云端 429


def _float32_to_wav_bytes(audio, sample_rate: int) -> bytes:
    """float32(-1..1) 数组 → 16-bit 单声道 WAV 字节。"""
    import io
    import wave as wavmod

    import numpy as np

    arr = np.asarray(audio, dtype=np.float32).reshape(-1)
    pcm_int16 = (arr * 32768.0).clip(-32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wavmod.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    return buf.getvalue()


async def _post_one(client, api_key: str, wav_bytes: bytes, name: str):
    """单段请求 + 重试。返回 (text, error)。"""
    last_err = None
    for attempt in range(3):
        try:
            resp = await client.post(
                MINIMAX_ASR_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (name, wav_bytes, "audio/wav")},
                data={"model": "asr-1.0"},
            )
            if resp.status_code == 200:
                return (resp.json().get("text") or "").strip(), None
            if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                return None, f"HTTP {resp.status_code}: {resp.text[:150]}"
            if resp.status_code == 429:
                # 云端并发/配额限流: 退避要比普通错误长, 并尊重 Retry-After
                ra = resp.headers.get("Retry-After")
                wait = float(ra) if ra and ra.isdigit() else 4.0 * (attempt + 1)
                last_err = f"HTTP 429, attempt {attempt + 1}, wait {wait:.0f}s"
                await asyncio.sleep(min(30, wait))
                continue
            last_err = f"HTTP {resp.status_code}, attempt {attempt + 1}"
        except Exception as e:  # noqa: BLE001
            last_err = f"attempt {attempt + 1}: {e}"
        await asyncio.sleep(min(30, 2 ** attempt))
    return None, last_err


async def transcribe_segments(
    segments,
    sample_rate: int = 16000,
    language: str = "zh",
    concurrency: int = SEGMENT_CONCURRENCY,
    on_progress=None,
):
    """按 VAD 段逐段调用 MiniMax，返回带**声学边界**时间戳的段落。

    Args:
        segments: audio_processor 产出的段列表，每项需有 .audio(float32)/.start_time/.end_time
        on_progress: 可选回调 (done, total)

    Returns:
        (segments, meta) — segments 项: {"text","start","end","idx","time_precision":"vad"}
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("MiniMax ASR key 未配置 (LLM_OPENAI_COMPAT_API_KEY/MIMO_API_KEY)")

    items = [s for s in (segments or []) if getattr(s, "audio", None) is not None]
    total = len(items)
    if not total:
        return [], {"backend": "minimax-asr-1.0", "mode": "vad", "clips": 0, "elapsed_sec": 0.0}

    sem = asyncio.Semaphore(max(1, concurrency))
    done = {"n": 0}
    t0 = time.time()
    errors = []

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        async def one(idx, seg):
            async with sem:
                wav = _float32_to_wav_bytes(seg.audio, sample_rate)
                text, err = await _post_one(client, api_key, wav, f"seg_{idx:04d}.wav")
            done["n"] += 1
            if on_progress:
                try:
                    on_progress(done["n"], total)
                except Exception:
                    pass
            if err:
                errors.append(f"seg{idx}: {err}")
            return idx, seg, text

        results = await asyncio.gather(*(one(i, s) for i, s in enumerate(items)))

    out = []
    for idx, seg, text in sorted(results, key=lambda x: x[1].start_time):
        if not text:
            continue
        out.append({
            "text": text,
            "start": round(float(seg.start_time), 2),
            "end": round(float(seg.end_time), 2),
            "idx": idx,
            "time_precision": "vad",
        })

    meta = {
        "backend": "minimax-asr-1.0",
        "mode": "vad",
        "clips": total,
        "failed_clips": len(errors),
        "elapsed_sec": round(time.time() - t0, 1),
        "last_error": errors[0] if errors else None,
    }
    logger.info(
        f"[minimax-asr:vad] {len(out)} 段文本 / {total} 段音频, "
        f"{meta['elapsed_sec']}s, failed={len(errors)}, err={meta['last_error'] or 'none'}"
    )
    return out, meta
