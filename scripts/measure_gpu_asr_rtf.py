"""实测 GPU 7B (VibeVoice-ASR) 的真实 RTF，用于校准 GPU_ASR_MAX_SEC 闸门。

背景：`GPU_ASR_MAX_SEC=3200` 最初是按 `docs/vibevoice-deployment-report-2026-09-07.md`
里的 "RTF 0.53~0.97"（20 分钟实测）拍的。但生产上 96 分 27 秒的会议提交 7B 后
**跑满 7200s 硬超时仍未完成** —— 真实 RTF 明显更差，说明那个数值不能外推到长音频
（分块变多、每块 max_new_tokens 更大、显存压力更高）。

本脚本取一段真实会议音频的前 N 秒，走完整守护链路跑一次 7B，读回 meta.rtf，
据此反推"在 JOB_TIMEOUT 预算内能处理多长的音频"，给出闸门建议值。

用法（容器内，需 host 守护在 :8005 且空闲）:
    docker cp scripts/measure_gpu_asr_rtf.py microbubble-agent-app-1:/tmp/
    docker exec -i microbubble-agent-app-1 python /tmp/measure_gpu_asr_rtf.py \
        --meeting 250 --seconds 600
"""
import argparse
import asyncio
import json
import sys
import time

sys.path.insert(0, "/app")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--seconds", type=float, default=600.0,
                    help="取音频前多少秒做实测")
    ap.add_argument("--out", default=None, help="把结果 json 落盘")
    args = ap.parse_args()

    import httpx
    import numpy as np
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.file_service import file_service
    from app.services.audio_processor import audio_processor
    from app.config import settings

    engine, sf = create_celery_engine_and_session()
    try:
        async with sf() as db:
            m = (await db.execute(select(Meeting).where(Meeting.id == args.meeting))).scalar_one()
            audio_url = m.audio_url
    finally:
        await engine.dispose()

    print(f"[1] 取音频 {audio_url}")
    data = await file_service.download_file(audio_url)
    pcm = await audio_processor.convert_webm_to_wav(data)
    sr = 16000
    clip = pcm[: int(args.seconds * sr)]
    print(f"    原音频 {len(pcm)/sr:.1f}s → 取前 {len(clip)/sr:.1f}s")

    base = settings.GPU_ASR_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as c:
        h = (await c.get(f"{base}/health")).json()
    print(f"[2] 守护健康: {h}")
    if h.get("running"):
        print("    ❌ 守护正忙，请等待当前作业结束再测（否则 RTF 会被并行任务污染）")
        return 3

    pcm16 = (np.clip(clip, -1, 1) * 32767).astype("<i2").tobytes()
    t0 = time.time()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{base}/transcribe?sr={sr}&meeting_id=rtf_probe",
                         content=pcm16,
                         headers={"Content-Type": "application/octet-stream"})
    job_id = r.json()["job_id"]
    print(f"[3] 已提交作业 {job_id}")

    last = None
    while True:
        await asyncio.sleep(10)
        async with httpx.AsyncClient(timeout=30) as c:
            info = (await c.get(f"{base}/jobs/{job_id}")).json()
        st = info.get("status")
        prog = info.get("progress") or {}
        if prog and prog != last:
            last = prog
            print(f"    [{time.time()-t0:6.0f}s] {prog.get('phase')} "
                  f"chunk={prog.get('chunk_done')}/{prog.get('chunks_total')} "
                  f"rtf={prog.get('rtf')} eta={prog.get('eta_sec')}")
        if st in ("done", "error"):
            break
        if time.time() - t0 > 3900:
            print("    实测超时（>65min），终止")
            break

    result = info.get("result") or {}
    meta = result.get("meta") or {}
    elapsed = time.time() - t0
    print()
    print(f"[4] 作业状态: {st}")
    print(f"    segments   : {len(result.get('segments') or [])}")
    print(f"    audio_sec  : {meta.get('audio_sec')}")
    print(f"    infer_sec  : {meta.get('infer_sec')}")
    print(f"    rtf        : {meta.get('rtf')}")
    print(f"    chunks     : {meta.get('chunks_done')}/{meta.get('chunks')}")
    print(f"    墙钟       : {elapsed:.0f}s")
    if result.get("error"):
        print(f"    error      : {result.get('error')}")
    if meta.get("log_tail"):
        print(f"    log_tail   : {meta['log_tail'][-400:]}")

    rtf = meta.get("rtf")
    budget = settings.GPU_ASR_TIMEOUT - 120
    suggestion = None
    if rtf:
        suggestion = int(budget / max(rtf, 0.01))
        print()
        print(f"[5] 校准建议：JOB_TIMEOUT={settings.GPU_ASR_TIMEOUT}s（worker 预算 {budget:.0f}s），"
              f"实测 RTF={rtf:.2f}")
        print(f"    → 预算内可处理约 {suggestion}s 音频（{suggestion/60:.1f} 分钟）")
        print(f"    → 当前 GPU_ASR_MAX_SEC={settings.GPU_ASR_MAX_SEC} "
              f"({'✅ 偏保守/安全' if settings.GPU_ASR_MAX_SEC <= suggestion else '⚠️ 偏激进，长音频仍会超时'})")

    if args.out:
        import pathlib
        pathlib.Path(args.out).write_text(json.dumps({
            "meeting_id": args.meeting, "clip_sec": len(clip) / sr,
            "status": st, "rtf": rtf, "meta": meta, "wall_sec": round(elapsed, 1),
            "suggested_max_sec": suggestion,
            "job_timeout": settings.GPU_ASR_TIMEOUT,
            "current_gpu_asr_max_sec": settings.GPU_ASR_MAX_SEC,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    结果已写入 {args.out}")
    return 0 if st == "done" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
