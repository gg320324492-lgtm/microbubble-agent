"""把声纹分析结果整理成给人核对用的报告: 时间聚类 + 区块音频导出。

为什么聚类: 另一个人说话必然是**连续的一段**, 单段打分容易被切碎;
按时间合并成区块后, 一眼能看出"这一整块是谁在说话"。
"""
import json
import os
import subprocess
import wave

BASE = r"E:\microbubble-agent\data\meeting-intake-2026-10-25"
JSON_PATH = os.path.join(BASE, "analysis-259.json")
OUT_DIR = os.path.join(BASE, "suspect-blocks")
os.makedirs(OUT_DIR, exist_ok=True)

d = json.load(open(JSON_PATH, encoding="utf-8"))
sus = d["suspects"]

# ---- 时间聚类: 相邻可疑段间隔 < GAP 秒则合并 ----
GAP = 12.0
blocks = []
for s in sorted(sus, key=lambda x: x["start"]):
    if blocks and s["start"] - blocks[-1]["end"] <= GAP:
        blocks[-1]["segs"].append(s)
        blocks[-1]["end"] = s["end"]
    else:
        blocks.append({"segs": [s], "start": s["start"], "end": s["end"]})

for b in blocks:
    segs = b["segs"]
    b["n"] = len(segs)
    b["label"] = max({s["speaker"] for s in segs}, key=lambda sp: sum(1 for s in segs if s["speaker"] == sp))
    b["z_max"] = max(s["z"] for s in segs)
    b["min_dist_max"] = max(s["min_dist"] for s in segs)
    b["text"] = "".join(s["text"] for s in segs)
    b["start"] = segs[0]["start"]
    b["end"] = segs[-1]["end"]

blocks.sort(key=lambda b: (-b["n"], -b["z_max"]))

# ---- 导出区块音频 (从原始会议音频切) ----
SRC_WAV = None
for cand in [r"E:\microbubble-agent\data\meeting-intake-2026-10-25\suspect-segments"]:
    pass

# 用已导出的单段音频拼接不精确, 改为直接用 ffmpeg 从会议音频切 —— 会议音频在容器 MinIO, 这里用宿主副本
MEETING_AUDIO = os.path.join(BASE, "orig", "week-10.19_1.m4a")
for i, b in enumerate(blocks, 1):
    out = os.path.join(OUT_DIR, f"block{i:02d}_{int(b['start']):04d}-{int(b['end']):04d}s_{b['label']}.wav")
    if os.path.exists(MEETING_AUDIO):
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", str(b["start"]), "-to", str(b["end"]),
             "-i", MEETING_AUDIO, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", out],
            capture_output=True,
        )
        if p.returncode == 0:
            b["audio_file"] = out
        else:
            b["audio_error"] = p.stderr[:120].decode("utf-8", "replace")

# ---- 生成报告 ----
lines = []
lines.append("# 会议 259（10-19 组会）声纹可疑片段清单\n")
lines.append(f"- 匹配阈值 MATCH_THRESHOLD = {d['match_threshold']}")
lines.append(f"- anchor 池（{len(d['anchor_pool'])} 人）：{'、'.join(d['anchor_pool'])}")
lines.append(f"- 参与计算段数：{d['segments_analyzed']}（剔除 <0.5s 的短段）")
lines.append("")
lines.append("## 各标签的距离分布（同标签在本会议内的相对基线）\n")
lines.append("| 标签 | 段数 | 距离中位数 | MAD | 说明 |")
lines.append("|---|---|---|---|---|")
for k, v in d["label_stats"].items():
    note = ""
    if v["median"] > 0.45:
        note = "**离阈值很近，整体勉强及格**"
    lines.append(f"| {k} | {v['n']} | {v['median']} | {v['mad']} | {note} |")
lines.append("")
lines.append("## 可疑区块（按可疑度排序）\n")
lines.append("判据：z = 该段到「当前标签」的距离相对同标签分布的离群度；"
             "d = 到 anchor 池最近者的距离（阈值 0.65，越接近越勉强）。")
lines.append("")
for i, b in enumerate(blocks, 1):
    lines.append(f"### 区块 {i} — {b['start']:.1f}s ~ {b['end']:.1f}s（{b['end']-b['start']:.1f}s，{b['n']} 段）")
    lines.append(f"- 当前标签：**{b['label']}** ｜ z_max={b['z_max']} ｜ 最大最近距离={b['min_dist_max']}")
    for s in b["segs"]:
        lines.append(f"  - `{s['start']:.1f}-{s['end']:.1f}s` 最近={s['min_to']}({s['min_dist']}) "
                     f"次近={s['second']} z={s['z']} → 「{s['text']}」")
    if b.get("audio_file"):
        lines.append(f"- 音频：`{os.path.basename(b['audio_file'])}`")
    lines.append("")

open(os.path.join(BASE, "SUSPECT-BLOCKS.md"), "w", encoding="utf-8").write("\n".join(lines))
print("区块数:", len(blocks))
print("报告:", os.path.join(BASE, "SUSPECT-BLOCKS.md"))
print("音频目录:", OUT_DIR)
