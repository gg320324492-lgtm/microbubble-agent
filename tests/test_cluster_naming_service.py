"""会议说话人**簇级命名**裁决的测试 (迁移 148, 2026-10-31)

重点覆盖四件容易做错的事:

1. **粒度=簇, 不与段级表混** —— 一次簇级决策写**一行**, 不展开成逐段;
   且段级表 (`meeting_speaker_adjudications`) 保持原样不被污染。
2. **簇的身份靠 member_spans** —— 簇号只在一次聚类运行内有意义,
   所以「簇 → 段」的映射必须存成区间集合, 应用时按段中点回查。
3. **冲突消解 = 段级优先** —— 段级是定点证据, 簇级是整簇推广 (类 20.244)。
4. **开关默认关** ⇒ `record_cluster_naming` 不写库 ⇒ 生产行为零变化。
"""
from __future__ import annotations

import pytest

from app.models.meeting_cluster_adjudication import (
    MeetingClusterAdjudication,
    member_fingerprint,
)
from app.services.cluster_naming_service import (
    CLUSTER_SOURCE_PREFIX,
    ClusterAdjudicationResolver,
    build_combined_resolver,
    clear_cluster_naming,
    cluster_naming_lookup,
    clusters_to_adjudication_rows,
    get_cluster_naming,
    record_cluster_naming,
)

MID = 99998          # 假 meeting_id, 避免碰真数据


class TestRowsExpansion:
    """簇 → 簇级裁决行的构造"""

    def test_one_row_per_cluster(self):
        rows = clusters_to_adjudication_rows([
            {"cluster_key": "c1", "cluster_id": 1, "speaker": "王天志",
             "segments": [{"start": 10.0, "end": 12.0},
                          {"start": 20.0, "end": 22.5}]},
            {"cluster_key": "c2", "cluster_id": 2, "speaker": "刘子煜",
             "segments": [{"start": 30.0, "end": 32.0}]},
        ])
        assert len(rows) == 2           # ⭐ 一行一簇, 不是一行一段
        assert rows[0]["n_members"] == 2
        assert rows[0]["member_spans"] == [[10.0, 12.0], [20.0, 22.5]]
        assert rows[1]["speaker"] == "刘子煜"

    def test_interleaved_clusters_keep_their_own_spans(self):
        """⭐ 交错的两簇 ⇒ 各自只记自己的区间, **不做区间合并**。

        c1 的段是 10-12 与 30-32, c2 的段是 20-22 ⇒ c1 的时间跨度 [10,32]
        **包含** c2 的段 ⇒ 若按「簇的时间区间」存就会误伤 c2 的段。
        """
        rows = clusters_to_adjudication_rows([
            {"cluster_key": "c1", "speaker": "甲",
             "segments": [{"start": 10.0, "end": 12.0}, {"start": 30.0, "end": 32.0}]},
            {"cluster_key": "c2", "speaker": "乙",
             "segments": [{"start": 20.0, "end": 22.0}]},
        ])
        spans = {r["cluster_key"]: r["member_spans"] for r in rows}
        assert spans["c1"] == [[10.0, 12.0], [30.0, 32.0]]
        assert spans["c2"] == [[20.0, 22.0]]

    def test_empty_speaker_or_key_skipped(self):
        rows = clusters_to_adjudication_rows([
            {"cluster_key": "c1", "speaker": "  ",
             "segments": [{"start": 1.0, "end": 2.0}]},
            {"cluster_key": "", "speaker": "甲",
             "segments": [{"start": 1.0, "end": 2.0}]},
        ])
        assert rows == []

    def test_invalid_ranges_dropped_and_empty_cluster_skipped(self):
        rows = clusters_to_adjudication_rows([
            {"cluster_key": "c1", "speaker": "甲",
             "segments": [{"start": 5.0, "end": 5.0}, {"start": 6.0, "end": 4.0},
                          {"start": None, "end": 2.0},
                          {"start": 8.0, "end": 9.0}]},
            {"cluster_key": "c2", "speaker": "乙",
             "segments": [{"start": 5.0, "end": 5.0}]},
        ])
        assert len(rows) == 1
        assert rows[0]["member_spans"] == [[8.0, 9.0]]
        assert rows[0]["n_members"] == 1

    def test_source_carries_cluster_key(self):
        rows = clusters_to_adjudication_rows([
            {"cluster_key": "c7", "speaker": "甲",
             "segments": [{"start": 1.0, "end": 2.0}]},
        ])
        assert rows[0]["source"] == f"{CLUSTER_SOURCE_PREFIX}:c7"

    def test_fingerprint_is_order_independent_but_content_sensitive(self):
        a = member_fingerprint([[10.0, 12.0], [20.0, 22.0]])
        b = member_fingerprint([[20.0, 22.0], [10.0, 12.0]])
        c = member_fingerprint([[10.0, 12.0], [20.0, 23.0]])
        assert a == b
        assert a != c


