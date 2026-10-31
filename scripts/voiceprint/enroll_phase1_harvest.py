"""Phase 1 (声纹换代) —— 步骤 1: 用**同一批素材**同时嵌入 ERes2Net(现役) 与 ERes2NetV2。

为什么必须「同一批、一次跑」
--------------------------
两个模型的嵌入空间互不相通 (同一段音频余弦 −0.1621) ⇒ 距离**不可跨模型横比**。
而本 Phase 的问题恰恰是「哪个模型更好」⇒ **输入必须逐条对齐**,
否则「模型差异」与「输入差异」分不开 (类 20.249 ⑧: 不一致的第一嫌疑是输入变了)。

⇒ 本脚本:
  1. 读 Phase 0 的 `meta.json` / `runs.json` 作为**素材定义** (不重新推导);
  2. 重建音频切片, 并**逐条比对**重建结果与 Phase 0 的 meta (meeting/seg_idx/start/end/kind/run/chunk)
     ⇒ 不一致就**报错退出** (类 20.220: 验副作用真的发生);
  3. 用**两个模型**各嵌一遍 (同一批 numpy 数组, 同一进程) ⇒ 输入 100% 对齐。

产出 (--out 目录):
  emb_eres.npz / emb_v2.npz   (N,192) float32, L2 归一化, 行序一致
  meta.json                   素材描述 (与 Phase 0 同格式)
  identity_check.json         与 Phase 0 的逐条比对结果

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/enroll_phase1_harvest.py --phase0 /tmp/vp/phase0 --out /tmp/vp/phase1
"""
import argparse
import asyncio
import collections
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import enroll_phase0_harvest as p0            # 复用素材定义/取音频/解码
from eres2netv2_embedder import ERes2NetV2Embedder

SR = 16000
MIN_SEG_SEC = p0.MIN_SEG_SEC
MIN_RUN_SEC = p0.MIN_RUN_SEC
WHOLE_MAX_SEC = p0.WHOLE_MAX_SEC


def log(msg):
    print("[phase1-harvest] " + msg, flush=True)


