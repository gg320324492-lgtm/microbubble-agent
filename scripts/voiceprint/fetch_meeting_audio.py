"""按 meetings.audio_url 取会议音频到容器本地(缓存名=完整对象键)。

⛔ 类 20.242: 缓存键必须用**完整对象键**。而且**不能假设 key 形如
`recordings/{id}/merged.m4a`** —— 250/257 等老会议用的是 `recordings/<uuid>.m4a`
(legacy 布局), 只有 255/256/259/262 是新布局 ⇒ **权威来源是 meetings.audio_url**。

同时带 fail-loud 自检: 取到的音频时长必须 >= 转录覆盖到的最大 end × 0.95。
"""
import asyncio
import json
import os
import subprocess
import sys

sys.path.insert(0, "/app")
WORK = "/tmp/vp"


async def main():
    ids = [int(x) for x in sys.argv[1].split(",")]
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        for mid in ids:
            m = (await db.execute(select(Meeting).where(Meeting.id == mid))).scalar_one()
            key = m.audio_url
            if not key:
                print("会议 %d 无 audio_url, 跳过" % mid)
                continue
            local = os.path.join(WORK, "src_" + key.replace("/", "__"))
            if not (os.path.exists(local) and os.path.getsize(local) > 1024):
                from minio import Minio
                c = Minio("minio:9000", access_key=os.environ["MINIO_ACCESS_KEY"],
                          secret_key=os.environ["MINIO_SECRET_KEY"], secure=False)
                r = c.get_object("microbubble", key)
                try:
                    data = r.read()
                finally:
                    r.close()
                    r.release_conn()
                with open(local, "wb") as fh:
                    fh.write(data)
                print("会议 %d 下载 %s (%.1f MB)" % (mid, key, len(data) / 1048576))
            else:
                print("会议 %d 已有缓存 (%.1f MB)" % (mid, os.path.getsize(local) / 1048576))

            # --- fail-loud 自检: 音频时长 vs 转录覆盖 ---
            p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", local], capture_output=True)
            dur = float(p.stdout.decode().strip())
            ends = [float(s.get("end") or 0) for s in (m.transcript or []) if s.get("end")]
            maxend = max(ends) if ends else 0.0
            ok = dur >= maxend * 0.95
            print("   音频 %.1fs / 转录最大 end %.1fs => %s" % (
                dur, maxend, "OK" if ok else "✗✗ 取错了音频(差 %.0f%%)!" % ((1 - dur / maxend) * 100)))
            if not ok:
                raise SystemExit("会议 %d 音频与转录不匹配, 中止" % mid)
            print("   本地: %s" % local)


if __name__ == "__main__":
    asyncio.run(main())
