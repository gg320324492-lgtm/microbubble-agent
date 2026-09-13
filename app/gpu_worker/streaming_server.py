# -*- coding: utf-8 -*-
"""Streaming-7B 实时 ASR 服务 v2 — 服务常驻、模型按需、空闲自动卸载

生命周期（与 8005 会议守护对齐）:
  - 服务进程常驻（:8006 健康检查随时可达），显存 0
  - 首次请求（/transcribe 或 /ws/asr）时加载模型（~20s）
  - 空闲 GPU_STREAMING_IDLE_UNLOAD_SEC 秒（默认 600）自动卸载，显存归零
  - 流式会话进行中不卸载（引用计数保护）

端点:
  GET  /healthz         → {"status":"ok","loaded":bool,"loading":bool}
  GET  /config          → 采样率/块时长（会触发加载）
  POST /transcribe      → body = 16kHz mono float32 PCM，无状态整段转写
  WS   /ws/asr          → 官方协议真流式（增量块输出）

启动: python -m app.gpu_worker.streaming_server
环境: GPU_STREAMING_IDLE_UNLOAD_SEC=600  GPU_ASR_ATTN=sdpa  GPU_ASR_TOKENIZER_DIR=...
"""
import argparse
import asyncio
import gc
import json
import os
import sys
import threading
import time
from pathlib import Path

_DEF_REPO = r"E:\microbubble-agent\.workbuddy\vibevoice-test\VibeVoice"
if _DEF_REPO not in sys.path and Path(_DEF_REPO).exists():
    sys.path.insert(0, _DEF_REPO)

import numpy as np  # noqa: E402
import torch  # noqa: E402
import uvicorn  # noqa: E402
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

DEF_MODEL_DIR = r"E:\microbubble-agent\.workbuddy\vibevoice-test\streaming-model"
DEF_TOKENIZER_DIR = r"E:\microbubble-agent\.workbuddy\vibevoice-test\qwen-tokenizer"
SR = 16000
TARGET_SR = 24000

IDLE_UNLOAD_SEC = int(os.environ.get("GPU_STREAMING_IDLE_UNLOAD_SEC", "600"))

state = {
    "model": None,
    "processor": None,
    "tokenizer": None,
    "meta": {},
    "loaded": False,
    "loading": False,
    "last_used": 0.0,
    "active_sessions": 0,
}
_load_lock = threading.Lock()
app = FastAPI(title="VibeVoice streaming ASR v2")
gpu_lock = asyncio.Lock()


def _load_model_sync(model_path: str, device: str, attn: str):
    from vibevoice.modular.modeling_vibevoice_asr import (
        VibeVoiceASRForConditionalGeneration)
    from vibevoice.processor.vibevoice_asr_processor import (
        VibeVoiceASRProcessor)

    processor = VibeVoiceASRProcessor.from_pretrained(
        model_path,
        language_model_pretrained_name=os.environ.get(
            "GPU_ASR_TOKENIZER_DIR", DEF_TOKENIZER_DIR))
    model = VibeVoiceASRForConditionalGeneration.from_pretrained(
        model_path, dtype=torch.bfloat16, attn_implementation=attn,
        trust_remote_code=True).to(device).eval()

    cfg = json.loads((Path(model_path) / "preprocessor_config.json")
                     .read_text(encoding="utf-8"))
    sr = cfg["target_sample_rate"]
    frame_sec = cfg["speech_tok_compress_ratio"] / sr
    meta = {
        "sample_rate": sr,
        "window_samples": int(cfg["chunk_frames"] * frame_sec * sr),
        "chunk_samples": int(cfg["chunk_frames"] * frame_sec * sr),
        "chunk_seconds": cfg["chunk_frames"] * frame_sec,
    }
    return model, processor, meta


def ensure_loaded() -> None:
    """按需加载模型（线程安全）"""
    if state["loaded"] or state["loading"]:
        state["last_used"] = time.time()
        return
    with _load_lock:
        if state["loaded"]:
            state["last_used"] = time.time()
            return
        state["loading"] = True
        try:
            print("[streaming-asr] 按需加载模型...", flush=True)
            model, processor, meta = _load_model_sync(
                os.environ.get("GPU_STREAMING_MODEL_DIR", DEF_MODEL_DIR),
                "cuda", os.environ.get("GPU_ASR_ATTN", "sdpa"))
            state["model"] = model
            state["processor"] = processor
            state["tokenizer"] = processor.tokenizer
            state["meta"] = meta
            state["loaded"] = True
            state["last_used"] = time.time()
            print(f"[streaming-asr] 模型已加载, chunk={meta['chunk_seconds']:.1f}s",
                  flush=True)
        finally:
            state["loading"] = False


def unload_model() -> None:
    """卸载模型，释放显存"""
    with _load_lock:
        if not state["loaded"]:
            return
        state["model"] = None
        state["processor"] = None
        state["tokenizer"] = None
        state["loaded"] = False
        gc.collect()
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
        print("[streaming-asr] 模型已卸载, 显存释放", flush=True)


def _idle_unload_loop():
    while True:
        time.sleep(30)
        if (state["loaded"] and not state["loading"]
                and state["active_sessions"] == 0
                and time.time() - state["last_used"] > IDLE_UNLOAD_SEC):
            unload_model()


