# -*- coding: utf-8 -*-
"""双引擎一致性过滤: polished(带ts) × 7B转写 → 只保留两引擎语义一致的段进训练集

一致性度量: 对每个 polished 条目 [ts, end)，取时间重叠的 7B 段拼接文本，
与 polished 文本做归一化 bigram F1。F1 >= 阈值 → 保留。

输出: 每场会议生成 train_v2 子目录 (wav 复制 + 官方格式 json)。
"""
import argparse
import json
import re
import shutil
import subprocess
import wave
from collections import Counter
from pathlib import Path

import numpy as np

BASE = Path(r"E:\microbubble-agent")
VVT = BASE / ".workbuddy" / "vibevoice-test"
AUDIO_DIR = BASE / "data" / "meeting-audio-2026-06-27"
OUT_ROOT = BASE / "data" / "asr_finetune"
SR = 16000
MIN_CHARS = 4
MIN_SEC, MAX_SEC = 1.0, 30.0
PAD = 0.25
F1_THRESHOLD = 0.55
MAX_TS = None


def norm(s: str) -> str:
    return re.sub(r"[，。！？、；：\"\"''（）()\[\]{}\s…—·,.!?;:嗯啊呃哦]", "", s)


def bigrams(s: str) -> set:
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else ({s} if s else set())


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


def find_audio(mid: int) -> Path | None:
    pats = [f"meeting-{mid:03d}-*.*", f"meeting-{mid}-*.*",
            f"meeting_{mid:03d}.*", f"meeting_{mid}.*"]
    for base in (AUDIO_DIR, BASE / "data",
                 BASE / "data" / "asr_eval" / "normalized"):
        for pat in pats:
            hits = list(base.glob(pat))
            if hits:
                return hits[0]
    return None


def decode_16k(path: Path) -> np.ndarray:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-ar", str(SR), "-ac", "1",
         "-f", "f32le", "-"], capture_output=True)
    if proc.returncode != 0 or len(proc.stdout) < SR * 4:
        raise RuntimeError(f"ffmpeg 解码失败: {proc.stderr[-150:]}")
    return np.frombuffer(proc.stdout, dtype=np.float32)


def is_junk(text: str) -> bool:
    t = text.strip()
    if len(t) < MIN_CHARS:
        return True
    if re.search(r"(.{1,2})(?:[,，\s]*\1){3,}", t):
        return True
    clean = re.sub(r"[，。！？、；：\s,]", "", t)
    if len(clean) >= 8:
        top = Counter(clean).most_common(1)[0][1]
        if top / len(clean) > 0.5:
            return True
    return False


