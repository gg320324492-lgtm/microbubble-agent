"""W91-X-20: glitchtip crash loop 修 e2e。

W90-X-14 据实: glitchtip-dev-1 在 Restarting crash loop (RestartCount=865)。
根因: DATABASE_URL 指向 `glitchtip` 库但该库从未建 →
      `FATAL: database "glitchtip" does not exist` → Django exit 1 → 无限 restart。

本套件 3 组断言:
  1. 容器不在 Restarting (crash loop 已解)
  2. /_health/ 可达 (真起来了, 不只是进程活着)
  3. ensure-db 脚本存在且幂等 (防回归: 换机器/重建 volume 不再踩)

环境不可用时 skip 而非 fail — 无 docker 的 CI runner 不该红。
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENSURE_DB_SCRIPT = REPO_ROOT / "scripts" / "glitchtip-ensure-db.sh"

# 两个 glitchtip 实例: 生产栈 127.0.0.2:8000, dev 栈 localhost:8001。
GLITCHTIP_HEALTH_URLS = (
    "http://127.0.0.2:8000/_health/",
    "http://localhost:8001/_health/",
)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ["docker", "info"], capture_output=True, text=True, timeout=60
    )
    return result.returncode == 0


def _glitchtip_ps() -> str:
    """docker ps -a 的 glitchtip 行 (含已退出容器, 才能看到 Restarting)。"""
    result = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=glitchtip",
            "--format",
            "{{.Names}}\t{{.Status}}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"docker ps failed: {result.stderr}"
    return result.stdout.strip()


def test_no_glitchtip_container_in_restart_loop():
    """任何 glitchtip 容器都不该处于 Restarting。

    这是本任务的核心断言: 修之前 dev-1 是 `Restarting (1)`, 修之后是 `Up`。
    注意必须逐行判定 — 两个实例同时存在时, 整串 stdout 做子串匹配会被
    健康那个的 `Up` 掩盖掉崩溃那个的 `Restarting` (类 20.24 精神)。
    """
    if not _docker_available():
        pytest.skip("docker unavailable")

    output = _glitchtip_ps()
    if not output:
        pytest.skip("no glitchtip container on this host")

    restarting = [
        line for line in output.splitlines() if "Restarting" in line
    ]
    assert not restarting, (
        "glitchtip container(s) stuck in crash loop:\n"
        + "\n".join(restarting)
        + "\n提示: 多半是 `glitchtip` 数据库未建, 跑 scripts/glitchtip-ensure-db.sh"
    )


def test_at_least_one_glitchtip_up():
    """至少一个 glitchtip 实例处于 Up。"""
    if not _docker_available():
        pytest.skip("docker unavailable")

    output = _glitchtip_ps()
    if not output:
        pytest.skip("no glitchtip container on this host")

    up = [line for line in output.splitlines() if "\tUp" in line]
    assert up, f"no glitchtip container is Up:\n{output}"


def test_glitchtip_health_endpoint_returns_200():
    """起来的 glitchtip 必须 /_health/ 200。

    只要有任一 endpoint 返 200 即通过 — 两个栈不保证同时在跑。
    全都连不上 (curl 000) 时 skip: 说明本机没跑 glitchtip, 不是回归。
    """
    if shutil.which("curl") is None:
        pytest.skip("curl unavailable")

    codes = {}
    for url in GLITCHTIP_HEALTH_URLS:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20", url],
            capture_output=True,
            text=True,
            timeout=60,
        )
        codes[url] = result.stdout.strip()

    if all(code in ("", "000") for code in codes.values()):
        pytest.skip(f"no glitchtip endpoint reachable: {codes}")

    assert "200" in codes.values(), f"glitchtip health not 200: {codes}"


def test_ensure_db_script_exists_and_is_idempotent_by_construction():
    """建库脚本必须存在, 且幂等 (先查 pg_database 再建)。

    CREATE DATABASE 不支持 IF NOT EXISTS, 所以幂等只能靠先查后建。
    这里静态校验脚本形态, 不真连 db — 保证脚本无条件重跑安全。
    """
    assert ENSURE_DB_SCRIPT.is_file(), f"missing {ENSURE_DB_SCRIPT}"

    content = ENSURE_DB_SCRIPT.read_text(encoding="utf-8")
    assert "pg_database" in content, "脚本必须先查 pg_database 才幂等"
    assert "CREATE DATABASE" in content, "脚本必须真建库"
    assert "set -euo pipefail" in content, "脚本必须 fail loud"


def test_compose_glitchtip_points_at_dedicated_database():
    """compose 的 DATABASE_URL 必须指向独立 `glitchtip` 库 (不与 microbubble 混用)。

    锁住本次根因的另一半: 库名一旦被改回 microbubble, 表会串。
    """
    for compose_name in ("docker-compose.yml", "docker-compose.dev.yml"):
        compose_path = REPO_ROOT / compose_name
        assert compose_path.is_file(), f"missing {compose_path}"
        content = compose_path.read_text(encoding="utf-8")
        assert (
            "@db:5432/glitchtip" in content
        ), f"{compose_name}: glitchtip DATABASE_URL 必须指向独立 glitchtip 库"
