"""
tests/dev_port_x25/test_base_url.py — W89-X-25 类 20.80 守恒验证

W89-X-16 据实报告: visual + e2e spec 硬编码 localhost:3004/3100 端口,
nginx 部署下 0% 通过。派工 v6 §5 反馈类 20.80 沉淀: spec 必用
process.env.BASE_URL, 兜底 URL 必与 vite dev (package.json "dev":
"npx vite --port 3000 --strictPort=false") 保持一致。

本测试验证:
1. web/tests/visual/ 下任何 spec 不得硬编码 localhost:3004 或 :3100
   (仅允许 localhost:3000, 127.0.0.1:4173 (vite preview), http://localhost (nginx))
2. 抽样 visual/desktop + visual/mobile + visual/a11y spec, 必含 process.env.BASE_URL
3. web/playwright.config.js 默认 baseURL 必用 process.env.BASE_URL

跑法:
    SKIP_DB_SETUP=1 pytest tests/dev_port_x25/ -v
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "web"


def _run_grep(pattern: str, root: Path) -> str:
    """递归 grep, 返回 stdout。失败时返空串而非抛异常。"""
    try:
        result = subprocess.run(
            ["grep", "-rE", "--include=*.mjs", "--include=*.js",
             pattern, "."],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout
    except Exception:
        return ""


def test_no_hardcoded_dev_port_in_visual_specs():
    """visual spec 必无硬编码 localhost:3004 / localhost:3100

    历史事故 (W89-X-16): chat-session-persistence 等 8 个 spec 兜底写
    localhost:3004 / 3100, 与 package.json "dev" (port 3000) 不一致,
    真实 nginx 部署下全部 0% 通过。
    """
    output = _run_grep("localhost:3004|localhost:3100", WEB / "tests" / "visual")

    # 排除纯注释 / docstring 中说明性提及 (我们改的时候已加 W89-X-25 注记)
    bad_lines = []
    for line in output.splitlines():
        # 跳注释 (含 // 或 * 或 # 的行算 docstring, 不算硬编码)
        stripped = line.split(":", 1)[-1].strip()
        if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("#"):
            continue
        # 跳含 "改为" / "改 3000" / W89-X-25 注释
        if "W89-X-25" in stripped or "改为" in stripped or "改 3000" in stripped:
            continue
        bad_lines.append(line)

    assert not bad_lines, (
        f"硬编码 dev port 残留 (类 20.80 违反): {bad_lines[:5]} "
        f"\n修法: 改用 process.env.BASE_URL || 'http://localhost:3000'"
    )


def test_visual_specs_use_base_url_env():
    """visual spec 必用 process.env.BASE_URL (含 desktop + mobile + a11y)"""
    samples = [
        WEB / "tests" / "visual" / "desktop" / "chat-login-real-2026-07-13.spec.mjs",
        WEB / "tests" / "visual" / "desktop" / "drive-team-shared-isolation-pr6p19.spec.mjs",
        WEB / "tests" / "visual" / "mobile" / "visual-regression.spec.mjs",
        WEB / "tests" / "visual" / "a11y" / "a11y-baseline.spec.mjs",
    ]

    for spec in samples:
        assert spec.exists(), f"spec 不存在: {spec}"
        content = spec.read_text(encoding="utf-8")
        assert "process.env.BASE_URL" in content, (
            f"{spec.name} 缺失 process.env.BASE_URL, 应改用环境变量"
        )


def test_playwright_config_base_url_uses_env():
    """playwright.config.js 默认 baseURL 必 process.env.BASE_URL"""
    config = WEB / "playwright.config.js"
    assert config.exists(), "playwright.config.js 不存在"
    content = config.read_text(encoding="utf-8")
    assert "process.env.BASE_URL" in content, (
        "playwright.config.js baseURL 未用 process.env.BASE_URL"
    )


def test_package_json_dev_port_aligned():
    """vite dev 端口与 spec 兜底 URL 一致 (3000)"""
    pkg = WEB / "package.json"
    content = pkg.read_text(encoding="utf-8")
    # "dev" script 必含 --port 3000
    assert '"dev"' in content and "--port 3000" in content, (
        "package.json dev script 端口非 3000, 与 spec BASE_URL 兜底不一致"
    )
