"""tests/perf/test_hnsw_recall_at_k.py — HNSW bench 入口测试

阶段 A.1 测试 (硬门禁):
- bench 脚本存在且 --help 退出 0
- bench 脚本接受 --param-grid / --table / --k 参数

阶段 A.2 由 test_hnsw_recall_calc.py 单独覆盖.
阶段 A.3 由 tests/integration/test_hnsw_bench_real.py 覆盖 (需 INTEGRATION=1).
"""
import os
import re
import subprocess
import sys

import pytest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BENCH_SCRIPT = os.path.join(REPO_ROOT, "scripts", "bench_hnsw_params.py")
PYTHONPATH_ROOT = REPO_ROOT


def _run_bench_help():
    """跑 bench --help, 强制 PYTHONPATH=REPO_ROOT 让 `from app.config import settings` 可解析."""
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH_ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, BENCH_SCRIPT, "--help"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
        timeout=30,
    )


@pytest.mark.skipif(
    not os.path.isfile(BENCH_SCRIPT),
    reason="bench_hnsw_params.py not yet created (TDD red phase)",
)
def test_bench_script_exists_and_runs_help():
    """bench 脚本存在且 --help 退出 0, 输出含 --param-grid / --table / --k."""
    result = _run_bench_help()
    assert result.returncode == 0, (
        f"bench --help exit {result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    for flag in ("--param-grid", "--table", "--k"):
        # --help 可能转义为短形式 (-p / -t / -k); 接受任一
        long_match = bool(re.search(rf"--{flag.lstrip('-')}\b", result.stdout))
        short_match = bool(re.search(rf"-{flag.lstrip('-')[0]}\b", result.stdout))
        assert long_match or short_match, (
            f"flag {flag!r} missing from bench --help:\n{result.stdout}"
        )


@pytest.mark.skipif(
    not os.path.isfile(BENCH_SCRIPT),
    reason="bench_hnsw_params.py not yet created (TDD red phase)",
)
def test_bench_help_lists_required_table_choices():
    """bench --help 必须列出 3 个合法 --table 值 (knowledge/meetings/members)."""
    result = _run_bench_help()
    assert result.returncode == 0
    out = result.stdout
    for table in ("knowledge", "meetings", "members"):
        assert table in out, f"table choice {table!r} missing from --help:\n{out}"