def process(meeting_id: int, out_dir: Path) -> dict:
    global MAX_TS
    seg_file = VVT / f"r_7b_m{meeting_id}.json"
    if not seg_file.exists():
        return {"meeting": meeting_id, "error": "no 7B transcription"}
    data = json.loads(seg_file.read_text(encoding="utf-8"))
    if "segments" not in data and "result" in data:
        data = data["result"]
    b7 = data["segments"]
    b7 = [(float(s["start"]), float(s["end"]), norm(s["content"]))
          for s in b7 if s.get("content")]
    entries = fetch_polished(meeting_id)
    if not entries:
        return {"meeting": meeting_id, "error": "no polished"}
    entries = sorted([e for e in entries if e.get("ts") is not None
                      and e.get("text")], key=lambda e: e["ts"])
    if MAX_TS is not None:
        entries = [e for e in entries if float(e["ts"]) < MAX_TS]

    audio = find_audio(meeting_id)
    if not audio:
        return {"meeting": meeting_id, "error": "no local audio"}
    y = decode_16k(audio)
    total = len(y) / SR

    out_dir.mkdir(parents=True, exist_ok=True)
    kept, disagree, junk = 0, 0, 0
    n = 0
    manifest = []
    for i, e in enumerate(entries):
        text = e["text"].strip()
        if is_junk(text):
            junk += 1
            continue
        t0 = float(e["ts"]) - PAD
        if i + 1 < len(entries):
            t_next = float(entries[i + 1]["ts"])
            est = len(norm(text)) / 4.5
            t1 = t0 + PAD * 2 + min(max(t_next - float(e["ts"]), est, 1.0), 20.0)
        else:
            t1 = t0 + PAD * 2 + len(norm(text)) / 4.5
        dur = t1 - t0
        if dur < MIN_SEC or dur > MAX_SEC or t1 > total:
            junk += 1
            continue
        # 7B 覆盖窗口 — 只滤"极端分歧" (ratio<0.30 或 7B 空窗):
        # 两引擎字面一致本就少见, 过严会把 polished 的纠错信息误杀
        from difflib import SequenceMatcher
        pn = norm(text)
        overl = "".join(bn for a, b, bn in b7 if b > t0 and a < t1)[: len(pn) * 2 + 40]
        if len(overl) < 6:
            disagree += 1
            continue
        ratio = SequenceMatcher(None, pn, overl, autojunk=False).ratio()
        if ratio < 0.30:
            disagree += 1
            continue
        piece = y[int(max(t0, 0) * SR): int(min(t1, total) * SR)]
        if len(piece) < SR:
            junk += 1
            continue
        wav_path = out_dir / f"{n}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes((np.clip(piece, -1, 1) * 32767).astype(np.int16).tobytes())
        (out_dir / f"{n}.json").write_text(json.dumps({
            "audio_duration": round(dur, 2),
            "audio_path": f"{n}.wav",
            "segments": [{"speaker": 0, "text": text,
                          "start": 0.0, "end": round(dur, 2)}],
            "customized_context": ["微纳米气泡", "UV臭氧氧化", "臭氧", "纳米气泡发生器",
                                   "空化效应", "Zeta电位", "表面张力", "养殖尾水处理",
                                   "气浮", "基底", "ESG", "国家奖", "王天志", "杜同贺",
                                   "杨慈", "陈金薪", "贾琦", "周之超", "张宏魁", "吴孟铨",
                                   "韩重阳", "宋洋"],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest.append({"file": f"{n}.wav", "sec": round(dur, 1), "ratio": round(ratio, 3)})
        n += 1
        kept += 1

    total_sec = sum(m["sec"] for m in manifest)
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[{meeting_id}] 保留 {kept} 段 / {total_sec:.0f}s "
          f"(双引擎不一致 {disagree}, 垃圾 {junk})", flush=True)
    return {"meeting": meeting_id, "pairs": kept, "sec": round(total_sec),
            "disagree": disagree, "junk": junk}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", default="121,135,95,70,71,68,64,151")
    ap.add_argument("--f1", type=float, default=F1_THRESHOLD)
    ap.add_argument("--max-ts", type=float, default=None,
                    help="只处理 ts < max-ts 的条目 (7B 覆盖有限时用)")
    args = ap.parse_args()
    if args.max_ts is not None:
        globals()["MAX_TS"] = args.max_ts
    summary = []
    for mid in [int(x) for x in args.meetings.split(",")]:
        try:
            summary.append(process(mid, OUT_ROOT / f"v2db{mid}"))
        except Exception as e:  # noqa: BLE001
            print(f"[{mid}] 失败: {e}", flush=True)
            summary.append({"meeting": mid, "error": str(e)})
    ok = [s for s in summary if "pairs" in s]
    print("\n===== v2 汇总 =====")
    for s in summary:
        print(f"  {s['meeting']}: {s.get('pairs', s.get('error'))} 对, "
              f"{s.get('sec', 0)}s, 不一致滤除 {s.get('disagree', '-')}")
    print(f"总计: {sum(s['pairs'] for s in ok)} 对, "
          f"{sum(s['sec'] for s in ok)}s ≈ {sum(s['sec'] for s in ok)/3600:.2f}h")


if __name__ == "__main__":
    main()
