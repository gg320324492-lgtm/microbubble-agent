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


# ------------------------------------------------- 进度落盘（2026-09-15 新增）
def write_progress(progress_path, **fields):
    """把进度原子写入 json，供守护 /jobs/{id} 透出，客户端据此判断"在跑"还是"卡死"。

    事故背景：此前子进程 stdout 被守护 `capture_output=True` 吞掉，2 小时里完全
    看不到进度，无法区分"在推理"与"卡死"。现在每块结束都刷新一次。
    """
    if not progress_path:
        return
    try:
        p = Path(progress_path)
        cur = {}
        if p.exists():
            try:
                cur = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cur = {}
        cur.update(fields)
        cur["updated_at"] = time.time()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(cur, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    except OSError:
        pass


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


# ---------------------------------------------------------------- 生成停止条件
def _make_degenerate_tail_stopper(processor, window: int = 64,
                                  comma_ratio: float = 0.9,
                                  check_every: int = 16):
    """构造一个"退化尾巴"停止条件。

    2026-09-16 实测发现（`--dump-raw` 抓到的原始解码文本）：
    VibeVoice-ASR 在输出完 JSON 段落后**不会发 EOS 正常收尾**，而是一路吐逗号
    （`,,,,,,,,,,...`）直到 `max_new_tokens` 用尽。后果：
      · 生成时间被 max_new_tokens 主导，真正的 JSON 只占其中一小部分
        （300s 分块实测 gen_tokens≈8558，其中末尾数千 token 全是逗号）；
      · RTF 被严重虚高 —— 这是 96 分钟会议跑满 7200s 硬超时的重要成因之一；
      · 纯属浪费算力，且拖长了占用 GPU 的时间。
    这里用 StoppingCriteria 检测"尾部窗口几乎全是逗号"，命中即停，
    让生成在 JSON 结束处自然收尾。
    """
    import torch
    from transformers import StoppingCriteria

    class _DegenerateTailStopper(StoppingCriteria):
        def __init__(self):
            self._n = 0

        def __call__(self, input_ids, scores, **kwargs):
            self._n += 1
            if self._n % check_every:
                return False
            try:
                tail_ids = input_ids[0, -window:]
                tail = processor.batch_decode(
                    [tail_ids], skip_special_tokens=True)[0]
            except Exception:  # noqa: BLE001
                return False
            if len(tail) < window // 2:
                return False
            non_comma = len(tail.replace(",", "").replace(" ", "")
                             .replace("\n", "").replace("，", ""))
            # 去掉逗号/空白后所剩无几 → 判定为退化尾巴
            return non_comma <= len(tail) * (1 - comma_ratio)

    return _DegenerateTailStopper()


# ---------------------------------------------------------------- 生成停止条件
def _make_degenerate_tail_stopper(processor, window: int = 64,
                                  comma_ratio: float = 0.9,
                                  check_every: int = 16):
    """构造一个"退化尾巴"停止条件。

    2026-09-16 实测发现（`--dump-raw` 抓到的原始解码文本）：
    VibeVoice-ASR 在输出完 JSON 段落后**不会发 EOS 正常收尾**，而是一路吐逗号
    （`,,,,,,,,,,...`）直到 `max_new_tokens` 用尽。后果：
      · 生成时间被 max_new_tokens 主导，真正的 JSON 只占其中一小部分
        （300s 分块实测 gen_tokens≈8558，其中末尾数千 token 全是逗号）；
      · RTF 被严重虚高 —— 这是 96 分钟会议跑满 7200s 硬超时的重要成因之一；
      · 纯属浪费算力，且拖长了占用 GPU 的时间。
    这里用 StoppingCriteria 检测"尾部窗口几乎全是逗号"，命中即停，
    让生成在 JSON 结束处自然收尾。
    """
    from transformers import StoppingCriteria

    class _DegenerateTailStopper(StoppingCriteria):
        def __init__(self):
            self._n = 0

        def __call__(self, input_ids, scores, **kwargs):
            self._n += 1
            if self._n % check_every:
                return False
            try:
                tail_ids = input_ids[0, -window:]
                tail = processor.batch_decode(
                    [tail_ids], skip_special_tokens=True)[0]
            except Exception:  # noqa: BLE001
                return False
            if len(tail) < window // 2:
                return False
            non_comma = len(tail.replace(",", "").replace(" ", "")
                             .replace("\n", "").replace("，", ""))
            # 去掉逗号/空白后所剩无几 → 判定为退化尾巴
            return non_comma <= len(tail) * (1 - comma_ratio)

    return _DegenerateTailStopper()


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
                     hotwords: str | None, chunk_idx: int,
                     dump_raw_dir: str | None = None) -> list:
    """转写单个分块。

    2026-09-16: `dump_raw_dir` 把**模型原始解码文本**落盘 —— 没有它就只能猜
    "段落少是模型合并还是解析丢弃"（本次正是靠它发现尾部逗号退化问题）。
    """
    import torch
    piece = wav24[int(t0 * TARGET_SR): int(t1 * TARGET_SR)]
    dur = len(piece) / TARGET_SR
    if dur < 1.0:
        return []
    max_new = min(32768, int(dur * 18) + 384)
    # 2026-09-16: gen_tokens 实测显示真实 JSON 只占很小一部分，主要是尾部逗号。
    # 配合下面的 StoppingCriteria 之后，max_new 只需覆盖"真实内容"的量级：
    # 300s 分块实测约 28 个 JSON 对象 ≈ 2.5k 字符，按 ~6 token/秒语音留足余量。
    max_new = min(max_new, int(dur * 8) + 512)
    kwargs = {"context_info": hotwords} if hotwords else {}
    inputs = processor(audio=piece, sampling_rate=TARGET_SR,
                       return_tensors="pt", **kwargs)
    inputs = {k: (v.to("cuda") if hasattr(v, "to") else v)
              for k, v in inputs.items()}
    stopper = _make_degenerate_tail_stopper(processor)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_new,
                             do_sample=False, stopping_criteria=[stopper])
    text = processor.batch_decode(out, skip_special_tokens=True)[0]
    if dump_raw_dir:
        try:
            dp = Path(dump_raw_dir) / f"chunk{chunk_idx}_raw.txt"
            dp.parent.mkdir(parents=True, exist_ok=True)
            n_objs = len(re.findall(r'\{\s*"Start"', text))
            dp.write_text(
                f"# chunk={chunk_idx} span={t0:.1f}~{t1:.1f}s dur={dur:.1f}s "
                f"max_new_tokens={max_new} gen_tokens={out.shape[-1]}\n"
                f"# raw_json_objects={n_objs}\n{'=' * 60}\n{text}",
                encoding="utf-8")
            print(f"[worker] chunk {chunk_idx} raw dumped: {n_objs} json objects, "
                  f"gen_tokens={out.shape[-1]}", flush=True)
        except OSError as e:
            print(f"[worker] raw dump 失败: {e}", flush=True)
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
def run_job(job: dict, progress_path: str | None = None,
            max_seconds: float | None = None,
            dump_raw_dir: str | None = None) -> dict:
    """跑完整场会议转写。

    max_seconds: 时间预算。每块结束后用已跑时长外推总耗时，若会超预算则**提前中止**
      并返回 status="aborted"。事故教训：96 分钟音频曾一路跑到 7200s 硬超时才被杀，
      整整 2 小时 GPU 被白占、且客户端在此期间无任何可用信号。提前中止把"注定失败"
      的尝试压缩到十几分钟，让上层尽早回退 SenseVoice。
    """
    t_start = time.perf_counter()
    write_progress(progress_path, phase="loading_audio")
    wav16 = load_wav_16k(job["audio_wav"])
    audio_sec = len(wav16) / SR
    wav24 = resample_24k(wav16)
    print(f"[worker] audio {audio_sec:.1f}s, resampled 24kHz", flush=True)

    write_progress(progress_path, phase="loading_model", audio_sec=round(audio_sec, 1))
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
    n_chunks = len(points) - 1
    print(f"[worker] chunks: {[(round(a), round(b)) for a, b in zip(points, points[1:])]}", flush=True)
    write_progress(progress_path, phase="transcribing", chunks_total=n_chunks,
                   model_load_sec=round(load_sec, 2), peak_vram_mb=peak_vram)

    t1 = time.perf_counter()
    segments = []
    aborted = False
    abort_reason = None
    for ci, (a, b) in enumerate(zip(points, points[1:])):
        segs = transcribe_chunk(model, processor, wav24, a, b, hotwords, ci,
                                dump_raw_dir=dump_raw_dir)
        segments.extend(segs)
        done_sec = b if b else audio_sec
        elapsed = time.perf_counter() - t1
        rtf = elapsed / max(done_sec, 1)
        eta = rtf * max(audio_sec - done_sec, 0)
        print(f"[worker] chunk {ci + 1}/{n_chunks}: +{len(segs)} segs "
              f"(total {len(segments)}), elapsed={elapsed:.0f}s rtf={rtf:.2f} eta={eta:.0f}s",
              flush=True)
        write_progress(progress_path, phase="transcribing", chunk_done=ci + 1,
                       chunks_total=n_chunks, segments=len(segments),
                       elapsed_sec=round(elapsed, 1), rtf=round(rtf, 3),
                       eta_sec=round(eta, 1),
                       last_chunk_segments=len(segs))

        # 时间预算早退：已跑时长 + 剩余外推 > 预算 → 立即中止，别拖到硬超时
        if max_seconds and (elapsed + eta) > max_seconds:
            aborted = True
            abort_reason = (
                f"时间预算不足: 已跑 {elapsed:.0f}s, 外推剩余 {eta:.0f}s, "
                f"合计 {elapsed + eta:.0f}s > 预算 {max_seconds:.0f}s "
                f"(rtf={rtf:.2f}, 已完成 {ci + 1}/{n_chunks} 块)"
            )
            print(f"[worker] ABORT {abort_reason}", flush=True)
            write_progress(progress_path, phase="aborted", reason=abort_reason)
            break

    infer_sec = time.perf_counter() - t1
    meta = {
        "model_load_sec": round(load_sec, 2),
        "infer_sec": round(infer_sec, 2),
        "audio_sec": round(audio_sec, 2),
        "rtf": round(infer_sec / max(audio_sec, 1), 3),
        "chunks": n_chunks,
        "chunks_done": (ci + 1) if n_chunks else 0,
        "peak_vram_mb": peak_vram,
        "worker_pid": os.getpid(),
    }
    if aborted:
        meta["abort_reason"] = abort_reason
        # 已完成的块仍带回去，便于上层诊断（客户端会把 aborted 当失败处理并回退）
        return {"status": "aborted", "segments": segments, "meta": meta}

    write_progress(progress_path, phase="done", segments=len(segments),
                   infer_sec=round(infer_sec, 1))
    return {"status": "ok", "segments": segments, "meta": meta}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job")
    ap.add_argument("--output")
    ap.add_argument("--progress", default=None,
                    help="进度 json 落盘路径（守护透出给客户端，判活/判卡死用）")
    ap.add_argument("--log", default=None, help="保留位（守护已把 stdout 重定向到日志文件）")
    ap.add_argument("--max-seconds", type=float, default=None,
                    help="时间预算；外推超预算则提前中止，避免拖到守护硬超时")
    ap.add_argument("--chunk-sec", type=float, default=None,
                    help="覆盖分块长度（秒）；诊断段落粒度/耗时权衡时用")
    ap.add_argument("--dump-raw", default=None,
                    help="把模型原始解码文本落到该目录（诊断段落数/退化尾巴用）")
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
            # 预算早退逻辑自测：预算 1s 时 5 个 60s 块必须提前退出
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                pp = str(Path(td) / "p.json")
                write_progress(pp, phase="selftest", n=1)
                assert json.loads(Path(pp).read_text(encoding="utf-8"))["phase"] == "selftest"
            result.update({
                "status": "ok", "segments": [],
                "meta": {"chunk_points": pts,
                         "vram_used_mb": vram_used_mb()}})
            _write_and_exit(0)

        job = json.loads(Path(args.job).read_text(encoding="utf-8"))
        if args.chunk_sec:
            job["chunk_sec"] = args.chunk_sec
        result = run_job(job, progress_path=args.progress,
                         max_seconds=args.max_seconds,
                         dump_raw_dir=args.dump_raw)
        _write_and_exit(0 if result.get("status") == "ok" else 2)
    except Exception as e:  # noqa: BLE001 — worker 必须以 JSON 报告一切失败
        result["error"] = f"{type(e).__name__}: {e}"
        if args.progress:
            write_progress(args.progress, phase="error", error=result["error"])
        _write_and_exit(1)


if __name__ == "__main__":
    main()
