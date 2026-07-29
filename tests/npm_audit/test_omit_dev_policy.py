"""W88-C-2: npm audit --omit=dev 生产链门禁 e2e.

W87-X-4c 留下 75 moderate。W88-C-2 调研结论 (类 20.44):

- 73/75 属于 `hint` (webhint) devDependency 子树 —— 纯 dev 工具链,
  不进 `web/dist` 生产 bundle, 由 `--omit=dev` 豁免。
- 2/75 是真生产依赖: `dompurify` + `echarts`。
  * dompurify 3.4.7 → 3.4.12 (在 ^3.4.7 semver 内, 仅动 lockfile) → 已清零
  * echarts 需 major 6.1.0 (破坏性), 留 W89 排期

因此本文件的门禁口径:
- `--omit=dev` 下 high == 0 且 critical == 0 —— 硬门禁
- `--omit=dev` 下 moderate 允许 <= ECHARTS_WAIVER 个 (当前 1 = echarts)
  一旦新增生产 moderate 会**立即变红**, 不会被 waiver 静默吞掉。

派工 v6 §1.2: 环境缺失 (无 npm / 无网络) 必须 skip 而非伪装 PASS。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"

NPM = shutil.which("npm") or shutil.which("npm.cmd")

# 生产链已知未修 moderate: echarts (需 major 6.1.0, 留 W89)
# 这是**上限**而非期望值 —— 修好 echarts 后应下调为 0。
ECHARTS_WAIVER = 1


def _run_audit(*extra: str) -> dict:
    if NPM is None:
        pytest.skip("npm 不在 PATH, 跳过 npm audit 门禁")
    assert WEB_DIR.is_dir(), f"缺失 web 目录: {WEB_DIR}"
    assert (WEB_DIR / "package-lock.json").is_file(), "缺失 web/package-lock.json"

    result = subprocess.run(
        [NPM, "audit", "--json", *extra],
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",  # Windows 默认 gbk 会在 advisory 文本上炸
        errors="replace",
        timeout=600,
    )
    # 有漏洞时 exit code 非 0 但 JSON 有效; 只有拿不到 JSON 才算环境问题
    if not (result.stdout or "").strip():
        pytest.skip(f"npm audit 无输出 (可能无网络): {(result.stderr or '')[:200]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - 环境异常分支
        pytest.skip(f"npm audit 输出非法 JSON: {exc}")


@pytest.fixture(scope="module")
def prod_audit() -> dict:
    """生产依赖树 (--omit=dev) 的 audit 结果。"""
    return _run_audit("--omit=dev")


def _severity_of(data: dict, sev: str) -> list[str]:
    return sorted(
        name
        for name, item in data.get("vulnerabilities", {}).items()
        if item.get("severity") == sev
    )


def test_prod_audit_json_valid(prod_audit: dict):
    """--omit=dev 的 audit JSON 必须含 vulnerabilities 段。"""
    assert "vulnerabilities" in prod_audit


def test_no_critical_in_production_tree(prod_audit: dict):
    """生产链 critical 必须为 0。"""
    offenders = _severity_of(prod_audit, "critical")
    assert not offenders, f"生产链存在 critical 漏洞: {offenders}"


def test_no_high_in_production_tree(prod_audit: dict):
    """生产链 high 必须为 0。"""
    offenders = _severity_of(prod_audit, "high")
    assert not offenders, f"生产链存在 high 漏洞: {offenders}"


def test_production_moderate_within_waiver(prod_audit: dict):
    """生产链 moderate 不得超过已知 waiver (echarts, 留 W89)。

    负向对照 (类 20.23): 若有人新引入一个生产 moderate 依赖,
    计数会 > ECHARTS_WAIVER 直接变红, 不会被 waiver 静默吞掉。
    """
    offenders = _severity_of(prod_audit, "moderate")
    assert len(offenders) <= ECHARTS_WAIVER, (
        f"生产链 moderate {len(offenders)} 个 > waiver {ECHARTS_WAIVER}: {offenders}"
    )


def test_dompurify_cleared_from_production_tree(prod_audit: dict):
    """dompurify 已升到 3.4.12 (semver ^3.4.7 内), 不应再出现在生产 audit。"""
    offenders = _severity_of(prod_audit, "moderate") + _severity_of(prod_audit, "low")
    assert "dompurify" not in offenders, (
        "dompurify 重新出现漏洞 —— 检查 package-lock.json 是否被回滚到 3.4.7"
    )


def test_hint_devdeps_are_excluded_by_omit_dev(prod_audit: dict):
    """webhint 子树必须被 --omit=dev 完全排除 (豁免论证的核心前提)。

    若 hint 出现在生产树, 说明它被误挪进 dependencies, 豁免论证失效。
    """
    names = set(prod_audit.get("vulnerabilities", {}))
    leaked = sorted(n for n in names if n == "hint" or n.startswith("@hint/"))
    assert not leaked, f"hint 子树泄漏进生产依赖树, --omit=dev 豁免失效: {leaked}"
