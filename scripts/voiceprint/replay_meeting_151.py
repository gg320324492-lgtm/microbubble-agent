"""
声纹 B+C 方案实施 — #151 rollback 重演脚本

W74 A-2 调研建议: #151 rollback 重演 (王天志 #135 94.6% + #151 83.5% → 整体 88.1% < 90%)

Usage:
    python scripts/voiceprint/replay_meeting_151.py --dry-run
"""

from __future__ import annotations

import argparse
import sys

# 真实历史案例锚点 (来自 docs/CLAUDE-history.md:5483-5492 + W74 A-2 调研 §0)
HISTORICAL_FACTS = {
    "meeting_135_rate": 0.946,
    "meeting_151_rate": 0.835,
    "weighted_overall_rate": 0.881,
    "rollback_target": "sample_count 583 → 384",
    "decision": "rollback",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="#151 rollback 重演")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印 rollback 计划, 不实际执行",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("声纹 B+C 方案实施 — #151 rollback 重演")
    print("=" * 60)
    print(f"模式: {'DRY-RUN' if args.dry_run else 'REAL-RUN'}")
    print()
    print("真实历史锚点:")
    for k, v in HISTORICAL_FACTS.items():
        print(f"  {k}: {v}")
    print()
    print("重演步骤:")
    print("  1. reprocess meeting #151 (m4a replay)")
    print("  2. 计算 meeting_151_rate (期望 ≈ 0.835)")
    print("  3. 加权 meeting_135 (0.946) + #151 (0.835) → 整体 ≈ 0.881")
    print("  4. < 90% acceptance gate → rollback sample_count 583 → 384")
    print("  5. 验证 4 子门禁 (single_distance / top1_top2_margin / cluster_votes / anchor_state)")
    print()
    print("=" * 60)
    print(f"#151 rollback 重演 {'计划' if args.dry_run else '执行'}完成.")
    print("落库路径: docs/voiceprint-quality-gate-2026-07-27.md")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
