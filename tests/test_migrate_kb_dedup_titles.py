"""KB title 重复去重脚本 — 纯函数 + 边界单测 (无 DB / 无 async 依赖)

跑法:
    docker exec microbubble-agent-app-1 bash -c "cd /app && python -m pytest tests/test_migrate_kb_dedup_titles.py -v"

覆盖:
- content_md5 hash 行为 (None / empty / 已知字符串)
- group_by_title 分组 (size=3 / size=1 跳过 / 多组 / 顺序保持)
- decide_group_deletion (md5 全部相同 / md5 不一致 / FK 引用)
- build_dedup_plan (聚合统计)
- TITLE_PREFIX 常量稳定性
"""

import sys
from pathlib import Path

# 容器内 / 本地都兼容
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
if (Path("/app") / "scripts" / "migrate_kb_dedup_titles.py").exists():
    sys.path.insert(0, "/app/scripts")

from migrate_kb_dedup_titles import (  # noqa: E402
    TITLE_PREFIX,
    CardRow,
    DedupPlan,
    TitleGroup,
    build_dedup_plan,
    content_md5,
    decide_group_deletion,
    group_by_title,
)


# ── content_md5: hash 行为 ─────────────────────────────────────
def test_content_md5_known_string():
    """已知字符串 → sha256 hex 头 32 字符"""
    h = content_md5("微纳米气泡在饮用水处理")
    assert len(h) == 32
    # 已知 sha256('微纳米气泡在饮用水处理')[:32]
    import hashlib
    expected = hashlib.sha256("微纳米气泡在饮用水处理".encode("utf-8")).hexdigest()[:32]
    assert h == expected


def test_content_md5_none():
    """None → 'EMPTY' (避免 hashlib 崩)"""
    assert content_md5(None) == "EMPTY"


def test_content_md5_empty_string():
    """空字符串 → sha256('')[:32] (固定值, 与 None 区分)"""
    import hashlib
    assert content_md5("") == hashlib.sha256(b"").hexdigest()[:32]
    assert content_md5("") != content_md5(None)


def test_content_md5_same_input_same_output():
    """幂等"""
    assert content_md5("hello") == content_md5("hello")


def test_content_md5_differs_for_diff_input():
    """不同输入 → 不同 hash"""
    assert content_md5("hello") != content_md5("world")


# ── group_by_title: 分组逻辑 ──────────────────────────────────
def test_group_by_title_groups_size_3():
    """3 张同 title → 1 组, all_content_same=True"""
    rows = [
        CardRow(id=1, title="[拓展-V01] x", content_md5="abc"),
        CardRow(id=2, title="[拓展-V01] x", content_md5="abc"),
        CardRow(id=3, title="[拓展-V01] x", content_md5="abc"),
    ]
    groups = group_by_title(rows)
    assert len(groups) == 1
    assert groups[0].title == "[拓展-V01] x"
    assert groups[0].all_content_same is True
    assert groups[0].distinct_md5_count == 1
    assert len(groups[0].rows) == 3


def test_group_by_title_skips_size_1():
    """单张同 title → 跳过 (无重复)"""
    rows = [CardRow(id=1, title="[拓展-V01] x", content_md5="abc")]
    assert group_by_title(rows) == []


def test_group_by_title_separates_distinct_titles():
    """3 组不同 title → 3 个 TitleGroup"""
    rows = [
        CardRow(id=1, title="[拓展-V01] a", content_md5="x"),
        CardRow(id=2, title="[拓展-V01] a", content_md5="x"),
        CardRow(id=3, title="[拓展-V02] b", content_md5="x"),
        CardRow(id=4, title="[拓展-V02] b", content_md5="x"),
        CardRow(id=5, title="[拓展-V03] c", content_md5="x"),
        CardRow(id=6, title="[拓展-V03] c", content_md5="x"),
    ]
    groups = group_by_title(rows)
    assert len(groups) == 3
    assert [g.title for g in groups] == [
        "[拓展-V01] a", "[拓展-V02] b", "[拓展-V03] c",
    ]


def test_group_by_title_preserves_id_order_in_group():
    """组内 rows 按 id 升序 (即使传入乱序)"""
    rows = [
        CardRow(id=3, title="t", content_md5="x"),
        CardRow(id=1, title="t", content_md5="x"),
        CardRow(id=2, title="t", content_md5="x"),
    ]
    groups = group_by_title(rows)
    assert [r.id for r in groups[0].rows] == [1, 2, 3]


