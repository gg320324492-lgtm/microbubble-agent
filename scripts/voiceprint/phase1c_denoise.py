"""Phase 1c: 降噪前端（FRCRN）对声纹判别力的影响 —— **A/B 对照**。

为什么做这个
------------
Phase 1 的误差预算: **跨场 EER 20.7% vs 同场 EER 11.6%** ⇒ 近一半错误来自
「**声学环境变化**」。换说话人嵌入模型(Phase 1, 已否) 与 加长 enrollment(Phase 0, 已否)
都打不到这一半 ⇒ 剩下对症的一招是**直接把环境变干净**(降噪前端)。
⇒ 社区建议的 ClearerVoice / FRCRN / MossFormer2 都有 Apache-2.0 权重。

本轮选 **FRCRN**(`iic/speech_frcrn_ans_cirm_16k`, modelscope 自带 pipeline ⇒ 接线成本最低)。

⭐ A/B 口径
-----------
- **只有音频变**（降噪前/后）, **段边界完全不变** ⇒ 台账真值映射不变 ⇒ 评测完全同口径
- 评测复用 `phase1b_diarize.py` 的同一套逻辑 (`--emb` 覆盖嵌入) ⇒
  common_MP / 候选池 / 台账 / EER 定义 **一个字都不改**
- ⭐ **回归核对**: 不降噪时必须复现 Phase 1 的 EER = 0.2067 (由 phase1b 的守卫保证)

⚠️ **两个必须说明的限制**
------------------------
1. **幅度还原**: modelscope 的 `audio_norm` 是**两级 RMS 归一化**
   (`10^(-25/20)/rms` 然后再按"高于平均功率"的 RMS 归一一次)
   ⇒ 降噪输出在归一化域 ⇒ 必须**乘回因子**才能回到原始尺度, 否则整场音量关系被抹掉。
   本脚本自己算这个因子 (与 modelscope 的实现逐行一致) ⇒ 精确还原。
2. **成员侧只有本场被降噪** (enrollment 来自**别的场**, 那些场没降噪)
   ⇒ 若降噪真的有用, 这里测到的收益是**偏保守**的下界。

产出:
  /tmp/vp/phase1c/emb_denoised.npz   (与 phase1/meta.json 行序**完全一致**)

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1c_denoise.py --phase1 /tmp/vp/phase1 --meetings 255,262 --out /tmp/vp/phase1c
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 16000
# ⚠️ 块长上限 100s 是**有意的**: FRCRN 的 forward 里
#    `if t > window * 120: decode_do_segement = True` (window = 16000 样本 = 1s)
#    ⇒ 超过 120s 的音频会走「内部按 1s 窗逐段前向」的慢路径 (实测慢 ~10 倍)。
#    ⇒ 块长取 100s (< 120s) ⇒ 走单次前向的快路径 (RTF ≈ 0.073)。
BLOCK_SEC = 100.0


def log(msg):
    print("[phase1c] " + msg, flush=True)


def audio_norm_factor(x):
    """modelscope `audio_norm` 的总因子 (逐行复刻 utils/audio/audio_utils.py:58)。

    返回 f, 使得  x_out = f * x  是 modelscope 归一化后的音频
    ⇒ 降噪输出除以 f 即回到原始尺度。
    """
    x = np.asarray(x, dtype=np.float64)
    rms = (x ** 2).mean() ** 0.5
    scalar = 10 ** (-25 / 20) / (rms if rms > 0 else 1.0)
    y = x * scalar
    pow_y = y ** 2
    avg_pow = pow_y.mean()
    sel = pow_y[pow_y > avg_pow]
    rmsx = (sel.mean() ** 0.5) if sel.size else 1.0
    scalarx = 10 ** (-25 / 20) / (rmsx if rmsx > 0 else 1.0)
    return float(scalar * scalarx)


def decode_audio(path):
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def fetch_audio(key):
    """⛔ 缓存名用**完整对象键** (类 20.242)。"""
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


def decode_output_pcm(raw, n_expected):
    """modelscope 的 ANSPipeline 返回的 `output_pcm` 是**裸 PCM bytes**(不是 WAV)。

    ⚠️ 实测踩到两点:
      ① 直接 `sf.read(BytesIO(raw))` 报 "Format not recognised" ⇒ 不是 WAV 容器
      ② `np.frombuffer` 要求字节数是元素大小的整数倍 ⇒ 输出长度**可能不是 4 的倍数**
         (padding 未裁干净) ⇒ 必须先截断再解读
    ⇒ 枚举候选编码 (f32 / f64 / i16), 取解读后长度最接近原始块的那个。
    """
    import soundfile as sf
    if not isinstance(raw, (bytes, bytearray)):
        return np.asarray(raw, dtype=np.float32).ravel()
    b = bytes(raw)
    if b[:4] == b"RIFF":
        y, _ = sf.read(io.BytesIO(b), dtype="float32")
        return np.asarray(y, dtype=np.float32).ravel()
    cands = []
    for dt in (np.float32, np.float64, np.int16):
        it = np.dtype(dt).itemsize
        n = len(b) // it
        if n <= 0:
            continue
        arr = np.frombuffer(b[:n * it], dtype=dt)
        if dt == np.int16:
            arr = arr.astype(np.float32) / 32768.0
        else:
            arr = arr.astype(np.float32)
        cands.append((str(dt), arr))
    if not cands:
        return np.zeros(0, dtype=np.float32)
    name, best = min(cands, key=lambda kv: abs(kv[1].size - n_expected))
    return np.asarray(best, dtype=np.float32)


def denoise_block(pipeline_obj, block, sr=SR):
    """降噪一个块, 返回**原始尺度**的音频。"""
    import soundfile as sf
    f = audio_norm_factor(block)
    buf = io.BytesIO()
    sf.write(buf, block, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    out = pipeline_obj(buf.getvalue())
    y = decode_output_pcm(out["output_pcm"], len(block))
    n = min(len(y), len(block))
    y = y[:n] / f                       # ⭐ 乘回归一化因子 ⇒ 回到原始尺度
    return y


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/phase1c")
    ap.add_argument("--meetings", default="255,262")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    meetings = [int(x) for x in args.meetings.split(",") if x.strip()]

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    log("meta %d 条; 目标会议 %s" % (len(META), meetings))

    from modelscope.pipelines import pipeline
    from modelscope.utils.constant import Tasks
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.voiceprint_service import VoiceprintService

    t0 = time.time()
    ans = pipeline(task=Tasks.acoustic_noise_suppression,
                   model="iic/speech_frcrn_ans_cirm_16k")
    log("FRCRN pipeline 加载完成 %.1fs" % (time.time() - t0))

    engine, Session = create_celery_engine_and_session()
    mt = {}
    async with Session() as db:
        rows = (await db.execute(
            select(Meeting).where(Meeting.id.in_(meetings)))).scalars().all()
        for m in rows:
            mt[m.id] = {"audio_url": m.audio_url,
                        "segs": sorted(m.transcript or [],
                                       key=lambda s: float(s.get("start") or 0))}
    await engine.dispose()

    # meta 里这些会议的段索引 (行序必须与 emb_eres.npz 一致 ⇒ 只替换这些行的嵌入)
    from collections import defaultdict
    row_of = defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg" and m["meeting"] in meetings:
            row_of[m["meeting"]].append(i)
    for mid in meetings:
        log("会议 %d: meta 里 %d 个段行" % (mid, len(row_of.get(mid, []))))

    svc = VoiceprintService()
    out_vec = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    replaced = 0

    for mid in meetings:
        t1 = time.time()
        info = mt.get(mid)
        if not info or not info["audio_url"]:
            log("会议 %d 无音频, 跳过" % mid)
            continue
        pcm = decode_audio(fetch_audio(info["audio_url"]))
        need = max((float(s.get("end") or 0) for s in info["segs"]), default=0.0)
        if len(pcm) / SR < need * 0.95:
            raise RuntimeError("会议 %d 音频长度不足" % mid)
        # 分块降噪 (不重叠)
        blk = int(BLOCK_SEC * SR)
        den = np.zeros_like(pcm)
        n_blocks = 0
        for pos in range(0, len(pcm), blk):
            chunk = pcm[pos:pos + blk]
            if len(chunk) < SR:          # <1s 的尾块跳过
                continue
            y = denoise_block(ans, chunk)
            m = min(len(y), len(chunk))
            den[pos:pos + m] = y[:m]
            n_blocks += 1
            if n_blocks % 20 == 0:
                log("  会议 %d: 降噪 %d 块 (%.0fs 音频), 用时 %.0fs" % (
                    mid, n_blocks, len(pcm) / SR, time.time() - t1))
        rms_o = float(np.sqrt((pcm ** 2).mean()))
        rms_d = float(np.sqrt((den ** 2).mean()))
        log("会议 %d 降噪完成: %d 块, 音频 %.0fs, 用时 %.0fs | RMS 原 %.5f → 降噪后 %.5f" % (
            mid, n_blocks, len(pcm) / SR, time.time() - t1, rms_o, rms_d))

        # 按**原来的段边界**重新切 + 重新嵌入
        clips = []
        keep_rows = []
        for i in row_of.get(mid, []):
            m = META[i]
            lo, hi = int(m["start"] * SR), int(m["end"] * SR)
            if lo < 0 or hi > len(den):
                continue
            clips.append(den[lo:hi])
            keep_rows.append(i)
        embs = svc.batch_extract_embeddings(clips)
        n_ok = 0
        for i, e in zip(keep_rows, embs):
            v = np.asarray(e, dtype=np.float32)
            n = float(np.linalg.norm(v))
            if n < 1e-6:
                continue
            out_vec[i] = v / n
            n_ok += 1
        replaced += n_ok
        log("会议 %d: 重新嵌入 %d/%d 段" % (mid, n_ok, len(keep_rows)))
        del pcm, den

    outp = os.path.join(args.out, "emb_denoised.npz")
    np.savez_compressed(outp, emb=out_vec)
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(META, fh, ensure_ascii=False)
    log("已写出 %s (替换 %d 行; 未替换的行保持原样)" % (outp, replaced))
    log("⚠️ 只有 %s 这几场被降噪, 其它场的行仍是**未降噪**的嵌入 ⇒ "
        "A/B 对照的有效范围限于这几场" % meetings)


if __name__ == "__main__":
    import asyncio
    import collections
    asyncio.run(main())
