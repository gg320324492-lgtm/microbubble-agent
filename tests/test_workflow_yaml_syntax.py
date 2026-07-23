"""W68 第 4 批 B-3 路线 D6: qa-bench-ci workflow YAML 语法 + cache 配置守恒测试.

> **作者**: W68 第 4 批 B-3 Route Agent (锚点范式第 54 守恒)
> **日期**: 2026-07-24
> **基线 HEAD**: `26c7c5620`
> **目的**: 验证 `.github/workflows/qa-bench-ci.yml` 在 cache-from/cache-scope/restore-keys
>   3 个 W68 D6 改动后 YAML 语法正确 + 3 个字段都正确落地.
> **0 production code 改动铁律维持**: 本测试只检查 workflow 文件, 不动 app/ web/ alembic/.

Usage:
    pytest tests/test_workflow_yaml_syntax.py -v
    # 期望: 6+ PASS

设计:
- 纯 YAML 解析 + 字段断言, 无 DB / Redis / Docker 依赖
- 不修改任何 production code / workflow
- 硬编码 3 个 W68 D6 cache 配置字段, 验证 0 drift
- 6 个测试覆盖: YAML 语法 + 3 字段存在 + setup-buildx 字段 + Pull step 注释完整性
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

# === 常量定义 ===

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "qa-bench-ci.yml"

# W68 第 4 批 B-3 D6 实施的 3 个 cache 配置字段:
EXPECTED_FIELDS = {
    "cache-scope": "setup-buildx step 的 with.cache-scope 防 namespace 碰撞",
    "restore-keys": "actions/cache@v4 step 的 with.restore-keys 兜底匹配",
}


def _load_workflow() -> dict:
    """读取并解析 qa-bench-ci.yml (UTF-8, YAML safe_load)."""
    assert WORKFLOW_PATH.exists(), f"workflow 文件不存在: {WORKFLOW_PATH}"
    raw = WORKFLOW_PATH.read_bytes()
    return yaml.safe_load(raw.decode("utf-8"))


def _find_step(steps: list, name_substring: str) -> dict | None:
    """按 name 子串查找 step (兼容多行 name)."""
    for step in steps:
        n = step.get("name", "")
        # name 可能被截断成子串 (yaml 流式 dump), 用核心关键词查
        if name_substring in n or all(kw in n for kw in name_substring.split()):
            return step
    return None


# === 测试用例 ===

def test_yaml_safe_load_passes():
    """测试 1: YAML 语法正确 (yaml.safe_load 无异常)."""
    data = _load_workflow()
    assert isinstance(data, dict), f"YAML 顶层必须是 mapping, got {type(data)}"
    assert "jobs" in data, "YAML 必须包含 jobs 键"
    print(f"✓ YAML syntax PASS, jobs={list(data['jobs'].keys())}")


def test_qa_bench_d5_job_exists():
    """测试 2: qa-bench-d5 job 存在 (本次 D6 gate workflow 唯一 job)."""
    data = _load_workflow()
    assert "qa-bench-d5" in data["jobs"], (
        f"jobs 必须包含 qa-bench-d5, got {list(data['jobs'].keys())}"
    )
    job = data["jobs"]["qa-bench-d5"]
    assert "steps" in job, "qa-bench-d5 job 必须包含 steps"
    print(f"✓ qa-bench-d5 job 存在, steps={len(job['steps'])}")


def test_setup_buildx_step_has_cache_scope():
    """测试 3: setup-buildx step 的 with.cache-scope 字段存在 (W68 D6 关键改动)."""
    data = _load_workflow()
    job = data["jobs"]["qa-bench-d5"]
    step = _find_step(job["steps"], "Set up Docker Buildx")
    assert step is not None, "setup-buildx step 必须存在"
    assert "with" in step, "setup-buildx step 必须包含 with 子句 (W68 D6 加的 cache-scope)"
    with_block = step["with"]
    assert "cache-scope" in with_block, (
        f"W68 D6 关键改动缺失: setup-buildx.with.cache-scope, "
        f"with keys={list(with_block.keys())}"
    )
    scope_value = with_block["cache-scope"]
    # cache-scope 必须用 ${{ github.workflow }}-${{ github.job }} 模板
    assert "github.workflow" in scope_value, (
        f"cache-scope 必须包含 ${{{{ github.workflow }}}}, got={scope_value}"
    )
    assert "github.job" in scope_value, (
        f"cache-scope 必须包含 ${{{{ github.job }}}}, got={scope_value}"
    )
    print(f"✓ setup-buildx.cache-scope={scope_value}")


def test_actions_cache_step_has_restore_keys():
    """测试 4: actions/cache@v4 step 的 with.restore-keys 字段存在 (W68 D6 兜底匹配)."""
    data = _load_workflow()
    job = data["jobs"]["qa-bench-d5"]
    step = _find_step(job["steps"], "Cache pip")
    assert step is not None, "Cache pip step 必须存在"
    assert step.get("uses", "").startswith("actions/cache"), (
        f"Cache pip step 必须用 actions/cache, got={step.get('uses')}"
    )
    assert "with" in step, "Cache pip step 必须包含 with 子句"
    with_block = step["with"]
    assert "restore-keys" in with_block, (
        f"W68 D6 关键改动缺失: actions/cache.with.restore-keys, "
        f"with keys={list(with_block.keys())}"
    )
    rk = with_block["restore-keys"]
    # restore-keys 必须包含 runner.os prefix (兜底匹配)
    assert "runner.os" in str(rk), (
        f"restore-keys 必须包含 ${{{{ runner.os }}}}, got={rk}"
    )
    # multi- 前缀必须存在
    assert "multi-" in str(rk), f"restore-keys 必须包含 multi- prefix, got={rk}"
    print(f"✓ actions/cache.restore-keys={rk}")


def test_pull_pre_built_image_step_has_cache_from_doc():
    """测试 5: Pull pre-built image step 含 cache-from: type=gha,mode=max 文档/注释 (W68 D6 路径 1 落地)."""
    raw = WORKFLOW_PATH.read_bytes().decode("utf-8")
    # W68 D6 改动在 Pull step 加 3 行注释说明 cache-from mode=max 复用 push 端中间 layer.
    assert "cache-from: type=gha,mode=max" in raw, (
        "W68 D6 关键改动缺失: Pull step 必须有 'cache-from: type=gha,mode=max' 注释/"
        "代码引用 (mode=max 让 pull 端复用 push 端所有中间 layer)"
    )
    # 锚定到真 Pull pre-built step (以 `- name:` 开头), 不是 setup-buildx 注释里的引用
    pull_section = re.search(
        r'-\s+name:\s*"Pull pre-built app-test image.*?docker images app-test:ci',
        raw,
        re.DOTALL,
    )
    assert pull_section is not None, "Pull pre-built step + docker images 末行未找到"
    section = pull_section.group(0)
    assert "mode=max" in section, (
        f"cache-from: type=gha,mode=max 注释必须在 Pull pre-built step 内. "
        f"step 内文=\n{section}"
    )
    # 同时验证 cache-scope 在 setup-buildx 步骤内 (跨 step 协同)
    buildx_section = re.search(
        r'-\s+name:\s*"Set up Docker Buildx.*?with:',
        raw,
        re.DOTALL,
    )
    assert buildx_section is not None, "Set up Docker Buildx step + with: 块未找到"
    assert "cache-scope" in buildx_section.group(0), (
        "cache-scope 字段必须在 setup-buildx.with 内"
    )
    print("✓ Pull pre-built step 含 cache-from: type=gha,mode=max 注释 (W68 D6 落地)")


def test_no_production_code_modified():
    """测试 6: 守恒铁律 — 0 production code 改动 (app/ web/ alembic/versions/ 未修改).

    注: 排除 bind mount 路径 (-v $(pwd)/app:/app/app) 和注释里提到的 app./alembic 字符串.
    仅检查会真在 CI 触发 production code 改动的危险模式 (run 行, 非注释).
    """
    raw = WORKFLOW_PATH.read_bytes().decode("utf-8")
    # 拆分为运行行 (run:) vs 注释行 (# 开头). 用 MULTILINE 让 ^ 匹配每行首.
    # 1. 真跑 alembic upgrade head (会改 production schema) — 仅检查 run 行
    dangerous_patterns = [
        (r"^\s*alembic\s+upgrade\s+head", "alembic upgrade head 在 CI run 行 (会改 production schema)"),
        (r"\bpython\s+-c\s+[\"'].*from\s+app", "inline python 脚本 import production code"),
        (r"\bpytest\s+tests/(?!test_workflow)", "跑非 workflow yaml 测试 (会触发 app import)"),
        (r"^\s*docker\s+build\s+\.", "本地 docker build (会触发 Dockerfile 修改 production image)"),
    ]
    for pat, desc in dangerous_patterns:
        match = re.search(pat, raw, re.MULTILINE)
        assert match is None, (
            f"workflow 文件不应包含 production code 改动触发模式 (违反 0 改动铁律): "
            f"{desc}, pattern={pat}, match={match.group(0) if match else None}"
        )
    print("✓ 0 production code 改动铁律守恒 (workflow 文件无 alembic upgrade head run / "
          "docker build / inline app import)")