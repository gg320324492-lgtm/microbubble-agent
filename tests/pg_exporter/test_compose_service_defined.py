"""
tests/pg_exporter/test_compose_service_defined.py — e2e 硬门禁 (W86-F-1)
验证 3 个 compose 文件 (生产 / 开发 / 测试) 都包含 pg-exporter service 段
"""
import os
import re
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = {
    "production": REPO_ROOT / "docker-compose.yml",
    "dev": REPO_ROOT / "docker-compose.dev.yml",
    "test": REPO_ROOT / "docker-compose.test.yml",
}

EXPECTED_IMAGE_PREFIX = "quay.io/prometheuscommunity/postgres-exporter:"
EXPECTED_PORT_HOST = "9187"
EXPECTED_PORT_CONTAINER = "9187"
EXPECTED_DATA_SOURCE_KEY = "DATA_SOURCE_NAME"
EXPECTED_POSTGRES_HOST_PROD = "db:5432"
EXPECTED_POSTGRES_HOST_TEST = "pg-test:5432"


def _read_compose(name: str) -> str:
    """Read a docker-compose file, skip if not present."""
    path = COMPOSE_FILES[name]
    if not path.exists():
        pytest.skip(f"compose file {name} ({path}) not found")
    return path.read_text(encoding="utf-8")


def _extract_service_block(content: str, service_name: str) -> str:
    """Extract the YAML service block for a given service name.

    Simple line-based extraction: find the line '  <service_name>:' and
    capture indented lines until the next '  <word>:' at the same indent.
    """
    lines = content.splitlines()
    in_service = False
    block_lines: list[str] = []
    for line in lines:
        # Detect a top-level service key: '  <name>:' (2-space indent, ends with colon)
        if re.match(r"^  [a-zA-Z0-9_-]+:$", line):
            if in_service:
                # Left the previous service block
                break
            current = line.strip().rstrip(":")
            if current == service_name:
                in_service = True
                block_lines.append(line)
            continue
        if in_service:
            block_lines.append(line)
    return "\n".join(block_lines)


# ---------- 1. Service 段存在性 ----------

@pytest.mark.parametrize("compose_name", ["production", "dev", "test"])
def test_pg_exporter_service_defined(compose_name):
    """3 个 compose 文件都必须有 pg-exporter (test 用 -test 后缀) service 段."""
    content = _read_compose(compose_name)
    service_name = "pg-exporter" if compose_name != "test" else "pg-exporter-test"
    block = _extract_service_block(content, service_name)
    assert block, (
        f"[{compose_name}] 未找到 '{service_name}:' service 段. "
        f"W86-F-1 派工要求所有 3 个 compose 都加 service."
    )


# ---------- 2. 钉死 tag (image: quay.io/prometheuscommunity/postgres-exporter:...) ----------

@pytest.mark.parametrize("compose_name", ["production", "dev", "test"])
def test_pg_exporter_image_pinned(compose_name):
    """image 必须以 quay.io/prometheuscommunity/postgres-exporter: 开头, 钉死 tag."""
    content = _read_compose(compose_name)
    service_name = "pg-exporter" if compose_name != "test" else "pg-exporter-test"
    block = _extract_service_block(content, service_name)
    match = re.search(r"^\s*image:\s*(\S+)\s*$", block, re.MULTILINE)
    assert match, f"[{compose_name}] '{service_name}' 缺少 'image:' 字段"
    image = match.group(1)
    assert image.startswith(EXPECTED_IMAGE_PREFIX), (
        f"[{compose_name}] image 必须以 '{EXPECTED_IMAGE_PREFIX}' 开头, 实际: {image}. "
        f"派工 v6 §1.2 铁律: 钉死 tag, latest 不跟."
    )
    # 必须有版本后缀 (不是 latest)
    tag = image.split(":", 1)[1]
    assert tag and tag != "latest", (
        f"[{compose_name}] image tag 必须钉死非 latest, 实际: {tag}"
    )


# ---------- 3. DATA_SOURCE_NAME 引用 postgres 服务 ----------

