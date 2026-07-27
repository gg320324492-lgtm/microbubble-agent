"""
声纹 B+C 方案实施 — 12 会议音频 reprocess 自动化脚本

W73 A-2 调研实战: 12 会议音频作为跨会议回归样本池
W74 A-2 调研建议: 必含 #151 rollback 重演 + 12 会议音频

Usage:
    python scripts/voiceprint/reprocess_12_meetings.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Tuple

# 12 会议音频样本池 (与 voiceprint_cross_meeting_regression.REPROCESS_12_MEETINGS 同步)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="12 会议音频 reprocess 自动化")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印任务清单, 不实际 reprocess",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("声纹 B+C 方案实施 — 12 会议音频 reprocess")
    print("=" * 60)
    print(f"模式: {'DRY-RUN' if args.dry_run else 'REAL-RUN'}")
    print(f"会议数: {len(TWELVE_MEETINGS)}")
    print(f"包含 #151 rollback 重演: YES (W74 A-2 调研建议)")
    print()

    pass_count = 0
    for idx, (mid, title) in enumerate(TWELVE_MEETINGS, start=1):
        marker = "ROLLBACK" if mid == 151 else "REPROCESS"
        print(f"[{idx:2d}/12] meeting_id={mid:3d} title={title!r:50s} marker={marker}")
        # 实跑版会接入 voiceprint_service.reprocess_meeting, 此处 dry-run 占位.
        if args.dry_run:
            pass

    print()
    print("=" * 60)
    print(f"12 会议 reprocess 计划完成 (dry-run={args.dry_run}).")
    print("落库路径: docs/voiceprint-quality-gate-2026-07-27.md")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
