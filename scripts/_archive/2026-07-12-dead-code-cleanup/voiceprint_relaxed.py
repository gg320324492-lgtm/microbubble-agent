"""
简化声纹识别 (宽松阈值, 会议 203)
- majority vote + ratio > 0.5 才标记
- 写回 transcript.speaker + speaker_mapping
"""
import asyncio
import sys
import numpy as np
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models.meeting import Meeting
from app.models.member import Member
from app.services.voiceprint_service import voiceprint_service
from app.services.voiceprint_voting import _cluster_center
from sklearn.cluster import KMeans

MEETING_ID = 203
AUDIO_PATH = "/tmp/meeting_203_16k.wav"

async def main():
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with sf() as db:
        m = await db.get(Meeting, MEETING_ID)
        transcript = list(m.transcript or [])
        print(f"[1] loaded {len(transcript)} segments", flush=True)
        
        r = await db.execute(select(Member).where(Member.voice_embedding.isnot(None)))
        enrolled = [
            (mm.id, mm.name, np.array(mm.voice_embedding, dtype=np.float32), mm.voice_sample_count or 1)
            for mm in r.scalars().all()
        ]
        print(f"[2] loaded {len(enrolled)} enrolled members", flush=True)
        
        voiceprint_service._load_pipeline()
        from scipy.io import wavfile as siowav
        sr, pcm_int = siowav.read(AUDIO_PATH)
        pcm = pcm_int.astype(np.float32) / 32768.0
        print(f"[3] loaded audio: {len(pcm)/sr:.1f}s, {sr}Hz", flush=True)
        
        chunks, valid_idx = [], []
        for i, seg in enumerate(transcript):
            if seg.get("removed"):
                continue
            st = seg.get("start", 0)
            et = seg.get("end", st + 1)
            text = (seg.get("text") or "").strip()
            if len(text) < 3:
                continue
            s = max(0, int(st * 16000))
            e = min(len(pcm), int(et * 16000))
            if e - s < int(16000 * 0.6):
                continue
            chunks.append(pcm[s:e])
            valid_idx.append(i)
        print(f"[4] valid chunks: {len(chunks)}", flush=True)
        
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(voiceprint_service._extract_via_model, c) for c in chunks]
            embs = [f.result() for f in futures]
        seg_embs = [None] * len(transcript)
        for j, i in enumerate(valid_idx):
            seg_embs[i] = embs[j]
        valid_count = sum(1 for e in seg_embs if e is not None and not np.all(np.array(e) == 0))
        print(f"[5] valid embs: {valid_count}", flush=True)
        
        # KMeans 6 簇
        arr = np.array([e for e in seg_embs if e is not None and not np.all(np.array(e) == 0)])
        if len(arr) < 6:
            print(f"WARN: not enough embs ({len(arr)}), skip KMeans")
            return
        km = KMeans(n_clusters=6, random_state=42, n_init=10).fit(arr)
        labels_full = [-1] * len(transcript)
        vi = 0
        for i in range(len(transcript)):
            if seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0):
                labels_full[i] = km.labels_[vi]
                vi += 1
        
        # Majority vote per cluster
        cluster_names = {}
        for cid in range(6):
            idxs = [i for i, l in enumerate(labels_full) if l == cid]
            emb_list = [seg_embs[i] for i in idxs if seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0)]
            if not emb_list:
                continue
            center = _cluster_center(emb_list)
            votes = Counter()
            for e in emb_list:
                best_name, best_d = None, 999
                for mid, name, emb, sc in enrolled:
                    d = np.linalg.norm(center - emb)
                    if d < best_d:
                        best_d, best_name = d, name
                votes[best_name] += 1
            total = len(emb_list)
            top_name, top_votes = votes.most_common(1)[0]
            ratio = top_votes / total
            cluster_names[cid] = (top_name, top_votes, total, ratio)
            print(f"  cluster {cid}: {top_name} {top_votes}/{total} ({ratio*100:.0f}%)", flush=True)
        
        # 写回 (ratio > 0.5)
        n_updated = 0
        for cid, (name, votes, total, ratio) in cluster_names.items():
            if ratio < 0.5:
                print(f"  SKIP cluster {cid} ({ratio*100:.0f}% < 50%)", flush=True)
                continue
            for i in range(len(transcript)):
                if labels_full[i] == cid and seg_embs[i] is not None:
                    transcript[i]["speaker"] = name
                    n_updated += 1
            print(f"  APPLIED cluster {cid} → {name} ({votes} segments)", flush=True)
        
        m.transcript = transcript
        m.speaker_mapping = {str(c): n for c, (n, v, t, r) in cluster_names.items() if r >= 0.5}
        m.speaker_stats = [
            {"name": n, "votes": v, "total_segments": t, "ratio": r}
            for c, (n, v, t, r) in cluster_names.items() if r >= 0.5
        ]
        m.cluster_id_history = list(m.cluster_id_history or []) + [
            {"timestamp": "2026-07-08-relaxed", "k": 6, "clusters": [
                {"cid": c, "name": n, "votes": v, "total": t, "ratio": r}
                for c, (n, v, t, r) in cluster_names.items()
            ]}
        ]
        await db.commit()
        print(f"✅ 写回 DB: {len(m.speaker_mapping)} cluster, {n_updated} segments updated")

if __name__ == "__main__":
    asyncio.run(main())
