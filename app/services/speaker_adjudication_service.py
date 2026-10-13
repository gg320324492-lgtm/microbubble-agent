"""说话人人工裁决的读写与匹配。

## 用途

会议 256 的实测结论: 570-623 / 729-871 / 872-910 三段经主指挥逐段听辨确认
**不是赵航佳**, 但它们距赵航佳质心仅 0.07-0.33 (阈值 0.65), 算法改不动 ——
按 0.8 融合旧质心重算后**照样认领 52/53 段**。

于是把人工裁决固化到 ``meeting_speaker_adjudications``, 重跑说话人识别时
**直接采用裁决结果, 不再过声纹匹配**, 避免「裁决 → 重跑 → 判回」的循环。

## 匹配口径

段**中点**落在某条裁决的 [seg_start, seg_end] 内即命中。理由见模型 docstring:
对转录重建导致的边界漂移免疫; 不依赖会整体错位的下标; 一条段只归属一条裁决。

裁决区间按 seg_start 排序 + ``bisect`` 定位, 会议 3198 段 × N 条裁决下仍是 O(log N) 定位。
"""
from __future__ import annotations

import bisect
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication


async def get_adjudications(
    db: AsyncSession, meeting_id: int
) -> List[MeetingSpeakerAdjudication]:
    """取一场会议的全部裁决, 按 seg_start 升序 (供 bisect 用)。"""
    result = await db.execute(
        select(MeetingSpeakerAdjudication)
        .where(MeetingSpeakerAdjudication.meeting_id == meeting_id)
        .order_by(MeetingSpeakerAdjudication.seg_start)
    )
    return list(result.scalars().all())


class AdjudicationResolver:
    """把裁决列表编成「段 [start,end] → 说话人」的可调用查询器。

    None = 无裁决, 调用方应走正常的声纹识别。
    """

    def __init__(self, adjudications: Sequence[MeetingSpeakerAdjudication]):
        self._rows = sorted(adjudications, key=lambda r: float(r.seg_start))
        self._starts = [float(r.seg_start) for r in self._rows]

    def __len__(self) -> int:
        return len(self._rows)

    def _find(self, start: Optional[float], end: Optional[float]):
        """按段中点定位命中的裁决行, 未命中返回 None。"""
        if start is None or end is None or not self._rows:
            return None
        mid = (float(start) + float(end)) / 2.0
        i = bisect.bisect_right(self._starts, mid) - 1
        # 区间可能重叠, 所以要向前扫而不是只看 i 那一行。
        # 单场裁决数是人工维护的小量 (实测 51 条), 最坏 O(n) 可接受。
        while i >= 0:
            row = self._rows[i]
            if float(row.seg_start) <= mid <= float(row.seg_end):
                return row
            i -= 1
        return None

    def lookup(self, start: Optional[float], end: Optional[float]) -> Optional[str]:
        """段中点命中某条裁决则返回其 speaker, 否则 None。"""
        row = self._find(start, end)
        return row.speaker if row is not None else None

    def match_index(self, start: Optional[float], end: Optional[float]):
        """返回命中的裁决行 (调试/审计用), 未命中返回 None。"""
        return self._find(start, end)


async def build_resolver(db: AsyncSession, meeting_id: int) -> AdjudicationResolver:
    return AdjudicationResolver(await get_adjudications(db, meeting_id))


async def record_adjudication(
    db: AsyncSession,
    meeting_id: int,
    seg_start: float,
    seg_end: float,
    speaker: str,
    source: Optional[str] = None,
    note: Optional[str] = None,
    seg_index: Optional[int] = None,
    commit: bool = True,
) -> MeetingSpeakerAdjudication:
    """登记一条人工裁决。同区间重复登记会被拒绝 (由调用方先查重)。"""
    row = MeetingSpeakerAdjudication(
        meeting_id=meeting_id,
        seg_start=float(seg_start),
        seg_end=float(seg_end),
        seg_index=seg_index,
        speaker=speaker.strip(),
        source=source,
        note=note,
    )
    db.add(row)
    if commit:
        await db.commit()
        await db.refresh(row)
    return row


async def apply_to_transcript(
    db: AsyncSession,
    meeting_id: int,
    transcript: Sequence[dict],
    extra_fields: Sequence[str] = ("transcript_polished",),
) -> Dict[str, int]:
    """把裁决就地写回转录的 ``speaker`` 字段。

    只改 ``speaker``，**保留 start/end/speaker_label** 等其余字段
    (CLAUDE.md H.9: 重建转录的写法会丢字段, 这里刻意不走那条路)。
    返回 {speaker: 改动段数} 统计。
    """
    from app.models.meeting import Meeting

    resolver = await build_resolver(db, meeting_id)
    meeting = (
        await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    ).scalar_one()

    stats: Dict[str, int] = {}

    def patch(entries):
        changed = {}
        if not isinstance(entries, list):
            return changed
        for i, seg in enumerate(entries):
            if not isinstance(seg, dict):
                continue
            want = resolver.lookup(seg.get("start"), seg.get("end"))
            if want and seg.get("speaker") != want:
                changed[i] = want
        return changed

    all_lists = [("transcript", meeting.transcript)] + [
        (name, getattr(meeting, name, None)) for name in extra_fields
    ]
    for _, entries in all_lists:
        changed = patch(entries)
        for i, want in changed.items():
            entries[i]["speaker"] = want
            stats[want] = stats.get(want, 0) + 1
    return stats


__all__ = [
    "AdjudicationResolver",
    "apply_to_transcript",
    "build_resolver",
    "get_adjudications",
    "record_adjudication",
]