class TestResolver:
    """簇级裁决的段 → 说话人 匹配"""

    def _row(self, key, speaker, spans):
        return MeetingClusterAdjudication(
            meeting_id=MID, cluster_key=key, speaker=speaker,
            n_members=len(spans), member_spans=spans)

    def test_midpoint_matching(self):
        r = ClusterAdjudicationResolver([self._row("c1", "甲", [[10.0, 12.0]])])
        assert r.lookup(10.0, 12.0) == "甲"
        assert r.lookup(11.0, 11.5) == "甲"
        assert r.lookup(20.0, 21.0) is None
        assert r.lookup(None, None) is None

    def test_interleaved_clusters_do_not_over_capture(self):
        """⭐ c1 的区间跨过 c2 的区间 ⇒ c2 的段不能被 c1 认领。"""
        r = ClusterAdjudicationResolver([
            self._row("c1", "甲", [[10.0, 12.0], [30.0, 32.0]]),
            self._row("c2", "乙", [[20.0, 22.0]]),
        ])
        assert r.lookup(11.0, 11.5) == "甲"
        assert r.lookup(21.0, 21.5) == "乙"
        assert r.lookup(31.0, 31.5) == "甲"

    def test_empty_resolver_returns_none(self):
        r = ClusterAdjudicationResolver([])
        assert len(r) == 0
        assert r.lookup(1.0, 2.0) is None


class TestPrecedence:
    """⭐ 段级优先于簇级（裁决更细 ⇒ 优先, 类 20.244）"""

    class _SegResolver:
        def __init__(self, mapping):
            self._m = mapping

        def __len__(self):
            return len(self._m)

        def lookup(self, start, end):
            return self._m.get((start, end))

    def test_segment_wins_when_both_hit(self):
        seg = self._SegResolver({(10.0, 12.0): "段级"})
        clu = ClusterAdjudicationResolver([
            MeetingClusterAdjudication(meeting_id=MID, cluster_key="c1",
                                      speaker="簇级", n_members=1,
                                      member_spans=[[10.0, 12.0]])])
        comb = build_combined_resolver(seg, clu)
        assert comb.lookup(10.0, 12.0) == "段级"

    def test_cluster_fills_gaps_left_by_segment(self):
        seg = self._SegResolver({(10.0, 12.0): "段级"})
        clu = ClusterAdjudicationResolver([
            MeetingClusterAdjudication(meeting_id=MID, cluster_key="c1",
                                      speaker="簇级", n_members=2,
                                      member_spans=[[10.0, 12.0], [20.0, 22.0]])])
        comb = build_combined_resolver(seg, clu)
        assert comb.lookup(10.0, 12.0) == "段级"
        assert comb.lookup(21.0, 21.5) == "簇级"
        assert comb.lookup(30.0, 31.0) is None

    def test_combined_handles_missing_resolvers(self):
        comb = build_combined_resolver(None, None)
        assert comb.lookup(1.0, 2.0) is None
        assert len(comb) == 0


