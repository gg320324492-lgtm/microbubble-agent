"""W85 第 1 批 D-1 6 类文档同步 + grand closure e2e (5 case).

派工 v4 铁律 3 真验证 实战:
1. CLAUDE.md 顶部 "当前状态" 段含 W85 第 1 批 grand closure + 锚点 320
2. ROADMAP.md "当前状态" 段含 W85 第 1 批
3. CHANGELOG.md 顶部含 W85 第 1 批 grand closure 章节
4. README.md "近期新增" 段含 W85 第 1 批条目
5. memory/MEMORY.md 顶部含 W85 第 1 批 grand closure 条目 + 锚点范式 320 守恒 +6 据实上报

范畴: tests/ 新建 (0 production code 改动铁律, 纯 docs/memory 同步)
不修改: app/ web/src/ alembic/ 老链路

锚点范式关键数字 (派工 v6 §1.2 真验证铁律 + W84 D-2 拦截 #18 实战):
- 起点 (W84 closure): 314
- W85 第 1 批真实施: 314 + 6 = 320 (D-2 据实上报, B-2 useTask 0 hit 不实施)
- W85 第 1 批 5 段同步必须如实写 +6, 不能写 +7

运行:
    pytest tests/test_w85_d1_docs_grand_closure_e2e.py -v
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
ROADMAP_MD = ROOT / "ROADMAP.md"
CHANGELOG_MD = ROOT / "CHANGELOG.md"
README_MD = ROOT / "README.md"
MEMORY_MD = ROOT / "memory" / "w85-1st-grand-closure-full-2026-07-29.md"
RUNBOOK = ROOT / "docs" / "w85-1st-batch-d1-grand-closure-2026-07-29.md"

USER_MEMORY_MD = Path("C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md")


def _read_text(path: Path) -> str:
    """跨平台 UTF-8 读取 (Windows 默认 GBK, 避免 UnicodeDecodeError)."""
    with path.open(encoding="utf-8") as f:
        return f.read()


# --- Case 1: CLAUDE.md 含 W85 段 + 锚点 320 验证 ---


def test_w85_d1_case1_claude_md_has_w85_section_and_anchor_320():
    """验证 CLAUDE.md 含 W85 第 1 批 grand closure 段 + 累计计数 27 批 + 锚点 320."""
    assert CLAUDE_MD.exists(), f"CLAUDE.md 不存在: {CLAUDE_MD}"
    text = _read_text(CLAUDE_MD)

    # CLAUDE.md 必须含 W85 第 1 批 grand closure 提及
    assert "W85" in text, "CLAUDE.md 缺少 W85 段"

    # 顶部状态段必须含 W85 + 锚点 320
    top_state = text[:3000]
    assert "W85 第 1 批" in top_state, "CLAUDE.md 顶部状态段缺少 W85 第 1 批"
    assert "锚点范式 W84 第 1 批 314 → W85 第 1 批 320" in top_state, \
        "CLAUDE.md 顶部状态段缺少锚点范式 314 → 320"
    assert "+6" in top_state, "CLAUDE.md 顶部状态段缺少锚点增量 +6 (D-2 据实上报, 不能写 +7)"
    # 顶部状态段不能写成 314 → 321 或 +7 (派工 brief 预填)
    # 注意: 文中如需解释 "派工 brief 预填 +7 vs D-2 据实上报 +6" 上下文, 不在本断言范围
    # 核心检查: 顶部状态段不能以 +7 / 321 作为"实际增量"表述
    import re
    bad_pattern = re.compile(r"锚点范式\s+W?84?\s*第\s*1\s*批\s*314\s*→\s*W?85?\s*第\s*1\s*批\s*321\s*守恒")
    assert not bad_pattern.search(top_state), \
        "CLAUDE.md 顶部状态段写了 314 → 321 守恒 (派工 brief 预填, 必须改为 314 → 320)"

    # 必须含 W85 第 1 批 D-1 6 类文档同步 + grand closure 章节
    assert "W85 第 1 批 D-1 6 类文档同步" in text, \
        "CLAUDE.md 缺少 W85 第 1 批 D-1 6 类文档同步章节"

    # 累计计数: 27 批 440+ commits + 440+ 铁律 (W85 第 1 批 +25+ 铁律)
    assert "27 批" in top_state, "CLAUDE.md 缺少累计 27 批计数"
    assert "440+" in top_state, "CLAUDE.md 缺少累计 440+ commits / 铁律"

    # 类 20 18 条实战 (W85 据实上报 2 实例: 类 20 实战 20 + 类 20.13 实战 19)
    assert "类 20" in top_state, "CLAUDE.md 缺少类 20 实战描述"
    assert "18 条实战" in top_state or "18 实例" in top_state, \
        "CLAUDE.md 缺少类 20 18 实例计数"

    # 必须含据实上报铁律 (W85 B-2 useTask 0 hit 不实施)
    assert "useTask" in text, "CLAUDE.md 缺少 useTask 据实上报描述"
    assert "0 hit" in text, "CLAUDE.md 缺少 useTask 0 hit 据实描述"

    # 必须含类 20.13 实战 19 (D-2 锚点据实)
    assert "类 20.13 实战 19" in top_state, "CLAUDE.md 缺少类 20.13 实战 19 描述"

    # 主指挥协调范式第 61 次派工
    assert "第 61 次派工" in top_state, "CLAUDE.md 缺少主指挥协调范式第 61 次派工"

    # W86/W87/W88 派工顺序表
    assert "W86/W87/W88" in top_state, "CLAUDE.md 缺少 W86/W87/W88 派工顺序表"


# --- Case 2: ROADMAP.md 含 W85 段 + 锚点 +6 ---


def test_w85_d1_case2_roadmap_md_has_w85_section_and_anchor_plus_6():
    """验证 ROADMAP.md 含 W85 第 1 批段 + 锚点 +6."""
    assert ROADMAP_MD.exists(), f"ROADMAP.md 不存在: {ROADMAP_MD}"
    text = _read_text(ROADMAP_MD)

    # 顶部状态段必须含 W85
    top_state = text[:3000]
    assert "W85 第 1 批" in top_state, "ROADMAP.md 顶部状态段缺少 W85 第 1 批"
    assert "锚点范式 W84 第 1 批 314 → W85 第 1 批 320" in top_state, \
        "ROADMAP.md 顶部状态段缺少锚点范式 314 → 320"

    # 必须含 +6 (D-2 据实上报), 不能写 +7
    assert "+6" in top_state, "ROADMAP.md 顶部状态段缺少锚点增量 +6 (D-2 据实上报)"
    # 顶部状态段不能写成 314 → 321 或 +7 守恒 (派工 brief 预填)
    bad_pattern = re.compile(r"锚点范式\s+W?84?\s*第\s*1\s*批\s*314\s*→\s*W?85?\s*第\s*1\s*批\s*321\s*守恒")
    assert not bad_pattern.search(top_state), \
        "ROADMAP.md 顶部状态段写了 314 → 321 守恒 (派工 brief 预填, 必须改为 314 → 320)"

    # W86/W87/W88 派工顺序表
    assert "W86/W87/W88" in top_state, "ROADMAP.md 缺少 W86/W87/W88 派工顺序表"


# --- Case 3: CHANGELOG.md 含 W85 段 + 锚点 +6 ---


def test_w85_d1_case3_changelog_md_has_w85_section_and_anchor_plus_6():
    """验证 CHANGELOG.md 顶部含 W85 第 1 批 grand closure 章节 + 锚点 +6."""
    assert CHANGELOG_MD.exists(), f"CHANGELOG.md 不存在: {CHANGELOG_MD}"
    text = _read_text(CHANGELOG_MD)

    # 顶部 (前 5000 字) 必须含 W85 第 1 批 grand closure 段
    top_part = text[:5000]
    assert "W85 第 1 批 D-1 6 类文档同步 + grand closure" in top_part, \
        "CHANGELOG.md 顶部缺少 W85 第 1 批 D-1 6 类文档同步章节"
    assert "锚点范式 314 → 320 守恒 +6" in top_part, \
        "CHANGELOG.md 顶部缺少锚点范式 314 → 320 +6"

    # 必须含 +6, 不能写 +7
    assert "+6" in top_part, "CHANGELOG.md 顶部缺少锚点增量 +6 (D-2 据实上报)"
    # 顶部不能写成 314 → 321 或 +7 守恒 (派工 brief 预填)
    bad_pattern = re.compile(r"锚点范式\s*314\s*→\s*321\s*守恒")
    assert not bad_pattern.search(top_part), \
        "CHANGELOG.md 顶部写了 314 → 321 守恒 (派工 brief 预填, 必须改为 314 → 320)"

    # 派工前提错配 18 实例 (W85 据实上报 2 实例: 类 20 + 类 20.13)
    assert "派工前提错配 18 实例" in top_part, \
        "CHANGELOG.md 缺少派工前提错配 18 实例计数"

    # 必须含据实上报铁律: 类 20 实战 20 B-2 + 类 20.13 实战 19 D-2
    assert "类 20 实战 20" in top_part, "CHANGELOG.md 缺少类 20 实战 20 (B-2 useTask 0 hit 跳过)"
    assert "类 20.13 实战 19" in top_part, "CHANGELOG.md 缺少类 20.13 实战 19 (D-2 锚点 +6 不凑 +7)"

    # 0 production code 例外 2 (B-1 + C-1)
    assert "0 production code 改动铁律 5/7 守恒" in top_part, \
        "CHANGELOG.md 缺少 0 production code 5/7 守恒"
    assert "2 例外已批 W85" in top_part, "CHANGELOG.md 缺少 W85 2 例外已批"


# --- Case 4: README.md 含 W85 段 + 5 项交付物 ---


def test_w85_d1_case4_readme_md_has_w85_section_and_5_deliverables():
    """验证 README.md 近期新增段含 W85 第 1 批 + 5 项交付物."""
    assert README_MD.exists(), f"README.md 不存在: {README_MD}"
    text = _read_text(README_MD)

    # 顶部 (前 5000 字) 必须含 W85 第 1 批
    top_part = text[:5000]
    assert "W85 第 1 批 D-1 6 类文档同步收口" in top_part, \
        "README.md 近期新增段缺少 W85 第 1 批 D-1 6 类文档同步收口"
    assert "锚点范式 314 → 320 守恒 +6 据实上报" in top_part, \
        "README.md 近期新增段缺少锚点范式 314 → 320 +6 据实上报"

    # 5 项交付物 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md)
    assert "5 项交付物 (W85 第 1 批)" in top_part, "README.md 缺少 5 项交付物 (W85 第 1 批)"
    assert "**CLAUDE.md**" in top_part, "README.md 5 项交付物缺 CLAUDE.md"
    assert "**ROADMAP.md**" in top_part, "README.md 5 项交付物缺 ROADMAP.md"
    assert "**CHANGELOG.md**" in top_part, "README.md 5 项交付物缺 CHANGELOG.md"
    assert "**README.md**" in top_part, "README.md 5 项交付物缺 README.md"
    assert "**memory/MEMORY.md**" in top_part, "README.md 5 项交付物缺 memory/MEMORY.md"

    # 必须含 6/6 真实施描述 (A-2 + B-1 + B-2 + C-1 + C-2 + D-2)
    assert "6/6 真实施" in top_part, "README.md 缺少 6/6 真实施描述"

    # 主指挥协调范式第 61 次派工
    assert "第 61 次派工" in top_part, "README.md 缺少主指挥协调范式第 61 次派工"


# --- Case 5: memory/MEMORY.md 含 W85 条目 + 锚点 320 守恒 ---


def test_w85_d1_case5_memory_md_has_w85_entry_and_anchor_320():
    """验证 memory/MEMORY.md 含 W85 第 1 批 grand closure 条目 + 锚点 320 + 据实上报."""
    assert USER_MEMORY_MD.exists(), f"memory/MEMORY.md 不存在: {USER_MEMORY_MD}"
    text = _read_text(USER_MEMORY_MD)

    # 顶部必须含 W85 第 1 批 grand closure 条目
    assert "w85-1st-grand-closure-full-2026-07-29" in text, \
        "memory/MEMORY.md 缺少 w85-1st-grand-closure-full-2026-07-29 条目"

    # 必须含锚点 320 (W85 收口)
    assert "锚点范式 W7 12 → W85 320" in text or "W85 320" in text, \
        "memory/MEMORY.md 缺少 W85 320 锚点"

    # 必须含 +6 据实上报
    assert "+6" in text or "据实上报" in text, \
        "memory/MEMORY.md 缺少 +6 据实上报描述"

    # 必须含 W85 D-1 类 20 实战 20 (B-2 useTask 0 hit) + 类 20.13 实战 19 (D-2 锚点)
    assert "类 20 实战 20" in text or "useTask 0 hit" in text, \
        "memory/MEMORY.md 缺少 W85 类 20 实战 20"
    assert "类 20.13 实战 19" in text, "memory/MEMORY.md 缺少 W85 类 20.13 实战 19"

    # 必须含据实上报 (派工 v6 §1.2 + W84 D-2 拦截 #18 实战)
    assert "据实上报" in text, "memory/MEMORY.md 缺少据实上报描述"

    # 必须含 178 active memory (W85 C-2 重整)
    assert "178" in text or "216 文件" in text, \
        "memory/MEMORY.md 缺少 178 active memory / 216 文件总计"


# --- Bonus Case: runbook + memory 文件存在性 ---


def test_w85_d1_bonus_runbook_and_memory_files_exist():
    """验证 docs runbook + memory 文件存在性 + 锚点范式 314 → 320 +6."""
    assert RUNBOOK.exists(), f"docs runbook 不存在: {RUNBOOK}"
    runbook_text = _read_text(RUNBOOK)
    assert "W85 第 1 批 D-1 grand closure" in runbook_text, \
        "docs runbook 缺少 W85 第 1 批 D-1 grand closure 章节"
    assert "314 → 320" in runbook_text, "docs runbook 缺少锚点范式 314 → 320"
    assert "(+6" in runbook_text, "docs runbook 缺少锚点增量 (+6)"
    # runbook 主体不能写成 314 → 321 或 +7 守恒 (派工 brief 预填)
    bad_pattern_runbook = re.compile(r"锚点范式\s*314\s*→\s*321\s*守恒")
    assert not bad_pattern_runbook.search(runbook_text), \
        "docs runbook 写了 314 → 321 守恒 (派工 brief 预填, 必须改为 314 → 320)"

    # 必须含 5 新铁律 (W85 D-1 沉淀)
    assert "5 新铁律" in runbook_text or "5 条铁律" in runbook_text, \
        "docs runbook 缺少 5 新铁律 (W85 D-1)"

    # 必须含据实上报铁律
    assert "据实上报" in runbook_text, "docs runbook 缺少据实上报铁律"

    assert MEMORY_MD.exists(), f"memory 文件不存在: {MEMORY_MD}"
    memory_text = _read_text(MEMORY_MD)
    assert "锚点范式 314 → 320" in memory_text, "memory 缺少锚点范式 314 → 320"
    assert "+6" in memory_text, "memory 缺少锚点增量 +6"
    bad_pattern_memory = re.compile(r"锚点范式\s*314\s*→\s*321\s*守恒")
    assert not bad_pattern_memory.search(memory_text), \
        "memory 写了 314 → 321 守恒 (派工 brief 预填, 必须改为 314 → 320)"

    # 必须含 W85 第 1 批 6/6 真实施 agent 列表
    assert "A-2" in memory_text and "B-1" in memory_text and "B-2" in memory_text, \
        "memory 缺少 W85 第 1 批 6/6 真实施 agent 列表"
    assert "C-1" in memory_text and "C-2" in memory_text and "D-2" in memory_text, \
        "memory 缺少 W85 第 1 批 6/6 真实施 agent 列表"

    # 必须含 W85 据实上报 2 实例
    assert "类 20 实战 20" in memory_text, "memory 缺少类 20 实战 20 (B-2 useTask 据实上报)"
    assert "类 20.13 实战 19" in memory_text, "memory 缺少类 20.13 实战 19 (D-2 锚点据实上报)"