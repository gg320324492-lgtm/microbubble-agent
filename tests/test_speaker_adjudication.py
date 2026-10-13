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
