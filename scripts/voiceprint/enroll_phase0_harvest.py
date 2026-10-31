"""Phase 0 (声纹换代) —— 步骤 1: 收割「长段」素材并一次性嵌入。

为什么需要它
------------
现役每个成员的质心 = 「若干个 1.5–8 秒会议片段的均值」⇒ 实测同一人自比对 0.723,
异人反而 0.685 (docs/voiceprint-upgrade-2026-10-31.md §3.4) ⇒ 质心本身是坏的。
Phase 0 的任务: 从**已有会议音频**里收割「长而连续、同一说话人」的长段, 建新质心,
量同一人跨场距离能否显著低于 0.5038。

素材来源
--------
人工确认台账 (docs/voiceprint-confirmed-blocks-2026-10-13.json / -2026-10-30.json)。
台账块是「逐窗切分后的区间」⇒ 先按 (who, meeting) 把相邻块**合并成连续段**,
再取每段 ≥ MIN_RUN_SEC 的连续发言。

产出 (--out 目录)
-----------------
  emb.npz    emb (N,192) float32, L2 归一化
  meta.json  每条嵌入的来源描述
  runs.json  连续段定义 (who/meeting/s/e/seg 列表/语音秒数)

嵌入的三种切法 (同一段素材, 用来比较「建库口径」的影响)
------------------------------------------------------
  seg      生产转录里的**短段** (1.5–8s) —— 这就是**旧质心**的建库口径
  chunk10  长段的 10s 窗均值 (3D-Speaker 官方 recipe)
  chunk5   长段的 5s 窗均值 (中间档, 用来量「窗长」这一混淆因素)
  whole    长段整段嵌入 (受模型长度敏感性影响, 单独标注)

⛔ 纪律
--------
- 类 20.242: MinIO 缓存文件名用**完整对象键**, 禁止 basename
- 类 20.220: 音频长度必须自检覆盖整场转录, 否则报错退出 (不产出结果)
- 类 20.216: 中文一律写文件 + UTF-8, 不走 heredoc
- **不写生产表**: 本脚本只读 DB, 只写 --out 目录

用法 (容器内):
    python /tmp/vp/enroll_phase0_harvest.py --out /tmp/vp/phase0
"""
import argparse
import asyncio
import collections
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, "/app")

SR = 16000
MIN_SEG_SEC = 0.5      # 与生产一致: 短于 0.5s 的段不参与识别
MIN_RUN_SEC = 15.0     # 连续段下限 (≥30s 的算「主素材」)
MERGE_GAP = 0.75       # 合并相邻台账块的最大空隙(秒)
WORK = "/tmp/vp"
MEETINGS = [229, 243, 247, 250, 254, 255, 256, 259, 262]
# 非人的台账标签 —— 不能当 enrollment 素材
NON_PERSON = {"视频", "人群杂音", "环境声", "发言人?", "未知", "其他"}
WHOLE_MAX_SEC = 300.0  # 整段嵌入的长度上限 (实测 600s 要 232s, 非线性爆炸)


def log(msg):
    print("[phase0] " + msg, flush=True)


def decode_audio(path):
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 解码失败: " + p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def fetch_audio(key):
    """从 MinIO 取会议音频到容器本地 (缓存复用)。

    ⛔ 缓存名必须用**完整对象键** (类 20.242): `recordings/255/merged.m4a` /
    `256/merged.m4a` / `259/merged.m4a` / `262/merged.m4a` 的 basename 全是
    `merged.m4a` ⇒ 用 basename 会让后几场**静默复用第一场的音频**。
    """
    local = os.path.join(WORK, "src_" + key.replace("/", "__"))
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
    log("下载 %s (%.1f MB)" % (key, len(data) / 1048576))
    return local


def load_ledger(paths):
    blocks = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for b in d["blocks"]:
            if b.get("_可用") is False:
                continue
            who = b["who"]
            if who in NON_PERSON:
                continue
            blocks.append({"who": who, "meeting": int(b["meeting"]),
                           "s": float(b["s"]), "e": float(b["e"])})
    return blocks


