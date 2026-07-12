"""dump 所有 enrolled 成员的 samples 数量 + 距离矩阵的解读"""
import sys
import numpy as np
sys.path.insert(0, "/app")

from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker as _sm
from app.config import settings
from app.models.member import Member
from sqlalchemy import select

_sync_engine = _ce(settings.DATABASE_URL)
SyncS = _sm(bind=_sync_engine)
with SyncS() as sdb:
    members = sdb.execute(
        select(Member).where(Member.voice_embedding.isnot(None))
    ).scalars().all()
_sync_engine.dispose()

print(f"{'name':<10} {'samples':<8} {'id':<4}")
print("-" * 30)
for m in sorted(members, key=lambda x: -(x.voice_sample_count or 0)):
    print(f"{m.name:<10} {m.voice_sample_count or 0:<8} {m.id:<4}")
