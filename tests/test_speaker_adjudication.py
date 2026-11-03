"""说话人人工裁决 (迁移 146) 的测试

重点覆盖**段中点匹配口径** —— 这是整个机制的正确性所在:
转录重建后段边界会微漂, 匹配必须免疫; 下标会整体错位, 不能用。

纯逻辑测试不需要 DB; 落库往返用 conftest 的 ``db`` fixture。
"""
from __future__ import annotations

import pytest

from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication
from app.services.speaker_adjudication_service import (
    AdjudicationResolver,
    collect_index_changes,
    collect_range_changes,
    get_adjudications,
    record_adjudication,
)


def _adj(start: float, end: float, speaker: str) -> MeetingSpeakerAdjudication:
    return MeetingSpeakerAdjudication(
        id=None, meeting_id=256, seg_start=start, seg_end=end, speaker=speaker,
    )


class TestResolverMidpoint:
    """中点匹配: 段完全落在裁决区间内 → 命中"""

    def test_segment_inside_range(self):
        r = AdjudicationResolver([_adj(570.0, 623.0, "王天志")])
        assert r.lookup(580.0, 590.0) == "王天志"

    def test_segment_outside_range(self):
        r = AdjudicationResolver([_adj(570.0, 623.0, "王天志")])
        assert r.lookup(630.0, 640.0) is None

    def test_boundary_midpoint_exactly_on_edges(self):
        r = AdjudicationResolver([_adj(570.0, 623.0, "王天志")])
        # 中点 570.0 → 段 [569, 571]
        assert r.lookup(569.0, 571.0) == "王天志"
        # 中点 623.0 → 段 [622, 624]
        assert r.lookup(622.0, 624.0) == "王天志"
        # 中点刚越过右端 → 不命中
        assert r.lookup(623.5, 624.5) is None

    def test_boundary_drift_tolerance(self):
        """转录重建后边界微漂 (±0.3s) 仍应命中 —— 这是选用中点而非精确相等的原因"""
        r = AdjudicationResolver([_adj(570.0, 623.0, "王天志")])
        assert r.lookup(569.7, 590.2) == "王天志"
        assert r.lookup(580.0, 623.3) == "王天志"

    def test_partially_overlapping_segment_missed(self):
        """只重叠一半、但中点在区间外 → 不命中 (中点唯一归属)"""
        r = AdjudicationResolver([_adj(570.0, 623.0, "王天志")])
        # 段 [560, 600]: 与区间重叠, 但中点 580 落在区间内 → 命中
        assert r.lookup(560.0, 600.0) == "王天志"
        # 段 [620, 700]: 重叠但中点 660 在区间外 → 不命中
        assert r.lookup(620.0, 700.0) is None


