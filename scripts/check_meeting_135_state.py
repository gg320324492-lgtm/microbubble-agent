"""检查会议 #135 重处理后状态"""
import asyncio
from collections import Counter
from app.core.database import async_session
from app.models.meeting import Meeting

async def main():
    async with async_session() as db:
        m = await db.get(Meeting, 135)
        t = m.transcript or []
        tp = m.transcript_polished or []
        sm = m.speaker_mapping or {}
        sp_counter = Counter()
        for e in t:
            sp_counter[e.get('speaker', '?')] += 1
        print("=== 会议 #135 重处理后状态 ===")
        print(f"transcript 段数: {len(t)}")
        print(f"transcript_polished 段数: {len(tp)}")
        print(f"transcript speaker 分布: {dict(sp_counter)}")
        print(f"speaker_mapping 总条数: {len(sm)}")
        # Only show first 10 mapping entries
        print(f"speaker_mapping (前 10 条):")
        for i, (k, v) in enumerate(list(sm.items())[:10]):
            print(f"  {k!r} -> {v!r}")
        print(f"summary 长度: {len(m.summary or '')} chars")
        print(f"key_points 数量: {len(m.key_points or [])}")
        print(f"decisions 数量: {len(m.decisions or [])}")
        if m.key_points:
            print(f"  key_points[0] 前 80 字: {(m.key_points[0] or '')[:80]}")
        if m.summary:
            print(f"  summary 前 200 字: {(m.summary or '')[:200]}")
        # Check what key_points contain (look for any old wrong names)
        for old_name in ["洪辉", "周之超", "杜同贺", "宋洋", "test_", "发言人A", "发言人B", "发言人C", "发言人D", "发言人E"]:
            found_in_kp = sum(1 for kp in (m.key_points or []) if old_name in (kp or ""))
            found_in_dec = sum(1 for d in (m.decisions or []) if old_name in (d or ""))
            if found_in_kp or found_in_dec:
                print(f"  ⚠️ {old_name}: key_points={found_in_kp}, decisions={found_in_dec}")
        # 赵航佳 is the REAL speaker at this meeting, so should appear
        for real_name in ["王天志", "赵航佳", "韩重阳", "张宏魁"]:
            found_in_t = sum(1 for e in t if e.get('speaker') == real_name)
            found_in_kp = sum(1 for kp in (m.key_points or []) if real_name in (kp or ""))
            found_in_sm = sum(1 for v in sm.values() if v == real_name)
            print(f"  ✓ {real_name}: transcript={found_in_t}段, key_points={found_in_kp}条, speaker_mapping={found_in_sm}条")

asyncio.run(main())
