"""重算某会议转写段的声纹距离, 找出「判据最弱」的段落供人工纠正。

为什么需要它: 刘子煜 / 肖佐林 等成员**没有声纹**(voice_sample_count=0、非 anchor),
他们的话在流水线里被归给了已有的 anchor(王天志 / 蒋芦笛)。流水线只留最终标签,
**不存距离** ⇒ 光看 transcript 无法判断哪一段归错了。

判据(全部是相对量, 不设自造绝对阈值 —— 类 20.226 ⑤「阈值不能凭空设」):
  A) z 同标签离群: 该段到「当前标签」的距离, 相对**同标签在本会议内**的距离分布
     (中位数 + k×MAD)。z 越大 = 越不像当前标签。
  B) m 最小距离: 该段到 anchor 池里**最近**那个人的距离。离 0.65 阈值越近 = 越勉强。
     (没声纹的成员, 其段对**所有** anchor 都远 ⇒ 这类段只能靠 min_dist 暴露)
  C) g 判据模糊: top1 与 top2 的距离差(margin)。差得小 = 连模型都分不出是谁。

输出: stdout 一份 JSON + 导出可疑段音频到 /tmp/vp/suspects/ 供人工听辨。
"""

import asyncio
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, "/app")

MEETING_ID = int(os.environ.get("MID", "259"))
SR = 16000
WORK = "/tmp/vp"
OUT = os.path.join(WORK, "suspects")
AUDIO_KEY = os.environ.get("AUDIO_KEY", "recordings/259/merged.m4a")
MIN_SEC = 0.5  # 与生产一致: 短于 0.5s 的段不参与识别
TOP_N = int(os.environ.get("TOP_N", "40"))
Z_K = float(os.environ.get("Z_K", "3.0"))  # 同标签离群阈值(k×MAD)


def decode_audio(path: str) -> np.ndarray:
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 解码失败: " + p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def write_wav(path: str, audio: np.ndarray) -> None:
    import wave

    a = np.clip(audio, -1.0, 1.0)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((a * 32767).astype(np.int16).tobytes())


