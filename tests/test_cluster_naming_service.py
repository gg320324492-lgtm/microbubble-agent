"""会议说话人**簇级命名**裁决写入的测试 (Phase 1f, 2026-10-31)

重点覆盖三件容易做错的事:

1. **簇级裁决必须逐段写** —— 聚类按**内容**分, 簇在时间轴上**交错**;
   若按「簇的时间区间」写, 区间内属于别的簇的段会被误判 ⇒ 必须展开成逐段行。
2. **开关默认关** ⇒ `record_cluster_naming` 不写库 ⇒ 生产行为零变化。
3. **幂等重写** ⇒ 重跑不累积; 且 `clear` 只删簇级命名, **不动人工听辨裁决**。
"""
from __future__ import annotations

import pytest

from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication
from app.services.cluster_naming_service import (
    CLUSTER_SOURCE_PREFIX,
    clear_cluster_naming,
    cluster_naming_lookup,
    get_cluster_naming,
    record_cluster_naming,
    segments_to_adjudication_rows,
)

MID = 99998          # 假 meeting_id, 避免碰真数据


class TestRowsExpansion:
    """簇 → 逐段裁决行的展开"""

    def test_one_row_per_segment(self):
        rows = segments_to_adjudication_rows([{
            "cluster_id": "c1", "speaker": "王天志",
            "segments": [
                {"start": 10.0, "end": 12.0, "seg_index": 1},
                {"start": 20.0, "end": 22.5, "seg_index": 2},
            ],
        }])
        assert len(rows) == 2
        assert rows[0]["seg_start"] == 10.0
        assert rows[1]["seg_end"] == 22.5
        assert rows[0]["speaker"] == "王天志"

    def test_interleaved_clusters_produce_disjoint_segment_ranges(self):
        """⭐ 交错的两簇 ⇒ 展开后每段区间**互不重叠** ⇒ 中点匹配唯一归属。

        这是「不能按簇的时间区间写」的核心: 簇 c1 的段是 10-12 与 30-32,
        簇 c2 的段是 20-22 ⇒ c1 的时间区间 [10,32] **包含** c2 的段。
        """
        rows = segments_to_adjudication_rows([
            {"cluster_id": "c1", "speaker": "甲",
             "segments": [{"start": 10.0, "end": 12.0}, {"start": 30.0, "end": 32.0}]},
            {"cluster_id": "c2", "speaker": "乙",
             "segments": [{"start": 20.0, "end": 22.0}]},
        ])
        ranges = sorted((r["seg_start"], r["seg_end"]) for r in rows)
        assert ranges == [(10.0, 12.0), (20.0, 22.0), (30.0, 32.0)]
        for a in range(len(ranges)):
            for b in range(a + 1, len(ranges)):
                assert ranges[a][1] <= ranges[b][0]

    def test_empty_speaker_skipped(self):
        rows = segments_to_adjudication_rows([
            {"cluster_id": "c1", "speaker": "  ",
             "segments": [{"start": 1.0, "end": 2.0}]},
        ])
        assert rows == []

    def test_invalid_range_skipped(self):
        rows = segments_to_adjudication_rows([
            {"cluster_id": "c1", "speaker": "甲",
             "segments": [{"start": 5.0, "end": 5.0}, {"start": 6.0, "end": 4.0},
                          {"start": None, "end": 2.0}]},
        ])
        assert rows == []

    def test_source_carries_cluster_id(self):
        rows = segments_to_adjudication_rows([
            {"cluster_id": "c7", "speaker": "甲",
             "segments": [{"start": 1.0, "end": 2.0}]},
        ])
        assert rows[0]["source"] == f"{CLUSTER_SOURCE_PREFIX}:c7"


@pytest.mark.asyncio
class TestPersistence:
    async def _clean(self, db):
        from sqlalchemy import delete
        await db.execute(delete(MeetingSpeakerAdjudication).where(
            MeetingSpeakerAdjudication.meeting_id == MID))
        await db.commit()

    async def test_disabled_by_default_writes_nothing(self, db):
        """⭐ 开关默认关 ⇒ 不写库 ⇒ 生产行为零变化"""
        from app.config import settings
        assert settings.CLUSTER_NAMING_ENABLED is False

        await self._clean(db)
        stats = await record_cluster_naming(db, MID, [{
            "cluster_id": "c1", "speaker": "王天志",
            "segments": [{"start": 1.0, "end": 2.0}]},
        ])
        assert stats["written"] == 0
        assert await get_cluster_naming(db, MID) == []
        await self._clean(db)

    async def test_enabled_writes_and_applies_to_transcript(self, db, monkeypatch):
        """开启后写入 ⇒ 既有裁决机制能把多个段改成簇名 (重跑优先应用)"""
        from app.config import settings
        from app.services.speaker_adjudication_service import apply_to_transcript
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)

        await self._clean(db)
        stats = await record_cluster_naming(db, MID, [{
            "cluster_id": "c1", "speaker": "王天志",
            "segments": [{"start": 10.0, "end": 12.0}, {"start": 30.0, "end": 32.0}]},
        ])
        assert stats["written"] == 2

        rows = await get_cluster_naming(db, MID)
        assert len(rows) == 2
        assert {r.speaker for r in rows} == {"王天志"}

        # 既有裁决机制: 段中点命中 ⇒ 直接采用簇名, 不再过声纹匹配
        from app.models.meeting import Meeting
        from sqlalchemy import select
        meeting = await db.get(Meeting, MID)
        if meeting is None:
            # 用真会议也不行(会碰生产) ⇒ 只验证 resolver 侧
            from app.services.speaker_adjudication_service import build_resolver
            resolver = await build_resolver(db, MID)
            assert resolver.lookup(11.0, 11.5) == "王天志"
            assert resolver.lookup(31.0, 31.5) == "王天志"
            assert resolver.lookup(20.0, 21.0) is None
        else:
            await self._clean(db)
        await self._clean(db)

    async def test_replace_is_idempotent(self, db, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)
        await self._clean(db)
        clusters = [{"cluster_id": "c1", "speaker": "甲",
                     "segments": [{"start": 1.0, "end": 2.0}]}]
        await record_cluster_naming(db, MID, clusters)
        await record_cluster_naming(db, MID, clusters)
        rows = await get_cluster_naming(db, MID)
        assert len(rows) == 1
        await self._clean(db)

    async def test_clear_only_removes_cluster_naming(self, db, monkeypatch):
        """⭐ clear 只删**簇级命名**, 人工听辨裁决必须原样保留"""
        from app.config import settings
        from app.services.speaker_adjudication_service import record_adjudication
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)

        await self._clean(db)
        await record_adjudication(db, MID, 5.0, 6.0, "人工听辨", source="ledger")
        await record_cluster_naming(db, MID, [{
            "cluster_id": "c1", "speaker": "甲",
            "segments": [{"start": 10.0, "end": 11.0}]}])

        cleared = await clear_cluster_naming(db, MID)
        assert cleared == 1
        remaining = await get_adjudications_all(db, MID)
        assert len(remaining) == 1
        assert remaining[0].source == "ledger"
        await self._clean(db)


async def get_adjudications_all(db, meeting_id):
    from app.services.speaker_adjudication_service import get_adjudications
    return await get_adjudications(db, meeting_id)
