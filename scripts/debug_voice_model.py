import sys
sys.path.insert(0, "/app")
import numpy as np
import wave
import subprocess
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from app.services.voiceprint_service import voiceprint_service

voiceprint_service._load_pipeline()

# Load real audio
wav_path = "/tmp/meeting_120_16k.wav"
if not os.path.exists(wav_path):
    subprocess.run(["ffmpeg", "-y", "-i", "/tmp/meeting_120.m4a", "-ar", "16000", "-ac", "1", "-f", "wav", wav_path], check=True, capture_output=True)
with wave.open(wav_path, "rb") as wf:
    pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
print(f"Total audio: {len(pcm)/16000:.1f}s")

# Get real segments from DB
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.meeting import Meeting

async def get_segs():
    engine = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        m = await db.get(Meeting, 120)
        return list(m.transcript)

segs = asyncio.run(get_segs())
print(f"Got {len(segs)} segments from DB")

# Test 50 random segments
import random
random.seed(42)
sample = random.sample(range(len(segs)), 50)
chunks = []
for i in sample:
    s = float(segs[i].get("start", 0))
    e = float(segs[i].get("end", 0))
    a = int(s * 16000)
    b = int(e * 16000)
    c = pcm[a:b]
    if len(c) < 8000:
        chunks.append((i, s, e, len(c), None))
    else:
        if len(c) > 3 * 16000:
            mid = len(c) // 2
            c = c[mid - int(1.5*16000): mid + int(1.5*16000)]
        chunks.append((i, s, e, len(c), c))

print("Sample chunks prepared. Testing...")

lock = threading.Lock()
def extract(item):
    i, s, e, n, c = item
    if c is None:
        return (i, "SKIP")
    try:
        with lock:
            emb = voiceprint_service._extract_via_model(c)
        if np.all(emb == 0):
            return (i, "ZERO")
        return (i, "OK", emb[:5].tolist())
    except Exception as ex:
        return (i, f"ERR: {type(ex).__name__}: {ex}")

with ThreadPoolExecutor(max_workers=8) as ex:
    results = list(ex.map(extract, chunks))

ok = sum(1 for r in results if r[1] == "OK")
zero = sum(1 for r in results if r[1] == "ZERO")
err = sum(1 for r in results if r[1].startswith("ERR"))
skip = sum(1 for r in results if r[1] == "SKIP")
print(f"OK: {ok}, ZERO: {zero}, ERR: {err}, SKIP: {skip}")
for r in results[:5]:
    print(r)
