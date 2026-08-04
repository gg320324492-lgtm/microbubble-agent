#!/usr/bin/env python3
"""Replay Meeting end-to-end (W2 +N 2026-08-04) — Python 版 (绕开 bash 引号问题)

用法:
  python scripts/replay_meeting.py <audio-file> <created_by_username>
  python scripts/replay_meeting.py "C:\\Users\\pc\\Desktop\\audio.m4a" zhanghongkui
"""
import os
import sys
import json
import time
import requests

SERVER = "https://agent.mnb-lab.cn"
PASSWORD = "123456"  # W2 +N 重置后默认密码
MAX_WAIT_SEC = 600
POLL_INTERVAL = 30

audio_file = sys.argv[1] if len(sys.argv) > 1 else ""
username = sys.argv[2] if len(sys.argv) > 2 else "zhanghongkui"

if not audio_file or not os.path.exists(audio_file):
    print(f"ERROR: audio file not found: {audio_file}")
    print("Usage: python scripts/replay_meeting.py <audio-file> <username>")
    sys.exit(1)

file_size = os.path.getsize(audio_file)
print("=" * 60)
print(" Replay Meeting (W2 +N 2026-08-04, Python 版)")
print("=" * 60)
print(f"  Audio:    {audio_file}")
print(f"  Size:     {file_size} bytes")
print(f"  User:     {username}")
print(f"  Server:   {SERVER}")
print()

# 1. Login
print("[1/6] Login...")
r = requests.post(f"{SERVER}/api/v1/auth/login",
                  json={"username": username, "password": PASSWORD}, timeout=30)
data = r.json()
token = data.get("access_token")
if not token:
    print(f"ERROR: {r.text}")
    sys.exit(1)
print(f"      Token: {token[:30]}...")

# 2. Start recording
print()
print("[2/6] Start recording...")
r = requests.post(f"{SERVER}/api/v1/meetings/start-recording",
                  headers={"Authorization": f"Bearer {token}"}, timeout=30)
data = r.json()
meeting_id = data.get("id")
if not meeting_id:
    print(f"ERROR: {r.text}")
    sys.exit(1)
print(f"      Meeting ID: {meeting_id}")

# 3. Upload audio (Python requests 直接处理, 无 bash 引号问题)
print()
print(f"[3/6] Upload audio ({file_size} bytes)...")
with open(audio_file, "rb") as f:
    files = {"file": ("recording.m4a", f, "audio/mp4")}
    r = requests.post(f"{SERVER}/api/v1/meetings/{meeting_id}/upload-audio",
                      headers={"Authorization": f"Bearer {token}"},
                      files=files, timeout=120)
print(f"      HTTP {r.status_code}: {r.text[:200]}")
if r.status_code != 200:
    print("ERROR: Upload failed")
    sys.exit(1)

# 4. Stop recording (触发 Celery)
print()
print("[4/6] Stop recording (触发 Celery post_meeting_process)...")
r = requests.post(f"{SERVER}/api/v1/meetings/{meeting_id}/stop-recording",
                  headers={"Authorization": f"Bearer {token}"}, timeout=30)
print(f"      HTTP {r.status_code}: {r.text[:200]}")

# 5. Poll
print()
print(f"[5/6] Polling status (max {MAX_WAIT_SEC}s, every {POLL_INTERVAL}s)...")
start_ts = time.time()
last_status = ""
while True:
    elapsed = int(time.time() - start_ts)
    if elapsed > MAX_WAIT_SEC:
        print(f"      [TIMEOUT {MAX_WAIT_SEC}s] last_status={last_status}")
        break

    r = requests.get(f"{SERVER}/api/v1/meetings/{meeting_id}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=30)
    if r.status_code != 200:
        print(f"      [{elapsed}s] HTTP {r.status_code}")
        time.sleep(POLL_INTERVAL)
        continue

    data = r.json()
    status = data.get("status", "unknown")
    upload = data.get("upload_status", "")
    title = data.get("title", "")
    tr_len = len(data.get("transcript") or "")
    pol = data.get("transcript_polished") or []
    pol_len = len(pol) if isinstance(pol, list) else len(str(pol))

    if status != last_status or elapsed % 60 < 5:
        print(f"      [{elapsed:3d}s] status={status} upload={upload} title=\"{title}\" transcript_len={tr_len} polished_segments={pol_len}")
        last_status = status

    if status == "completed":
        print(f"      ✓ completed at {elapsed}s")
        break
    if status == "failed":
        print(f"      ✗ failed")
        break

    time.sleep(POLL_INTERVAL)

# 6. Final state
print()
print("[6/6] Final meeting state:")
print("=" * 60)
r = requests.get(f"{SERVER}/api/v1/meetings/{meeting_id}",
                 headers={"Authorization": f"Bearer {token}"}, timeout=30)
data = r.json()
# 截断过长的 transcript 输出
transcript = data.get("transcript") or ""
if isinstance(transcript, list) and len(transcript) > 5:
    data["transcript"] = transcript[:3] + ["... (truncated)"] + transcript[-2:]
elif isinstance(transcript, str) and len(transcript) > 1000:
    data["transcript"] = transcript[:500] + "..."
print(json.dumps(data, ensure_ascii=False, indent=2, default=str)[:3000])
print()
print("=" * 60)
print(f" Meeting ID:    {meeting_id}")
print(f" Frontend URL: {SERVER}/meetings/{meeting_id}")
print("=" * 60)