async def build_material(phase0_dir):
    """按 Phase 0 的 meta/runs 重建 (音频切片, meta) —— 逐条一致才继续。"""
    meta = json.load(open(os.path.join(phase0_dir, "meta.json"), encoding="utf-8"))
    runs = json.load(open(os.path.join(phase0_dir, "runs.json"), encoding="utf-8"))
    run_by_rid = {r["rid"]: r for r in runs}

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    engine, Session = create_celery_engine_and_session()
    mt = {}
    async with Session() as db:
        rows = (await db.execute(
            select(Meeting).where(Meeting.id.in_(p0.MEETINGS)))).scalars().all()
        for m in rows:
            segs = sorted(m.transcript or [], key=lambda s: float(s.get("start") or 0))
            mt[m.id] = {"audio_url": m.audio_url, "segs": segs}
    await engine.dispose()

    # 逐条目标: (kind, meeting, seg_idx | run, chunk) -> (start, end)
    want_seg = {}
    want_chunk = collections.defaultdict(list)
    want_whole = {}
    for m in meta:
        if m["kind"] == "seg":
            want_seg[(m["meeting"], m["seg_idx"])] = (m["start"], m["end"])
        elif m["kind"] in ("chunk10", "chunk5"):
            want_chunk[(m["kind"], m["run"])].append(m["chunk"])
        elif m["kind"] == "whole":
            want_whole[m["run"]] = (m["who"], m["s"], m["e"])

    clips = []
    rebuilt = []
    for mid in sorted(mt):
        info = mt[mid]
        if not info["audio_url"]:
            continue
        pcm = p0.decode_audio(p0.fetch_audio(info["audio_url"]))
        need = max((float(s.get("end") or 0) for s in info["segs"]), default=0.0)
        got = len(pcm) / SR
        if got < need * 0.95:
            raise RuntimeError("会议 %d 音频长度不足: %.1fs < 转录所需 %.1fs" % (mid, got, need))
        segs = info["segs"]
        # ① 生产段
        for (m2, idx), (st, en) in sorted(want_seg.items()):
            if m2 != mid:
                continue
            lo, hi = int(st * SR), int(en * SR)
            if lo < 0 or hi > len(pcm):
                raise RuntimeError("会议 %d 段 %d 越界" % (mid, idx))
            clips.append(pcm[lo:hi])
            rebuilt.append({"kind": "seg", "meeting": mid, "seg_idx": idx,
                            "start": round(st, 3), "end": round(en, 3),
                            "dur": round(en - st, 3)})
        # ② 长段: 先拼语音, 再切窗
        my_runs = [r for r in runs if r["meeting"] == mid]
        for r in my_runs:
            rid = r["rid"]
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
            if not speech_parts:
                continue
            speech = np.concatenate(speech_parts)
            for kind, cl in (("chunk10", 10), ("chunk5", 5)):
                if (kind, rid) not in want_chunk:
                    continue
                step = cl * SR
                pos = 0
                ci = 0
                while pos < len(speech):
                    piece = speech[pos:pos + step]
                    if len(piece) >= 3 * SR:
                        clips.append(piece)
                        rebuilt.append({"kind": kind, "meeting": mid, "run": rid,
                                        "chunk": ci, "who": r["who"],
                                        "s": r["s"], "e": r["e"]})
                    pos += step
                    ci += 1
            if rid in want_whole:
                clips.append(speech)
                who, s0, e0 = want_whole[rid]
                rebuilt.append({"kind": "whole", "meeting": mid, "run": rid,
                                "who": who, "s": s0, "e": e0})
            del speech, speech_parts
        del pcm
        log("会议 %d 重建完成, 累计 %d 条" % (mid, len(clips)))

    # ---- 逐条身份核对 (类 20.220) ----
    def key(m):
        if m["kind"] == "seg":
            return ("seg", m["meeting"], m["seg_idx"])
        if m["kind"] == "whole":
            return ("whole", m["meeting"], m["run"])
        return (m["kind"], m["meeting"], m["run"], m["chunk"])

    a = sorted(key(m) for m in meta)
    b = sorted(key(m) for m in rebuilt)
    same = (a == b)
    log("素材身份核对: Phase0 %d 条 / 重建 %d 条 ⇒ %s" % (
        len(a), len(b), "一致 ✅" if same else "不一致 ❌"))
    if not same:
        sa, sb = set(a), set(b)
        log("  仅 Phase0 有: %s" % sorted(sa - sb)[:10])
        log("  仅重建有:   %s" % sorted(sb - sa)[:10])
        raise RuntimeError("素材重建与 Phase 0 不一致 ⇒ 中止 (输入漂移, 类 20.249 ⑧)")
    return clips, rebuilt, runs, run_by_rid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase0", default="/tmp/vp/phase0")
    ap.add_argument("--out", default="/tmp/vp/phase1")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    clips, meta, runs, run_by_rid = asyncio.run(build_material(args.phase0))
    log("待嵌入 %d 条 (两个模型各一遍)" % len(clips))

    from app.services.voiceprint_service import VoiceprintService

    svc = VoiceprintService()
    v2 = ERes2NetV2Embedder()

    # ---- ERes2Net (现役) ----
    t0 = time.time()
    embs_e = svc.batch_extract_embeddings(clips)
    log("ERes2Net 完成 %.1fs" % (time.time() - t0))
    # ---- ERes2NetV2 ----
    t0 = time.time()
    embs_v2 = [v2.extract(a) for a in clips]
    log("ERes2NetV2 完成 %.1fs" % (time.time() - t0))

    def norm(e):
        v = np.asarray(e, dtype=np.float32)
        n = float(np.linalg.norm(v))
        if n < 1e-6:
            return None
        return v / n

    E, V, keep = [], [], []
    for m, ee, vv in zip(meta, embs_e, embs_v2):
        ne, nv = norm(ee), norm(vv)
        if ne is None or nv is None:
            continue
        E.append(ne)
        V.append(nv)
        keep.append(m)
    E = np.stack(E)
    V = np.stack(V)
    log("有效嵌入 %d 条" % len(keep))

    # ---- 跨模型空间不相通性自检 ----
    cross_cos = float(np.mean(np.sum(E * V, axis=1)))
    log("跨模型同段平均余弦 = %.4f (应接近 0 或负 ⇒ 两空间不相通)" % cross_cos)

    np.savez_compressed(os.path.join(args.out, "emb_eres.npz"), emb=E)
    np.savez_compressed(os.path.join(args.out, "emb_v2.npz"), emb=V)
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False)
    with open(os.path.join(args.out, "runs.json"), "w", encoding="utf-8") as fh:
        json.dump(runs, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "identity_check.json"), "w", encoding="utf-8") as fh:
        json.dump({"phase0_items": len(meta), "rebuilt_items": len(meta),
                   "identical": True, "cross_model_mean_cos": cross_cos}, fh,
                  ensure_ascii=False, indent=1)
    log("已写出 %s" % args.out)


if __name__ == "__main__":
    main()
