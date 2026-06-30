#!/usr/bin/env python3
"""
从已保存的 transcripts 重建 metrics.json。
当 benchmark_asr.py 中途崩溃时, transcripts 仍然存在, 用此脚本补 metrics。

用法:
    python scripts/aggregate_metrics.py --transcripts-dir results/asr_benchmark_2026-06-30/transcripts/ \
        --ground-truth data/asr_eval/ground_truth.jsonl \
        --output-dir results/asr_benchmark_2026-06-30/
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from statistics import median
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_ground_truth(gt_path: Path) -> dict:
    gt = {}
    with open(gt_path) as f:
        for line in f:
            rec = json.loads(line)
            audio_path = rec.get("audio_path", "")
            text = rec.get("text", "")
            if audio_path and text:
                # 多种 key 形式
                gt[Path(audio_path).name] = text
                gt[audio_path] = text
                abs_path = rec.get("absolute_path", "")
                if abs_path:
                    gt[abs_path] = text
    return gt


def parse_transcript(path: Path) -> dict:
    """解析 transcript txt 文件, 返回 backend, audio, raw_text, clean_text"""
    content = path.read_text(encoding="utf-8", errors="ignore")
    # 格式: "=== {backend} | {audio} ==="
    m = re.match(r"===\s+(\S+)\s+\|\s+(\S+)\s+===", content)
    if not m:
        return {}
    backend, audio = m.group(1), m.group(2)
    # Raw text
    raw_m = re.search(r"Raw text \(length=\d+\):\n(.*?)\n\nClean text", content, re.DOTALL)
    raw_text = raw_m.group(1) if raw_m else ""
    # Clean text
    clean_m = re.search(r"Clean text \(length=\d+\):\n(.*?)(?:\n===|$)", content, re.DOTALL)
    clean_text = clean_m.group(1).strip() if clean_m else raw_text.strip()
    return {"backend": backend, "audio": audio, "raw_text": raw_text, "clean_text": clean_text}


def get_audio_duration(audio_path: Path) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def hallucination_count(text: str) -> int:
    from app.voice.asr_filters import _has_strong_hallucination, _has_weak_hallucination, _is_repetitive_text, _is_alphanumeric_run
    count = 0
    if _has_strong_hallucination(text):
        count += 1
    if _has_weak_hallucination(text, audio_rms=0.005):
        count += 1
    if _is_repetitive_text(text):
        count += 1
    if _is_alphanumeric_run(text):
        count += 1
    return count


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。！？、；：""''《》（）.,!?;:'\"]", "", text)
    return text


def compute_cer(ref: str, hyp: str) -> float:
    try:
        from jiwer import cer
        return cer(ref, hyp)
    except Exception:
        return -1.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transcripts-dir", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    transcripts_dir = Path(args.transcripts_dir)
    output_dir = Path(args.output_dir)
    gt_path = Path(args.ground_truth)

    ground_truth = load_ground_truth(gt_path)
    print(f"[INFO] Loaded {len(ground_truth)} ground truth records")

    # 按 backend 分组
    backend_metrics = {}
    for transcript_file in sorted(transcripts_dir.glob("*.txt")):
        info = parse_transcript(transcript_file)
        if not info:
            print(f"  [WARN] Failed to parse {transcript_file.name}")
            continue
        backend = info["backend"]
        audio = info["audio"]
        raw_text = info["raw_text"]
        clean_text = info["clean_text"]

        # 找 ground truth (by audio filename)
        gt_text = ""
        for k, v in ground_truth.items():
            if k.endswith(audio) or audio in k or k == audio:
                gt_text = v
                break

        # 音频时长
        audio_path = None
        for sub_dir in [ROOT / "data" / "asr_eval" / "synthetic",
                       ROOT / "data" / "asr_eval" / "normalized"]:
            for ext in [".wav", ".webm", ".m4a"]:
                p = sub_dir / audio
                # audio may be without extension (like meeting-083.webm vs meeting-083)
                if not p.exists() and "." not in audio:
                    p = sub_dir / f"{audio}{ext}"
                if p.exists():
                    audio_path = p
                    break
            if audio_path:
                break
        duration = get_audio_duration(audio_path) if audio_path else 0.0

        # CER
        raw_cer = compute_cer(gt_text, raw_text) if gt_text else None
        filtered_cer = None
        if gt_text and clean_text:
            from app.voice.asr_filters import apply_7_layers
            filtered_text = apply_7_layers(clean_text, audio_rms=0.5, segment_duration_sec=1.0)
            if filtered_text:
                filtered_cer = compute_cer(gt_text, filtered_text)
            else:
                filtered_cer = 0.0  # 全过滤掉

        # 幻觉
        raw_halluc = hallucination_count(raw_text)
        filtered_halluc = hallucination_count(clean_text)

        metric = {
            "backend": backend,
            "audio": audio,
            "duration_sec": duration,
            "rtf_median": -1.0,  # 没法从 transcript 反推
            "elapsed_median_sec": -1.0,
            "vram_peak_gb": -1.0,
            "vram_resident_gb": -1.0,
            "raw_cer": raw_cer,
            "filtered_cer": filtered_cer,
            "raw_hallucination_count": raw_halluc,
            "filtered_hallucination_count": filtered_halluc,
            "punctuation_present": "，" in clean_text or "。" in clean_text,
            "text_len": len(clean_text),
        }
        backend_metrics.setdefault(backend, []).append(metric)
        print(f"  [OK] {backend:12s} {audio:30s} dur={duration:6.1f}s "
              f"raw_cer={raw_cer} filt_cer={filtered_cer} text_len={len(clean_text)}")

    # 写 per-backend metrics.json
    metrics_dir = output_dir / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    for backend, ms in backend_metrics.items():
        with open(metrics_dir / f"{backend}.json", "w") as f:
            json.dump(ms, f, indent=2, ensure_ascii=False)
        print(f"[OK] Wrote {metrics_dir / f'{backend}.json'} ({len(ms)} records)")

    # 写 summary.json
    summary = {"date": "2026-06-30", "backends": backend_metrics, "note": "from transcripts (recovered)"}
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[OK] Wrote {output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()