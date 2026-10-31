"""Phase 1i: **CAM++** 嵌入 (替代已否掉的 ERes2NetV2_w24s4ep4 —— 后者 ModelScope 上 404)。

为什么换目标
------------
升级文档把 **ERes2NetV2_w24s4ep4**（CN-Celeb 2.31%, 中文数最好的候选）列为嵌入候选,
但实测 `iic/speech_eres2netv2_w24s4ep4*` **三个变体在 ModelScope 上全部 404** ⇒ 取不到。
⇒ 本轮改测另一个未被否掉的候选: **CAM++**
(`damo/speech_campplus_sv_zh-cn_16k-common`, emb_size 192, yesOrno_thr 0.31)。

CAM++ 的实现**不在 modelscope** ⇒ 在 `funasr/models/campplus/model.py` (`CAMPPlus`)。
funasr 1.4.16 容器里已装 ⇒ 零新增依赖。
⭐ 好消息: `CAMPPlus.forward` 吃 **(B, T, F) 的 fbank 特征** ⇒ **天然可批量**
(不像 ERes2Net 的 `__extract_feature` 强制 batch=1)。
⚠️ 但**必须用 funasr 自己的前端** (`extract_feature`) 算 fbank —— 它的参数与
`torchaudio.compliance.kaldi.fbank(num_mel_bins=80)` 不同 ⇒ 混用会静默掉精度。

产出:
  emb_camp.npy   (N,192) float32, L2 归一化
  meta_camp.json  每条: meeting / start / end / kind

用法 (容器内):
    python /tmp/vp/phase1i_campplus.py --phase1 /tmp/vp/phase1 --sw /tmp/vp/phase1h \
        --out /tmp/vp/phase1i
"""
import argparse
import json
import os
import subprocess
import sys
import time

import collections

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 16000
MODEL_ID = "damo/speech_campplus_sv_zh-cn_16k-common"
BATCH = 64


def log(m):
    print("[phase1i] " + m, flush=True)


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


