"""Phase 1 探针: **ERes2Net(现役) vs ERes2NetV2** 并排测量。

回答三个问题
------------
① **吞吐**: 本项目规模 (1.1 万段) 下逐条路径够不够快? (决定要不要做真批量)
② **整段嵌入的算力**: 10/30/60/120/300/600s 各要多久 (决定长 enrollment 可不可行)
③ **⭐ 长度敏感性**: 同一段 10s 真实语音后面接 0/5/20/60s 静音 ⇒ 嵌入还剩多少相似度。
   ⇒ 这是 Phase 0 结论「整段质心属于另一个表征空间」的**决定性后续**:
   若 V2 的长度敏感性明显更低 ⇒ 整段质心可直接用于逐段匹配;
   若一样敏感 ⇒ 整段质心只在「簇质心↔簇质心」范式成立。

外加 (④) **padding 污染量化**: 朴素批量 (fbank pad 到同长, 无 mask) vs 逐条 ⇒ 最大逐元素差。
   用来证明「为什么本项目不做真批量」。

⛔ 不写任何生产数据; 不改 members; 只读。

用法 (容器内):
    python /tmp/vp/probe_model_length_sensitivity.py
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 16000
WORK = "/tmp/vp"


def log(msg):
    print("[probe] " + msg, flush=True)


def decode_audio(path):
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def fetch_audio(key):
    """⛔ 缓存名用**完整对象键** (类 20.242)。"""
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
    return local


async def load_real_speech(meeting_id=255, n_short=20, n_base=10):
    """从 DB 取该场转录 → 从 MinIO 取音频 → 切出**真实**语音段。"""
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        m = (await db.execute(
            select(Meeting).where(Meeting.id == meeting_id))).scalar_one()
        segs = sorted(m.transcript or [], key=lambda s: float(s.get("start") or 0))
        url = m.audio_url
    await engine.dispose()
    pcm = decode_audio(fetch_audio(url))
    shorts, base = [], []
    for s in segs:
        st, en = float(s.get("start") or 0), float(s.get("end") or 0)
        if en - st < 2.0 or en > len(pcm) / SR:
            continue
        piece = pcm[int(st * SR):int(en * SR)]
        if len(shorts) < n_short:
            shorts.append(piece)
        if sum(len(x) for x in base) < n_base * SR:
            base.append(piece)
    log("会议 %d: 取到 %d 条真实短段, 基准 10s 语音由 %d 段拼成" % (
        meeting_id, len(shorts), len(base)))
    return shorts, np.concatenate(base), pcm


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return float("nan")
    return float(np.dot(a, b) / (na * nb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, default=255)
    ap.add_argument("--out", default=os.path.join(WORK, "phase1_probe.json"))
    args = ap.parse_args()

    from app.services.voiceprint_service import VoiceprintService
    from eres2netv2_embedder import ERes2NetV2Embedder

    res = {}

    async def _prep():
        return await load_real_speech(args.meeting)

    shorts, base10, pcm = asyncio.run(_prep())

    svc = VoiceprintService()
    svc._load_pipeline()
    v2 = ERes2NetV2Embedder()
    log("ERes2NetV2 已加载: 目录=%s 参数=%.1fM 设备=%s" % (
        v2.model_dir, v2.n_params / 1e6, v2.device))

    models = [
        ("ERes2Net(现役)", lambda a: svc.extract_embedding(a)),
        ("ERes2NetV2", lambda a: v2.extract(a)),
    ]

    # ---------- ① 吞吐 ----------
    log("=== ① 吞吐 (真实 2-4s 语音段) ===")
    res["throughput"] = {}
    for name, fn in models:
        fn(shorts[0])                                     # 预热
        t0 = time.time()
        embs = [fn(a) for a in shorts]
        dt = time.time() - t0
        res["throughput"][name] = {"n": len(shorts), "total_sec": round(dt, 3),
                                   "per_seg_sec": round(dt / len(shorts), 4),
                                   "mean_dur": round(float(np.mean([len(a) / SR for a in shorts])), 2)}
        log("  %-16s %d 条 %.2fs ⇒ %.4f s/段" % (
            name, len(shorts), dt, dt / len(shorts)))

    # ---------- ② 整段嵌入耗时 (真实音频) ----------
    log("=== ② 整段嵌入耗时 (真实连续音频) ===")
    res["whole_timing"] = {}
    for name, fn in models:
        res["whole_timing"][name] = {}
        for secs in (10, 30, 60, 120, 300, 600):
            need = int(secs * SR)
            if len(pcm) < need:
                audio = np.concatenate([pcm, np.zeros(need - len(pcm), dtype=np.float32)])
            else:
                audio = pcm[:need]
            t0 = time.time()
            e = fn(audio)
            dt = time.time() - t0
            res["whole_timing"][name][str(secs)] = round(dt, 3)
            log("  %-16s %4ds ⇒ %.2fs" % (name, secs, dt))

    # ---------- ③ ⭐ 长度敏感性 ----------
    log("=== ③ 长度敏感性 (10s 真实语音 + 尾部静音) ===")
    res["length_sensitivity"] = {}
    for name, fn in models:
        e0 = fn(base10)
        row = {"0": 1.0}
        for pad in (5, 20, 60):
            a = np.concatenate([base10, np.zeros(int(pad * SR), dtype=np.float32)])
            row[str(pad)] = round(cos(e0, fn(a)), 5)
        res["length_sensitivity"][name] = row
        log("  %-16s +0s=1.0000  +5s=%.4f  +20s=%.4f  +60s=%.4f" % (
            name, row["5"], row["20"], row["60"]))

    # ---------- ④ padding 污染量化 (V2 + 现役) ----------
    log("=== ④ 朴素批量(pad 无 mask) vs 逐条 ⇒ 嵌入被改掉多少 ===")
    res["padding_contamination"] = {}
    # ERes2Net 的等价朴素批量: 复刻 modelscope 的 __extract_feature 再 pad
    import torch
    import torchaudio.compliance.kaldi as Kaldi

    def eres_batch(audios):
        feats = []
        for a in audios:
            t = torch.from_numpy(np.asarray(a, dtype=np.float32))
            if t.dim() == 1:
                t = t.unsqueeze(0)
            f = Kaldi.fbank(t, num_mel_bins=80)
            f = f - f.mean(dim=0, keepdim=True)
            feats.append(f)
        T = max(f.shape[0] for f in feats)
        batch = torch.zeros(len(feats), T, 80)
        for i, f in enumerate(feats):
            batch[i, :f.shape[0], :] = f
        # ⚠️ 必须用**底层 nn.Module** (embedding_model): 外层
        # SpeakerVerificationERes2Net.forward 断言输入是 2D (N,T) 且会 unsqueeze(0)
        # ⇒ 直接喂 3D 会抛 "the shape of input audio to model needs to be [N, T]"
        net = svc._pipeline.model.embedding_model
        dev = next(net.parameters()).device
        with torch.no_grad():
            out = net(batch.to(dev))
        out = out.squeeze(1).float().cpu().numpy()
        return out

    group = shorts[:8]
    per_item_v2 = np.stack([v2.extract(a) for a in group])
    batch_v2, lens = v2.extract_padded_batch(group)
    diff_v2 = float(np.max(np.abs(per_item_v2 - np.stack(batch_v2))))
    res["padding_contamination"]["ERes2NetV2"] = {
        "n": len(group), "frame_lens": lens, "max_abs_diff": diff_v2,
        "mean_cos_to_peritem": round(float(np.mean([
            cos(per_item_v2[i], batch_v2[i]) for i in range(len(group))])), 5)}
    log("  ERes2NetV2  max_abs_diff = %.4f  (mean cos %.5f)" % (
        diff_v2, res["padding_contamination"]["ERes2NetV2"]["mean_cos_to_peritem"]))

    try:
        per_item_e = np.stack([svc.extract_embedding(a) for a in group])
        batch_e = eres_batch(group)
        diff_e = float(np.max(np.abs(per_item_e - batch_e)))
        res["padding_contamination"]["ERes2Net(现役)"] = {
            "n": len(group), "max_abs_diff": diff_e,
            "mean_cos_to_peritem": round(float(np.mean([
                cos(per_item_e[i], batch_e[i]) for i in range(len(group))])), 5)}
        log("  ERes2Net     max_abs_diff = %.4f  (mean cos %.5f)" % (
            diff_e, res["padding_contamination"]["ERes2Net(现役)"]["mean_cos_to_peritem"]))
    except Exception as ex:
        log("  ERes2Net 批量对照失败: %s" % repr(ex)[:160])

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % args.out)


if __name__ == "__main__":
    main()