def transcribe_window(window: np.ndarray, session: dict) -> str:
    model = state["model"]
    audio = torch.from_numpy(window).to(next(model.parameters()).device)
    features = model.encode_speech(audio.unsqueeze(0))
    text, _ = model.streaming_generate_step(
        audio_features=features,
        streaming_state=session["stream"],
        tokenizer=state["tokenizer"],
        max_new_tokens=session["max_tokens"],
        temperature=session["temperature"],
    )
    return text


@app.get("/healthz")
async def healthz():
    return JSONResponse({"status": "ok", "loaded": state["loaded"],
                         "loading": state["loading"],
                         "active_sessions": state["active_sessions"]})


@app.get("/config")
async def config():
    ensure_loaded()
    return JSONResponse(state["meta"])


@app.post("/transcribe")
async def transcribe_pcm(request: Request):
    """无状态整段转写: body = 16kHz mono float32 PCM"""
    ensure_loaded()
    state["last_used"] = time.time()
    pcm_bytes = await request.body()
    pcm = np.frombuffer(pcm_bytes, dtype="<f4").astype(np.float32)
    if len(pcm) < SR // 2:
        return JSONResponse({"error": "audio too short"}, status_code=400)
    import scipy.signal as sps
    wav24 = sps.resample_poly(pcm, TARGET_SR, SR).astype(np.float32)

    state["active_sessions"] += 1
    try:
        model = state["model"]
        tokenizer = state["processor"].tokenizer
        session = {"stream": model.init_streaming_state(
            tokenizer, context_info=None), "max_tokens": 8192,
            "temperature": 0.0}
        window_samples = state["meta"]["window_samples"]
        chunk_samples = state["meta"]["chunk_samples"]

        buffer = wav24
        texts = []
        while True:
            if len(buffer) >= window_samples:
                window = buffer[:window_samples]
            elif len(buffer) > 0:
                window = np.zeros(window_samples, dtype=np.float32)
                window[: len(buffer)] = buffer
            else:
                break
            async with gpu_lock:
                text = await asyncio.to_thread(transcribe_window, window, session)
            texts.append(text)
            buffer = buffer[chunk_samples:]
            if len(buffer) == 0:
                break
        return JSONResponse({"text": "".join(texts), "chunks": len(texts)})
    finally:
        state["active_sessions"] -= 1
        state["last_used"] = time.time()


@app.websocket("/ws/asr")
async def ws_asr(ws: WebSocket):
    await ws.accept()
    ensure_loaded()
    state["active_sessions"] += 1
    try:
        opts = json.loads(await ws.receive_text())
    except Exception:
        state["active_sessions"] -= 1
        await ws.close()
        return

    model = state["model"]
    window_samples = state["meta"]["window_samples"]
    chunk_samples = state["meta"]["chunk_samples"]

    async with gpu_lock:
        session = {
            "stream": model.init_streaming_state(
                state["processor"].tokenizer,
                context_info=opts.get("context_info") or None),
            "max_tokens": int(opts.get("max_tokens") or 256),
            "temperature": float(opts.get("temperature") or 0.0),
        }

    buffer = np.zeros(0, dtype=np.float32)
    texts = []

    async def drain(flush: bool):
        nonlocal buffer
        while True:
            available = len(buffer)
            if available >= window_samples:
                window = buffer[:window_samples]
            elif flush and available > 0:
                window = np.zeros(window_samples, dtype=np.float32)
                window[:available] = buffer
            else:
                return
            async with gpu_lock:
                text = await asyncio.to_thread(transcribe_window, window, session)
            texts.append(text)
            buffer = buffer[chunk_samples:]
            await ws.send_text(json.dumps({"chunks": len(texts),
                                           "text": "".join(texts)}))
            if flush and len(buffer) <= 0:
                return

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                return
            if message.get("bytes") is not None:
                pcm = np.frombuffer(message["bytes"], dtype="<f4")
                buffer = np.concatenate([buffer, pcm])
                state["last_used"] = time.time()
                await drain(flush=False)
            elif message.get("text") == "end":
                await drain(flush=True)
                await ws.send_text(json.dumps({"chunks": len(texts),
                                               "text": "".join(texts),
                                               "done": True}))
                return
    except WebSocketDisconnect:
        return
    finally:
        state["active_sessions"] -= 1
        state["last_used"] = time.time()


def _hide_console() -> None:
    """隐藏宿主控制台窗口（任务栏/Alt+Tab 不再显示，服务照常运行）。
    设 GPU_ASR_SHOW_CONSOLE=1 可保留窗口查看日志。"""
    if sys.platform != "win32" or os.environ.get("GPU_ASR_SHOW_CONSOLE"):
        return
    import ctypes
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE


def main():
    _hide_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("GPU_STREAMING_PORT", "8006")))
    args = ap.parse_args()

    threading.Thread(target=_idle_unload_loop, daemon=True).start()
    print(f"[streaming-asr v2] listening on 0.0.0.0:{args.port} "
          f"(模型按需加载, 空闲 {IDLE_UNLOAD_SEC}s 自动卸载)", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
