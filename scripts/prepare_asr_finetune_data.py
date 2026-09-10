# -*- coding: utf-8 -*-
"""ASR LoRA 微调数据准备 — 半自动对齐版 (2026-09-07)

思路: VibeVoice 官方 finetuning-asr 要求数据格式为
    {n}.mp3 + {n}.json  (json: {"audio_duration": ..., "transcript": [...]})
人工校对稿 (如 meeting83_final.md) 没有时间戳, 无法直接切片。
本脚本用 7B 转写结果 (带精确时间戳) 作为"时间锚", 将人工稿按句对齐:

  1. 解析人工校对稿段落 (### N.【发言人】(N字) → 引用文本)
  2. 加载 7B 转写 segments (r_7b_full.json)
  3. 按字符 2-gram 滑动匹配, 把每个人工段对齐到 7B 段落的时间区间
  4. 按对齐区间切音频 → {n}.wav + {n}.json (transcript = 人工稿文本)

产出目录可直接喂给 finetuning-asr 训练脚本。
置信度: 对齐分数 < 阈值 (0.55) 的样本丢弃, 宁缺毋滥。

用法:
  python scripts/prepare_asr_finetune_data.py \
      --gt meeting83_final.md --segments .workbuddy/vibevoice-test/r_7b_full.json \
      --audio .workbuddy/vibevoice-test/meeting-083_16k.wav \
      --out data/asr_finetune/meeting083 [--min-score 0.55]
"""
import argparse
import json
import re
import wave
from pathlib import Path

import numpy as np


def parse_gt_paragraphs(md_path: Path):
    text = md_path.read_text(encoding="utf-8")
    body = text.split("## 会议内容")[-1]
    pat = re.compile(r"###\s*\d+\.【([^】]+)】\((\d+)字\)[^\n]*\n\n>((?:[^\n>]+\n?)+)")
    out = []
    for m in pat.finditer(body):
        speaker, n_str, content = m.group(1), m.group(2), m.group(3)
        content = re.sub(r"\s+", "", content)
        out.append({"speaker": speaker, "declared": int(n_str), "text": content})
    return out


def norm_for_align(s: str) -> str:
    return re.sub(r"[，。！？、；：\"\"''（）()\[\]{}\s…—·,.!?;:嗯啊呃哦]", "", s)


def bigrams(s: str) -> set:
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s} if s else set()


def align(gt_paras, segments):
    """difflib 字符级对位：把每个人工段映射到 7B 拼接文本上的时间区间

    拼接文本逐字符携带时间戳（段内线性插值）。
    评分 = 匹配字符数 / 人工段字符数 (0~1)。
    """
    from difflib import SequenceMatcher
    seg_texts, char_times = [], []  # char_times: 每个拼接字符的时间
    for s in segments:
        t = norm_for_align(s["content"])
        dur = max(s["end"] - s["start"], 0.2)
        for k, ch in enumerate(t):
            char_times.append(s["start"] + dur * k / max(len(t), 1))
        seg_texts.append(t)
    big = "".join(seg_texts)
    results, cursor = [], 0
    for para in gt_paras:
        ptxt = norm_for_align(para["text"])
        if len(ptxt) < 6:
            continue
        sm = SequenceMatcher(None, big[cursor:], ptxt, autojunk=False)
        mb = sm.get_matching_blocks()
        matched = sum(m.size for m in mb)
        score = matched / max(len(ptxt), 1)
        # 映射回时间: 取第一个大匹配块起点到最后一个块终点
        blocks = [m for m in mb if m.size >= 4]
        if not blocks:
            continue
        c0, c1 = cursor + blocks[0].a, cursor + blocks[-1].a + blocks[-1].size
        if c1 <= c0 or c1 > len(char_times):
            continue
        results.append({
            "speaker": para["speaker"],
            "start": char_times[c0],
            "end": char_times[min(c1, len(char_times) - 1)],
            "transcript": para["text"],
            "score": round(score, 3),
        })
        cursor = max(cursor, c1 - 20)  # 单调推进 (少量回退容错)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--segments", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-score", type=float, default=0.45)
    ap.add_argument("--min-sec", type=float, default=3.0)
    ap.add_argument("--max-sec", type=float, default=60.0)
    args = ap.parse_args()

    gt_paras = parse_gt_paragraphs(Path(args.gt))
    segments = json.loads(Path(args.segments).read_text(encoding="utf-8"))["segments"]
    print(f"人工段: {len(gt_paras)}, 7B 段: {len(segments)}")

    aligned = align(gt_paras, segments)
    kept = [a for a in aligned if a["score"] >= args.min_score
            and args.min_sec <= a["end"] - a["start"] <= args.max_sec]
    print(f"对齐成功: {len(aligned)}, 达标: {len(kept)}")

    with wave.open(args.audio, "rb") as wf:
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, dtype=np.int16)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for n, a in enumerate(kept):
        i0, i1 = int(a["start"] * sr), int(a["end"] * sr)
        piece = pcm[i0:i1]
        if len(piece) < sr:
            continue
        wav_path = out_dir / f"{n}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(piece.tobytes())
        (out_dir / f"{n}.json").write_text(json.dumps({
            "audio_duration": round(len(piece) / sr, 2),
            "transcript": [{"speaker": a["speaker"], "content": a["transcript"]}],
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        manifest.append({"file": f"{n}.wav", "speaker": a["speaker"],
                         "sec": round(len(piece) / sr, 1), "score": a["score"]})
    (out_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    total_sec = sum(m["sec"] for m in manifest)
    print(f"已导出 {len(manifest)} 对, 共 {total_sec:.0f}s 音频 → {out_dir}")
    print("下一步: 按 finetuning-asr/README.md 训练 (pip install peft; 数据目录指向本目录)")


if __name__ == "__main__":
    main()
