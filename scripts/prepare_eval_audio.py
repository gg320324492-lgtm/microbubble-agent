#!/usr/bin/env python3
"""
准备 ASR benchmark 评估音频:
1. 用 edge-tts 生成 10 个合成测试样本（精确 ground truth）
2. 用 ffmpeg 转换 11 个真实会议音频为 16kHz mono WAV
3. 写 data/asr_eval/ground_truth.jsonl

用法:
    python scripts/prepare_eval_audio.py
"""
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = ROOT / "data" / "asr_eval" / "synthetic"
NORMALIZED_DIR = ROOT / "data" / "asr_eval" / "normalized"
GT_FILE = ROOT / "data" / "asr_eval" / "ground_truth.jsonl"
SOURCE_AUDIO_DIR = ROOT / "data" / "meeting-audio-2026-06-27"

# 10 个合成样本 - 覆盖中文 ASR 难点
SYNTHETIC_SAMPLES = [
    # 1. 纯中文短句
    ("01_basics", "今天天气真好，我们一起去公园散步吧。"),
    # 2. 数字串
    ("02_numbers", "项目预算共计一百二十三万四千五百六十七元。"),
    # 3. 日期
    ("03_date", "二零二六年六月三十日下午三点准时开始会议。"),
    # 4. 中英混排
    ("04_mixed", "我们需要用 AI 模型解决 hallucination 问题。"),
    # 5. 专业术语
    ("05_terms", "微纳米气泡的 zeta 电位与表面张力密切相关。"),
    # 6. ITN 数字
    ("06_phone", "请拨打 13800138000 转 6 号分机联系王工程师。"),
    # 7. 重复词
    ("07_repeat", "啊对对对对对，我同意这个方案。"),
    # 8. 长句（标点测试）
    ("08_long", "虽然今天下雨了，但是我们仍然坚持完成了实验，并记录了所有数据，希望明天的天气会更好。"),
    # 9. 同音字（ASR 难点）
    ("09_homophone", "他的事迹已被列入公司的发展计划。"),
    # 10. 多人对话（标点+连读）
    ("10_dialogue", "您说，我们需要测试一下。然后呢？好的，那就这样办吧。"),
]

# 真实会议音频（来自 data/meeting-audio-2026-06-27/）
REAL_AUDIO_FILES = [
    # (源文件名, 目标名, ground_truth 来源标签, 时长类别)
    ("meeting-064-小气助手软件适配性测试.webm", "meeting-064.webm", "manual_short", "short"),
    ("meeting-068-臭氧气泡实验变量分析.webm", "meeting-068.webm", "manual_short", "short"),
    ("meeting-070-实验数据可靠性排查与实验条件分析.webm", "meeting-070.webm", "manual_short", "short"),
    ("meeting-071-臭氧微纳米气泡实验条件的影响.webm", "meeting-071.webm", "manual_short", "short"),
    ("meeting-083-持续研究UV臭氧纳米气泡技术.webm", "meeting-083.webm", "meeting83_polished", "medium"),
    ("meeting-095-水产养殖纳米气泡技术与双业务平台构建.webm", "meeting-095.webm", "db_soft", "medium"),
    ("meeting-120-实验相关工作安排.wav", "meeting-120.wav", "db_soft", "long"),
    ("meeting-121-普通泡与纳米气泡技术对比.webm", "meeting-121.webm", "db_soft", "medium"),
    ("meeting-135-研究方案讨论与实验指导.webm", "meeting-135.webm", "db_soft", "medium"),
    ("meeting-151-铜鹤实验相关讨论.m4a", "meeting-151.m4a", "db_soft", "medium"),
]


