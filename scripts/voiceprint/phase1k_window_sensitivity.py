"""Phase 1h: 官方 recipe 的 **1.5s 窗 / 0.75s shift（50% 重叠）** 滑窗簇。

为什么做这一格
--------------
Phase 1b~1f 的结论都指向同一个瓶颈: **聚类要把人分开(主导簇)**。
Phase 1b 用的是**生产 ASR 段**(1.5–8s, **无重叠**) ⇒ 每个窗的上下文很短 ⇒
同一人的相邻发言被切碎 ⇒ 主导簇难形成。
3D-Speaker 官方 recipe 用的是 **1.5s 滑窗 / 0.75s shift (50% 重叠)** ⇒
每个窗都有上下文, 且相邻窗重叠 ⇒ 聚类更稳。

⭐ 评测口径**保持不变** (这是本脚本最重要的设计)
------------------------------------------------
滑窗会改变「聚类的输入单元」, 但**评测单元仍是 ASR 段**:
  - 簇 = 滑窗的聚类
  - 段 → 簇: 取**覆盖该段中点**的滑窗 ⇒ 段所属簇
  - 簇质心 = 该簇所有**滑窗**嵌入的均值
  - 段级归属 = 簇的命名
  - EER[簇质心]: 被验证段的表示 = 簇质心
⇒ ⇒ 所有数字**与 Phase 1b / 1d / 1e 横比**(同分母 7731 / 同 common_MP 39 / 同参照集)。

窗口取窗规则 (零额外依赖, 与生产一致)
--------------------------------------
官方 recipe 用 FSMN-VAD 出语音区; 本项目**已有生产 ASR 段** ⇒ 用它当语音区:
  1. 把该场所有 ASR 段的 [start,end] 按时间排序, **间隙 ≤ 0.3s 的相邻段合并**成语音区
  2. 在每个语音区内滑 1.5s 窗 / 0.75s shift, **窗必须完全落在语音区内**
  ⇒ 不产生静音窗, 且与生产同源

产出 (/tmp/vp/phase1h):
  emb_sw.npy    (N,192) float32, L2 归一化 (N ≈ 5.3 万)
  meta_sw.json  每窗: meeting / start / end

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1h_sliding_windows.py --phase1 /tmp/vp/phase1 --out /tmp/vp/phase1h
"""
import argparse
import collections
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 16000
WIN = 1.5          # 窗长 (秒) —— 3D-Speaker recipe (Phase 1k 可用 --win/--hop 覆盖)
HOP = 0.75         # shift (秒) —— 50% 重叠
MERGE_GAP = 0.3     # ASR 段合并成语音区的最大间隙
EMB_BATCH = 8000    # 每批窗数 (控内存: 8000×1.5s×16000×4 ≈ 768 MB)


def log(msg):
    print("[phase1h] " + msg, flush=True)


def decode_audio(path):
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def fetch_audio(key):
    local = os.path.join("/tmp/vp", "src_" + key.replace("/", "__"))
    if os.path.exists(local) and os.path.getsize(local) > 1024:
        return local
    from minio import Minio
    c = Minio("minio:9000", access_key=os.environ["MINIO_ACCESS_KEY"],
              secret_key=os.environ["MINIO_SECRET_KEY"], secure=False)
    resp = c.get_object("microbubble", key)
    try:
        data = resp.read()
    finally:
        resp.close()
        resp.release_conn()
    with open(local, "wb") as fh:
        fh.write(data)
    return local


