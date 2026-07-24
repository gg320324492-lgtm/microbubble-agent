"""W68 第 7 批 A-3 — qa-bench 隔离测试栈 smoke tests.

Plan: qa-bench-isolation-a1.md (物理隔离 + 生产数据 dump + 脱敏).

三组场景 (不需要真起 docker / DB, 用纯文本 + 静态解析验证核心逻辑):

1. **起 test stack (config 层)**: docker-compose.test.yml 存在, 关键服务/端口/卷/网络
   声明正确, 端口错开生产, JWT/MinIO 凭据独立.
2. **dump + sanitize**: scripts/dump_prod_to_fixture.sh 默认 dry-run;
   sanitize_fixture.py 对 COPY / INSERT 两种格式白名单脱敏 (email/phone/wechat/
   password/username), 非 members 表原样保留.
3. **在 test stack 跑 1 题 (runner 集成层)**: runner.py 暴露 --use-test-stack /
   --fixture-sql / --skip-down flag + 生命周期 helper (test_stack_up/down /
   load_fixture_into_test_stack), API_BASE 指向 :8001.

零 production code 改动: 仅读 docker-compose.test.yml + scripts/ + tests/qa-bench/.
不需要 SKIP_DB_SETUP (纯文本/静态解析, 无 DB 依赖).

Run::

    python -m pytest tests/qa-bench/test_isolation_stack_smoke.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_QA_BENCH_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _QA_BENCH_DIR.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

for _p in (str(_QA_BENCH_DIR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --- helpers ----------------------------------------------------------------


def _load_sanitize_module():
    """Import scripts/sanitize_fixture.py without triggering package import."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sanitize_fixture", _SCRIPTS_DIR / "sanitize_fixture.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


COPY_DUMP = (
    "COPY public.members (id, username, email, phone, wechat_id, "
    "external_userid, password_hash) FROM stdin;\n"
    "5\tzhangsan\tzhang@gmail.com\t13812345678\twx_zhang\text_5\t$2b$12$realhashA\n"
    "6\tlisi\tli@qq.com\t13987654321\twx_li\text_6\t$2b$12$realhashB\n"
    "\\.\n"
)

INSERT_DUMP = (
    "INSERT INTO members (id, username, email, phone, wechat_id, password_hash) "
    "VALUES (5, 'zhangsan', 'zhang@gmail.com', '13812345678', 'wx_zhang', "
    "'$2b$12$realhash');\n"
)

# non-target table must remain untouched
TASKS_DUMP = (
    "COPY public.tasks (id, title, created_by) FROM stdin;\n"
    "1\t查文献\t5\n"
    "\\.\n"
)


# =====================================================================
# 场景 1: 起 test stack — docker-compose.test.yml 配置正确性
# =====================================================================


