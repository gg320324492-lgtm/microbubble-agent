"""手动修复 #68 transcript 里被 apply 重 KMeans 拆开的 6 段 发言人?

场景: apply 重新跑 KMeans K=3 把 inject 合并的 cluster 又拆开, 5 段 cluster_id=0 + 1 段 cluster_id=1 被质量门控拒绝
修复: 按 cluster_id 直接 assign speaker (cluster_id=0 → 陈金薪, cluster_id=1 → 杜同贺)

用法:
    python scripts/fix_meeting_speakers.py --meeting 68 \
        --mapping "0:陈金薪,1:杜同贺"
"""
import argparse
import asyncio
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.meeting import Meeting


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", type=int, required=True)
    parser.add_argument("--mapping", type=str, required=True,
                        help="cluster_id:speaker 映射, 逗号分隔, 如 '0:陈金薪,1:杜同贺'")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # 解析 mapping
    cid_to_speaker = {}
    for item in args.mapping.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        cid_str, name = item.split(":", 1)
        cid_to_speaker[int(cid_str.strip())] = name.strip()

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == args.meeting))
        m = r.scalar_one()

        t = list(m.transcript or [])
        fixed_count = {sp: 0 for sp in cid_to_speaker.values()}

        for seg in t:
            if not isinstance(seg, dict):
                continue
            cid = seg.get("cluster_id", -1)
            sp = seg.get("speaker", "")
            if sp == "发言人?" and cid in cid_to_speaker:
                seg["speaker"] = cid_to_speaker[cid]
                fixed_count[cid_to_speaker[cid]] += 1

        # 镜像 transcript_polished
        tp = list(m.transcript_polished or [])
        for pseg in tp:
            if not isinstance(pseg, dict):
                continue
            if pseg.get("speaker") == "发言人?":
                idx = tp.index(pseg)
                if idx < len(t):
                    pseg["speaker"] = t[idx]["speaker"]

        # 当前分布
        ctr = Counter(s.get("speaker", "?") for s in t if isinstance(s, dict))

        print(f"修复段数: {fixed_count}")
        print(f"# {args.meeting} 修复后 speaker 分布: {dict(ctr)}")

        if args.dry_run:
            print("[DRY-RUN] 不写 DB")
            await engine.dispose()
            return

        # 写回
        m.transcript = t
        m.transcript_polished = tp

        if m.cluster_id_history is None:
            m.cluster_id_history = []
        m.cluster_id_history.append({
            "ts": datetime.utcnow().isoformat(),
            "source": "manual_fix",
            "injector": "scripts/fix_meeting_speakers.py",
            "n_segments": len(t),
            "fixed_segments": fixed_count,
            "notes": f"按 cluster_id 修正 发言人? → {cid_to_speaker}",
        })
        flag_modified(m, "transcript")
        flag_modified(m, "transcript_polished")
        flag_modified(m, "cluster_id_history")
        m.updated_at = datetime.utcnow()

        await db.commit()
        print("✅ DB updated")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())