def test_group_by_title_detects_mixed_md5():
    """3 张同 title 但 md5 不全相同 → all_content_same=False, distinct_md5_count=2"""
    rows = [
        CardRow(id=1, title="t", content_md5="aaa"),
        CardRow(id=2, title="t", content_md5="aaa"),
        CardRow(id=3, title="t", content_md5="bbb"),  # 不同
    ]
    groups = group_by_title(rows)
    assert groups[0].all_content_same is False
    assert groups[0].distinct_md5_count == 2


# ── decide_group_deletion: 决策核心 ───────────────────────────
def test_decide_all_same_keeps_min_id():
    """md5 全相同 + 无 FK 引用 → keep_id = min, delete_ids = 其他"""
    rows = [
        CardRow(id=101, title="t", content_md5="x"),
        CardRow(id=102, title="t", content_md5="x"),
        CardRow(id=103, title="t", content_md5="x"),
    ]
    group = TitleGroup(title="t", rows=rows, all_content_same=True, distinct_md5_count=1)
    d = decide_group_deletion(group, fk_referenced_ids=set())
    assert d.skipped is False
    assert d.keep_id == 101
    assert d.delete_ids == [102, 103]
    assert d.skip_reason == ""


def test_decide_md5_mismatch_skips():
    """md5 不全相同 → 跳过 (走 C 方案)"""
    rows = [
        CardRow(id=1, title="t", content_md5="aaa"),
        CardRow(id=2, title="t", content_md5="bbb"),
        CardRow(id=3, title="t", content_md5="aaa"),
    ]
    group = TitleGroup(title="t", rows=rows, all_content_same=False, distinct_md5_count=2)
    d = decide_group_deletion(group, fk_referenced_ids=set())
    assert d.skipped is True
    assert d.skip_reason == "content_md5_mismatch"
    assert d.keep_id == -1
    assert d.delete_ids == []


def test_decide_fk_referenced_skips_whole_group():
    """组内任一 id 被 FK 引用 → 整组跳过 (保守策略)"""
    rows = [
        CardRow(id=101, title="t", content_md5="x"),
        CardRow(id=102, title="t", content_md5="x"),
        CardRow(id=103, title="t", content_md5="x"),
    ]
    group = TitleGroup(title="t", rows=rows, all_content_same=True, distinct_md5_count=1)
    # 102 被引用 (即使 101 / 103 没被引用也整组跳过)
    d = decide_group_deletion(group, fk_referenced_ids={102})
    assert d.skipped is True
    assert d.skip_reason == "fk_referenced"
    assert d.delete_ids == []


def test_decide_fk_referenced_keeps_min_id_also_skipped():
    """即使 min_id 被 FK 引用也保守跳过 (避免半删导致孤儿)"""
    rows = [
        CardRow(id=101, title="t", content_md5="x"),
        CardRow(id=102, title="t", content_md5="x"),
    ]
    group = TitleGroup(title="t", rows=rows, all_content_same=True, distinct_md5_count=1)
    d = decide_group_deletion(group, fk_referenced_ids={101})  # min_id 被引
    assert d.skipped is True  # 保守: 整组保留


def test_decide_fk_check_only_when_all_content_same():
    """md5 不全同时, FK 引用不检查 (跳过逻辑优先)"""
    rows = [
        CardRow(id=1, title="t", content_md5="aaa"),
        CardRow(id=2, title="t", content_md5="bbb"),
    ]
    group = TitleGroup(title="t", rows=rows, all_content_same=False, distinct_md5_count=2)
    # 即使 1 在 fk_referenced, 仍报 content_md5_mismatch 优先
    d = decide_group_deletion(group, fk_referenced_ids={1})
    assert d.skip_reason == "content_md5_mismatch"


