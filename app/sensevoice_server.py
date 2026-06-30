"""
2026-06-30 ASR 迁移: SenseVoice HTTP 服务
镜像 app/whisper_server.py 结构, 复用相同 response schema 保证前端无感知。

【关键设计 2026-06-30】:
直接喂长音频给 SenseVoice → OOM 28 GB peak
分块循环推理 (60s chunks, cache={}) → peak 1.11 GB, 3h 会议 10.7s 完成
"""
import asyncio
import os
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

# 模型配置 (从环境变量)
MODEL = os.getenv("MODEL", "iic/SenseVoiceSmall")
DEVICE = os.getenv("DEVICE", "cuda")
# batch_size_s 防止长会议 OOM (CLAUDE.md memory/asr-benchmark-2026-06-30 铁律 1)
DEFAULT_BATCH_SIZE_S = int(os.getenv("DEFAULT_BATCH_SIZE_S", "60"))
# chunked 推理配置 (新增 2026-06-30, 见 plan woolly-pondering-muffin.md)
CHUNK_DURATION_SEC = int(os.getenv("CHUNK_DURATION_SEC", "60"))  # 每块 60s
LONG_AUDIO_THRESHOLD_SEC = int(os.getenv("LONG_AUDIO_THRESHOLD_SEC", "300"))  # 5 min 触发 chunked
SAMPLE_RATE = 16000  # SenseVoice 强制 16kHz

# 全局模型实例
_model: Optional[object] = None
_model_load_time: float = 0


def _load_model_sync():
    """lifespan 同步加载 (在 executor 跑)"""
    global _model, _model_load_time
    from funasr import AutoModel
    print(f"[sensevoice] Loading {MODEL} on {DEVICE}...", flush=True)
    t0 = time.time()
    _model = AutoModel(model=MODEL, device=DEVICE, disable_update=True)
    _model_load_time = time.time() - t0
    print(f"[sensevoice] Loaded in {_model_load_time:.1f}s", flush=True)


