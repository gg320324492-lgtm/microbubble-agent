# -*- coding: utf-8 -*-
"""GPU 会议处理 worker（子进程入口）

每次会议处理由 manager.py 拉起本进程，处理完毕进程退出 → 显存彻底释放。

用法:
  python -m app.gpu_worker.meeting_worker --job job.json --output result.json
  python -m app.gpu_worker.meeting_worker --selftest   # 无 GPU 验证生命周期管线

Job JSON:
{
  "task": "transcribe_meeting",
  "audio_path": "E:/microbubble-agent/data/.../meeting-xxx.wav",
  "hotwords": ["微纳米气泡", "UV臭氧", "王天志"],       # 可选
  "members": [{"id": 1, "name": "王天志", "embedding": [0.1, ...]}],  # anchor 声纹
  "match_threshold": 0.7,
  "model": "microsoft/VibeVoice-ASR-7B",
  "asr_repo": "E:/path/to/VibeVoice"                    # 可选: 官方仓库路径
}

Result JSON:
{
  "status": "ok" | "error",
  "segments": [{"speaker": "王天志", "speaker_label": "Speaker 1",
                "start": 0.0, "end": 12.3, "text": "..."}],
  "speaker_map": {"Speaker 1": {"name": "王天志", "member_id": 1,
                                 "dist": 0.31, "segments": 55}},
  "meta": {"model_load_sec": 42.1, "infer_sec": 130.0, "audio_sec": 1216.0,
           "peak_vram_mb": 16200, "worker_pid": 12345}
}
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------- 声纹名字映射
def map_speakers_to_members(
    segments: list,
    members: list,
    match_threshold: float = 0.7,
) -> dict:
    """说话人簇质心 ↔ 成员声纹 匹配（会议级投票，非单段匹配）

    segments: [{"speaker_label": "Speaker 1", "start": s, "end": e}, ...]
              需带 audio_path 时由调用方先提嵌入（此处假设已完成）
    members:  [{"id": 1, "name": "王天志", "embedding": [...]}]
    返回: {"Speaker 1": {"name": ..., "member_id": ..., "dist": ..., "segments": n}}
          无法匹配（dist >= threshold）时 name=None。
    """
    # 每个说话人聚合全部时段 → 质心（会议级投票）
    cluster_emb = {}
    for seg, emb in segments:
        label = seg.get("speaker_label") or "Unknown"
        cluster_emb.setdefault(label, []).append(emb)

    mapping = {}
    for label, embs in cluster_emb.items():
        cent = np.mean(np.stack(embs), axis=0)
        norm = float(np.linalg.norm(cent))
        cent = cent / norm if norm > 1e-6 else cent
        best = None
        for m in members:
            v = np.asarray(m["embedding"], dtype=np.float32)
            vn = float(np.linalg.norm(v))
            if vn < 1e-6:
                continue  # 跳过坏向量
            v = v / vn
            dist = float(1.0 - float(np.dot(cent, v)))
            if best is None or dist < best[0]:
                best = (dist, m)
        if best is not None and best[0] < match_threshold:
            dist, m = best
            mapping[label] = {"name": m["name"], "member_id": m["id"],
                              "dist": round(dist, 4), "segments": len(embs)}
        else:
            mapping[label] = {"name": None, "member_id": None,
                              "dist": None if best is None else round(best[0], 4),
                              "segments": len(embs)}
    return mapping


# ---------------------------------------------------------------- VRAM 探针
def vram_used_mb() -> int | None:
    """当前 GPU 显存占用 (MB)；驱动不可用时返回 None"""
    import subprocess
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return None
        return int(r.stdout.strip().splitlines()[0])
    except Exception:
        return None


# ---------------------------------------------------------------- ASR 推理
def load_asr_model(model_id: str, asr_repo: str | None):
    """载入 VibeVoice-ASR（EXPERIMENTAL：待 GPU 驱动修复后按官方
    demo/vibevoice_asr_inference_from_file.py 校准调用方式）

    优先策略:
      1. asr_repo 指向官方 VibeVoice 仓库 → 复用其推理实现
      2. 否则 transformers AutoModel 加载 (microsoft/VibeVoice-ASR-HF)
    """
    import torch
    from transformers import AutoModel, AutoProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        raise RuntimeError(
            "CUDA 不可用（当前驱动异常或无 GPU）。"
            "会议 worker 必须跑在 GPU 上，请先修复 NVIDIA 驱动。")
    model = AutoModel.from_pretrained(model_id, torch_dtype=torch.float16)
    model = model.to(device).eval()
    try:
        processor = AutoProcessor.from_pretrained(model_id)
    except Exception:
        processor = None
    return model, processor, device


def run_asr_inference(model, processor, device: str, audio_path: str,
                      hotwords: list | None, asr_repo: str | None) -> list:
    """执行转写，返回结构化段落
    [{speaker_label, start, end, text}, ...] （EXPERIMENTAL，待 GPU 实测校准）
    """
    import torch
    t0 = time.perf_counter()
    # TODO(GPU 复测): 按 VibeVoice 官方 demo 校准 preprocess/generate/解析
    # 官方输出含 "Start"/"End"/"Speaker"/"Content" 结构化字段
    wav, sr = _load_audio_16k(audio_path)
    inputs = processor(wav, sampling_rate=sr, return_tensors="pt",
                       hotwords=hotwords or None)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=8192)
    text = processor.batch_decode(out, skip_special_tokens=True)[0]
    segments = _parse_structured_output(text)
    _ = time.perf_counter() - t0
    return segments


def _load_audio_16k(path: str):
    import soundfile as sf
    import scipy.signal as sps
    wav, sr = sf.read(path, dtype="float32")
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != 16000:
        wav = sps.resample_poly(wav, 16000, sr).astype(np.float32)
        sr = 16000
    return wav, sr


def _parse_structured_output(text: str) -> list:
    """解析官方结构化输出 → 段落列表（容错：无结构时退化为单段）"""
    import re
    segs = []
    pat = re.compile(
        r"\[?([\d.]+)\s*-\s*([\d.]+)\]?\s*(?:Speaker\s*(\d+))?\s*[:：]\s*(.+)")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = pat.match(line)
        if m:
            segs.append({"speaker_label": f"Speaker {m.group(3)}" if m.group(3)
                         else "Unknown",
                         "start": float(m.group(1)), "end": float(m.group(2)),
                         "text": m.group(4).strip()})
    if not segs and text.strip():
        segs = [{"speaker_label": "Unknown", "start": 0.0, "end": 0.0,
                 "text": text.strip()}]
    return segs


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", help="job JSON 路径")
    ap.add_argument("--output", help="result JSON 输出路径")
    ap.add_argument("--selftest", action="store_true",
                    help="无 GPU 生命周期自测（跳过模型加载）")
    args = ap.parse_args()

    result = {"status": "error", "segments": [], "speaker_map": {},
              "meta": {"worker_pid": __import__("os").getpid()}}

    def _write_and_exit(code: int):
        if args.output:
            Path(args.output).write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8")
        # flush 后退出 —— exit 即显存释放保证
        sys.stdout.flush()
        sys.exit(code)

    try:
        if args.selftest:
            # 自测: 模拟段落 + 假成员，验证 JSON 管线与映射逻辑
            rng = np.random.default_rng(7)
            base = rng.normal(size=192).astype(np.float32)
            base /= np.linalg.norm(base)
            members = [{"id": 1, "name": "王天志",
                        "embedding": (base + rng.normal(scale=0.02, size=192)
                                      ).tolist()},
                       {"id": 2, "name": "杨慈",
                        "embedding": np.zeros(192).tolist()}]  # 坏向量应被跳过
            segs = []
            for i in range(10):
                emb = (base + rng.normal(scale=0.05, size=192)).astype(np.float32)
                emb /= np.linalg.norm(emb)
                segs.append(({"speaker_label": "Speaker 1", "start": i * 10.0,
                              "end": i * 10.0 + 8.0, "text": f"seg{i}"}, emb.tolist()))
            t0 = time.perf_counter()
            mapping = map_speakers_to_members(segs, members)
            result.update({
                "status": "ok",
                "segments": [s for s, _ in segs],
                "speaker_map": mapping,
                "meta": {**result["meta"],
                         "selftest_sec": round(time.perf_counter() - t0, 3),
                         "vram_used_mb": vram_used_mb()}})
            _write_and_exit(0)

        job = json.loads(Path(args.job).read_text(encoding="utf-8"))
        audio_path = job["audio_path"]
        hotwords = job.get("hotwords") or []
        members = job.get("members") or []
        threshold = float(job.get("match_threshold", 0.7))
        model_id = job.get("model", "microsoft/VibeVoice-ASR-7B")
        asr_repo = job.get("asr_repo")

        t0 = time.perf_counter()
        model, processor, device = load_asr_model(model_id, asr_repo)
        load_sec = time.perf_counter() - t0
        peak_vram = vram_used_mb()

        infer0 = time.perf_counter()
        segments = run_asr_inference(model, processor, device, audio_path,
                                     hotwords, asr_repo)
        infer_sec = time.perf_counter() - infer0

        # 会议级声纹映射：对每个 Speaker 聚合其段落嵌入质心
        # （嵌入提取复用 app/services/voiceprint_service.py 的 ERes2Net）
        from app.services.voiceprint_service import VoiceprintService
        vs = VoiceprintService()
        import soundfile as sf
        wav, _ = sf.read(audio_path, dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        pairs = []
        for seg in segments:
            a, b = int(seg.get("start", 0) * 16000), int(seg.get("end", 0) * 16000)
            chunk = wav[a:b] if b > a else wav[:16000]
            if len(chunk) < 8000:
                chunk = np.pad(chunk, (0, 16000 - len(chunk)))
            pairs.append((seg, vs.extract_embedding(chunk.astype(np.float32)).tolist()))
        mapping = map_speakers_to_members(pairs, members, threshold)

        named = []
        for seg in segments:
            m = mapping.get(seg.get("speaker_label"), {})
            named.append({**seg, "speaker": m.get("name") or seg.get("speaker_label")})

        result.update({
            "status": "ok",
            "segments": named,
            "speaker_map": mapping,
            "meta": {**result["meta"], "model_load_sec": round(load_sec, 2),
                     "infer_sec": round(infer_sec, 2), "device": device,
                     "peak_vram_mb": peak_vram}})
        _write_and_exit(0)

    except Exception as e:  # noqa: BLE001 — worker 必须以 JSON 报告一切失败
        result["error"] = f"{type(e).__name__}: {e}"
        _write_and_exit(1)


if __name__ == "__main__":
    main()