def load_campplus():
    """加载 CAMPPlus (funasr 实现) ⇒ (model, extract_feature)。"""
    import torch
    from funasr.models.campplus.model import CAMPPlus
    from modelscope.hub.snapshot_download import snapshot_download
    import yaml

    d = snapshot_download(MODEL_ID)
    with open(os.path.join(d, "configuration.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    mc = cfg["model"]["model_config"]
    with open(os.path.join(d, "config.yaml"), encoding="utf-8") as fh:
        ycfg = yaml.safe_load(fh)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = CAMPPlus(**ycfg["model_conf"])   # config.yaml: model/model_conf 两级
    ckpt = os.path.join(d, cfg["model"]["pretrained_model"])
    sd = torch.load(ckpt, map_location="cpu")
    if isinstance(sd, dict) and "model" in sd:
        sd = sd["model"]
    model.load_state_dict(sd, strict=False)
    model.to(dev).eval()
    log("CAMPPlus 加载 OK: %.1fM 参数, emb_size=%s, device=%s" % (
        sum(p.numel() for p in model.parameters()) / 1e6, mc["emb_size"], dev))
    return model, dev


def embed_batch(model, audios, dev):
    """CAM++ 嵌入 (192 维, L2 归一化)。

    ⭐ **按帧数分桶批量 ⇒ 零 padding**:
    funasr 自带的 `extract_feature` 会 `pad_list` 到同长 ⇒ 补零帧会进 stats pooling
    (与 ERes2Net 同型陷阱, 类 20.220)。这里**自己算 fbank**(逐行照抄 funasr 的实现:
    `Kaldi.fbank(au.unsqueeze(0), num_mel_bins=80)` + 逐条减自己的均值),
    再**按帧数分桶** ⇒ 同一批帧数相同 ⇒ **零 padding**。
    ⇒ 滑窗全是 1.5s ⇒ 帧数完全相同 ⇒ 完美批量。
    """
    import torch
    import torchaudio.compliance.kaldi as Kaldi
    feats = []
    for a in audios:
        t = torch.from_numpy(np.asarray(a, dtype=np.float32))
        f = Kaldi.fbank(t.unsqueeze(0), num_mel_bins=80)
        f = f - f.mean(dim=0, keepdim=True)
        feats.append(f)
    groups = collections.defaultdict(list)
    for i, f in enumerate(feats):
        groups[f.shape[0]].append(i)
    out = np.zeros((len(feats), 192), dtype=np.float32)
    with torch.no_grad():
        for _L, idxs in groups.items():
            batch = torch.stack([feats[i] for i in idxs]).to(dev).float()
            o = model.forward(batch)
            o = o.squeeze(1).float().cpu().numpy()
            for k, i in enumerate(idxs):
                out[i] = o[k]
    n = np.linalg.norm(out, axis=1, keepdims=True)
    return out / np.maximum(n, 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--sw", default="/tmp/vp/phase1h")
    ap.add_argument("--out", default="/tmp/vp/phase1i")
    ap.add_argument("--what", default="both", choices=["seg", "sw", "both"])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    model, dev = load_campplus()
    t0 = time.time()
    vecs, metas = [], []

    if args.what in ("seg", "both"):
        META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
        E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
        from sqlalchemy import select
        from app.core.celery_db import create_celery_engine_and_session
        from app.models.meeting import Meeting
        import asyncio

        async def _segs():
            engine, Session = create_celery_engine_and_session()
            mt = {}
            async with Session() as db:
                rows = (await db.execute(select(Meeting))).scalars().all()
                for m in rows:
                    mt[m.id] = {"audio_url": m.audio_url,
                                "segs": sorted(m.transcript or [],
                                               key=lambda s: float(s.get("start") or 0))}
            await engine.dispose()
            return mt

        mt = asyncio.run(_segs())
        idx = [i for i, m in enumerate(META) if m["kind"] == "seg"]
        by_meeting = {}
        for i in idx:
            by_meeting.setdefault(META[i]["meeting"], []).append(i)
        for mid in sorted(by_meeting):
            rows = by_meeting[mid]
            pcm = decode_audio(fetch_audio(mt[mid]["audio_url"]))
            for b in range(0, len(rows), BATCH):
                part = rows[b:b + BATCH]
                # ⚠️ 过滤掉太短的段时必须**同时丢掉对应元数据**, 否则向量与元数据错位
                keep = []
                clips = []
                for i in part:
                    c = pcm[int(META[i]["start"] * SR):int(META[i]["end"] * SR)]
                    if len(c) >= SR // 2:
                        clips.append(c)
                        keep.append(i)
                if not clips:
                    continue
                v = embed_batch(model, clips, dev)
                for k, c in enumerate(clips):
                    vecs.append(v[k])
                    metas.append({"meeting": mid, "start": META[keep[k]]["start"],
                                  "end": META[keep[k]]["end"], "kind": "seg"})
            log("  CAM++ 段: 会议 %d 完成 (累计 %d 条, %.0fs)" % (
                mid, len(vecs), time.time() - t0))
            del pcm
        np.save(os.path.join(args.out, "emb_camp_seg.npy"), np.stack(vecs))
        with open(os.path.join(args.out, "meta_camp_seg.json"), "w", encoding="utf-8") as fh:
            json.dump(metas, fh, ensure_ascii=False)

    if args.what in ("sw", "both"):
        SWM = json.load(open(os.path.join(args.sw, "meta_sw.json"), encoding="utf-8"))
        from sqlalchemy import select
        from app.core.celery_db import create_celery_engine_and_session
        from app.models.meeting import Meeting
        import asyncio

        async def _urls():
            engine, Session = create_celery_engine_and_session()
            out = {}
            async with Session() as db:
                rows = (await db.execute(select(Meeting))).scalars().all()
                for m in rows:
                    out[m.id] = m.audio_url
            await engine.dispose()
            return out

        urls = asyncio.run(_urls())
        by_meeting = {}
        for i, m in enumerate(SWM):
            by_meeting.setdefault(m["meeting"], []).append(i)
        v2, m2 = [], []
        for mid in sorted(by_meeting):
            rows = by_meeting[mid]
            pcm = decode_audio(fetch_audio(urls[mid]))
            for b in range(0, len(rows), BATCH):
                part = rows[b:b + BATCH]
                keep = []
                clips = []
                for i in part:
                    c = pcm[int(SWM[i]["start"] * SR):int(SWM[i]["end"] * SR)]
                    if len(c) >= SR // 2:
                        clips.append(c)
                        keep.append(i)
                if not clips:
                    continue
                v = embed_batch(model, clips, dev)
                for k, c in enumerate(clips):
                    v2.append(v[k])
                    m2.append({"meeting": mid, "start": SWM[keep[k]]["start"],
                               "end": SWM[keep[k]]["end"], "kind": "sw"})
            log("  CAM++ 滑窗: 会议 %d 完成 (累计 %d 条, %.0fs)" % (
                mid, len(v2), time.time() - t0))
            del pcm
        np.save(os.path.join(args.out, "emb_camp_sw.npy"), np.stack(v2))
        with open(os.path.join(args.out, "meta_camp_sw.json"), "w", encoding="utf-8") as fh:
            json.dump(m2, fh, ensure_ascii=False)

    log("完成 %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
