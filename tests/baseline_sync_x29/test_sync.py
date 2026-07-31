"""
tests/baseline_sync_x29/test_sync.py — W89-X-29 a11y baseline sync git 门禁

派工 brief: W89-X-16 据实报告 25 baseline .txt 写出来了(匿名态)
            是否 sync git 待主指挥拍板.
主指挥拍板: 选项 C — sync git (因为 P-6 已 commit, baseline 必入 git 才有效).

本测试验证:
1. baseline 文件数 ≥ 25 (派工 brief §5 派工必 ≥ 25 个)
2. baseline 文件必在 git 跟踪中 (选项 C sync git 决策落地)

派工 v6 §5 反馈 类 20.84 沉淀:
"a11y baseline 必入 git + 必在登录态生成 (匿名态 baseline 0 violations 是假绿信号)"
"""

from pathlib import Path

SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "tests"
    / "visual"
    / "a11y"
    / "__snapshots__"
)
REPO_ROOT = SNAPSHOT_DIR.parents[3]  # web/tests/visual/a11y/__snapshots__ -> <repo-root>


def test_baseline_files_exist():
    """a11y baseline 必 ≥ 25 个文件 (派工 brief §5 守恒)"""
    files = list(SNAPSHOT_DIR.glob("*.txt"))
    assert len(files) >= 25, (
        f"期望 ≥ 25 baseline, 实际 {len(files)}. "
        f"W89-P-6 cherry-pick 应已写入 25 个快照 (5 pages × 5 projects)."
    )


def test_baseline_files_tracked_by_git():
    """a11y baseline 必在 git 跟踪中 (选项 C sync git 决策落地)"""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", str(SNAPSHOT_DIR)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = [line for line in result.stdout.strip().split("\n") if line]
    assert len(tracked) >= 25, (
        f"期望 ≥ 25 tracked, 实际 {len(tracked)}. "
        f"主指挥选项 C: baseline 必入 git, 否则 baseline 漂移无源."
    )


def test_baseline_files_have_authed_field():
    """每个 baseline 文件必含 authed 字段 (派工 v6 §5 反馈 类 20.84 一致性)"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert len(files) >= 25, f"期望 ≥ 25 baseline, 实际 {len(files)}"

    for f in files:
        content = f.read_text(encoding="utf-8")
        assert "authed:" in content, (
            f"{f.name} 缺 authed 字段 — baseline 必标记登录态/匿名态, "
            f"否则无法识别假绿 (类 20.25 + 类 20.84)."
        )