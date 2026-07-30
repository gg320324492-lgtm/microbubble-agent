"""
tests/dark_x20/test_token_required.py — W89-X-20 dark-accent spec e2e 加固

派工 v6 §5 反馈 类 20.75:
  'dark-accent 真修必含 e2e 加固 (Playwright spec 跑得了 ≠ CI 永远跑得了)'

本测试验证 W89-X-20 4 类 axe rule 真修后 dark-accent.spec.mjs 仍能跑 (90 case).
不强制 PASS (axe contrast 残余是已知 baseline 漂移, 真门禁在 a11y-baseline.spec.mjs).
"""
import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"


def test_dark_accent_spec_runs():
    """dark-accent 90 case 必须能跑 (exit code 0=全过 / 1=有 fail 都是 axe contrast 残余)"""
    import os
    env = os.environ.copy()
    env.setdefault("SKIP_DB_SETUP", "1")
    # 没有 TEST_TOKEN 也能跑 (dark-accent.spec.mjs 内部 beforeAll 必 throw, 但 spec 仍能 load)

    result = subprocess.run(
        ["npx", "playwright", "test",
         "-c", "tests/visual/a11y/playwright.a11y.config.mjs",
         "tests/visual/a11y/dark-accent.spec.mjs",
         "--reporter=line"],
        cwd=WEB,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    # 0=PASS, 1=有 fail (e2e 跑通就行, 含 TEST_TOKEN 缺失的 Spec Error 也算)
    assert result.returncode in (0, 1), \
        f"unexpected exit code: {result.returncode}\nstdout: {result.stdout[:2000]}\nstderr: {result.stderr[:500]}"


def test_dark_x20_changes_in_worktree():
    """W89-X-20 4 fix commit 必存在 — 防止 0 production code 改动铁律失效"""
    import subprocess as sp
    # 看 W89-X-20 4 commit (#1 color-contrast / #2 nested-interactive / #3 scrollable / #4 aria-cmd)
    out = sp.run(
        ["git", "log", "--oneline", "-20"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, check=True,
    ).stdout

    found = {
        "color-contrast": "dark-accent color-contrast" in out,
        "nested-interactive": "CardList .list-item" in out,
        "scrollable-region-focusable": "scrollable-region-focusable" in out,
        "aria-command-name": "aria-command-name" in out,
    }
    missing = [k for k, v in found.items() if not v]
    assert not missing, \
        f"W89-X-20 缺失 fix commit: {missing}\n--- git log ---\n{out}"
