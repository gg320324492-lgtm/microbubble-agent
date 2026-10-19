"""把一份已落盘的 m4a 录音收录进会议系统（一次性上传路径）。

在 app 容器内执行：JWT 在进程内生成，不落盘不打印。
用法: docker exec -w /app microbubble-agent-app-1 python /tmp/ingest_meeting.py <audio_path> "<title>" "<location>" <owner_member_id> <participant_id...>
"""
import asyncio
import sys

import httpx

from app.core.security import create_access_token


async def main() -> int:
    audio_path = sys.argv[1]
    title = sys.argv[2]
    location = sys.argv[3]
    owner_id = int(sys.argv[4])
    participants = [int(x) for x in sys.argv[5:]]

    token = create_access_token({"sub": str(owner_id)})
    headers = {"Authorization": f"Bearer {token}"}
    base = "http://127.0.0.1:8000/api/v1"

    async with httpx.AsyncClient(timeout=600.0) as c:
        r = await c.post(f"{base}/meetings/start-recording", headers=headers)
        r.raise_for_status()
        mid = r.json()["id"]
        print(f"[1/4] meeting created id={mid}")

        with open(audio_path, "rb") as f:
            r = await c.post(
                f"{base}/meetings/{mid}/upload-audio",
                headers=headers,
                files={"file": (audio_path.split("/")[-1], f, "audio/mp4")},
            )
        r.raise_for_status()
        print(f"[2/4] audio uploaded: {r.json()}")

        r = await c.put(
            f"{base}/meetings/{mid}",
            headers=headers,
            json={
                "title": title,
                "location": location,
                "participants": participants,
                "presenter_ids": [1],
            },
        )
        r.raise_for_status()
        print(f"[3/4] metadata updated: id={r.json()['id']} title={r.json()['title']!r}")

        r = await c.post(f"{base}/meetings/{mid}/stop-recording", headers=headers)
        r.raise_for_status()
        print(f"[4/4] stop-recording: {r.json()}")

    print(f"\nMEETING_ID={mid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
