#!/usr/bin/env python3
"""持续污染净化 CLI 工具

v2026-06-27 用户决策：
- 用户会逐步告知每场会议的真实参会人
- 本工具根据真实参会人净化会议的 speaker_mapping

用法:
  python scripts/purify_voiceprints.py \\
      --meeting 153 \\
      --real-participants "王天志,张宏魁,杜同贺" \\
      [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.meeting import Meeting, MeetingParticipant


def parse_batch(text: str) -> List[Tuple[int, List[str]]]:
    """解析批量输入: '153: name1,name2,name3' 格式"""
    result = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            print(f"WARN: 跳过无效行 '{line}'（格式：<meeting_id>: <names>）")
            continue
        mid_str, names_str = line.split(":", 1)
        try:
            mid = int(mid_str.strip())
        except ValueError:
            print(f"WARN: 跳过无效 meeting_id '{mid_str}'")
            continue
        names = [n.strip() for n in names_str.split(",") if n.strip()]
        result.append((mid, names))
    return result


async def purify_one_meeting(
    session_factory, meeting_id: int, real_names: List[str], dry_run: bool
) -> dict:
    """净化一场会议: 用真实参会人覆盖 speaker_mapping"""
    async with session_factory() as db:
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = result.scalar_one_or_none()
        if not meeting:
            return {"meeting_id": meeting_id, "error": "会议不存在"}

        # 查真实参会人的 member_id
        real_member_ids = set()
        real_name_to_id = {}
        for name in real_names:
            r = await db.execute(select(Member).where(Member.name == name))
            m = r.scalar_one_or_none()
            if m:
                real_member_ids.add(m.id)
                real_name_to_id[name] = m.id

        # 解析当前 speaker_mapping
        current_mapping = dict(meeting.speaker_mapping or {})
        old_mapping = dict(current_mapping)

        # 找出"被清除的"成员
        cleared_member_names = set()
        for label, name in current_mapping.items():
            if name and not name.startswith("发言人") and name not in real_names:
                cleared_member_names.add(name)

        # 统计每个 cluster 的段数
        from collections import Counter
        seg_count_by_label = Counter()
        if meeting.transcript:
            for e in meeting.transcript:
                if isinstance(e, dict):
                    seg_count_by_label[e.get("speaker", "?")] += 1

        # 按 seg_count 排序 cluster labels
        sorted_labels = sorted(
            [l for l in current_mapping.keys()],
            key=lambda l: seg_count_by_label.get(l, 0),
            reverse=True,
        )

        # 重新映射：top-N cluster 分配给真实人
        new_mapping = {}
        real_names_iter = iter(real_names)
        for label in sorted_labels:
            if seg_count_by_label.get(label, 0) == 0:
                continue
            try:
                real_name = next(real_names_iter)
                new_mapping[label] = real_name
            except StopIteration:
                idx = len([k for k in new_mapping.keys() if k.startswith("speaker_")])
                new_mapping[label] = f"发言人{chr(65+idx) if idx < 26 else idx-25}"

        # 未分配完的真实人 → 加到 unknown cluster
        for remaining_name in real_names_iter:
            new_mapping[f"unknown_{remaining_name}"] = remaining_name

        # 改写 transcript/transcript_polished 的 speaker 字段
        # v2026-06-27 修复：用 cluster_id（int）索引 label_to_newname
        # transcript_segments 的 seg.cluster_id 是 int（如 0,1,2），但 old_mapping 的 key 是 "cluster_0" 字符串
        label_to_newname = {}
        for label in old_mapping.keys():
            label_to_newname[label] = new_mapping.get(label, old_mapping[label])

        new_transcript = []
        for seg in (meeting.transcript or []):
            if not isinstance(seg, dict):
                new_transcript.append(seg)
                continue
            old_speaker = seg.get("speaker", "")
            # 用 cluster_id 拼成 'cluster_N' 找 label_to_newname
            cluster_id = seg.get("cluster_id")
            lookup_key = f"cluster_{cluster_id}" if cluster_id is not None and cluster_id >= 0 else None
            new_name = label_to_newname.get(lookup_key, old_speaker) if lookup_key else old_speaker
            new_seg = dict(seg)
            new_seg["speaker"] = new_name
            new_transcript.append(new_seg)

        new_polished = []
        for seg in (meeting.transcript_polished or []):
            if not isinstance(seg, dict):
                new_polished.append(seg)
                continue
            old_speaker = seg.get("speaker", "")
            cluster_id = seg.get("cluster_id")
            lookup_key = f"cluster_{cluster_id}" if cluster_id is not None and cluster_id >= 0 else None
            new_name = label_to_newname.get(lookup_key, old_speaker) if lookup_key else old_speaker
            new_seg = dict(seg)
            new_seg["speaker"] = new_name
            new_polished.append(new_seg)

        # 更新 meeting_participants
        await db.execute(
            delete(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id)
        )
        new_participants = []
        for name in real_names:
            if name in real_name_to_id:
                mp = MeetingParticipant(
                    meeting_id=meeting_id,
                    member_id=real_name_to_id[name],
                    role="speaker",
                )
                db.add(mp)
                new_participants.append(name)

        report = {
            "meeting_id": meeting_id,
            "real_names": real_names,
            "old_mapping": old_mapping,
            "new_mapping": new_mapping,
            "cleared_member_names": sorted(cleared_member_names),
            "new_participants": new_participants,
        }

        if not dry_run:
            meeting.speaker_mapping = new_mapping
            meeting.transcript = new_transcript
            meeting.transcript_polished = new_polished
            meeting.updated_at = datetime.utcnow()
            await db.commit()

        return report


async def amain():
    parser = argparse.ArgumentParser(
        description="持续污染净化 CLI：根据用户提供的真实参会人净化会议 speaker_mapping"
    )
    parser.add_argument("--meeting", type=int, help="会议 ID")
    parser.add_argument(
        "--real-participants",
        type=str,
        help='真实参会人列表，逗号分隔，如 "王天志,张宏魁,杜同贺"',
    )
    parser.add_argument("--dry-run", action="store_true", help="只输出报告，不修改 DB")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="从 stdin 读取批量输入",
    )
    args = parser.parse_args()

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    if args.batch:
        print("批量模式（stdin 输入，每行：<meeting_id>: <names>）")
        stdin_text = sys.stdin.read()
        items = parse_batch(stdin_text)
        for mid, names in items:
            report = await purify_one_meeting(session_factory, mid, names, args.dry_run)
            print_report(report, args.dry_run)
    elif args.meeting and args.real_participants:
        names = [n.strip() for n in args.real_participants.split(",") if n.strip()]
        report = await purify_one_meeting(session_factory, args.meeting, names, args.dry_run)
        print_report(report, args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)

    await engine.dispose()


def print_report(report: dict, dry_run: bool):
    if "error" in report:
        print(f"\n❌ 会议 {report['meeting_id']}: {report['error']}")
        return
    print(f"\n{'='*60}")
    print(f"会议 {report['meeting_id']} {'[DRY-RUN] ' if dry_run else ''}净化报告")
    print(f"{'='*60}")
    print(f"真实参会人: {', '.join(report['real_names'])}")
    print(f"被清除的旧成员: {', '.join(report['cleared_member_names']) if report['cleared_member_names'] else '(无)'}")
    print(f"\n旧 speaker_mapping → 新 speaker_mapping:")
    for label in report['old_mapping']:
        old_name = report['old_mapping'][label]
        new_name = report['new_mapping'].get(label, '?')
        marker = "✓" if old_name == new_name else "→"
        if old_name != new_name:
            print(f"  {label}: {old_name} {marker} {new_name}")
    print(f"\n新 meeting_participants: {len(report['new_participants'])} 行")
    if dry_run:
        print(f"\n[DRY-RUN] 未修改 DB（去掉 --dry-run 实际执行）")
    else:
        print(f"\n✅ 已写入 DB")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(amain())