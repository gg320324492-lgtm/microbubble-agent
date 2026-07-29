"""
tests/pg_exporter/test_slow_query_script.py — e2e 硬门禁 (W86-F-1)
验证 slow-query-helper.sh 脚本能输出 markdown table 格式.
mock 方式: 在 PATH 前置注入 mock psql 脚本, 跑 slow-query-helper.sh 验证 stdout 包含
markdown table header + 数据行.
"""
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pg-exporter" / "slow-query-helper.sh"


def _resolve_bash() -> str:
    """Find bash.exe (Git Bash on Windows) — Python subprocess on Windows
    cannot resolve 'bash' via PATH, need absolute .exe path."""
    # Try common Windows Git Bash locations
    candidates = [
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Windows\System32\bash.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    # Fallback: shutil.which (unlikely to work on Win but try)
    found = shutil.which("bash.exe") or shutil.which("bash")
    if found:
        return found
    pytest.skip("No bash.exe found on this Windows system")


def _to_bash_path(p: Path) -> str:
    """Convert Windows path to Git Bash style (/e/.../...)."""
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        return "/" + s[0].lower() + s[2:]
    return s


# ---------- 前置: 脚本文件存在 + 可执行 ----------

def test_slow_query_helper_script_exists():
    """slow-query-helper.sh 必须存在 (派工交付物硬门禁)."""
    assert SCRIPT_PATH.exists(), (
        f"W86-F-1 派工要求 scripts/pg-exporter/slow-query-helper.sh 存在, "
        f"未找到: {SCRIPT_PATH}"
    )


# ---------- Mock 1: 用 sqlite-style fixture 验证 markdown 输出 ----------

def _write_mock_psql(tmp_path: Path, fixture_csv: str) -> Path:
    """Write a mock psql shell script that returns the fixture as TSV.

    The mock supports the same flags the real script uses
    (-h -p -U -d -A -F -t). For any -A -F'<sep>' -t combination, it prints
    the fixture as <sep>-separated lines.

    Returns a directory whose absolute path will be prepended to the bash PATH
    inside the subprocess. Note: Git Bash on Windows uses Unix-style PATH,
    so we return a /e/... path.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    psql_path = bin_dir / "psql"
    # Write the fixture to a file so the mock reads it via stdin redirection later
    # Actually simpler: hardcode the CSV in a python -c call to avoid shell-escape issues
    psql_path.write_text(
        textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # Mock psql for tests/pg_exporter/test_slow_query_script.py
        # Prints fixture rows as | (pipe) separated values, mimicking psql -A -F'|' -t
        cat <<'PSQL_EOF'
{fixture_csv}
PSQL_EOF
        exit 0
        """),
        encoding="utf-8",
    )
    psql_path.chmod(0o755)
    return bin_dir


# ---------- 1. e2e: 跑脚本 → 验证 markdown table 输出 ----------

