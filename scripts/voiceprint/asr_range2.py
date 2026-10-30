"""任意会议/任意区间: SenseVoice 逐窗转写 + 逐窗声学判定(vs 全体已录入质心)。

用法: python /tmp/vp/asr_range2.py <audio_path> <start> <end> <out_prefix> [win_sec]

判据口径 = 类 20.247 ②:
  窗口「离所有已知质心都远」⇒ 这是一个**没有声纹的人**;
  最近者是某人但距离大 ⇒ 可能是被吸走。
"""
import asyncio
import io
import json
import os
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, "/app")
SR = 16000


def pcm_of(a, b, path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-to", str(b), "-i", path,
                        "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def wav_bytes(pcm_f32, sr=16000):
    pcm16 = (np.clip(pcm_f32, -1, 1) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm16.tobytes())
    return buf.getvalue()


async def main():
    AUDIO = sys.argv[1]
    A, B = float(sys.argv[2]), float(sys.argv[3])
    PREFIX = sys.argv[4]
    WIN = float(sys.argv[5]) if len(sys.argv) > 5 else 6.0

    from app.voice.asr import SpeechRecognizer
    sr = SpeechRecognizer()
    texts = {}
    t = A
    while t < B - 0.5:
        b = min(t + WIN, B)
        pcm = pcm_of(t, b, AUDIO)
        if len(pcm) < 16000:
            break
        try:
            r = await sr.transcribe(wav_bytes(pcm), language="zh", task="transcribe",
                                    skip_convert=True)
            txt = (r.get("text") or "").strip()
            texts[(round(t, 2), round(b, 2))] = txt
            print("[vp] %7.1f-%7.1f  %s" % (t, b, txt[:120]), flush=True)
        except Exception as e:
            texts[(round(t, 2), round(b, 2))] = ""
            print("[vp] %7.1f-%7.1f  FAIL %r" % (t, b, e), flush=True)
        t += WIN

    # ---- 全体已录入质心 ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member
    engine, Session = create_celery_engine_and_session()
    cents = {}
    async with Session() as db:
        rows = (await db.execute(select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all()
        for m in rows:
            v = np.asarray(m.voice_embedding, dtype=np.float32)
            n = np.linalg.norm(v)
            if n > 0:
                cents[m.name] = v / n
    print("[vp] 质心 %d 人: %s" % (len(cents), list(cents.keys())), flush=True)

    from app.services.voiceprint_service import VoiceprintService
    svc = VoiceprintService()
    wins, metas = [], []
    t = A
    while t < B - 0.5:
        b = min(t + WIN, B)
        wins.append(pcm_of(t, b, AUDIO))
        metas.append((round(t, 2), round(b, 2)))
        t += WIN
    embs = svc.batch_extract_embeddings(wins)

    rows = []
    for (a, b), e in zip(metas, embs):
        txt = texts.get((a, b), "")
        if e is None or np.all(e == 0):
            rows.append({"s": a, "e": b, "text": txt, "judge": "?", "d": None,
                         "margin": None, "second": None})
            continue
        v = np.asarray(e, dtype=np.float32)
        v = v / np.linalg.norm(v)
        ds = sorted((float(1.0 - v @ c), k) for k, c in cents.items())
        d0, n0 = ds[0]
        d1 = ds[1][0] if len(ds) > 1 else 9.9
        rows.append({"s": a, "e": b, "text": txt, "judge": n0, "d": round(d0, 3),
                     "margin": round(d1 - d0, 3),
                     "second": ds[1][1] if len(ds) > 1 else None})
    json.dump(rows, open("/tmp/vp/%s_windows.json" % PREFIX, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    lines = ["区间 %.1f-%.1f 逐窗判定 (每窗 %.0fs)" % (A, B, WIN), "",
             "| 时间 | 最近者(d/差) | 次近 | 文本 |", "|---|---|---|---|"]
    for r in rows:
        lines.append("| %.1f-%.1f | **%s** %.3f / %.3f | %s | %s |" % (
            r["s"], r["e"], r["judge"], r["d"] or 0, r["margin"] or 0,
            r.get("second") or "", (r["text"] or "")[:78]))
    open("/tmp/vp/%s_windows.md" % PREFIX, "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
