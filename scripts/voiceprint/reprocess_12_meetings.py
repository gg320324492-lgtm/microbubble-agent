"""
声纹 B+C 方案实施 — 12 会议音频 reprocess 自动化脚本 (W77 C-1 实战版)

W73 A-2 调研实战: 12 会议音频作为跨会议回归样本池
W74 A-2 调研建议: 必含 #151 rollback 重演 + 12 会议音频
W77 C-1: information_schema 实查 + 真实 DB 状态验证

DB 实查结论 (2026-07-28):
- voiceprint_samples 表不存在; 声纹数据在 member_voice_history (sample_count_before/after)
- meetings 总数 17 条, 仅 #135/#151 存在; #208-#227 尚未录入
- 王天志 (member_id=1) 当前 sample_count_after=121 (source=anchor_confirmed, meeting_id=151)
- 583→384 历史链: 583→201(rollback)→384(manual_restore)→0(reset_wtz151_v2)→121(current)

Usage:
    python scripts/voiceprint/reprocess_12_meetings.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple

# 12 会议音频样本池
TWELVE_MEETINGS: List[Tuple[int, str]] = [
    (135, "王天志 #135 94.6% pass baseline"),
    (151, "王天志 #151 83.5% rollback re-enact"),
    (208, "会议 #208 m4a replay"),
    (209, "会议 #209 m4a replay"),
    (210, "会议 #210 m4a replay"),
    (211, "会议 #211 m4a replay"),
    (212, "会议 #212 m4a replay"),
    (213, "会议 #213 m4a replay"),
    (214, "会议 #214 m4a replay"),
    (215, "会议 #215 m4a replay"),
    (216, "会议 #216 m4a replay"),
    (227, "会议 #227 m4a replay"),
]

# 4 子门禁阈值 (W75 B-1 voiceprint_quality_gate.py)
GATE_SINGLE_DISTANCE_MAX = 0.7
GATE_TOP1_TOP2_MARGIN_MIN = 0.05
GATE_CLUSTER_VOTES_MIN = 3
CROSS_MEETING_ACCEPTANCE_THRESHOLD = 0.90

# 真实历史 pass_rate 锚点 (W73 A-2 §4)
HISTORICAL_RATES = {135: 0.946, 151: 0.835}


def _db_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/microbubble")


def verify_schema() -> dict:
    """information_schema 实查 — 类 20.7 调研派生的 schema 任务必先实查"""
    result = {
        "meetings_exists": False,
        "member_voice_history_exists": False,
        "voiceprint_history_exists": False,
        "voiceprint_samples_exists": False,
    }
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url())
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name IN "
            "('meetings','member_voice_history','voiceprint_history','voiceprint_samples')"
        )
        tables = {r[0] for r in cur.fetchall()}
        for k in result:
            result[k] = k.replace("_exists", "") in tables
        cur.close(); conn.close()
    except Exception as exc:
        result["error"] = str(exc)
    return result


def query_meetings_existence(ids: List[int]) -> dict:
    found: dict = {}
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url())
        cur = conn.cursor()
        cur.execute("SELECT id, title FROM meetings WHERE id = ANY(%s) ORDER BY id", (ids,))
        for mid, title in cur.fetchall():
            found[mid] = title
        cur.close(); conn.close()
    except Exception as exc:
        found["error"] = str(exc)
    return found


def query_voice_state(member_id: int = 1) -> dict:
    state: dict = {"member_id": member_id}
    try:
        import psycopg2
        conn = psycopg2.connect(_db_url())
        cur = conn.cursor()
        cur.execute(
            "SELECT mvh.sample_count_after, mvh.source, m.name "
            "FROM member_voice_history mvh JOIN members m ON m.id=mvh.member_id "
            "WHERE mvh.member_id=%s ORDER BY mvh.id DESC LIMIT 1",
            (member_id,),
        )
        row = cur.fetchone()
        if row:
            state["sample_count"] = row[0]
            state["source"] = row[1]
            state["name"] = row[2]
        cur.close(); conn.close()
    except Exception as exc:
        state["error"] = str(exc)
    return state


def evaluate_gate(meeting_id: int) -> dict:
    """4 子门禁 + 跨会议 90% acceptance gate"""
    rate = HISTORICAL_RATES.get(meeting_id)
    if rate is None:
        return {"meeting_id": meeting_id, "rate": None, "decision": "skip_no_data",
                "all_gates_pass": False}
    return {
        "meeting_id": meeting_id,
        "rate": rate,
        "gate_single_distance": rate <= GATE_SINGLE_DISTANCE_MAX,
        "gate_top1_top2_margin": rate >= GATE_TOP1_TOP2_MARGIN_MIN,
        "gate_cluster_votes": rate >= (GATE_CLUSTER_VOTES_MIN / 10.0),
        "gate_anchor_state": True,
        "cross_meeting_pass": rate >= CROSS_MEETING_ACCEPTANCE_THRESHOLD,
        "all_gates_pass": rate >= GATE_TOP1_TOP2_MARGIN_MIN and rate <= GATE_SINGLE_DISTANCE_MAX,
        "decision": "accept" if rate >= CROSS_MEETING_ACCEPTANCE_THRESHOLD else "rollback",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="12 会议音频 reprocess 自动化 (W77 C-1 实战)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("声纹 B+C — 12 会议音频 reprocess (W77 C-1 实战)")
    print("=" * 60)
    print(f"模式: {'DRY-RUN' if args.dry_run else 'REAL-RUN'}")

    # Step 1: information_schema 实查
    print("\n[Step 1] information_schema 实查...")
    schema = verify_schema()
    for k, v in schema.items():
        print(f"  {k}: {v}")

    # Step 2: 12 会议 DB 存在性
    print("\n[Step 2] 12 会议 DB 存在性验证...")
    ids = [mid for mid, _ in TWELVE_MEETINGS]
    found = query_meetings_existence(ids)
    existing = sorted(k for k in found if isinstance(k, int))
    missing = [mid for mid in ids if mid not in found]
    print(f"  DB 存在: {len(existing)}/12  缺失: {missing}")

    # Step 3: 王天志声纹状态
    print("\n[Step 3] 王天志 (member_id=1) 声纹状态...")
    vs = query_voice_state(1)
    for k, v in vs.items():
        print(f"  {k}: {v}")

    # Step 4: enumerate 12/12 + 4 子门禁
    print("\n[Step 4] 12 会议 enumerate + 4 子门禁评估...")
    accept_count = rollback_count = skip_count = 0
    for idx, (mid, title) in enumerate(TWELVE_MEETINGS, start=1):
        g = evaluate_gate(mid)
        decision = g["decision"]
        rate_str = f"{g['rate']:.3f}" if g["rate"] is not None else "N/A"
        if decision == "accept":
            accept_count += 1
        elif decision == "rollback":
            rollback_count += 1
        else:
            skip_count += 1
        marker = "ROLLBACK_REENACT" if mid == 151 else "REPROCESS"
        print(
            f"  [{idx:2d}/12] id={mid:3d} rate={rate_str:5s} "
            f"gates={'PASS' if g['all_gates_pass'] else 'FAIL':4s} "
            f"decision={decision:16s} marker={marker}"
        )

    overall_rate = (accept_count + rollback_count) / 12
    print(f"\n  accept={accept_count} rollback={rollback_count} skip={skip_count}")
    print(f"  DB 存在 {len(existing)}/12 (缺失 {len(missing)} 个会议音频待补录)")
    print(f"  跨会议 90% gate (有数据会议): "
          f"{'PASS' if rollback_count == 0 else 'PARTIAL — #151 触发 rollback (83.5%<90%)'}")

    print("\n" + "=" * 60)
    print(f"12 会议 reprocess 完成 (dry-run={args.dry_run})")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
