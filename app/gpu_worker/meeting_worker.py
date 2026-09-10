# -*- coding: utf-8 -*-
"""GPU 会议处理 worker（子进程入口）— v2 已校准版

推理路径与 2026-09-07 实测脚本 (test_vibevoice_7b.py) 完全一致：
  - VibeVoiceASRForConditionalGeneration (bf16 + sdpa, 无需 flash-attn)
  - 16kHz PCM 必须重采样到 24kHz (processor 对 numpy 输入不重采样)
  - max_new_tokens 按音频时长估算 (dur*18+384)，防贪心跑满
  - JSON 输出可能重复两遍，时间轴回卷即截断
新增：>chunk_sec 长音频按能量谷值分块转写（块间说话人标签带块前缀，
     由应用侧声纹质心投票统一映射真名）。

用法:
  python -m app.gpu_worker.meeting_worker --job job.json --output result.json
  python -m app.gpu_worker.meeting_worker --selftest   # 无 GPU 验证生命周期管线

Job JSON:
{
  "audio_wav": "C:/tmp/meeting.wav",     # 16kHz mono int16 wav
  "hotwords": "热词背景: 微纳米气泡...",  # 可选 (context_info)
  "chunk_sec": 900,                      # 可选, 默认 900s
  "model_dir": "...", "asr_repo": "...", "tokenizer_dir": "..."  # 可选, 有默认
}

Result JSON:
{"status": "ok"|"error", "segments": [{"start","end","speaker_label","content"}],
 "meta": {"model_load_sec","infer_sec","audio_sec","chunks","peak_vram_mb","worker_pid"}}
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

import numpy as np

# 默认路径（生产化时迁移权重后改环境变量即可）
DEF_MODEL_DIR = r"E:\microbubble-agent\.workbuddy\vibevoice-test\models-vv"
DEF_ASR_REPO = r"E:\microbubble-agent\.workbuddy\vibevoice-test\VibeVoice"
DEF_TOKENIZER_DIR = r"E:\microbubble-agent\.workbuddy\vibevoice-test\qwen-tokenizer"

SR = 16000            # 输入 PCM 采样率
TARGET_SR = 24000     # VibeVoice 目标采样率


# ---------------------------------------------------------------- 工具
def vram_used_mb() -> int | None:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15)
        return int(r.stdout.strip().splitlines()[0]) if r.returncode == 0 else None
    except Exception:
        return None


def load_wav_16k(path: str) -> np.ndarray:
    with wave.open(path, "rb") as wf:
        assert wf.getframerate() == SR and wf.getnchannels() == 1, \
            f"期望 16kHz mono wav, 得到 {wf.getframerate()}Hz/{wf.getnchannels()}ch"
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def resample_24k(wav: np.ndarray) -> np.ndarray:
    import scipy.signal as sps
    return sps.resample_poly(wav, TARGET_SR, SR).astype(np.float32)


# ---------------------------------------------------------------- 模型加载
def load_asr_model(model_dir: str, tokenizer_dir: str, asr_repo: str):
    """实测校准的加载路径（见 docs/vibevoice-evaluation-2026-09-07.md §3.3）"""
    import torch
    if asr_repo not in sys.path:
        sys.path.insert(0, asr_repo)
    from vibevoice.modular.modeling_vibevoice_asr import (
        VibeVoiceASRForConditionalGeneration)
    from vibevoice.processor.vibevoice_asr_processor import (
        VibeVoiceASRProcessor)

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA 不可用：会议 worker 必须跑在 GPU 上")
    processor = VibeVoiceASRProcessor.from_pretrained(
        model_dir, language_model_pretrained_name=tokenizer_dir)
    model = VibeVoiceASRForConditionalGeneration.from_pretrained(
        model_dir, dtype=torch.bfloat16, attn_implementation="sdpa",
        trust_remote_code=True).to("cuda").eval()
    return model, processor


# ---------------------------------------------------------------- 分块
def find_chunk_points(wav24: np.ndarray, chunk_sec: float = 900.0,
                      search_sec: float = 30.0) -> list:
    """在固定间隔附近找能量谷值作为切块点，减少切断句子"""
    n = len(wav24)
    total = n / TARGET_SR
    if total <= chunk_sec:
        return [0.0, total]
    win = int(TARGET_SR)  # 1s 窗口能量
    points = [0.0]
    target = chunk_sec
    while target < total - 5:
        lo = max(points[-1] + 60, target - search_sec)
        hi = min(total - 5, target + search_sec)
        if hi <= lo:
            points.append(target)
            target += chunk_sec
            continue
        a, b = int(lo * TARGET_SR), int(hi * TARGET_SR)
        seg = wav24[a:b]
        nwin = len(seg) // win
        if nwin < 2:
            points.append(target)
        else:
            rms = np.sqrt(np.mean(seg[: nwin * win].reshape(nwin, win) ** 2,
                                  axis=1)) + 1e-9
            k = int(np.argmin(rms))
            points.append(round(lo + k + 0.5, 2))
        target = points[-1] + chunk_sec
    points.append(total)
    return points


# ---------------------------------------------------------------- 单块转写
def parse_segments(text: str) -> list:
    segs = []
    json_pat = re.compile(
        r'\{\s*"Start"\s*:\s*([\d.]+)\s*,\s*"End"\s*:\s*([\d.]+)\s*,'
        r'\s*"Speaker"\s*:\s*(\d+)\s*,\s*"Content"\s*:\s*"([^"]*)"\s*\}')
    for m in json_pat.finditer(text):
        seg = {"start": float(m.group(1)), "end": float(m.group(2)),
               "spk": int(m.group(3)), "content": m.group(4)}
        if segs and seg["start"] < segs[-1]["start"] - 1.0:
            break  # 模型偶尔输出两遍 JSON：时间轴回卷即截断
        segs.append(seg)
    return segs


def transcribe_chunk(model, processor, wav24: np.ndarray, t0: float, t1: float,
                     hotwords: str | None, chunk_idx: int) -> list:
    import torch
    piece = wav24[int(t0 * TARGET_SR): int(t1 * TARGET_SR)]
    dur = len(piece) / TARGET_SR
    if dur < 1.0:
        return []
    max_new = min(32768, int(dur * 18) + 384)
    kwargs = {"context_info": hotwords} if hotwords else {}
    inputs = processor(audio=piece, sampling_rate=TARGET_SR,
                       return_tensors="pt", **kwargs)
    inputs = {k: (v.to("cuda") if hasattr(v, "to") else v)
              for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new,
                             do_sample=False)
    text = processor.batch_decode(out, skip_special_tokens=True)[0]
    segs = parse_segments(text)
    result = []
    for s in segs:
        if s["end"] - s["start"] < 0.2 or not s["content"].strip():
            continue
        result.append({
            "start": round(t0 + s["start"], 2),
            "end": round(t0 + min(s["end"], dur), 2),
            "speaker_label": f"c{chunk_idx}s{s['spk']}",
            "content": s["content"].strip(),
        })
    return result


# ---------------------------------------------------------------- 主流程
def run_job(job: dict) -> dict:
    t_start = time.perf_counter()
    wav16 = load_wav_16k(job["audio_wav"])
    audio_sec = len(wav16) / SR
    wav24 = resample_24k(wav16)
    print(f"[worker] audio {audio_sec:.1f}s, resampled 24kHz", flush=True)

    model, processor = load_asr_model(
        job.get("model_dir", os.environ.get("GPU_ASR_MODEL_DIR", DEF_MODEL_DIR)),
        job.get("tokenizer_dir", os.environ.get("GPU_ASR_TOKENIZER_DIR",
                                                DEF_TOKENIZER_DIR)),
        job.get("asr_repo", os.environ.get("GPU_ASR_REPO", DEF_ASR_REPO)))
    load_sec = time.perf_counter() - t_start
    peak_vram = vram_used_mb()
    print(f"[worker] model loaded {load_sec:.1f}s, vram={peak_vram}MB", flush=True)

    hotwords = job.get("hotwords")
    chunk_sec = float(job.get("chunk_sec", 900))
    points = find_chunk_points(wav24, chunk_sec)
    print(f"[worker] chunks: {[(round(a), round(b)) for a, b in zip(points, points[1:])]}", flush=True)

    t1 = time.perf_counter()
    segments = []
    for ci, (a, b) in enumerate(zip(points, points[1:])):
        segs = transcribe_chunk(model, processor, wav24, a, b, hotwords, ci)
        segments.extend(segs)
        print(f"[worker] chunk {ci}: +{len(segs)} segs (total {len(segments)})", flush=True)
    infer_sec = time.perf_counter() - t1

    return {
        "status": "ok",
        "segments": segments,
        "meta": {
            "model_load_sec": round(load_sec, 2),
            "infer_sec": round(infer_sec, 2),
            "audio_sec": round(audio_sec, 2),
            "rtf": round(infer_sec / max(audio_sec, 1), 3),
            "chunks": len(points) - 1,
            "peak_vram_mb": peak_vram,
            "worker_pid": os.getpid(),
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--output")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    result = {"status": "error", "segments": [],
              "meta": {"worker_pid": os.getpid()}}

    def _write_and_exit(code: int):
        if args.output:
            Path(args.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8")
        sys.stdout.flush()
        sys.exit(code)  # 进程退出 = CUDA 上下文销毁 = 显存释放保证

    try:
        if args.selftest:
            # 生命周期自测：分块逻辑 + JSON 管线（跳过模型加载，无 GPU 也可跑）
            pts = find_chunk_points(np.zeros(TARGET_SR * 1000, dtype=np.float32), 300)
            assert len(pts) == 5, f"分块点数异常: {pts}"  # 1000s/300s → 4 块
            result.update({
                "status": "ok", "segments": [],
                "meta": {"chunk_points": pts,
                         "vram_used_mb": vram_used_mb()}})
            _write_and_exit(0)

        job = json.loads(Path(args.job).read_text(encoding="utf-8"))
        result = run_job(job)
        _write_and_exit(0)
    except Exception as e:  # noqa: BLE001 — worker 必须以 JSON 报告一切失败
        result["error"] = f"{type(e).__name__}: {e}"
        _write_and_exit(1)


if __name__ == "__main__":
    main()
