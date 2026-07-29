"""
W87-E-1 k6 脚本存在性 + 关键段验证 (硬门禁).

不真跑 k6 binary. 只验证:
1. 3 个 .js 文件存在
2. 每个文件头部含 'k6' keyword
3. 每个文件含 'thresholds:' 段 (派工 v6 §5 反馈 #类 20.26 门禁)
4. npm scripts 中 3 个 load:* 存在 (web/package.json)

跑法:
    pytest tests/k6/ -v

预期全 PASS.
"""

import os
import re
from pathlib import Path

import pytest


# ============================================================
# 路径常量
# ============================================================

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_K6_DIR = REPO_ROOT / "scripts" / "k6"
WEB_PACKAGE_JSON = REPO_ROOT / "web" / "package.json"

CHAT_STREAM = SCRIPTS_K6_DIR / "chat_stream.js"
WS_NOTIFICATIONS = SCRIPTS_K6_DIR / "ws_notifications.js"
DRIVE_COLLAB = SCRIPTS_K6_DIR / "drive_collab.js"

ALL_SCRIPTS = [CHAT_STREAM, WS_NOTIFICATIONS, DRIVE_COLLAB]


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def package_json() -> dict:
    """读 web/package.json."""
    import json
    with open(WEB_PACKAGE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 1. 文件存在
# ============================================================

@pytest.mark.parametrize("script_path", ALL_SCRIPTS)
def test_k6_script_exists(script_path: Path):
    """3 个 .js 文件必须存在."""
    assert script_path.exists(), f"k6 script not found: {script_path}"
    assert script_path.is_file(), f"k6 script is not a regular file: {script_path}"


# ============================================================
# 2. 头部含 'k6' keyword (import or comment)
# ============================================================

@pytest.mark.parametrize("script_path", ALL_SCRIPTS)
def test_k6_script_header_has_k6_keyword(script_path: Path):
    """每个脚本头部 (前 20 行) 必须含 'k6' 标识 — 装机命令或 import 头."""
    content = script_path.read_text(encoding="utf-8")
    header = "\n".join(content.splitlines()[:20])
    assert "k6" in header.lower(), (
        f"{script_path.name} header missing 'k6' keyword:\n{header}"
    )


# ============================================================
# 3. 含 'thresholds:' 段 (派工 v6 §5 反馈 #类 20.26 门禁)
# ============================================================

@pytest.mark.parametrize("script_path", ALL_SCRIPTS)
def test_k6_script_has_thresholds_block(script_path: Path):
    """每个脚本必须含 thresholds 段 — 无阈值的压测基线无意义."""
    content = script_path.read_text(encoding="utf-8")
    # 匹配 'thresholds:' (k6 options.thresholds 段头)
    assert re.search(r"^\s*thresholds\s*:", content, re.MULTILINE), (
        f"{script_path.name} missing 'thresholds:' block (派工 v6 §5 反馈 #类 20.26 门禁)"
    )


# ============================================================
# 4. 阈值含 p(95) 量化指标 (不是空 dict)
# ============================================================

@pytest.mark.parametrize("script_path", ALL_SCRIPTS)
def test_k6_script_thresholds_have_quantitative_metric(script_path: Path):
    """thresholds 段不能是空 dict, 至少含 p(95)<N> 形式."""
    content = script_path.read_text(encoding="utf-8")
    assert re.search(r"p\(\d+\)\s*<", content), (
        f"{script_path.name} thresholds block must contain p(95)<Nms style metric"
    )


# ============================================================
# 5. npm scripts 包含 3 个 load:* 命令
# ============================================================

EXPECTED_LOAD_SCRIPTS = ["load:chat", "load:ws", "load:drive"]


@pytest.mark.parametrize("load_script", EXPECTED_LOAD_SCRIPTS)
def test_npm_load_script_exists(load_script: str, package_json: dict):
    """web/package.json 的 scripts 段必须含 load:chat / load:ws / load:drive."""
    scripts = package_json.get("scripts", {})
    assert load_script in scripts, (
        f"web/package.json scripts 缺 {load_script!r}, 现有: {sorted(scripts.keys())}"
    )
    # 验证 load:* 命令调的是 k6 run + 我们的脚本
    cmd = scripts[load_script]
    assert "k6 run" in cmd, f"{load_script} 命令应含 'k6 run', 实际: {cmd!r}"
    assert "scripts/k6/" in cmd, f"{load_script} 命令应引用 scripts/k6/, 实际: {cmd!r}"


# ============================================================
# 6. 不动 web/package.json 老 scripts / deps
# ============================================================

EXPECTED_OLD_SCRIPTS = {
    "dev",
    "build",
    "build:raw",
    "build:pwa",
    "postbuild:fix-manifest",
    "preview",
    "test:unit",
    "test:watch",
    "lint:css",
    "lint:css:fix",
    "test:visual",
    "test:visual:update",
}


def test_package_json_old_scripts_preserved(package_json: dict):
    """web/package.json 现有 scripts 必须全部保留 — 不动老路径."""
    scripts = set(package_json.get("scripts", {}).keys())
    missing = EXPECTED_OLD_SCRIPTS - scripts
    assert not missing, f"web/package.json 现有 scripts 被删: {missing}"


def test_package_json_load_scripts_count(package_json: dict):
    """新增 load:* 脚本数量 = 3, 不多不少 (防止漏写或多写)."""
    load_scripts = [k for k in package_json.get("scripts", {}).keys() if k.startswith("load:")]
    assert len(load_scripts) == 3, (
        f"web/package.json load:* 脚本数量应为 3, 实际: {load_scripts}"
    )
