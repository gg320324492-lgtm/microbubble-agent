# -*- coding: utf-8 -*-
"""ASR LoRA 微调数据准备 — DB transcript_polished 时间戳直切版 (2026-09-07)

比 md 对齐版 (prepare_asr_finetune_data.py) 更强：
  transcript_polished 是 [{"speaker","text","ts"}] JSON，自带秒级时间戳，
  直接按 ts 从音频切片配文本，无需任何模型对位、无需 GPU。

过滤规则 (弱监督去噪):
  - 文本 < 4 字符 跳过
  - 同一 token 重复 ≥4 次 (LLM 幻觉如 "这,这,这,这") 跳过
  - 切片时长 < 1s 或 > 30s 跳过
  - 段末 = 下一相邻条目的 ts (间隔 >6s 时按 4.5字/秒 估算)

用法:
  python scripts/prepare_asr_finetune_data_db.py \
      --meeting 121 --audio "data/meeting-audio-2026-06-27/meeting-121-xxx.webm" \
      --out data/asr_finetune/db121
批量: --meetings 121,135,95,70,71,68,64,83
"""
import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

BASE = Path(r"E:\microbubble-agent")
AUDIO_DIR = BASE / "data" / "meeting-audio-2026-06-27"
OUT_ROOT = BASE / "data" / "asr_finetune"
SR = 16000
MIN_CHARS = 4
MIN_SEC, MAX_SEC = 1.0, 30.0
PAD = 0.25
CPS = 4.5  # 中文语速估算 字/秒


def fetch_polished(meeting_id: int) -> list | None:
    r = subprocess.run(
        ["docker", "exec", "microbubble-agent-db-1", "psql", "-U", "postgres",
         "-d", "microbubble", "-At", "-c",
         f"SELECT transcript_polished::text FROM meetings WHERE id={meeting_id}"],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout.strip())
    except json.JSONDecodeError:
        return None


def find_local_audio(meeting_id: int) -> Path | None:
    pats = [f"meeting-{meeting_id:03d}-*.*", f"meeting-{meeting_id}-*.*",
            f"meeting_{meeting_id:03d}.*", f"meeting_{meeting_id}.*",
            f"meeting-{meeting_id:03d}.*"]
    for base in (AUDIO_DIR, BASE / "data", BASE / "data" / "asr_eval" / "normalized"):
        for pat in pats:
            hits = list(base.glob(pat))
            if hits:
                return hits[0]
    return None


def decode_16k(path: Path) -> np.ndarray:
    """ffmpeg 解码任意格式 → 16kHz mono float32"""
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ar", str(SR), "-ac", "1",
         "-f", "f32le", "-"], capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) < SR * 4:
        raise RuntimeError(f"ffmpeg 解码失败: {proc.stderr[-200:]}")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def is_junk(text: str) -> bool:
    t = text.strip()
    if len(t) < MIN_CHARS:
        return True
    # 重复 token 幻觉: 单字/双字 连续 ≥4 次
    if re.search(r"(.{1,2})(?:[,，\s]*\1){3,}", t):
        return True
    # 同字占比过高
    from collections import Counter
    clean = re.sub(r"[，。！？、；：\s,]", "", t)
    if len(clean) >= 8:
        top = Counter(clean).most_common(1)[0][1]
        if top / len(clean) > 0.5:
            return True
    return False


import re


def process_meeting(meeting_id: int, audio_path: Path, out_dir: Path,
                    min_score_len: int = 4) -> dict:
    entries = fetch_polished(meeting_id)
    if not entries:
        return {"meeting": meeting_id, "error": "no polished transcript"}
    entries = [e for e in entries if isinstance(e, dict) and e.get("ts") is not None
               and e.get("text")]
    entries.sort(key=lambda e: e["ts"])
    print(f"[{meeting_id}] polished 条目: {len(entries)}")

    y = decode_16k(audio_path)
    total = len(y) / SR
    print(f"[{meeting_id}] audio {total:.0f}s @ {audio_path.name}")

    out_dir.mkdir(parents=True, exist_ok=True)
    kept, skipped = 0, 0
    manifest = []
    n = 0
    for i, e in enumerate(entries):
        text = e["text"].strip()
        if is_junk(text):
            skipped += 1
            continue
        t0 = max(0.0, float(e["ts"]) - PAD)
        # 段末: 下一相邻条目 ts; 若间隔过大 (>6s) 按语速估算
        if i + 1 < len(entries):
            t_next = float(entries[i + 1]["ts"])
            est = len(re.sub(r"[，。！？、；：\s,]", "", text)) / CPS
            t1 = t0 + PAD * 2 + (min(t_next - float(e["ts"]), max(est, 1.0)))
        else:
            t1 = t0 + PAD * 2 + len(re.sub(r"[，。！？、；：\s,]", "", text)) / CPS
        dur = t1 - t0
        if dur < MIN_SEC or dur > MAX_SEC or t1 > total:
            skipped += 1
            continue
        piece = y[int(t0 * SR): int(t1 * SR)]
        if len(piece) < SR or np.max(np.abs(piece)) < 0.005:
            skipped += 1
            continue
        wav_path = out_dir / f"{n}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes((np.clip(piece, -1, 1) * 32767).astype(np.int16).tobytes())
        (out_dir / f"{n}.json").write_text(json.dumps({
            "audio_duration": round(dur, 2),
            "transcript": [{"speaker": e.get("speaker") or "未知",
                            "content": text}],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest.append({"file": f"{n}.wav", "sec": round(dur, 1),
                         "speaker": e.get("speaker"), "ts": e["ts"]})
        n += 1
        kept += 1

    total_sec = sum(m["sec"] for m in manifest)
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{meeting_id}] 导出 {kept} 对 / {total_sec:.0f}s (跳过 {skipped})")
    return {"meeting": meeting_id, "pairs": kept, "sec": round(total_sec),
            "skipped": skipped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", default="121,135,95,70,71,68,64,151,153")
    ap.add_argument("--audio-dir", default=str(AUDIO_DIR))
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    args = ap.parse_args()

    ids = [int(x) for x in args.meetings.split(",") if x.strip()]
    summary = []
    for mid in ids:
        audio = find_local_audio(mid)
        if not audio:
            print(f"[{mid}] 本地无音频, 跳过")
            summary.append({"meeting": mid, "error": "no local audio"})
            continue
        try:
            summary.append(process_meeting(mid, audio,
                                           Path(args.out_root) / f"db{mid}"))
        except Exception as e:  # noqa: BLE001
            print(f"[{mid}] 失败: {e}")
            summary.append({"meeting": mid, "error": str(e)})

    ok = [s for s in summary if "pairs" in s]
    total_pairs = sum(s["pairs"] for s in ok)
    total_sec = sum(s["sec"] for s in ok)
    print("\n===== 汇总 =====")
    for s in summary:
        print(f"  meeting {s['meeting']}: "
              f"{s.get('pairs', s.get('error'))} 对, {s.get('sec', 0)}s")
    print(f"总计: {total_pairs} 对, {total_sec}s ≈ {total_sec/3600:.2f}h 可用训练音频")


if __name__ == "__main__":
    main()
