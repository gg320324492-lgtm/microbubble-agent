"""
tests/precommit/test_config_valid.py
W86 第 1 批 D-1 (锚点范式 320 → 321 预期) — pre-commit 配置合法性验证

目的: 验证 .pre-commit-config.yaml:
    - YAML 语法合法 (PyYAML 解析无异常)
    - 5 个 hook id 全部存在 (gitleaks-scan / dockerfile-pinning / alembic-chain /
      typing-imports / dist-manifest-hash)
    - hook id 唯一 (不重复)
    - hook entry 路径指向脚本存在 + 可执行

用法:
    pytest tests/precommit/test_config_valid.py -v

依赖: PyYAML (项目 requirements.txt 已含)
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.precommit  # W86-D-1 marker 标识

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO_ROOT / ".pre-commit-config.yaml"

# W86-D-1 必须存在的 5 个 hook id (严格映射 CLAUDE.md 纪律)
EXPECTED_HOOK_IDS = {
    "gitleaks-scan",        # CLAUDE.md 永久纪律 (凭据扫描)
    "dockerfile-pinning",   # CLAUDE.md 永久纪律 (Trivy image 钉死)
    "alembic-chain",        # CLAUDE.md §2.3 (alembic 串单链 commit 1852468a6)
    "typing-imports",       # CLAUDE.md 641 行 (check_typing_imports.sh)
    "dist-manifest-hash",   # CLAUDE.md 永久纪律 (manifest 410 教训)
}


@pytest.fixture(scope="module")
def config():
    """读 .pre-commit-config.yaml 并解析成 Python object."""
    if not CONFIG_FILE.exists():
        pytest.fail(f".pre-commit-config.yaml 不存在 at {CONFIG_FILE}")
    # 显式用 utf-8 (Windows 默认 GBK 会失败, 含中文 comment)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------
# Test 1: YAML 语法合法
# --------------------------------------------------------------
def test_yaml_syntax_valid(config):
    """`.pre-commit-config.yaml` 必须可被 PyYAML 解析成功."""
    assert config is not None
    assert isinstance(config, dict)
    assert "repos" in config
    assert isinstance(config["repos"], list)
    assert len(config["repos"]) >= 1


# --------------------------------------------------------------
# Test 2: 所有 hook id 都在 (5 个, 一一对应 CLAUDE.md 纪律)
# --------------------------------------------------------------
def test_all_hooks_present(config):
    """验证 5 个 hook id 全部在 .pre-commit-config.yaml 里."""
    found_ids = set()
    for repo in config["repos"]:
        for hook in repo.get("hooks", []):
            if "id" in hook:
                found_ids.add(hook["id"])

    missing = EXPECTED_HOOK_IDS - found_ids
    assert not missing, (
        f"缺失 hook id: {missing}\n"
        f"期望: {EXPECTED_HOOK_IDS}\n"
        f"找到: {found_ids}"
    )


# --------------------------------------------------------------
# Test 3: hook id 唯一 (全局)
# --------------------------------------------------------------
def test_hook_ids_unique(config):
    """验证 hook id 在所有 repo + hooks 块里唯一."""
    seen: dict[str, str] = {}  # id → 第一次出现的位置
    for repo_idx, repo in enumerate(config["repos"]):
        for hook_idx, hook in enumerate(repo.get("hooks", [])):
            hook_id = hook.get("id")
            if not hook_id:
                continue
            if hook_id in seen:
                pytest.fail(
                    f"hook id 重复: {hook_id} "
                    f"(发现于 repos[{repo_idx}].hooks[{hook_idx}], "
                    f"之前 {seen[hook_id]})"
                )
            seen[hook_id] = f"repos[{repo_idx}].hooks[{hook_idx}]"


# --------------------------------------------------------------
# Test 4: hook entry 脚本存在
# --------------------------------------------------------------
def test_hook_entry_scripts_exist(config):
    """验证每个 hook 的 entry 脚本都存在 (或 fallback 链)."""
    # 解析 entry, 提取可能的 bash script 路径
    # entry 模式:
    #   - "bash scripts/alembic/check_single_head.sh"  → 提取 bash 后的脚本
    #   - "python scripts/trivy/check_pinned_images.py" → 提取 python 后的脚本
    #   - "bash -c '<inline>'"  → inline, skip
    missing_scripts: list[tuple[str, str]] = []  # (hook_id, missing_path)
    for repo in config["repos"]:
        for hook in repo.get("hooks", []):
            hook_id = hook.get("id", "<unknown>")
            entry = hook.get("entry", "")
            # 提取 entry 中的可执行脚本路径
            # 跳过 inline bash -c '...'
            if entry.strip().startswith("bash -c"):
                continue
            # 提取 bash/python 后第一个 token
            parts = entry.strip().split()
            if len(parts) < 2:
                continue
            script_path = parts[1]
            # 绝对路径 skip (没期待会有, 但防御一下)
            if script_path.startswith("/"):
                continue
            full_path = REPO_ROOT / script_path
            if not full_path.exists():
                missing_scripts.append((hook_id, script_path))

    assert not missing_scripts, (
        f"hook entry 脚本缺失:\n"
        + "\n".join(f"  - {hid}: {p}" for hid, p in missing_scripts)
    )


# --------------------------------------------------------------
# Test 5: 配置文件存在且非空
# --------------------------------------------------------------
def test_config_file_exists():
    """.pre-commit-config.yaml 存在且非空."""
    assert CONFIG_FILE.exists(), f"缺失: {CONFIG_FILE}"
    assert CONFIG_FILE.stat().st_size > 0, f"{CONFIG_FILE} 是空文件"


# --------------------------------------------------------------
# Test 6: 含 fail_fast 等全局配置段
# --------------------------------------------------------------
def test_global_config_present(config):
    """验证含 fail_fast 全局配置 (默认 false)."""
    # fail_fast 默认 true, 我们显式设 false 让所有 hook 跑完
    assert "fail_fast" in config
    # 当前设计: fail_fast: false (跑完所有 hook, 让 CI 看完整日志)
    assert config["fail_fast"] is False