def merge_runs(blocks):
    """把台账块按 (who, meeting) 合并成连续发言段。

    台账块是「逐窗切分后的区间」⇒ 相邻块之间可能只隔一点点 ⇒ 合并。
    空隙 ≤ MERGE_GAP 才合并 (更大的空隙是别人的话, 不能吞掉)。
    """
    by = collections.defaultdict(list)
    for b in blocks:
        by[(b["who"], b["meeting"])].append((b["s"], b["e"]))
    runs = []
    for (who, mid), v in sorted(by.items()):
        v.sort()
        mg = [list(v[0])]
        for s, e in v[1:]:
            if s <= mg[-1][1] + MERGE_GAP:
                mg[-1][1] = max(mg[-1][1], e)
            else:
                mg.append([s, e])
        for s, e in mg:
            if e - s >= MIN_RUN_SEC:
                runs.append({"who": who, "meeting": mid, "s": s, "e": e})
    runs.sort(key=lambda r: (r["who"], r["meeting"], r["s"]))
    for i, r in enumerate(runs):
        r["rid"] = i          # 全局 run id (meta 里用它回指 runs.json)
    return runs


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(WORK, "phase0"))
    ap.add_argument("--ledgers", default=",".join([
        "/tmp/vp/ledger_13.json", "/tmp/vp/ledger_30.json"]))
    ap.add_argument("--chunk-lens", default="10,5")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    blocks = load_ledger(args.ledgers.split(","))
    runs = merge_runs(blocks)
    log("台账人物块 %d 条 → 连续段(≥%.0fs) %d 条" % (len(blocks), MIN_RUN_SEC, len(runs)))
    who_m = collections.defaultdict(set)
    for r in runs:
        who_m[r["who"]].add(r["meeting"])
    log("覆盖人物 %d 位, 其中跨场(≥2 场) %d 位: %s" % (
        len(who_m), sum(1 for v in who_m.values() if len(v) >= 2),
        sorted(w for w, v in who_m.items() if len(v) >= 2)))

    # ---- 取会议音频与转录 ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    engine, Session = create_celery_engine_and_session()
    mt = {}
    async with Session() as db:
        rows = (await db.execute(
            select(Meeting).where(Meeting.id.in_(MEETINGS)))).scalars().all()
        for m in rows:
            segs = sorted(m.transcript or [], key=lambda s: float(s.get("start") or 0))
            mt[m.id] = {"audio_url": m.audio_url, "segs": segs}
    await engine.dispose()
    for mid in MEETINGS:
        if mid not in mt or not mt[mid]["audio_url"]:
            log("跳过会议 %d (无音频或无转录)" % mid)
    mt = {k: v for k, v in mt.items() if v["audio_url"]}

    # ---- 逐会议: 解码 → 切段 → 切长段 → 当场嵌入 (逐会议释放音频, 避免 8GB cgroup 爆) ----
    chunk_lens = [int(x) for x in args.chunk_lens.split(",") if x.strip()]

    from app.services.voiceprint_service import VoiceprintService
    svc = VoiceprintService()

    all_meta = []
    all_vecs = []

    for mid in sorted(mt):
        t0 = time.time()
        info = mt[mid]
        segs = info["segs"]
        pcm = decode_audio(fetch_audio(info["audio_url"]))
        # ⛔ 自检 (类 20.220): 音频长度必须覆盖整场转录, 否则是取错了对象
        need = max((float(s.get("end") or 0) for s in segs), default=0.0)
        got = len(pcm) / SR
        if got < need * 0.95:
            raise RuntimeError("会议 %d 音频长度不足: %.1fs < 转录所需 %.1fs (%s) —— "
                               "取错对象或缓存键碰撞" % (mid, got, need, info["audio_url"]))
        log("会议 %d: %d 段, 音频 %.1fs (转录覆盖到 %.1fs)" % (mid, len(segs), got, need))

        clips, meta = [], []
        my_runs = [r for r in runs if r["meeting"] == mid]
        run_of_seg = collections.defaultdict(list)
        for ri, r in enumerate(my_runs):
            for i, s in enumerate(segs):
                st = float(s.get("start") or 0)
                en = float(s.get("end") or 0)
                if en - st < MIN_SEG_SEC:
                    continue
                mid_t = (st + en) / 2.0
                if r["s"] <= mid_t <= r["e"]:
                    run_of_seg[(mid, i)].append(r["rid"])

        for i, s in enumerate(segs):
            st = float(s.get("start") or 0)
            en = float(s.get("end") or 0)
            if en - st < MIN_SEG_SEC:
                continue
            lo, hi = int(st * SR), int(en * SR)
            if lo < 0 or hi > len(pcm):
                continue
            clips.append(pcm[lo:hi])
            meta.append({"kind": "seg", "meeting": mid, "seg_idx": i,
                         "start": round(st, 3), "end": round(en, 3),
                         "dur": round(en - st, 3),
                         "text": (s.get("text") or "")[:120],
                         "db_speaker": s.get("speaker") or "",
                         "runs": sorted(set(run_of_seg.get((mid, i), [])))})

        # ---- 长段素材: 语音拼接(去掉段间静音) → 切窗 / 整段 ----
        for ri, r in enumerate(my_runs):
            speech_parts, speech_sec = [], 0.0
            for i, s in enumerate(segs):
                st = float(s.get("start") or 0)
                en = float(s.get("end") or 0)
                if en - st < MIN_SEG_SEC:
                    continue
                mid_t = (st + en) / 2.0
                if not (r["s"] <= mid_t <= r["e"]):
                    continue
                lo, hi = int(st * SR), int(en * SR)
                if lo < 0 or hi > len(pcm):
                    continue
                speech_parts.append(pcm[lo:hi])
                speech_sec += (hi - lo) / SR
            r["speech_sec"] = round(speech_sec, 2)
            r["n_segs"] = len(speech_parts)
            if not speech_parts:
                continue
            speech = np.concatenate(speech_parts)
            for cl in chunk_lens:
                step = cl * SR
                pos = 0
                ci = 0
                while pos < len(speech):
                    piece = speech[pos:pos + step]
                    if len(piece) >= 3 * SR:      # < 3s 的尾块丢弃 (生产也这么干)
                        clips.append(piece)
                        meta.append({"kind": "chunk%d" % cl, "meeting": mid,
                                     "run": r["rid"], "chunk": ci,
                                     "who": r["who"], "s": r["s"], "e": r["e"]})
                    pos += step
                    ci += 1
            if speech_sec <= WHOLE_MAX_SEC:
                clips.append(speech)
                meta.append({"kind": "whole", "meeting": mid, "run": r["rid"],
                             "who": r["who"], "s": r["s"], "e": r["e"]})
            else:
                r["whole_skipped"] = True
            del speech, speech_parts

        # ---- 当场嵌入这一场, 立刻释放音频 ----
        t1 = time.time()
        embs = svc.batch_extract_embeddings(clips)
        n_ok = 0
        for m, e in zip(meta, embs):
            if e is None or np.all(e == 0):
                continue
            v = np.asarray(e, dtype=np.float32)
            n = float(np.linalg.norm(v))
            if n < 1e-6:
                continue
            all_vecs.append(v / n)
            all_meta.append(m)
            n_ok += 1
        del clips, meta, embs, pcm
        log("会议 %d 完成: 嵌入 %d/%d 条, 用时 %.1fs (累计 %d)" % (
            mid, n_ok, len(all_meta), time.time() - t0, len(all_meta)))

    with open(os.path.join(args.out, "runs.json"), "w", encoding="utf-8") as fh:
        json.dump(runs, fh, ensure_ascii=False, indent=1)

    E = np.stack(all_vecs) if all_vecs else np.zeros((0, 192), dtype=np.float32)
    log("嵌入有效 %d 条" % len(all_vecs))
    np.savez_compressed(os.path.join(args.out, "emb.npz"), emb=E)
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(all_meta, fh, ensure_ascii=False)
    log("已写出 %s" % args.out)


if __name__ == "__main__":
    asyncio.run(main())