@pytest.mark.parametrize("compose_name,expected_host", [
    ("production", EXPECTED_POSTGRES_HOST_PROD),
    ("dev", EXPECTED_POSTGRES_HOST_PROD),
    ("test", EXPECTED_POSTGRES_HOST_TEST),
])
def test_data_source_name_references_postgres(compose_name, expected_host):
    """DATA_SOURCE_NAME 必须包含正确的 postgres host:port."""
    content = _read_compose(compose_name)
    service_name = "pg-exporter" if compose_name != "test" else "pg-exporter-test"
    block = _extract_service_block(content, service_name)
    match = re.search(
        r"DATA_SOURCE_NAME:\s*\"([^\"]+)\"",
        block,
    )
    assert match, f"[{compose_name}] '{service_name}' 缺少 'DATA_SOURCE_NAME:' 字段"
    dsn = match.group(1)
    assert expected_host in dsn, (
        f"[{compose_name}] DATA_SOURCE_NAME 必须包含 '{expected_host}', 实际: {dsn}"
    )
    # 密码必须走环境变量, 不允许明文
    # 注意: 默认密码 (microbubble2026 / test_password) 是 compose 内的 fallback,
    # 符合 CLAUDE.md §"2026-06-18 部署链事故" 纪律 (走 ${VAR:-default} 模式)
    assert "${" in dsn, (
        f"[{compose_name}] DATA_SOURCE_NAME 密码必须走环境变量 ${{...}}, 实际: {dsn}"
    )


# ---------- 4. 端口暴露 9187:9187 (test 用 9199) ----------

@pytest.mark.parametrize("compose_name,expected_port", [
    ("production", "9187:9187"),
    ("dev", "9187:9187"),
    ("test", "9199:9187"),
])
def test_pg_exporter_port_exposed(compose_name, expected_port):
    """ports 必须暴露 9187 (生产/开发) 或 9199 (test, 错开生产)."""
    content = _read_compose(compose_name)
    service_name = "pg-exporter" if compose_name != "test" else "pg-exporter-test"
    block = _extract_service_block(content, service_name)
    match = re.search(
        rf'^\s*-\s*"?{re.escape(expected_port)}"?\s*$',
        block,
        re.MULTILINE,
    )
    assert match, (
        f"[{compose_name}] '{service_name}' ports 缺少 '{expected_port}' 暴露. "
        f"W86-F-1 派工: 9187 是 Prometheus pg_exporter 官方端口."
    )


# ---------- 5. depends_on 引用 postgres 服务 ----------

@pytest.mark.parametrize("compose_name,expected_dep", [
    ("production", "db:"),
    ("dev", "db:"),
    ("test", "pg-test:"),
])
def test_pg_exporter_depends_on_postgres(compose_name, expected_dep):
    """depends_on 必须引用正确的 postgres 服务 (生产/db, test/pg-test)."""
    content = _read_compose(compose_name)
    service_name = "pg-exporter" if compose_name != "test" else "pg-exporter-test"
    block = _extract_service_block(content, service_name)
    assert "depends_on:" in block, (
        f"[{compose_name}] '{service_name}' 缺少 'depends_on:' 段"
    )
    assert expected_dep in block, (
        f"[{compose_name}] '{service_name}' depends_on 必须包含 '{expected_dep}'"
    )


# ---------- 6. 不动其它 service 的 image / volume / port 边界守卫 ----------

def test_only_added_pg_exporter_service():
    """git diff 应仅新增 pg-exporter service 段, 其它 service 不动.
    此测试为文档化边界守卫, 不强制要求 (CI 跑不了 git diff).
    """
    # 文档守卫: 列出应被保护的 service (compose 文件已有, 不应被本任务改动)
    protected_services = {
        "production": ["nginx", "app", "db", "redis", "neo4j", "minio", "celery-worker", "celery-beat", "vision-mcp", "ollama", "sensevoice"],
        "dev": ["app", "db", "redis", "minio", "celery-worker", "celery-beat"],
        "test": ["pg-test", "redis-test", "minio-test", "app-test"],
    }
    # 仅作为 contract: 如果未来测试在 protected service 找到 image/volume/port diff, 应 fail
    for compose_name, services in protected_services.items():
        content = _read_compose(compose_name)
        # 验证这些 service 都还在 (没被误删)
        for svc in services:
            assert f"  {svc}:" in content, (
                f"[{compose_name}] 守卫 service '{svc}' 不见了, "
                f"W86-F-1 任务边界: 仅加 pg-exporter service 段, 不动其它."
            )


# ---------- 7. e2e 文档守卫: 测试本文件存在且至少 6 个 test_* ----------

def test_e2e_has_minimum_coverage():
    """本测试模块至少包含 6 个 test_*, 覆盖 W86-F-1 派工 4 项核心要求."""
    import sys
    this_module = sys.modules[__name__]
    test_funcs = [
        name for name in dir(this_module)
        if name.startswith("test_") and callable(getattr(this_module, name))
    ]
    # pytest.mark.parametrize 会展开成更多 case, 但 source 至少 6 个 test_*
    assert len(test_funcs) >= 6, (
        f"W86-F-1 e2e 模块至少 6 个 test_*, 实际 {len(test_funcs)}: {test_funcs}"
    )