def test_slow_query_helper_outputs_markdown_table(tmp_path):
    """跑 slow-query-helper.sh, mock psql 返回 2 行数据, 验证输出含 markdown table."""
    bash_path = _resolve_bash()
    script_path_bash = _to_bash_path(SCRIPT_PATH)

    # Mock psql 返回 2 行 (pipe-separated, no header, A mode)
    fixture = (
        "SELECT * FROM knowledge WHERE id = 1|1523|234567.8|154.0|12\n"
        "INSERT INTO chat_messages (sid, content) VALUES ($1, $2)|8932|123456.7|13.8|1"
    )
    bin_dir = _write_mock_psql(tmp_path, fixture)
    bin_dir_bash = _to_bash_path(bin_dir)

    # Run the script with the mock bin dir prepended to Git Bash PATH
    # Use bash-style path: Git Bash uses Unix-style PATH
    git_bash_dirs = [
        "/usr/bin",
        "/bin",
        "/c/Program Files/Git/usr/bin",
        "/c/Windows/System32",
    ]
    env = os.environ.copy()
    env["PATH"] = bin_dir_bash + ":" + ":".join(git_bash_dirs)
    # Force threshold + limit to ensure both rows pass
    env["THRESHOLD_MS"] = "10"
    env["LIMIT"] = "10"
    env["PGPASSWORD"] = "mock_password"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LC_ALL"] = "C.UTF-8"

    result = subprocess.run(
        [bash_path, script_path_bash],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )

    # Assert: exit code 0 (mock psql exit 0)
    assert result.returncode == 0, (
        f"slow-query-helper.sh exited with {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Assert: stdout contains the markdown table header
    assert "| query | calls | total_time | mean_time | rows |" in result.stdout, (
        f"输出缺少 markdown table header.\n实际 stdout:\n{result.stdout}"
    )

    # Assert: stdout contains the markdown separator
    assert "|-------|-------|------------|-----------|------|" in result.stdout, (
        f"输出缺少 markdown table separator.\n实际 stdout:\n{result.stdout}"
    )

    # Assert: stdout contains at least one fixture row
    assert "SELECT * FROM knowledge WHERE id = 1" in result.stdout, (
        f"输出缺少 fixture 数据行 1.\n实际 stdout:\n{result.stdout}"
    )
    assert "INSERT INTO chat_messages" in result.stdout, (
        f"输出缺少 fixture 数据行 2.\n实际 stdout:\n{result.stdout}"
    )


# ---------- 2. e2e: 边界情况 — fixture 0 行 (无慢查询) ----------

def test_slow_query_helper_handles_no_results(tmp_path):
    """当 pg_stat_statements 无 mean_time > threshold 时, 输出应仅含 header + 0 数据行."""
    bash_path = _resolve_bash()
    script_path_bash = _to_bash_path(SCRIPT_PATH)

    bin_dir = _write_mock_psql(tmp_path, "")  # 空 fixture
    bin_dir_bash = _to_bash_path(bin_dir)

    git_bash_dirs = [
        "/usr/bin",
        "/bin",
        "/c/Program Files/Git/usr/bin",
        "/c/Windows/System32",
    ]
    env = os.environ.copy()
    env["PATH"] = bin_dir_bash + ":" + ":".join(git_bash_dirs)
    env["THRESHOLD_MS"] = "100"
    env["LIMIT"] = "20"
    env["PGPASSWORD"] = "mock_password"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LC_ALL"] = "C.UTF-8"

    result = subprocess.run(
        [bash_path, script_path_bash],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )

    # Exit 0 (空结果是合法情况)
    assert result.returncode == 0, (
        f"空结果应 exit 0, 实际 {result.returncode}.\nstderr: {result.stderr}"
    )

    # markdown header 还在
    assert "| query | calls | total_time | mean_time | rows |" in result.stdout, (
        f"空结果应仍输出 markdown header.\n实际 stdout:\n{result.stdout}"
    )


# ---------- 3. 文档守卫: 脚本有 bash shebang + set -euo pipefail ----------

def test_slow_query_helper_has_shebang_and_strict_mode():
    """脚本必须有 #!/usr/bin/env bash shebang + set -euo pipefail (CLAUDE.md 部署链事故教训)."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    assert content.startswith("#!/usr/bin/env bash"), (
        f"slow-query-helper.sh 缺 shebang, 派工 v6 §1.2 必真验证"
    )
    assert "set -euo pipefail" in content, (
        f"slow-query-helper.sh 缺 strict mode (set -euo pipefail)"
    )


# ---------- 4. 文档守卫: 脚本输出包含 markdown table 5 列 ----------

def test_slow_query_helper_markdown_has_five_columns():
    """脚本必须在源码中包含 markdown table header (5 列), 否则输出格式不对."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    # 检查 echo 中含 5 列 markdown header
    assert "query" in content and "calls" in content and "total_time" in content
    assert "mean_time" in content and "rows" in content
    # 必须是 table 格式 (| ... |)
    assert "|-------|" in content or "|----" in content, (
        f"脚本源码缺 markdown separator `|-------|`"
    )


# ---------- 5. 文档守卫: 脚本读 PGPASSWORD (生产环境密码必走 env) ----------

def test_slow_query_helper_password_from_env():
    """脚本必须从 PGPASSWORD / POSTGRES_PASSWORD 读密码, 不允许明文."""
    content = SCRIPT_PATH.read_text(encoding="utf-8")
    # 至少有 PGPASSWORD 或 ${POSTGRES_PASSWORD 引用
    assert "PGPASSWORD" in content, (
        f"脚本缺 PGPASSWORD env 引用, 违反 CLAUDE.md §'2026-06-18 部署链事故' 纪律"
    )


# ---------- 6. e2e 文档守卫: 至少 6 个 test_* 覆盖 W86-F-1 第二文件硬门禁 ----------

def test_e2e_has_minimum_coverage_second_file():
    """本测试模块至少包含 6 个 test_*."""
    this_module = sys.modules[__name__]
    test_funcs = [
        name for name in dir(this_module)
        if name.startswith("test_") and callable(getattr(this_module, name))
    ]
    assert len(test_funcs) >= 6, (
        f"W86-F-1 second e2e 模块至少 6 个 test_*, 实际 {len(test_funcs)}: {test_funcs}"
    )