# ── build_dedup_plan: 聚合统计 ─────────────────────────────────
def test_build_plan_aggregates_all_counters():
    """5 组: 3 all_same + 1 mismatch + 1 fk → 各计数器正确"""
    groups = [
        # 3 组 all_same, 无 FK → scheduled
        TitleGroup("t1", [
            CardRow(id=1, title="t1", content_md5="x"),
            CardRow(id=2, title="t1", content_md5="x"),
        ], True, 1),
        TitleGroup("t2", [
            CardRow(id=3, title="t2", content_md5="x"),
            CardRow(id=4, title="t2", content_md5="x"),
        ], True, 1),
        TitleGroup("t3", [
            CardRow(id=5, title="t3", content_md5="x"),
            CardRow(id=6, title="t3", content_md5="x"),
        ], True, 1),
        # 1 组 mismatch
        TitleGroup("t4", [
            CardRow(id=7, title="t4", content_md5="a"),
            CardRow(id=8, title="t4", content_md5="b"),
        ], False, 2),
        # 1 组 fk
        TitleGroup("t5", [
            CardRow(id=9, title="t5", content_md5="x"),
            CardRow(id=10, title="t5", content_md5="x"),
        ], True, 1),
    ]
    plan = build_dedup_plan(groups, fk_referenced_ids={9})  # 9 被 FK 引用
    assert plan.groups_total == 5
    assert plan.groups_scheduled == 3
    assert plan.groups_skipped_mismatch == 1
    assert plan.groups_skipped_fk == 1
    assert plan.total_to_delete == 3  # 3 scheduled 组 × 1 delete_ids (size=2 → 删 1 留 1)
    assert len(plan.decisions) == 5


def test_build_plan_empty_groups():
    """空 groups → 全部计数 0"""
    plan = build_dedup_plan([], fk_referenced_ids=set())
    assert plan.groups_total == 0
    assert plan.groups_scheduled == 0
    assert plan.total_to_delete == 0
    assert plan.decisions == []


# ── TITLE_PREFIX 常量稳定性 ────────────────────────────────────
def test_title_prefix_stable():
    """与 migrate_kb_source_type 脚本的扫描条件对齐, 防字符漂移"""
    assert TITLE_PREFIX == "[拓展"
    # 不含 ] (因为 [拓展-XX] 后面还有内容, 不是完整 title 模式)
    assert "]" not in TITLE_PREFIX
    assert "(" not in TITLE_PREFIX and ")" not in TITLE_PREFIX


# ── 真实场景: 180 张 [拓展-XX] 数据模拟 ────────────────────────
def test_real_180_card_scenario_mixed_md5():
    """模拟用户 180 张卡片: 49 字节相同组 (97 总) + 48 字节不同组 + 0 FK 引用
    期望: 49 组 scheduled, 48 组 skipped_mismatch, total_to_delete = 98 (49×2)
    """
    groups = []

    # 49 字节相同组 (每组 3 张, md5 全相同, 每组删 2 张)
    for i in range(49):
        groups.append(TitleGroup(
            title=f"[拓展-S{i:02d}] x",
            rows=[
                CardRow(id=i*10+1, title=f"[拓展-S{i:02d}] x", content_md5="same_md5"),
                CardRow(id=i*10+2, title=f"[拓展-S{i:02d}] x", content_md5="same_md5"),
                CardRow(id=i*10+3, title=f"[拓展-S{i:02d}] x", content_md5="same_md5"),
            ],
            all_content_same=True,
            distinct_md5_count=1,
        ))

    # 48 字节不同组 (每组 3 张, md5 不同, 全跳过)
    for i in range(48):
        groups.append(TitleGroup(
            title=f"[拓展-V{i:02d}] x",
            rows=[
                CardRow(id=1000+i*10+1, title=f"[拓展-V{i:02d}] x", content_md5=f"md5_{i}_a"),
                CardRow(id=1000+i*10+2, title=f"[拓展-V{i:02d}] x", content_md5=f"md5_{i}_b"),
                CardRow(id=1000+i*10+3, title=f"[拓展-V{i:02d}] x", content_md5=f"md5_{i}_c"),
            ],
            all_content_same=False,
            distinct_md5_count=3,
        ))

    # 0 FK 引用
    plan = build_dedup_plan(groups, fk_referenced_ids=set())

    assert plan.groups_total == 97
    assert plan.groups_scheduled == 49
    assert plan.groups_skipped_mismatch == 48
    assert plan.groups_skipped_fk == 0
    assert plan.total_to_delete == 98  # 49 × 2 = 98 (保留每组 id 最小, 删另 2)
    # 验证每组都正确: keep_id 应该是 (i*10+1) (最小), delete_ids = (i*10+2, i*10+3)
    for i, d in enumerate(plan.decisions[:49]):
        if d.skipped:
            continue
        assert d.keep_id == i*10+1
        assert d.delete_ids == [i*10+2, i*10+3]