async def generate_synthetic():
    """生成 10 个合成样本 WAV 文件"""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    voice = "zh-CN-XiaoxiaoNeural"
    for name, text in SYNTHETIC_SAMPLES:
        out_path = SYNTHETIC_DIR / f"{name}.wav"
        if out_path.exists():
            print(f"  [skip] {out_path.name} already exists")
            continue
        mp3_path = SYNTHETIC_DIR / f"{name}.mp3"
        print(f"  [gen]  {name}: {text[:40]}...")
        communicate = edge_tts.Communicate(text=text, voice=voice)
        await communicate.save(str(mp3_path))
        # MP3 → WAV 16kHz mono
        cmd = [
            "ffmpeg", "-y", "-i", str(mp3_path),
            "-ar", "16000", "-ac", "1", "-f", "wav",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        mp3_path.unlink()
    print(f"[OK] Generated {len(SYNTHETIC_SAMPLES)} synthetic samples")


def get_audio_duration(path: Path) -> float:
    """用 ffprobe 获取音频时长（秒）"""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def normalize_real_audio():
    """将真实音频转为 16kHz mono WAV"""
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name, _, _ in REAL_AUDIO_FILES:
        src_path = SOURCE_AUDIO_DIR / src_name
        dst_path = NORMALIZED_DIR / dst_name
        if dst_path.exists():
            print(f"  [skip] {dst_path.name} already exists")
            continue
        if not src_path.exists():
            print(f"  [miss] {src_name} not found")
            continue
        print(f"  [conv] {src_name} → {dst_name}")
        cmd = [
            "ffmpeg", "-y", "-i", str(src_path),
            "-ar", "16000", "-ac", "1", "-f", "wav",
            str(dst_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    print(f"[OK] Normalized {len(REAL_AUDIO_FILES)} real audio files")


def load_meeting83_polished() -> str:
    """从 meeting83_final.md 加载人工校对的 transcript"""
    polished_path = ROOT / "meeting83_final.md"
    if not polished_path.exists():
        return ""
    text = polished_path.read_text(encoding="utf-8")
    # 提取每行的文字内容（跳过标题/分隔符）
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        if "【" in line and "】" in line:
            # 提取【发言人】后面的内容
            m = re.search(r"】(.+)$", line)
            if m:
                lines.append(m.group(1).strip())
        else:
            lines.append(line)
    return " ".join(lines)


def write_ground_truth():
    """写 ground_truth.jsonl"""
    GT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 1. 合成样本（精确 ground truth）
    gt_records = []
    for name, text in SYNTHETIC_SAMPLES:
        wav_path = SYNTHETIC_DIR / f"{name}.wav"
        if not wav_path.exists():
            continue
        duration = get_audio_duration(wav_path)
        gt_records.append({
            "audio_path": str(wav_path.relative_to(ROOT)),
            "absolute_path": str(wav_path),
            "duration_sec": duration,
            "language": "zh",
            "text": text,
            "source": "synthetic",
        })

    # 2. 真实音频 - meeting-083 有人工校对 transcript
    meeting83_text = load_meeting83_polished()
    for src_name, dst_name, source_tag, length_cat in REAL_AUDIO_FILES:
        wav_path = NORMALIZED_DIR / dst_name
        if not wav_path.exists():
            continue
        duration = get_audio_duration(wav_path)
        # meeting-083 用 polished，meeting-120 用 DB transcript 近似
        if "meeting-083" in dst_name:
            text = meeting83_text
        else:
            text = ""  # ground truth 待人工标注（DB transcript 仅供参考）
        gt_records.append({
            "audio_path": str(wav_path.relative_to(ROOT)),
            "absolute_path": str(wav_path),
            "duration_sec": duration,
            "language": "zh",
            "text": text,
            "source": source_tag,
            "length_category": length_cat,
        })

    with open(GT_FILE, "w", encoding="utf-8") as f:
        for rec in gt_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[OK] Wrote {len(gt_records)} ground truth records to {GT_FILE}")
    print(f"    Synthetic (precise): {sum(1 for r in gt_records if r['source'] == 'synthetic')}")
    print(f"    Real - polished: {sum(1 for r in gt_records if r['source'] == 'meeting83_polished')}")
    print(f"    Real - manual/db: {sum(1 for r in gt_records if r['source'] != 'synthetic' and not r['text'])}")


def main():
    print("[STEP 1/3] Generate synthetic TTS samples...")
    asyncio.run(generate_synthetic())
    print("[STEP 2/3] Normalize real audio to 16kHz mono WAV...")
    normalize_real_audio()
    print("[STEP 3/3] Write ground_truth.jsonl...")
    write_ground_truth()
    print("[DONE]")


if __name__ == "__main__":
    main()