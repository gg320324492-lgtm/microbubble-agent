"""从**人工确认台账**提取逐段嵌入, 供声纹重建与污染体检使用。

为什么需要它
------------
流水线只写最终姓名、不存距离 (类 20.220 的「状态字段在说谎」) ⇒ 光看 transcript
判断不了哪一段归错了。而**唯一可信的参照是人耳确认的台账**
(`docs/voiceprint-confirmed-blocks-2026-10-13.json` / `-2026-10-30.json`)。

⛔ 判「某人本场有没有发言」必须用**跨场人工台账重建的真值质心**,
不能用库里那个 anchor —— anchor 自己就可能被污染过 (类 20.241)。

产出 `/tmp/vp/ledger_samples.npz`:
  emb      (N, 192) float32  每段的 L2 归一化嵌入
  meta     每段一条: {meeting, seg_idx, start, end, dur, text, who, block, in_ledger}
            who = 台账确认的说话人 (空字符串 = 该段不在台账里, 走 DB 当前标签)
            in_ledger = 1 表示该段落在人工确认块内 (可作训练/验证样本)

用法 (在 app 容器内):
    MID_LIST="250,254,255,256,259" python /app/scripts/voiceprint/ledger_samples.py \
        --ledgers /tmp/ledger_13.json,/tmp/ledger_30.json
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, "/app")

SR = 16000
MIN_SEC = 0.5  # 与生产一致: 短于 0.5s 的段不参与识别
WORK = "/tmp/vp"
# 台账里有块的会议 (音频都还在 MinIO)
ALL_MEETINGS = [229, 243, 247, 250, 254, 255, 256, 259]


def decode_audio(path: str) -> np.ndarray:
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 解码失败: " + p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def fetch_audio(key: str) -> str:
    """从 MinIO 取会议音频到容器本地 (缓存复用)。

    ⛔ 缓存文件名必须用**完整对象键**, 不能用 basename ——
    `recordings/255/merged.m4a` / `256/merged.m4a` / `259/merged.m4a` 的 basename
    全是 `merged.m4a` ⇒ 用 basename 做缓存键会让**后两场静默复用第一场的音频**
    (2026-10-30 实测踩中: 255/256/259 三场音频长度全被打印成 3424.4s = 259 的长度)。
    ⇒ 键里把 '/' 换掉, 保留全路径。
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
    print("[vp] 下载 %s (%.1f MB)" % (key, len(data) / 1048576), flush=True)
    return local