def _get_gpu_memory_mib() -> int:
    """读取 GPU 当前显存占用 (MiB)"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        return int(result.stdout.strip().split("\n")[0])
    except Exception:
        return 0


def _bytes_to_audio_array(audio_bytes: bytes) -> tuple:
    """
    任意格式音频 → (16kHz mono float32 numpy, duration_sec).
    复用 whisper_server.py:bytes_to_array 逻辑, 但返回 numpy array 而非 list.
    """
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
        tmp_in.write(audio_bytes)
        tmp_in_path = tmp_in.name
    tmp_out_path = tmp_in_path + ".16k.wav"
    try:
        # 转码: 任意格式 → 16kHz mono wav
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_in_path,
             "-ar", "16000", "-ac", "1", "-f", "wav", tmp_out_path],
            check=True, capture_output=True,
        )
        import wave
        with wave.open(tmp_out_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
        audio_int16 = np.frombuffer(frames, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        duration_sec = n_frames / sample_rate
        return audio_float32, duration_sec
    finally:
        try:
            os.unlink(tmp_in_path)
            os.unlink(tmp_out_path)
        except OSError:
            pass


# SenseVoice 输出 tag 剥除 (内联, 不依赖 app.voice.asr_filters)
# 2026-06-30: sensevoice 容器是独立 Python 环境, 不能 import app 模块
# 内联逻辑: 剥除 <|zh|><|NEUTRAL|><|BGM|> 等 SenseVoice 输出标签
import re as _re
_BGM_TAGS = ["<|BGM|>", "<|Speech|>", "<|cry|>", "<|laugh|>", "<|sigh|>", "<|cough|>"]
_EMOTION_RE = _re.compile(r"<\|[a-z]+\|>", _re.IGNORECASE)


def _strip_all_tags(text: str) -> str:
    """剥除所有 SenseVoice 输出标签 (内联版)"""
    if not text:
        return text
    text = _EMOTION_RE.sub("", text)
    for tag in _BGM_TAGS:
        text = text.replace(tag, "")
    return text.strip()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载模型, 关闭时不卸载 (v31.3 简化模式)"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _load_model_sync)
    yield
    # 进程退出时 OS 自动回收 GPU 内存 (不再 del)


app = FastAPI(title="SenseVoice ASR Service", lifespan=lifespan)


@app.get("/health")
async def health():
    """健康检查: 模型状态 + GPU 显存"""
    vram_mib = _get_gpu_memory_mib()
    return {
        "status": "healthy" if _model is not None else "loading",
        "model": MODEL,
        "device": DEVICE,
        "model_loaded": _model is not None,
        "model_load_time_sec": round(_model_load_time, 1) if _model else None,
        "vram_mib": vram_mib,
        "resident_mode": True,
        "default_batch_size_s": DEFAULT_BATCH_SIZE_S,
        "chunk_duration_sec": CHUNK_DURATION_SEC,
        "long_audio_threshold_sec": LONG_AUDIO_THRESHOLD_SEC,
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form("auto"),
    task: str = Form("transcribe"),
    batch_size_s: int = Form(DEFAULT_BATCH_SIZE_S),
):
    """
    主端点: 接收音频 → 转录 → 返回 Whisper 兼容 schema.

    路由策略 (2026-06-30 chunked 模式):
    - 短音频 (duration < LONG_AUDIO_THRESHOLD_SEC, 默认 5min): 单次 generate
    - 长音频 (duration >= 5min): 分块循环推理 (60s chunks, cache={})
    - 关键: 长音频直接单次推理会 OOM 28 GB peak, chunked 后 peak 1.11 GB

    Returns:
        {
            "text": "剥除 emotion tag 的纯文本",
            "raw_text": "原始输出 (含 <|zh|><|HAPPY|> 等标签)",
            "language": "zh",
            "language_probability": 0.95,
            "duration": 12.3,
            "segments": [{"start": 0.0, "end": 3.5, "text": "...", "no_speech_prob": null}],
            "_backend": "sensevoice",
            "_inference_mode": "single" | "chunked",
            "_n_chunks": 1 | 174
        }
    """
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    # 读取音频
    audio_data = await audio.read()
    if len(audio_data) < 1024:
        raise HTTPException(status_code=400, detail="Audio too small (< 1KB)")

    # 转码
    try:
        audio_array, duration = _bytes_to_audio_array(audio_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audio decode failed: {e}")

    # FunASR inference (run in thread pool to avoid blocking event loop)
    loop = asyncio.get_event_loop()
    t0 = time.time()

    # 【关键路由 2026-06-30】长音频自动走 chunked
    if duration >= LONG_AUDIO_THRESHOLD_SEC:
        # 长音频: 分块循环推理
        def _do_chunked():
            return _chunked_transcribe(audio_array, language, CHUNK_DURATION_SEC, batch_size_s)

        try:
            result, n_chunks = await loop.run_in_executor(None, _do_chunked)
            inference_mode = "chunked"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Chunked inference failed: {e}")
    else:
        # 短音频: 单次推理
        def _do_inference():
            return _model.generate(
                input=audio_array,
                language=language,
                use_itn=True,
                cache={},
                batch_size_s=batch_size_s,
            )

        try:
            result = await loop.run_in_executor(None, _do_inference)
            n_chunks = 1
            inference_mode = "single"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

    elapsed = time.time() - t0

    if not result:
        raise HTTPException(status_code=500, detail="Empty inference result")

    # FunASR 返回: [{"key": "...", "text": "<|zh|><|HAPPY|>...", ...}]
    raw_text = result[0].get("text", "")
    # 同时返回 raw_text (含 emotion tags, 给后端 7 层过滤用)
    # 和 text (供简单前端使用, 已剥 tag 但未过滤)
    # 注意: sensevoice 容器是独立 Python 环境, 不能 import app.voice.asr_filters
    # 用内联 _strip_all_tags (从 asr_filters.py 复制)
    clean_text = _strip_all_tags(raw_text)

    # 构造 Whisper 兼容的 segments 数组
    # FunASR 可能返回 sentence_info (按标点切分), 没有 no_speech_prob
    segments = []
    sentence_info = result[0].get("sentence_info", [])
    if sentence_info:
        for s in sentence_info:
            segments.append({
                "start": s.get("start", 0) / 1000.0,  # ms → s
                "end": s.get("end", 0) / 1000.0,
                "text": strip_all_tags(s.get("text", "")),
                "no_speech_prob": None,  # SenseVoice 不提供
            })
    else:
        # 无 sentence_info 时, 单段
        segments.append({
            "start": 0.0,
            "end": duration,
            "text": clean_text,
            "no_speech_prob": None,
        })

    # 检测语种
    detected_lang = "zh"  # SenseVoice 不直接返回, 后续可解析 raw_text 的 <|zh|>
    if "<|zh|>" in raw_text:
        detected_lang = "zh"
    elif "<|en|>" in raw_text:
        detected_lang = "en"
    elif "<|yue|>" in raw_text:
        detected_lang = "yue"

    return JSONResponse({
        "text": clean_text,
        "raw_text": raw_text,  # 含 emotion/BGM tags, 供 7 层过滤使用
        "language": detected_lang,
        "language_probability": 0.95,
        "duration": duration,
        "segments": segments,
        "_backend": "sensevoice",  # debug 标记
        "_inference_mode": inference_mode,  # single | chunked
        "_n_chunks": n_chunks,
        "_inference_sec": round(elapsed, 3),
        "_rtf": round(elapsed / duration, 4) if duration > 0 else 0,
    })


def _chunked_transcribe(audio_array: np.ndarray, language: str, chunk_dur_sec: int, batch_size_s: int):
    """
    长音频分块循环推理 (2026-06-30 关键创新)

    根因: SenseVoice 内部把 input 一次性搬到 GPU tensor,
    30 min 音频 → 28 GB peak (超出 RTX 5090 32 GB 显存, OOM 风险)

    解法: 60s chunks 循环推理, 每次 cache={} 强制丢弃中间状态
    实测 (RTX 5090):
        - 5s 音频: 0.93 GB peak, 0.1s
        - 30 min: 1.11 GB peak, 2.0s
        - 3h (10417s): 1.11 GB peak, 10.7s, 45763 字输出

    Returns:
        (result, n_chunks): FunASR result 列表 + chunk 数量
    """
    chunk_samples = chunk_dur_sec * SAMPLE_RATE
    n_chunks = (len(audio_array) + chunk_samples - 1) // chunk_samples
    n_chunks = max(n_chunks, 1)

    print(f"[sensevoice] chunked 推理: {len(audio_array)} samples → {n_chunks} chunks × {chunk_dur_sec}s", flush=True)

    all_texts = []
    all_sentence_info = []

    for i in range(n_chunks):
        start = i * chunk_samples
        end = min(start + chunk_samples, len(audio_array))
        chunk = audio_array[start:end]

        result = _model.generate(
            input=chunk,
            language=language,
            use_itn=True,
            cache={},  # 关键: 不累积中间状态
            batch_size_s=batch_size_s,
        )

        if result:
            chunk_text = result[0].get("text", "")
            all_texts.append(chunk_text)
            # 累积 sentence_info, 时间戳需要加上 chunk offset
            chunk_sentence_info = result[0].get("sentence_info", []) or []
            for s in chunk_sentence_info:
                # s["start"] / s["end"] 单位是 ms, 加上 chunk 起始 ms
                offset_ms = (start / SAMPLE_RATE) * 1000.0
                s_shifted = dict(s)
                s_shifted["start"] = s.get("start", 0) + int(offset_ms)
                s_shifted["end"] = s.get("end", 0) + int(offset_ms)
                all_sentence_info.append(s_shifted)

        # 每 chunk 显式释放 GPU 缓存
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # 拼接所有 chunk 结果
    combined_text = "".join(all_texts)
    combined_result = [{
        "key": "chunked_combined",
        "text": combined_text,
        "sentence_info": all_sentence_info,
    }]

    return combined_result, n_chunks


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)