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
    """取一场会议的全部裁决, 按 seg_start 升序 (供 bisect 用)。

    tiebreaker ``id ASC``: 同 seg_start 的行 (如新旧两版裁决区间完全相同)
    **旧行在前、新行在后** —— resolver 的命中扫描**从列表尾往前**走,
    同起点时后到的 (id 大的) 新裁决先被命中, 胜负不再取决于数据库返回顺序。
    (2026-10-31 m259 实测: 区间不完全相等的重叠靠 seg_start 排序尚可,
    完全相等时是掷硬币。)
    """
    result = await db.execute(
        select(MeetingSpeakerAdjudication)
        .where(MeetingSpeakerAdjudication.meeting_id == meeting_id)
        .order_by(MeetingSpeakerAdjudication.seg_start,
                  MeetingSpeakerAdjudication.id.asc())
    )
    return list(result.scalars().all())


class AdjudicationResolver:
    """把裁决列表编成「段 [start,end] → 说话人」的可调用查询器。

    None = 无裁决, 调用方应走正常的声纹识别。
    """

    def __init__(self, adjudications: Sequence[MeetingSpeakerAdjudication]):
        # (seg_start, id): 同起点时**旧行在前、新行在后** ⇒ 命中扫描从列表尾
        # 往前走, 同起点时先命中新裁决 (id 大)。id 可能为 None (测试手工构造) ⇒ 按 0。
        self._rows = sorted(
            adjudications,
            key=lambda r: (float(r.seg_start), (r.id or 0)))
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


def collect_range_changes(entries, lookup) -> Dict[int, str]:
    """段自带 start/end ⇒ 按「中点落区间」收集要改的 {index: speaker}。"""
    changed: Dict[int, str] = {}
    if not isinstance(entries, list):
        return changed
    for i, seg in enumerate(entries):
        if not isinstance(seg, dict):
            continue
        want = lookup(seg.get("start"), seg.get("end"))
        if want and seg.get("speaker") != want:
            changed[i] = want
    return changed


def collect_index_changes(entries, base, lookup) -> Dict[int, str]:
    """polished 等无 start/end 的平行数组 ⇒ 与主转录**按索引对齐**收集变更。

    对齐判据: 文本一致; 文本被润色改写时用 ``ts`` 落回主转录段区间校验。
    长度不一致 (润色重切了段) ⇒ 结构不同步, 全部跳过不硬写。
    """
    changed: Dict[int, str] = {}
    if not isinstance(entries, list) or not isinstance(base, list):
        return changed
    if len(entries) != len(base):
        return changed
    for i, seg in enumerate(entries):
        if not isinstance(seg, dict) or not isinstance(base[i], dict):
            continue
        ref = base[i]
        aligned = ((seg.get("text") or "").strip()
                   == (ref.get("text") or "").strip())
        if (not aligned and seg.get("ts") is not None
                and isinstance(ref.get("start"), (int, float))):
            ts = float(seg["ts"])
            aligned = float(ref["start"]) <= ts <= float(ref.get("end") or 0)
        if not aligned:
            continue
        want = lookup(ref.get("start"), ref.get("end"))
        if want and seg.get("speaker") != want:
            changed[i] = want
    return changed


async def apply_to_transcript(
    db: AsyncSession,
    meeting_id: int,
    transcript: Sequence[dict],
    extra_fields: Sequence[str] = ("transcript_polished",),
) -> Dict[str, int]:
    """把裁决写回转录的 ``speaker`` 字段并**确保持久化**。

    只改 ``speaker``，**保留 start/end/speaker_label** 等其余字段
    (CLAUDE.md H.9: 重建转录的写法会丢字段, 这里刻意不走那条路)。
    返回 {speaker: 改动段数} 统计（transcript 与各 extra_fields 合计）。
    ⚠️ 参数 ``transcript`` 仅为兼容保留, 实际以 meeting 自身字段为准。

    2026-11-04 修复的两个静默失效 (会议 265 实战踩中, 类 20.220):
    ① **就地改 dict ⇒ SQLAlchemy 检测不到变更** —— 变更检测对 committed 基线做
       相等比较, 而 committed 存的是**同一个对象的引用**, 就地突变把基线也污染了;
       事后整体重新赋值也无效 (新值 == 被污染的基线) ⇒ UPDATE 被**静默跳过**,
       界面永远看不到改动。修法: patch 后 :func:`flag_modified` 强制把属性标脏。
    ② **polished 段没有 start/end** (是 ``{ts,text,speaker}``) ⇒ resolver 的
       「中点落区间」永远匹配不上 ⇒ transcript_polished 从未被同步过。
       修法: 与主转录按索引对齐 (:func:`collect_index_changes`)。
    """
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.meeting import Meeting

    resolver = await build_resolver(db, meeting_id)
    meeting = (
        await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    ).scalar_one()

    stats: Dict[str, int] = {}
    main_entries = meeting.transcript

    def apply_field(name: str, entries, use_index: bool) -> None:
        if use_index:
            changed = collect_index_changes(entries, main_entries, resolver.lookup)
        else:
            changed = collect_range_changes(entries, resolver.lookup)
        if not changed:
            return
        for i, want in changed.items():
            entries[i]["speaker"] = want
            stats[want] = stats.get(want, 0) + 1
        # ⭐ 就地突变必须强制标脏, 否则 commit 会静默跳过 (见 docstring ①)
        flag_modified(meeting, name)

    apply_field("transcript", main_entries, use_index=False)
    for name in extra_fields:
        entries = getattr(meeting, name, None)
        if not isinstance(entries, list):
            continue
        has_range = bool(entries) and isinstance(entries[0], dict) \
            and entries[0].get("start") is not None
        apply_field(name, entries, use_index=not has_range)
    return stats


__all__ = [
    "AdjudicationResolver",
    "apply_to_transcript",
    "build_resolver",
    "get_adjudications",
    "record_adjudication",
]