@pytest.mark.asyncio
class TestPersistence:
    async def _clean(self, db):
        from sqlalchemy import delete
        await db.execute(delete(MeetingClusterAdjudication).where(
            MeetingClusterAdjudication.meeting_id == MID))
        await db.commit()

    async def test_disabled_by_default_writes_nothing(self, db):
        """⭐ 开关默认关 ⇒ 不写库 ⇒ 生产行为零变化"""
        from app.config import settings
        assert settings.CLUSTER_NAMING_ENABLED is False

        await self._clean(db)
        stats = await record_cluster_naming(db, MID, [{
            "cluster_key": "c1", "speaker": "王天志",
            "segments": [{"start": 1.0, "end": 2.0}]},
        ])
        assert stats["written"] == 0
        assert await get_cluster_naming(db, MID) == []
        await self._clean(db)

    async def test_enabled_writes_one_row_per_cluster(self, db, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)

        await self._clean(db)
        stats = await record_cluster_naming(db, MID, [
            {"cluster_key": "c1", "cluster_id": 1, "speaker": "王天志",
             "segments": [{"start": 10.0, "end": 12.0}, {"start": 30.0, "end": 32.0}]},
            {"cluster_key": "c2", "cluster_id": 2, "speaker": "刘子煜",
             "segments": [{"start": 20.0, "end": 22.0}]},
        ])
        assert stats["written"] == 2        # ⭐ 两簇 ⇒ 两行

        rows = await get_cluster_naming(db, MID)
        assert len(rows) == 2
        by_key = {r.cluster_key: r for r in rows}
        assert by_key["c1"].speaker == "王天志"
        assert by_key["c1"].n_members == 2
        assert by_key["c2"].member_spans == [[20.0, 22.0]]
        assert by_key["c1"].member_fingerprint
        await self._clean(db)

    async def test_replace_is_idempotent(self, db, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)
        await self._clean(db)
        clusters = [{"cluster_key": "c1", "speaker": "甲",
                     "segments": [{"start": 1.0, "end": 2.0}]}]
        await record_cluster_naming(db, MID, clusters)
        await record_cluster_naming(db, MID, clusters)
        rows = await get_cluster_naming(db, MID)
        assert len(rows) == 1
        await self._clean(db)

    async def test_clear_only_removes_cluster_naming(self, db, monkeypatch):
        """⭐ clear 只删**簇级命名**, 段级人工听辨裁决必须原样保留"""
        from app.config import settings
        from app.services.speaker_adjudication_service import record_adjudication
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)

        await self._clean(db)
        await record_adjudication(db, MID, 5.0, 6.0, "人工听辨", source="ledger")
        await record_cluster_naming(db, MID, [{
            "cluster_key": "c1", "speaker": "甲",
            "segments": [{"start": 10.0, "end": 11.0}]}])

        cleared = await clear_cluster_naming(db, MID)
        assert cleared == 1
        from app.services.speaker_adjudication_service import get_adjudications
        remaining = await get_adjudications(db, MID)
        assert len(remaining) == 1
        assert remaining[0].source == "ledger"
        await self._clean(db)

    async def test_lookup_map(self, db, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "CLUSTER_NAMING_ENABLED", True, raising=False)
        await self._clean(db)
        await record_cluster_naming(db, MID, [{
            "cluster_key": "c1", "speaker": "甲",
            "segments": [{"start": 10.0, "end": 11.0}]}])
        m = await cluster_naming_lookup(db, MID)
        assert m == {"c1": "甲"}
        await self._clean(db)


class TestIsolation:
    """⭐ 两张表必须物理隔离 —— 簇级决策不得写进段级表"""

    def test_cluster_service_never_touches_segment_table(self):
        """结构守卫: 簇级裁决服务**不 import** 段级模型。

        ⚠️ 用 **AST** 判「有没有 import」, 不用 grep (类 20.251 ③):
        docstring 里**提到** 段级表是正常说明, 只有真的 import 才算耦合。
        """
        import ast
        import pathlib
        tree = ast.parse(
            pathlib.Path("app/services/cluster_naming_service.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    imported.add(a.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    imported.add(a.name)
        assert "MeetingSpeakerAdjudication" not in imported
        assert not any("meeting_speaker_adjudication" in i for i in imported)
        assert "MeetingClusterAdjudication" in imported

    def test_cluster_model_has_no_foreign_key_to_meetings(self):
        """结构守卫: 簇级模型的 meeting_id **不带 FK**。

        生产库 meetings 表无主键 ⇒ PG 拒绝建 FK (迁移 148 已改为不建);
        模型侧也必须一致 ⇒ 否则 create_all 在无 PK 的库上会炸。
        """
        import pathlib
        src = pathlib.Path(
            "app/models/meeting_cluster_adjudication.py").read_text(encoding="utf-8")
        assert "ForeignKey" not in src
        assert "ForeignKeyConstraint" not in src
