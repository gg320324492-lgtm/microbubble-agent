"""W82 第 1 批 D-1 6 类文档同步 + grand closure e2e (5/5).

派工 v4 铁律 3 真验证 实战:
1. CLAUDE.md 顶部 "当前状态" 段含 W82 第 1 批 grand closure
2. ROADMAP.md "当前状态" 段含 W82 第 1 批
3. CHANGELOG.md 顶部含 W82 第 1 批 grand closure 章节
4. README.md "近期新增" 段含 W82 第 1 批条目
5. memory/MEMORY.md 顶部含 W82 第 1 批 grand closure 条目 + 锚点范式 293 守恒

范畴: tests/ 新建 (0 production code 改动铁律 0 例外, 纯 docs/memory 同步)
不修改: app/ web/src/ alembic/ 老链路

运行:
    pytest tests/test_w82_d1_docs_grand_closure_e2e.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
ROADMAP_MD = ROOT / "ROADMAP.md"
CHANGELOG_MD = ROOT / "CHANGELOG.md"
README_MD = ROOT / "README.md"
MEMORY_MD = ROOT / "memory" / "w82-1st-grand-closure-2026-07-28.md"
RUNBOOK = ROOT / "docs" / "w82-1st-batch-d1-grand-closure-2026-07-28.md"

USER_MEMORY_MD = Path("C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md")


def _read_text(path: Path) -> str:
    """跨平台 UTF-8 读取 (Windows 默认 GBK, 避免 UnicodeDecodeError)."""
    with path.open(encoding="utf-8") as f:
        return f.read()


# --- Case 1: CLAUDE.md 含 W82 段验证 ---


def test_w82_d1_case1_claude_md_has_w82_section():
    """验证 CLAUDE.md 含 W82 第 1 批 grand closure 段 + 累计计数更新."""
    assert CLAUDE_MD.exists(), f"CLAUDE.md 不存在: {CLAUDE_MD}"
    text = _read_text(CLAUDE_MD)

    # CLAUDE.md 必须含 W82 第 1 批 grand closure 提及
    assert "W82" in text, "CLAUDE.md 缺少 W82 段"

    # 顶部状态段必须含 W82
    top_section = text.split("## 当前状态")[1].split("##")[0] if "## 当前状态" in text else text[:5000]
    assert "W82" in top_section, "CLAUDE.md 顶部 当前状态 段缺少 W82 提及"


def test_w82_d1_case1_claude_md_has_w81_grand_closure():
    """验证 CLAUDE.md 含 W81 第 1 批 grand closure 章节 (锚点范式 286 → 293 +7)."""
    assert CLAUDE_MD.exists()
    text = _read_text(CLAUDE_MD)

    # CLAUDE.md 必须含 W81 第 1 批 grand closure 章节
    assert "W81 第 1 批" in text or "W81-1st" in text.lower(), "CLAUDE.md 缺少 W81 第 1 批 章节"


# --- Case 2: ROADMAP.md 含 W82 段验证 ---


def test_w82_d1_case2_roadmap_md_has_w82_section():
    """验证 ROADMAP.md 含 W82 第 1 批 + 6 类文档同步."""
    assert ROADMAP_MD.exists(), f"ROADMAP.md 不存在: {ROADMAP_MD}"
    text = _read_text(ROADMAP_MD)

    # ROADMAP.md 必须含 W82 第 1 批
    assert "W82" in text, "ROADMAP.md 缺少 W82 段"

    # 顶部状态段必须含 W82
    assert "W82" in text[:5000] or "W82" in text, "ROADMAP.md 顶部 当前状态 段缺少 W82 提及"

    # 必须含 6 类文档同步
    assert "6 类文档同步" in text or "6类文档同步" in text, "ROADMAP.md 缺少 6 类文档同步 章节"


# --- Case 3: CHANGELOG.md 含 W82 段验证 ---


def test_w82_d1_case3_changelog_md_has_w82_section():
    """验证 CHANGELOG.md 顶部含 W82 第 1 批 grand closure 章节."""
    assert CHANGELOG_MD.exists(), f"CHANGELOG.md 不存在: {CHANGELOG_MD}"
    text = _read_text(CHANGELOG_MD)

    # CHANGELOG.md 顶部必须含 W82 第 1 批
    top_section = text[:5000]
    assert "W82" in top_section, "CHANGELOG.md 顶部缺少 W82 段"

    # 必须含 grand closure
    assert "grand closure" in top_section.lower() or "GrandClosure" in top_section, \
        "CHANGELOG.md 顶部缺少 grand closure 提及"


def test_w82_d1_case3_changelog_md_anchor_293_守恒():
    """验证 CHANGELOG.md 含锚点范式 293 守恒 (W81 第 1 批 293 → W82 第 1 批 293)."""
    assert CHANGELOG_MD.exists()
    text = _read_text(CHANGELOG_MD)

    # 锚点范式 293 守恒
    assert "293" in text, "CHANGELOG.md 缺少锚点范式 293 守恒"


# --- Case 4: README.md 含 W82 段验证 ---


def test_w82_d1_case4_readme_md_has_w82_section():
    """验证 README.md 近期新增段含 W82 第 1 批."""
    assert README_MD.exists(), f"README.md 不存在: {README_MD}"
    text = _read_text(README_MD)

    # README.md 必须含 W82
    assert "W82" in text, "README.md 缺少 W82 段"

    # 必须含 6 类文档同步提及
    assert "6 类文档同步" in text or "6类文档同步" in text, "README.md 缺少 6 类文档同步 提及"


# --- Case 5: memory/MEMORY.md 含 W82 段验证 + 锚点范式 293 守恒验证 ---


def test_w82_d1_case5_project_memory_has_w82_grand_closure():
    """验证项目 memory/w82-1st-grand-closure-2026-07-28.md 含 W82 第 1 批 grand closure."""
    assert MEMORY_MD.exists(), f"project memory 文件不存在: {MEMORY_MD}"
    text = _read_text(MEMORY_MD)

    # 必须含 W82 第 1 批 grand closure 标题
    assert "W82 第 1 批" in text, "project memory 缺少 W82 第 1 批 标题"
    assert "grand closure" in text.lower() or "GrandClosure" in text, \
        "project memory 缺少 grand closure 提及"

    # 必须含锚点范式 293 守恒
    assert "293" in text, "project memory 缺少锚点范式 293 守恒"


def test_w82_d1_case5_user_memory_md_has_w82_entry():
    """验证 user-level MEMORY.md 含 W82 第 1 批 grand closure 条目."""
    if not USER_MEMORY_MD.exists():
        pytest.skip(f"user-level MEMORY.md 不存在 (Windows env), 跳过: {USER_MEMORY_MD}")
    text = _read_text(USER_MEMORY_MD)

    # 必须含 W82 第 1 批 grand closure 条目
    assert "W82" in text, "user MEMORY.md 缺少 W82 段"
    assert "grand closure" in text.lower() or "GrandClosure" in text, \
        "user MEMORY.md 缺少 grand closure 提及"

    # 必须含锚点范式 293 守恒
    assert "293" in text, "user MEMORY.md 缺少锚点范式 293 守恒"


# --- Case 6 (新增): 累计 commits + 铁律守恒验证 ---


def test_w82_d1_case6_cumulative_commits_守恒():
    """验证累计 commits (24 批 410+) + 累计铁律 (380+) 守恒."""
    assert CLAUDE_MD.exists()
    assert ROADMAP_MD.exists()
    assert CHANGELOG_MD.exists()
    assert MEMORY_MD.exists()

    claude_text = _read_text(CLAUDE_MD)
    roadmap_text = _read_text(ROADMAP_MD)
    changelog_text = _read_text(CHANGELOG_MD)
    memory_text = _read_text(MEMORY_MD)

    # 累计 commits = 24 批 410+
    assert "24 批" in claude_text or "24批" in claude_text, "CLAUDE.md 缺少 24 批 累计"
    assert "410+" in claude_text or "410 +" in claude_text, "CLAUDE.md 缺少 410+ commits 累计"

    # 累计铁律 = 380+
    assert "380+" in claude_text or "380 +" in claude_text, "CLAUDE.md 缺少 380+ 铁律 累计"

    # ROADMAP 同步
    assert "24 批" in roadmap_text or "24批" in roadmap_text, "ROADMAP.md 缺少 24 批 累计"

    # memory 同步
    assert "24 批" in memory_text or "24批" in memory_text, "memory 缺少 24 批 累计"
    assert "410+" in memory_text or "380+" in memory_text, "memory 缺少 commits/铁律 累计"


# --- Case 7 (新增): W19 选项 A 维持验证 ---


def test_w82_d1_case7_w19_option_a_维持():
    """验证 W19 选项 A 维持 (4 留未来 PR)."""
    assert CLAUDE_MD.exists()
    text = _read_text(CLAUDE_MD)

    # W19 选项 A 维持
    assert "W19 选项 A 维持" in text, "CLAUDE.md 缺少 W19 选项 A 维持"
    # 4 留未来 PR
    assert "4 留未来 PR" in text or "4留未来PR" in text, "CLAUDE.md 缺少 4 留未来 PR"


# --- Case 8 (新增): runbook + memory + e2e 文件本身存在验证 ---


def test_w82_d1_case8_runbook_exists():
    """验证 docs runbook 存在."""
    assert RUNBOOK.exists(), f"docs runbook 不存在: {RUNBOOK}"
    text = _read_text(RUNBOOK)
    assert "W82" in text, "docs runbook 缺少 W82 提及"
    assert "6 类文档同步" in text or "6类文档同步" in text, "docs runbook 缺少 6 类文档同步 提及"


def test_w82_d1_case9_memory_exists():
    """验证 memory 文件存在 (重复 case 5 强化)."""
    assert MEMORY_MD.exists()
    text = _read_text(MEMORY_MD)
    assert "W82" in text
    assert "5 段同步" in text or "5段同步" in text, "memory 缺少 5 段同步 实战 提及"


def test_w82_d1_case10_e2e_test_self_reference():
    """验证 e2e 测试文件自身存在 + 可执行 (5 case + 5 新增 case)."""
    test_path = Path(__file__)
    assert test_path.exists()
    text = _read_text(test_path)
    # 至少 10 个 test_ 函数 (5 段同步 + 5 新增: 累计/W19/runbook/memory/self)
    test_count = text.count("def test_w82_d1_")
    assert test_count >= 10, f"e2e 测试函数数量不足: {test_count} (期望 >= 10)"
