"""KB dedup admin CLI 单测 — 纯函数覆盖 (不需要 DB)

跑法:
    docker exec microbubble-agent-app-1 bash -c "cd /app && SKIP_DB_SETUP=1 python -m pytest tests/test_dedup_kb_duplicates.py -v"

覆盖:
- make_merge_plan: 保留 best (max quality_score, 平局 max id)
- 多组并列: 每组独立 keep 1 条
- 单条组: 不删任何
"""
import sys
from datetime import datetime
from pathlib import Path

# 让 scripts/ 可 import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dedup_kb_duplicates import (  # noqa: E402
    DuplicateGroup,
    KbRecord,
    make_merge_plan,
)


def _rec(id: int, title: str, quality: float = 0.0) -> KbRecord:
    return KbRecord(
        id=id,
        title=title,
        quality_score=quality,
        created_at=datetime(2026, 6, 14, 15, 3, 1),
        source="",
        source_type="auto_expansion",
        created_by=None,
        storage_mode="kb",
    )


class TestMakeMergePlan:
    """合并计划: keep best + delete rest"""

    def test_keep_highest_quality_score(self):
        """质量分最高的保留"""
        group = DuplicateGroup(title="[拓展-S22] test", group=[
            _rec(38, "[拓展-S22] test", quality=0.5),
            _rec(135, "[拓展-S22] test", quality=0.9),  # 最高
            _rec(86, "[拓展-S22] test", quality=0.7),
        ])
        plan = make_merge_plan(group)
        assert plan.keep_id == 135
        assert sorted(plan.delete_ids) == [38, 86]

    def test_tie_score_keeps_largest_id(self):
        """平局 quality → id 最大"""
        group = DuplicateGroup(title="[拓展-S22] test", group=[
            _rec(38, "[拓展-S22] test", quality=None),  # None → 0.0
            _rec(86, "[拓展-S22] test", quality=None),
            _rec(135, "[拓展-S22] test", quality=None),
        ])
        plan = make_merge_plan(group)
        assert plan.keep_id == 135  # 平局 id 最大
        assert sorted(plan.delete_ids) == [38, 86]

    def test_single_record_group_no_delete(self):
        """单条组不删"""
        group = DuplicateGroup(title="single", group=[_rec(1, "single")])
        plan = make_merge_plan(group)
        assert plan.keep_id == 1
        assert plan.delete_ids == []

    def test_two_record_group(self):
        """两条组删 1 留 1"""
        group = DuplicateGroup(title="dup", group=[
            _rec(10, "dup", quality=0.3),
            _rec(20, "dup", quality=0.7),
        ])
        plan = make_merge_plan(group)
        assert plan.keep_id == 20
        assert plan.delete_ids == [10]


class TestMakeMergePlanMultiGroup:
    """多组独立计算 (覆盖 48 组场景的逻辑)"""

    def test_three_groups_independent(self):
        """3 组独立 keep, 删除其他"""
        g1 = DuplicateGroup(title="G1", group=[
            _rec(1, "G1"), _rec(2, "G1"), _rec(3, "G1"),
        ])
        g2 = DuplicateGroup(title="G2", group=[
            _rec(10, "G2", quality=0.5),
            _rec(11, "G2", quality=0.9),  # 最高
        ])
        g3 = DuplicateGroup(title="G3", group=[
            _rec(20, "G3"), _rec(21, "G3"), _rec(22, "G3"),
        ])
        plans = [make_merge_plan(g) for g in [g1, g2, g3]]
        # G1: 平局 id 最大 → 3
        assert plans[0].keep_id == 3
        assert sorted(plans[0].delete_ids) == [1, 2]
        # G2: quality 最高 → 11
        assert plans[1].keep_id == 11
        assert plans[1].delete_ids == [10]
        # G3: 平局 id 最大 → 22
        assert plans[2].keep_id == 22
        assert sorted(plans[2].delete_ids) == [20, 21]