class TestResolverEdgeCases:
    def test_empty_resolver(self):
        r = AdjudicationResolver([])
        assert len(r) == 0
        assert r.lookup(570.0, 623.0) is None

    def test_none_start_end_is_safe(self):
        r = AdjudicationResolver([_adj(570.0, 623.0, "王天志")])
        assert r.lookup(None, None) is None
        assert r.lookup(580.0, None) is None

    def test_multiple_ranges_pick_correct_one(self):
        """会议 256 的真实形态: 三个不相邻区间"""
        r = AdjudicationResolver([
            _adj(570.00, 623.00, "王天志"),
            _adj(729.00, 871.00, "王天志"),
            _adj(872.00, 910.00, "王天志"),
        ])
        assert r.lookup(580.0, 590.0) == "王天志"
        assert r.lookup(800.0, 810.0) == "王天志"
        assert r.lookup(880.0, 890.0) == "王天志"
        # 区间之间的空隙不命中
        assert r.lookup(650.0, 700.0) is None
        assert r.lookup(911.0, 920.0) is None

    def test_overlapping_ranges_returns_latest_start(self):
        """区间重叠时取 seg_start 最大的那条 (更具体的那条优先)"""
        r = AdjudicationResolver([
            _adj(570.0, 700.0, "王天志"),
            _adj(600.0, 650.0, "张宏魁"),
        ])
        assert r.lookup(610.0, 620.0) == "张宏魁"
        assert r.lookup(580.0, 590.0) == "王天志"

    def test_placeholder_speaker_is_valid(self):
        """「发言人?」是合法裁决值 —— 算法超阈值时人工确认就是无人认领"""
        r = AdjudicationResolver([_adj(803.11, 806.01, "发言人?")])
        assert r.lookup(804.0, 805.0) == "发言人?"

    def test_unsorted_input_is_normalized(self):
        r = AdjudicationResolver([
            _adj(872.0, 910.0, "c"),
            _adj(570.0, 623.0, "a"),
            _adj(729.0, 871.0, "b"),
        ])
        assert [r.lookup(*p) for p in ((580, 590), (800, 810), (880, 890))] == ["a", "b", "c"]

    def test_match_index_returns_row(self):
        row = _adj(570.0, 623.0, "王天志")
        r = AdjudicationResolver([row])
        assert r.match_index(580.0, 590.0) is row
        assert r.match_index(900.0, 910.0) is None

    def test_same_interval_newest_id_wins(self):
        """同 seg_start 的两行 (新旧两版裁决区间完全相同) ⇒ **新裁决 (id 大) 胜**。

        2026-10-31 m259 实测的坑: 区间相等时胜负取决于数据库返回顺序。
        机制: 排序键 (seg_start, id) 把新行排在同起点组的**后面**,
        而命中扫描从列表尾往前 ⇒ 先命中新行。
        """
        old_row = _adj(600.0, 650.0, "王天志")
        old_row.id = 1
        new_row = _adj(600.0, 650.0, "肖佐林")
        new_row.id = 2
        r = AdjudicationResolver([old_row, new_row])
        assert r.lookup(610.0, 620.0) == "肖佐林"
        # 反向传入也一样 (排序在 resolver 内做, 与输入顺序无关)
        r2 = AdjudicationResolver([new_row, old_row])
        assert r2.lookup(610.0, 620.0) == "肖佐林"

    def test_narrow_row_inside_wide_row_still_prefers_narrow(self):
        """窄行在宽行内部时仍取窄行 (seg_start 更大优先于 id tiebreaker)"""
        wide = _adj(570.0, 700.0, "王天志")
        wide.id = 99          # id 更大也不该赢 —— seg_start 才是第一排序键
        narrow = _adj(600.0, 650.0, "张宏魁")
        narrow.id = 2
        r = AdjudicationResolver([wide, narrow])
        assert r.lookup(610.0, 620.0) == "张宏魁"
        assert r.lookup(580.0, 590.0) == "王天志"


@pytest.mark.asyncio
class TestPersistence:
    async def test_record_and_read_back(self, db):
        from sqlalchemy import delete, select

        await db.execute(delete(MeetingSpeakerAdjudication).where(
            MeetingSpeakerAdjudication.meeting_id == 99999))
        await db.commit()

        await record_adjudication(
            db, meeting_id=99999, seg_start=1.0, seg_end=2.0,
            speaker="王天志", source="unit-test", note="note", seg_index=7,
        )
        rows = await get_adjudications(db, 99999)
        assert len(rows) == 1
        assert rows[0].speaker == "王天志"
        assert rows[0].seg_index == 7
        assert rows[0].source == "unit-test"

        await db.execute(delete(MeetingSpeakerAdjudication).where(
            MeetingSpeakerAdjudication.meeting_id == 99999))
        await db.commit()

    async def test_resolver_over_db_rows(self, db):
        from sqlalchemy import delete

        await db.execute(delete(MeetingSpeakerAdjudication).where(
            MeetingSpeakerAdjudication.meeting_id == 99998))
        await db.commit()
        for s, e in ((10.0, 20.0), (30.0, 40.0)):
            await record_adjudication(db, meeting_id=99998, seg_start=s, seg_end=e,
                                      speaker="蒋芦笛")
        rows = await get_adjudications(db, 99998)
        r = AdjudicationResolver(rows)
        assert len(r) == 2
        assert r.lookup(15.0, 16.0) == "蒋芦笛"
        assert r.lookup(25.0, 26.0) is None

        await db.execute(delete(MeetingSpeakerAdjudication).where(
            MeetingSpeakerAdjudication.meeting_id == 99998))
        await db.commit()