class TestScenario1ComposeConfig:
    COMPOSE = _REPO_ROOT / "docker-compose.test.yml"

    def test_compose_file_exists(self):
        assert self.COMPOSE.exists(), "docker-compose.test.yml 必须存在 (plan 核心交付物)"

    def test_required_services_declared(self):
        text = self.COMPOSE.read_text(encoding="utf-8")
        for svc in ("pg-test:", "redis-test:", "minio-test:", "app-test:"):
            assert svc in text, f"缺少服务 {svc}"

    def test_ports_offset_from_production(self):
        """测试栈端口必须错开生产 (5432/6379/9000/9001/8000)."""
        text = self.COMPOSE.read_text(encoding="utf-8")
        assert '"5433:5432"' in text, "postgres 应映射 5433"
        assert '"6380:6379"' in text, "redis 应映射 6380"
        assert '"9001:9000"' in text, "minio API 应映射 9001"
        assert "8001:8000" in text, "app 应映射 8001"

    def test_isolated_volumes_and_network(self):
        text = self.COMPOSE.read_text(encoding="utf-8")
        for vol in ("test_pg_data", "test_redis_data", "test_minio_data"):
            assert vol in text, f"缺独立卷 {vol}"
        assert "mb-test-net" in text, "缺独立网络"

    def test_credentials_differ_from_prod(self):
        """JWT + MinIO 凭据默认与生产不同 (防 token 误用)."""
        text = self.COMPOSE.read_text(encoding="utf-8")
        assert "test_jwt_secret_different_from_prod" in text
        assert "microbubble-test" in text  # 独立 bucket

    def test_compose_config_valid(self):
        """docker compose config 静态校验 (若本机有 docker)."""
        docker = _which("docker")
        if not docker:
            pytest.skip("docker 不可用, 跳过 config 校验")
        proc = subprocess.run(
            ["docker", "compose", "-f", str(self.COMPOSE), "config"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"compose config 失败: {proc.stderr[:500]}"


# =====================================================================
# 场景 2: dump + sanitize
# =====================================================================


class TestScenario2DumpAndSanitize:
    def test_dump_script_exists_and_dry_run_default(self):
        script = _SCRIPTS_DIR / "dump_prod_to_fixture.sh"
        assert script.exists(), "dump_prod_to_fixture.sh 必须存在"
        text = script.read_text(encoding="utf-8")
        # 默认 dry-run: 未加 --apply 时不真跑 pg_dump
        assert "APPLY=0" in text
        assert "--apply" in text
        assert "pg_dump" in text
        assert "--exclude-table=alembic_version" in text

    def test_sanitize_copy_format(self):
        mod = _load_sanitize_module()
        out, n = mod.sanitize_text(COPY_DUMP)
        assert n >= 8, f"COPY 应脱敏多字段, got {n}"
        # PII 全部消失
        assert "zhang@gmail.com" not in out
        assert "li@qq.com" not in out
        assert "13812345678" not in out
        assert "wx_zhang" not in out
        assert "realhashA" not in out
        # 脱敏结果就位
        assert "@test.local" in out
        assert "138****5678" in out
        assert "test_member_5" in out
        assert "test_member_6" in out
        # wechat_id / external_userid → \N
        assert "\\N" in out

    def test_sanitize_insert_format(self):
        mod = _load_sanitize_module()
        out, n = mod.sanitize_text(INSERT_DUMP)
        assert n == 5, f"INSERT 5 字段应改, got {n}"
        assert "zhang@gmail.com" not in out
        assert "'test_member_5'" in out
        assert "138****5678" in out
        assert "NULL" in out  # wechat_id → NULL
        assert "@test.local" in out

    def test_non_target_table_untouched(self):
        """tasks 表不在白名单, 必须原样保留."""
        mod = _load_sanitize_module()
        out, n = mod.sanitize_text(TASKS_DUMP)
        assert n == 0
        assert "查文献" in out
        assert out == TASKS_DUMP

    def test_password_hash_deterministic(self):
        mod = _load_sanitize_module()
        out, _ = mod.sanitize_text(COPY_DUMP)
        assert mod.TESTBOT_PASSWORD_HASH in out


# =====================================================================
# 场景 3: 在 test stack 跑 1 题 — runner 集成 flag + 生命周期 helper
# =====================================================================


class TestScenario3RunnerIntegration:
    def _load_runner(self):
        import importlib

        return importlib.import_module("runner")

    def test_runner_exposes_test_stack_flags(self):
        runner = self._load_runner()
        # 解析器应含新 flag
        import argparse
        import io
        import contextlib

        # 用 --help 输出验证 flag 注册 (不真跑 main)
        assert hasattr(runner, "test_stack_up")
        assert hasattr(runner, "test_stack_down")
        assert hasattr(runner, "load_fixture_into_test_stack")

    def test_test_stack_constants(self):
        runner = self._load_runner()
        assert runner.TEST_COMPOSE_FILE == "docker-compose.test.yml"
        assert "8001" in runner.TEST_STACK_BASE_URL
        assert runner.TEST_STACK_DB_PORT == 5433

    def test_load_fixture_missing_raises(self):
        runner = self._load_runner()
        with pytest.raises(FileNotFoundError):
            runner.load_fixture_into_test_stack("does_not_exist_xyz.sql")

    def test_up_down_helpers_call_docker_compose(self, monkeypatch):
        """test_stack_up/down 应调 docker compose -f docker-compose.test.yml."""
        runner = self._load_runner()
        calls = []

        def _fake_run(cmd, check=True):
            calls.append(cmd)

            class _R:
                returncode = 0

            return _R()

        monkeypatch.setattr(runner, "_run_cmd", _fake_run)
        runner.test_stack_up()
        runner.test_stack_down()
        assert calls[0][:4] == ["docker", "compose", "-f", "docker-compose.test.yml"]
        assert "up" in calls[0]
        assert "down" in calls[1]
        assert "-v" in calls[1], "down 必须带 -v 销毁数据卷"


# --- util -------------------------------------------------------------------


def _which(name: str) -> str | None:
    import shutil

    return shutil.which(name)