def speech_regions(segs):
    """把 ASR 段合并成连续语音区 (间隙 ≤ MERGE_GAP)。"""
    iv = sorted((float(s.get("start") or 0), float(s.get("end") or 0))
                for s in segs
                if float(s.get("end") or 0) - float(s.get("start") or 0) >= 0.2)
    if not iv:
        return []
    out = [list(iv[0])]
    for s, e in iv[1:]:
        if s <= out[-1][1] + MERGE_GAP:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def windows_in(regions):
    """在语音区里滑 1.5s/0.75s 窗 (必须完全落在区内)。"""
    w, h = int(WIN * SR), int(HOP * SR)   # ⚠️ 必须是 int, 否则 numpy 切片报 TypeError
    out = []
    for s, e in regions:
        i0, i1 = int(s * SR), int(e * SR)
        pos = i0
        while pos + w <= i1:
            out.append((pos, pos + w))
            pos += h
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/phase1h")
    ap.add_argument("--meetings", default="")
    # Phase 1k: 窗口长度 / 重叠率敏感性 ⇒ 这两个是**聚类输入单元**的参数
    ap.add_argument("--win", type=float, default=WIN)
    ap.add_argument("--hop", type=float, default=HOP)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    globals()["WIN"] = float(args.win)
    globals()["HOP"] = float(args.hop)
    assert 0 < globals()["HOP"] <= globals()["WIN"], "hop 必须落在 (0, win]"
    log("窗口参数: win=%.2fs hop=%.2fs (重叠率 %.0f%%)" % (
        globals()["WIN"], globals()["HOP"],
        100 * (1 - globals()["HOP"] / globals()["WIN"])))

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.voiceprint_service import VoiceprintService

    engine, Session = create_celery_engine_and_session()
    mt = {}
    async with Session() as db:
        rows = (await db.execute(select(Meeting))).scalars().all()
        for m in rows:
            mt[m.id] = {"audio_url": m.audio_url,
                        "segs": sorted(m.transcript or [],
                                       key=lambda s: float(s.get("start") or 0))}
    await engine.dispose()

    meetings = ([int(x) for x in args.meetings.split(",") if x.strip()]
                if args.meetings else sorted(mt))
    # 先估总窗数 (只用语音区, 不解码)
    est = 0
    for mid in meetings:
        if mid not in mt or not mt[mid]["audio_url"]:
            continue
        est += len(windows_in(speech_regions(mt[mid]["segs"])))
    log("预估窗数 %d (9 场) ⇒ 嵌入约 %.0f 分钟 (0.05 s/段)" % (est, est * 0.05 / 60))

    svc = VoiceprintService()
    vec_path = os.path.join(args.out, "emb_sw.npy")
    meta_all = []
    chunks = []
    n_written = 0
    t0 = time.time()
    for mid in meetings:
        info = mt.get(mid)
        if not info or not info["audio_url"]:
            continue
        t1 = time.time()
        regions = speech_regions(info["segs"])
        pcm = decode_audio(fetch_audio(info["audio_url"]))
        # ⛔ 语音区可能超出**实际音频长度** (转录 end 比音频长) ⇒ 必须裁到音频内
        n_pcm = len(pcm)
        regions = [(max(0.0, s), min(n_pcm / SR, e)) for s, e in regions]
        regions = [(s, e) for s, e in regions if e - s >= WIN]
        wins = windows_in(regions)
        n_win = len(wins)
        log("会议 %d: 语音区 %d 段 ⇒ 窗 %d 个, 解码 %.0fs" % (
            mid, len(regions), n_win, time.time() - t1))
        for b in range(0, n_win, EMB_BATCH):
            part = wins[b:b + EMB_BATCH]
            clips = [pcm[s:e] for s, e in part]
            # 兜底: 任何越界的窗直接裁到音频内 (防御性)
            clips = [c for c in clips if len(c) >= int(0.5 * SR)]
            embs = svc.batch_extract_embeddings(clips)
            for (s, e), em in zip(part, embs):
                v = np.asarray(em, dtype=np.float32)
                n = float(np.linalg.norm(v))
                if n < 1e-6:
                    continue
                chunks.append(v / n)
                meta_all.append({"meeting": mid, "start": round(s / SR, 3),
                                 "end": round(e / SR, 3)})
            del clips
        np.save(vec_path, np.stack(chunks))
        n_written = len(chunks)
        log("  会议 %d 完成: 累计 %d 窗, 用时 %.0fs" % (mid, n_written, time.time() - t1))
        del pcm, wins

    np.save(vec_path, np.stack(chunks))
    with open(os.path.join(args.out, "meta_sw.json"), "w", encoding="utf-8") as fh:
        json.dump(meta_all, fh, ensure_ascii=False)
    with open(os.path.join(args.out, "identity_check.json"), "w", encoding="utf-8") as fh:
        json.dump({"n_windows": len(chunks), "est_windows": est,
                   "win_sec": WIN, "hop_sec": HOP, "merge_gap": MERGE_GAP,
                   "elapsed_sec": round(time.time() - t0, 1)}, fh, ensure_ascii=False, indent=1)
    log("完成 %d 窗, %.0fs ⇒ 已写出 %s" % (len(chunks), time.time() - t0, args.out))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
