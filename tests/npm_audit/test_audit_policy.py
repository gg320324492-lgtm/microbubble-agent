"""W88-C-2: web/.npmrc audit 政策静态校验 (类 20.44).

不跑 npm, 纯读文件 —— 无网络也必须 PASS。

核心断言 (含负向对照, 类 20.23):
1. `audit-level=high` 存在 —— moderate 不阻断 CI
2. `omit=dev` **不得**出现在 .npmrc —— 实测它会同时作用于 install/ci,
   导致 devDependencies 完全不装, 摧毁 build 与测试链路。
   dev-only 豁免只能用命令行 flag `npm audit --omit=dev`。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NPMRC = REPO_ROOT / "web" / ".npmrc"
PACKAGE_JSON = REPO_ROOT / "web" / "package.json"


def _directives() -> dict[str, str]:
    """解析 .npmrc 为 key=value, 忽略注释与空行。"""
    out: dict[str, str] = {}
    for raw in NPMRC.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def test_npmrc_exists():
    assert NPMRC.is_file(), f"缺失 web/.npmrc: {NPMRC}"


def test_audit_level_is_high():
    """audit-level=high —— 只有 high/critical 阻断。"""
    assert _directives().get("audit-level") == "high", (
        f"web/.npmrc 缺 audit-level=high, 实际: {_directives()}"
    )


def test_npmrc_does_not_set_omit_dev():
    """负向对照: omit=dev 若写进 .npmrc 会破坏 devDependencies 安装。

    W88-C-2 实测: 带 `omit=dev` 的 .npmrc 跑 `npm install` 后
    devDependencies 目录完全不存在 → vite/vitest/playwright 全丢。
    """
    directives = _directives()
    assert "omit" not in directives, (
        f"web/.npmrc 出现 omit={directives.get('omit')} —— 会破坏 devDependencies 安装, "
        "dev 豁免请改用命令行 `npm audit --omit=dev`"
    )


def test_npmrc_documents_the_omit_dev_hazard():
    """.npmrc 必须留注释解释为何不能写 omit=dev (防后人好心加回)。"""
    text = NPMRC.read_text(encoding="utf-8")
    assert "omit=dev" in text, ".npmrc 应在注释中说明 omit=dev 的禁用原因"
    assert re.search(r"--omit=dev", text), ".npmrc 应指明命令行 --omit=dev 才是正确豁免方式"


def test_devdependencies_still_declared():
    """hint 仍应留在 devDependencies (豁免论证的前提: 它不是生产依赖)。"""
    import json

    pkg = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    assert "hint" in pkg.get("devDependencies", {}), (
        "hint 必须留在 devDependencies —— 若挪进 dependencies, --omit=dev 豁免立即失效"
    )
    assert "hint" not in pkg.get("dependencies", {}), (
        "hint 不得出现在 dependencies (会进生产 bundle)"
    )
