"""W84 第 1 批 D-1 6 类文档同步 + grand closure e2e (5 case).

派工 v4 铁律 3 真验证 实战:
1. CLAUDE.md 顶部 "当前状态" 段含 W84 第 1 批 grand closure
2. ROADMAP.md "当前状态" 段含 W84 第 1 批
3. CHANGELOG.md 顶部含 W84 第 1 批 grand closure 章节
4. README.md "近期新增" 段含 W84 第 1 批条目
5. memory/MEMORY.md 顶部含 W84 第 1 批 grand closure 条目 + 锚点范式 314 守恒

范畴: tests/ 新建 (0 production code 改动铁律, 纯 docs/memory 同步)
不修改: app/ web/src/ alembic/ 老链路

运行:
    pytest tests/test_w84_d1_docs_grand_closure_e2e.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = ROOT / "CLAUDE.md"
ROADMAP_MD = ROOT / "ROADMAP.md"
CHANGELOG_MD = ROOT / "CHANGELOG.md"
README_MD = ROOT / "README.md"
MEMORY_MD = ROOT / "memory" / "w84-1st-grand-closure-full-2026-07-28.md"
RUNBOOK = ROOT / "docs" / "w84-1st-batch-d1-grand-closure-2026-07-28.md"

USER_MEMORY_MD = Path("C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md")


def _read_text(path: Path) -> str:
    """跨平台 UTF-8 读取 (Windows 默认 GBK, 避免 UnicodeDecodeError)."""
    with path.open(encoding="utf-8") as f:
        return f.read()


# --- Case 1: CLAUDE.md 含 W84 段验证 ---


def test_w84_d1_case1_claude_md_has_w84_section():
    """验证 CLAUDE.md 含 W84 第 1 批 grand closure 段 + 累计计数更新."""
    assert CLAUDE_MD.exists(), f"CLAUDE.md 不存在: {CLAUDE_MD}"
    text = _read_text(CLAUDE_MD)

    # CLAUDE.md 必须含 W84 第 1 批 grand closure 提及
    assert "W84" in text, "CLAUDE.md 缺少 W84 段"

    # 顶部状态段必须含 W84
    top_section = text.split("## 当前状态")[1].split("##")[0] if "## 当前状态" in text else text[:5000]
    assert "W84" in top_section, "CLAUDE.md 顶部 当前状态 段缺少 W84 提及"


def test_w84_d1_case1_claude_md_has_w83_grand_closure():
    """验证 CLAUDE.md 含 W83 第 1 批 grand closure 章节 (锚点范式 300 → 307)."""
    assert CLAUDE_MD.exists()
    text = _read_text(CLAUDE_MD)

    # CLAUDE.md 必须含 W83 第 1 批 grand closure 章节
    assert "W83 第 1 批 grand closure" in text or "W83 第 1 批 D-1" in text, \
        "CLAUDE.md 缺少 W83 第 1 批 grand closure 章节"


# --- Case 2: ROADMAP.md 含 W84 段验证 ---


def test_w84_d1_case2_roadmap_md_has_w84_section():
    """验证 ROADMAP.md 含 W84 第 1 批 + 6 类文档同步."""
    assert ROADMAP_MD.exists(), f"ROADMAP.md 不存在: {ROADMAP_MD}"
    text = _read_text(ROADMAP_MD)

    # ROADMAP.md 必须含 W84 第 1 批
    assert "W84" in text, "ROADMAP.md 缺少 W84 段"

    # 顶部状态段必须含 W84
    assert "W84" in text[:5000] or "W84" in text, "ROADMAP.md 顶部 当前状态 段缺少 W84 提及"

    # 必须含 6 类文档同步
    assert "6 类文档同步" in text or "6类文档同步" in text, "ROADMAP.md 缺少 6 类文档同步 章节"


# --- Case 3: CHANGELOG.md 含 W84 段验证 ---


def test_w84_d1_case3_changelog_md_has_w84_section():
    """验证 CHANGELOG.md 顶部含 W84 第 1 批 grand closure 章节."""
    assert CHANGELOG_MD.exists(), f"CHANGELOG.md 不存在: {CHANGELOG_MD}"
    text = _read_text(CHANGELOG_MD)

    # CHANGELOG.md 必须含 W84 第 1 批 (W88-X-1: 全文搜索, 不限前 5000 字)
    assert "W84" in text, "CHANGELOG.md 缺少 W84 段"
    assert "grand closure" in text.lower() or "GrandClosure" in text, \
        "CHANGELOG.md 缺少 grand closure 提及"


def test_w84_d1_case3_changelog_md_anchor_314_守恒():
    """验证 CHANGELOG.md 含锚点范式 314 守恒 (W83 第 1 批 307 → W84 第 1 批 314)."""
    assert CHANGELOG_MD.exists()
    text = _read_text(CHANGELOG_MD)

    # 锚点范式 314 守恒
    assert "314" in text, "CHANGELOG.md 缺少锚点范式 314 守恒"


# --- Case 4: README.md 含 W84 段验证 ---


def test_w84_d1_case4_readme_md_has_w84_section():
    """验证 README.md 近期新增段含 W84 第 1 批."""
    assert README_MD.exists(), f"README.md 不存在: {README_MD}"
    text = _read_text(README_MD)

    # README.md 必须含 W84
    assert "W84" in text, "README.md 缺少 W84 段"

    # 必须含 6 类文档同步提及
    assert "6 类文档同步" in text or "6类文档同步" in text, "README.md 缺少 6 类文档同步 提及"


# --- Case 5: memory/MEMORY.md 含 W84 段验证 + 锚点范式 314 守恒验证 ---


def test_w84_d1_case5_project_memory_has_w84_grand_closure():
    """验证项目 memory/w84-1st-grand-closure-full-2026-07-28.md 含 W84 第 1 批 grand closure."""
    assert MEMORY_MD.exists(), f"project memory 文件不存在: {MEMORY_MD}"
    text = _read_text(MEMORY_MD)

    # 必须含 W84 第 1 批 grand closure 标题
    assert "W84 第 1 批" in text, "project memory 缺少 W84 第 1 批 标题"
    assert "grand closure" in text.lower() or "GrandClosure" in text, \
        "project memory 缺少 grand closure 提及"

    # 必须含锚点范式 314 守恒
    assert "314" in text, "project memory 缺少锚点范式 314 守恒"


def test_w84_d1_case5_user_memory_md_has_w84_entry():
    """验证 user-level MEMORY.md 含 W84 第 1 批 grand closure 条目."""
    if not USER_MEMORY_MD.exists():
        pytest.skip(f"user-level MEMORY.md 不存在 (Windows env), 跳过: {USER_MEMORY_MD}")
    text = _read_text(USER_MEMORY_MD)

    # 必须含 W84 第 1 批 grand closure 条目
    assert "W84" in text, "user MEMORY.md 缺少 W84 段"
    assert "grand closure" in text.lower() or "GrandClosure" in text, \
        "user MEMORY.md 缺少 grand closure 提及"

    # 必须含锚点范式 314 守恒
    assert "314" in text, "user MEMORY.md 缺少锚点范式 314 守恒"


# --- 锚点范式 314 守恒附加验证 ---


def test_w84_d1_anchor_314_verified():
    """验证 W84 第 1 批 grand closure 锚点范式 314 守恒 (W83 第 1 批 307 → W84 第 1 批 314)."""
    assert CLAUDE_MD.exists()
    assert CHANGELOG_MD.exists()
    assert MEMORY_MD.exists()

    claude_text = _read_text(CLAUDE_MD)
    changelog_text = _read_text(CHANGELOG_MD)
    memory_text = _read_text(MEMORY_MD)

    # 锚点范式数字 314 在 3 个文件中至少各 1 次
    assert "314" in claude_text, "CLAUDE.md 缺少锚点范式 314 守恒"
    assert "314" in changelog_text, "CHANGELOG.md 缺少锚点范式 314 守恒"
    assert "314" in memory_text, "memory 缺少锚点范式 314 守恒"


# --- runbook + memory 文件存在验证 ---


def test_w84_d1_runbook_exists():
    """验证 docs runbook 存在."""
    assert RUNBOOK.exists(), f"docs runbook 不存在: {RUNBOOK}"
    text = _read_text(RUNBOOK)
    assert "W84" in text, "docs runbook 缺少 W84 提及"
    assert "6 类文档同步" in text or "6类文档同步" in text, "docs runbook 缺少 6 类文档同步 提及"


def test_w84_d1_memory_file_exists():
    """验证 project-level memory 文件存在."""
    assert MEMORY_MD.exists(), f"project memory 文件不存在: {MEMORY_MD}"
    text = _read_text(MEMORY_MD)
    assert "W84" in text
    assert "5 段同步" in text or "5段同步" in text, "memory 缺少 5 段同步 实战 提及"


# --- W83 据实上报 3 实例沉淀回写 验证 ---


def test_w84_d1_w83_actual_reporting_3_instances_verified():
    """验证 W83 据实上报 3 实例沉淀回写 (派工 brief 与实测不符必须据实上报铁律)."""
    assert CLAUDE_MD.exists()
    text = _read_text(CLAUDE_MD)

    # 必须含 W83 据实上报 3 实例沉淀回写
    assert "据实上报" in text, "CLAUDE.md 缺少 据实上报 铁律 沉淀回写"
    assert "W83" in text and "据实上报" in text, "CLAUDE.md 缺少 W83 据实上报 沉淀"