class TestCollectChanges:
    """apply_to_transcript 的两个纯收集器 (2026-11-04 会议 265 静默失效修复)

    背景: 会议 265 实战踩中两个坑 ——
    ① 就地改 dict ⇒ SQLAlchemy 变更检测按值比较 committed 基线（同一对象引用，
       已被突变污染）⇒ UPDATE 被静默跳过（flag_modified 修）；
    ② polished 段只有 {ts,text,speaker}、没有 start/end ⇒ 按区间匹配永远落空，
       transcript_polished 从未被同步（collect_index_changes 修）。
    """

    @staticmethod
    def _lookup(start, end):
        # 模拟 resolver 的中点匹配口径: 段中点落在 [100, 110] 内 → 命中
        if start is None or end is None:
            return None
        mid = (float(start) + float(end)) / 2
        return "陈金薪" if 100.0 <= mid <= 110.0 else None

    # ---- 区间模式（主转录，段自带 start/end） ----

    def test_range_collects_midpoint_hit(self):
        entries = [{"start": 100.0, "end": 110.0, "speaker": "发言人B", "text": "a"}]
        assert collect_range_changes(entries, self._lookup) == {0: "陈金薪"}

    def test_range_skips_same_speaker_and_misses(self):
        entries = [
            {"start": 100.0, "end": 110.0, "speaker": "陈金薪"},  # 已是目标
            {"start": 200.0, "end": 210.0, "speaker": "王天志"},  # 区间外
        ]
        assert collect_range_changes(entries, self._lookup) == {}

    def test_range_tolerates_boundary_drift(self):
        """与 resolver 同口径: 边界 ±0.3s 漂移仍命中（中点在区间内即可）"""
        entries = [{"start": 99.7, "end": 110.2, "speaker": "发言人B"}]
        assert collect_range_changes(entries, self._lookup) == {0: "陈金薪"}

    # ---- 索引模式（polished，只有 ts） ----

    def test_index_aligns_by_text(self):
        base = [{"start": 100.0, "end": 110.0, "speaker": "发言人B", "text": "你好"}]
        entries = [{"ts": 105.0, "speaker": "发言人B", "text": "你好"}]
        assert collect_index_changes(entries, base, self._lookup) == {0: "陈金薪"}

    def test_index_falls_back_to_ts_when_text_rewritten(self):
        """润色改写了文本 ⇒ 文本对不上，用 ts 落回主转录段区间判对齐"""
        base = [{"start": 100.0, "end": 110.0, "speaker": "发言人B", "text": "原文"}]
        entries = [{"ts": 105.0, "speaker": "发言人B", "text": "润色后的文字"}]
        assert collect_index_changes(entries, base, self._lookup) == {0: "陈金薪"}

    def test_index_skips_misaligned_segment(self):
        """文本不一致且 ts 落不进对应区间 ⇒ 不硬写（宁缺勿错）"""
        base = [{"start": 100.0, "end": 110.0, "speaker": "发言人B", "text": "原文"}]
        entries = [{"ts": 999.0, "speaker": "发言人B", "text": "完全不同的话"}]
        assert collect_index_changes(entries, base, self._lookup) == {}

    def test_index_length_mismatch_is_noop(self):
        """润色重切了段 ⇒ 结构不同步，整字段跳过"""
        base = [{"start": 100.0, "end": 110.0, "speaker": "发言人B", "text": "原文"}]
        entries = [{"ts": 105.0, "speaker": "发言人B", "text": "原文"},
                   {"ts": 106.0, "speaker": "发言人B", "text": "原文二"}]
        assert collect_index_changes(entries, base, self._lookup) == {}

    def test_index_skips_already_target(self):
        base = [{"start": 100.0, "end": 110.0, "speaker": "陈金薪", "text": "你好"}]
        entries = [{"ts": 105.0, "speaker": "陈金薪", "text": "你好"}]
        assert collect_index_changes(entries, base, self._lookup) == {}

    def test_index_handles_non_dict_entries(self):
        base = [{"start": 100.0, "end": 110.0, "speaker": "发言人B", "text": "你好"},
                None]
        entries = [{"ts": 105.0, "speaker": "发言人B", "text": "你好"}, "垃圾行"]
        assert collect_index_changes(entries, base, self._lookup) == {0: "陈金薪"}
