"""W87 第 1 批 X-3 — alembic pre-commit hook 假阳性修复 e2e.

派工 v6 §5 反馈 类 20.30 实战:
- 原 hook 用 `python -c "..." 2>&1 | wc -w` 把 stderr SyntaxWarning 数成 head
- 冷缓存 (删 alembic/versions/__pycache__) 时 028_figure_structured_fields.py
  的 `\\d` 转义警告 → 报 13 heads (假红)
- 热缓存或 PYTHONWARNINGS=ignore 报 1 head (假绿, 但非确定性)
- 旧 e2e 断言 returncode ∈ {0, 1, 2} 弱放过

本测试精确断言:
1. 冷缓存: hook 必须 exit 0 (确认不会 SyntaxWarning 假红)
2. 冷缓存 + 多次执行都稳定 exit 0 (确认非侥幸, 拦截 1/13 假阳性窗口)
3. 即使 stderr 有 SyntaxWarning, exit code 仍 0 (W87-X-3 修法验证)
4. 实际 alembic head 数量 (跨 import 隔离测试) 必须确实 == 1
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = REPO_ROOT / "scripts" / "alembic" / "check_single_head.sh"
PYCACHE_DIR = REPO_ROOT / "alembic" / "versions" / "__pycache__"


def _bash_path() -> str:
    """Resolve real bash. 关键: 用 shutil.which 找 git-bash, 别传 env= 把 PATH 丢了."""
    bash = shutil.which("bash")
    if bash:
        return bash
    # 兜底: Windows git-bash 常见位置
    for p in (
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
    ):
        if Path(p).exists():
            return p
    raise RuntimeError("bash not found")


def _hook_env() -> dict:
    """继承父 env + 强制 utf-8 + 屏蔽 SyntaxWarning."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONWARNINGS"] = "default"
    return env


def _run_hook() -> subprocess.CompletedProcess:
    """Cold cache + run hook. 冷缓存才能暴露 SyntaxWarning 假红."""
    if PYCACHE_DIR.exists():
        shutil.rmtree(PYCACHE_DIR)
    return subprocess.run(
        [_bash_path(), str(HOOK_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_hook_env(),
    )


@pytest.mark.precommit
def test_check_single_head_exits_zero_cold_cache() -> None:
    """W87-X-3 类 20.30 修法核心: 冷缓存必须 exit 0."""
    result = _run_hook()
    assert result.returncode == 0, (
        f"Hook 必须 exit 0 (W87-X-3 修法). 实际 {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.precommit
def test_check_single_head_stable_across_cold_runs() -> None:
    """冷缓存连跑 3 次, 必须稳定 exit 0 (拦截 1/13 假阳性窗口)."""
    results = [_run_hook() for _ in range(3)]
    for i, r in enumerate(results, 1):
        assert r.returncode == 0, (
            f"第 {i} 次冷缓存运行 exit {r.returncode} (不稳定).\n"
            f"stdout: {r.stdout}\nstderr: {r.stderr}"
        )


@pytest.mark.precommit
def test_check_single_head_ignores_syntax_warning() -> None:
    """即使 028_figure_structured_fields.py 触发 SyntaxWarning, hook 仍 exit 0.

    这是 W87-X-3 修法核心: 分离 stdout/stderr, exit code 直接由 python sys.exit
    决定, 不被 wc -w 误算.
    """
    result = _run_hook()
    # 警告可能出现在 stderr, 但不影响 exit code
    if "SyntaxWarning" in result.stderr or "SyntaxWarning" in result.stdout:
        # 如果有警告, 必须仍 exit 0 (修法核心)
        assert result.returncode == 0, (
            f"有 SyntaxWarning 但 hook 仍需 exit 0. 实际 {result.returncode}."
        )
    # 不论有没有警告, 都必须 exit 0
    assert result.returncode == 0, (
        f"Hook 必须 exit 0 即使有/无 SyntaxWarning. 实际 {result.returncode}."
    )


@pytest.mark.precommit
def test_actual_alembic_head_count_is_one() -> None:
    """独立 import 隔离测试, 验证 alembic 真的只有 1 head (不是 hook 假阳/假阴).

    这是基线锚点: 如果这个测试 PASS, 前面 hook 测试 PASS 才算真合规.
    """
    # 冷缓存 + 屏蔽警告, 直接查 alembic head
    if PYCACHE_DIR.exists():
        shutil.rmtree(PYCACHE_DIR)
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys, warnings; warnings.filterwarnings('ignore'); "
         "from alembic.config import Config; "
         "from alembic.script import ScriptDirectory; "
         "c=Config(); c.set_main_option('script_location','alembic'); "
         "s=ScriptDirectory.from_config(c); "
         "heads=s.get_heads(); print(len(heads)); print(' '.join(heads))"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_hook_env(),
    )
    assert result.returncode == 0, f"alembic head 查询失败: {result.stderr}"
    lines = result.stdout.strip().splitlines()
    count = int(lines[0])
    assert count == 1, (
        f"alembic 必须 1 head. 实际 {count}. lines: {lines}. "
        f"如发现真多 head, 走派工 v6 §6 串单链纪律修复, 非 hook 假阳."
    )
    # 期望 head 已知 (实测当前 head, 不凭 CLAUDE.md 历史)
    assert lines[1] == "091_add_kg_entity", (
        f"alembic head 应为 091_add_kg_entity. 实际: {lines[1]}"
    )