async def main() -> None:
    from sqlalchemy import select

    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.voiceprint_service import MATCH_THRESHOLD, VoiceprintService

    os.makedirs(OUT, exist_ok=True)

    # ---- 1. 取会议转写 + anchor 池 ----
    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        m = (await db.execute(select(Meeting).where(Meeting.id == MEETING_ID))).scalar_one()
        segs = sorted(m.transcript or [], key=lambda s: float(s.get("start") or 0))
        svc = VoiceprintService()
        anchors = await svc.get_anchor_members(db)
        anchor_names = [a.name for a in anchors]
        anchor_vecs = np.stack([np.array(a.voice_embedding, dtype=np.float32) for a in anchors])
    await engine.dispose()

    print(f"[vp] 会议 {MEETING_ID}: {len(segs)} 段; anchor 池 {len(anchors)} 人: {anchor_names}", flush=True)

    # ---- 2. 下载音频 ----
    audio_path = os.path.join(WORK, "audio.m4a")
    if not (os.path.exists(audio_path) and os.path.getsize(audio_path) > 1024):
        from minio import Minio

        c = Minio("minio:9000", access_key=os.environ["MINIO_ACCESS_KEY"],
                  secret_key=os.environ["MINIO_SECRET_KEY"], secure=False)
        # minio SDK 的 fget_object 第三参是**文件路径**不是文件对象 ⇒ 用 get_object 读字节
        resp = c.get_object("microbubble", AUDIO_KEY)
        try:
            data = resp.read()
        finally:
            resp.close()
            resp.release_conn()
        with open(audio_path, "wb") as fh:
            fh.write(data)
        print(f"[vp] 已下载 {AUDIO_KEY}: {len(data)} bytes", flush=True)
    pcm = decode_audio(audio_path)
    print(f"[vp] 音频解码 {len(pcm)/SR:.1f}s", flush=True)

    # ---- 3. 按转写段切片 ----
    clips, used = [], []
    for i, s in enumerate(segs):
        st = float(s.get("start") or 0)
        en = float(s.get("end") or 0)
        seg_audio = pcm[int(st * SR):int(en * SR)]
        if len(seg_audio) < SR * MIN_SEC:
            continue
        clips.append(seg_audio)
        used.append((i, st, en, s.get("speaker") or "?", s.get("text") or ""))
    print(f"[vp] 参与计算 {len(clips)}/{len(segs)} 段 (剔除 <{MIN_SEC}s)", flush=True)

    # ---- 4. 批量 embedding (GPU) ----
    embs = svc.batch_extract_embeddings(clips)
    good = [e for e in embs if e is not None and not np.all(e == 0)]
    print(f"[vp] embedding 有效 {len(good)}/{len(clips)}", flush=True)

    # ---- 5. 距离矩阵 ----
    rows = []
    for (i, st, en, spk, text), e in zip(used, embs):
        if e is None or np.all(e == 0):
            continue
        en_ = e / (np.linalg.norm(e) + 1e-8)
        an = anchor_vecs / (np.linalg.norm(anchor_vecs, axis=1, keepdims=True) + 1e-8)
        dists = 1.0 - an @ en_
        order = np.argsort(dists)
        rows.append({
            "idx": i, "start": st, "end": en, "dur": round(en - st, 2),
            "speaker": spk, "text": text,
            "min_dist": round(float(dists[order[0]]), 4),
            "min_to": anchor_names[int(order[0])],
            "margin": round(float(dists[order[1]] - dists[order[0]]), 4) if len(order) > 1 else None,
            "second": anchor_names[int(order[1])] if len(order) > 1 else None,
            "dists": {anchor_names[j]: round(float(dists[j]), 4) for j in order[:4]},
            "d_cur": round(float(dists[anchor_names.index(spk)]), 4) if spk in anchor_names else None,
        })

    # ---- 6. 同标签离群度 z (中位数 + k×MAD) ----
    by_spk = {}
    for r in rows:
        if r["d_cur"] is not None:
            by_spk.setdefault(r["speaker"], []).append(r["d_cur"])
    stats = {}
    for spk, ds in by_spk.items():
        arr = np.array(ds)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med))) or 1e-6
        stats[spk] = {"n": len(ds), "median": round(med, 4), "mad": round(mad, 4)}
        for r in rows:
            if r["speaker"] == spk and r["d_cur"] is not None:
                r["z"] = round((r["d_cur"] - med) / (1.4826 * mad), 2)

    # ---- 7. 打分排序: 越可疑分越高 ----
    for r in rows:
        r.setdefault("z", 0.0)
        # 离阈值越近越勉强
        r["near_threshold"] = round(max(0.0, MATCH_THRESHOLD - r["min_dist"]), 4)
        # margin 小 = 判据模糊
        r["margin_pen"] = round(1.0 / (1.0 + (r["margin"] or 1.0)), 3)
        r["score"] = round(
            max(r["z"], 0) * 1.0 + r["near_threshold"] * 3.0 + (1 - r["margin_pen"]) * 1.5,
            3,
        )

    ranked = sorted(rows, key=lambda r: -r["score"])[:TOP_N]

    # ---- 8. 导出可疑段音频供人工听辨 ----
    for k, r in enumerate(ranked, 1):
        a = pcm[int(r["start"] * SR):int(r["end"] * SR)]
        safe = "".join(ch if ch.isalnum() else "_" for ch in r["speaker"])
        fn = os.path.join(OUT, f"{k:02d}_{int(r['start']):04d}s_{safe}_z{r['z']}_d{r['min_dist']}.wav")
        write_wav(fn, a)
        r["audio_file"] = fn

    out = {
        "meeting_id": MEETING_ID,
        "match_threshold": MATCH_THRESHOLD,
        "anchor_pool": anchor_names,
        "segments_analyzed": len(rows),
        "label_stats": stats,
        "suspects": ranked,
    }
    with open(os.path.join(WORK, "analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print("[vp] JSON 已写出:", os.path.join(WORK, "analysis.json"), flush=True)
    print("[vp] 可疑段音频:", OUT, f"({len(ranked)} 个)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