def seg_mid_in(s: float, e: float, lo: float, hi: float) -> bool:
    """段是否属于台账块 [lo, hi]: 用**中点**判定, 避免跨界段被双算。"""
    mid = (s + e) / 2.0
    return lo <= mid <= hi


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledgers", required=True, help="逗号分隔的台账 json 路径")
    ap.add_argument("--out", default=os.path.join(WORK, "ledger_samples.npz"))
    ap.add_argument("--meetings", default="")
    args = ap.parse_args()

    os.makedirs(WORK, exist_ok=True)

    blocks = []
    for p in args.ledgers.split(","):
        if not p.strip():
            continue
        with open(p.strip(), encoding="utf-8") as fh:
            d = json.load(fh)
        for b in d["blocks"]:
            # 台账里被声学/复核判定为不可用的块 (_可用=false) 必须跳过
            # —— 否则一条错标的块会污染质心 (2026-10-30 实测: 「刘子煜 @ 250 4940-4982」
            #    证明那不是刘子煜, 用它训练会让质心在别的会议抢走 70+ 段)。
            if b.get("_可用") is False:
                print("[vp] 跳过已订正为不可用的块: %s @ 会议%s %s-%s" % (
                    b["who"], b["meeting"], b["s"], b["e"]), flush=True)
                continue
            blocks.append({
                "who": b["who"], "meeting": int(b["meeting"]),
                "s": float(b["s"]), "e": float(b["e"]),
                "ledger": os.path.basename(p.strip()),
            })
    print("[vp] 台账块 %d 条" % len(blocks), flush=True)

    from sqlalchemy import select

    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.voiceprint_service import VoiceprintService

    engine, Session = create_celery_engine_and_session()
    meetings = {}
    async with Session() as db:
        rows = (await db.execute(
            select(Meeting).where(Meeting.id.in_(ALL_MEETINGS)))).scalars().all()
        for m in rows:
            segs = sorted(m.transcript or [], key=lambda s: float(s.get("start") or 0))
            meetings[m.id] = {"audio_url": m.audio_url, "segs": segs}
    await engine.dispose()

    wanted = sorted({b["meeting"] for b in blocks})
    if args.meetings:
        wanted = [int(x) for x in args.meetings.split(",") if x.strip()]

    # ---- 切片 + 收集待嵌入段 ----
    clips, meta = [], []
    for mid in wanted:
        info = meetings.get(mid)
        if not info or not info["audio_url"]:
            print("[vp] 跳过会议 %d (无音频)" % mid, flush=True)
            continue
        pcm = decode_audio(fetch_audio(info["audio_url"]))
        # ⛔ 自检: 音频长度必须覆盖整场转录 —— 这是「取错了音频」的**唯一可测信号**。
        # basename 缓存碰撞那次, 255/256 的转录最长到 3xxx s 而音频只有 259 的 3424 s,
        # 若不做这项检查, 后两场会**静默**用错音频切段 (类 20.220)。
        need = max((float(s.get("end") or 0) for s in info["segs"]), default=0.0)
        got = len(pcm) / SR
        if got < need * 0.95:
            raise RuntimeError(
                "会议 %d 音频长度不足: 音频 %.1fs < 转录所需 %.1fs (音频=%s) —— "
                "取错对象或缓存键碰撞" % (mid, got, need, info["audio_url"]))
        print("[vp] 会议 %d: %d 段, 音频 %.1fs (转录覆盖到 %.1fs)" % (
            mid, len(info["segs"]), got, need), flush=True)
        my_blocks = [b for b in blocks if b["meeting"] == mid]
        for i, s in enumerate(info["segs"]):
            st = float(s.get("start") or 0)
            en = float(s.get("end") or 0)
            if en - st < MIN_SEC:
                continue
            lo = int(st * SR)
            hi = int(en * SR)
            if lo < 0 or hi > len(pcm):
                continue
            who, blk = "", None
            for bi, b in enumerate(my_blocks):
                if seg_mid_in(st, en, b["s"], b["e"]):
                    who, blk = b["who"], bi
                    break
            clips.append(pcm[lo:hi])
            meta.append({
                "meeting": mid, "seg_idx": i, "start": round(st, 3), "end": round(en, 3),
                "dur": round(en - st, 3), "text": (s.get("text") or "")[:120],
                "db_speaker": s.get("speaker") or "",
                "who": who, "block": blk if blk is not None else -1,
                "in_ledger": 1 if blk is not None else 0,
            })
        del pcm
    print("[vp] 待嵌入 %d 段" % len(clips), flush=True)

    # ---- GPU 批量嵌入 ----
    svc = VoiceprintService()
    embs = svc.batch_extract_embeddings(clips)
    keep, evecs = [], []
    for m, e in zip(meta, embs):
        if e is None or np.all(e == 0):
            continue
        v = np.asarray(e, dtype=np.float32)
        n = float(np.linalg.norm(v))
        if n < 1e-6:
            continue
        evecs.append(v / n)
        keep.append(m)
    print("[vp] 嵌入有效 %d/%d" % (len(evecs), len(clips)), flush=True)

    E = np.stack(evecs) if evecs else np.zeros((0, 192), dtype=np.float32)
    np.savez_compressed(args.out, emb=E)
    with open(args.out.replace(".npz", "_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(keep, fh, ensure_ascii=False)
    print("[vp] 已写出", args.out, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
