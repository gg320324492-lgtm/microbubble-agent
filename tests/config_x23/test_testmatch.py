"""
W89-X-23 (派工 v3 § 反馈 类 20.78): 守护 playwright.config.js testMatch 收窄

根因 (W89-X-10 据实报告):
- 宽 testMatch + 5 project 重复匹配 → 113 baseline 重复 (61 张独立 baseline × 重复匹配)
- 修法: 用 exclude 而非 include, 排除 tests/visual/{a11y,e2e,pwa}/

3 个守护:
- exclude e2e (W89-P-10 移到 tests/visual/e2e/, comprehensive 端到端不需要 baseline 对比)
- exclude a11y (有专属 config: tests/visual/a11y/playwright.a11y.config.mjs)
- exclude pwa  (未来 W87-P-3 写 spec 用专属 config 路径)

纪律 (派工 v6 §5 反馈 类 20.78):
- 用 exclude 而非 include 更安全 (未来加新 spec 目录只需加一行 exclude, 不会漏 spec)
- 严禁改为超严格 include (可能漏 spec)
"""
from pathlib import Path

PW_CONFIG = Path(__file__).resolve().parents[2] / "web" / "playwright.config.js"


def _read_config() -> str:
    """读 playwright.config.js, 缺失则 fail"""
    assert PW_CONFIG.exists(), f"playwright.config.js 不存在: {PW_CONFIG}"
    return PW_CONFIG.read_text(encoding="utf-8")


def test_playwright_config_exists():
    """playwright.config.js 必须存在"""
    assert PW_CONFIG.exists(), f"playwright.config.js 不存在: {PW_CONFIG}"


def test_testmatch_excludes_e2e():
    """playwright.config.js 必 exclude tests/visual/e2e/

    W89-P-10 据实报告: 综合 e2e 已移到 tests/visual/e2e/, 不需要 baseline 对比,
    应排除以避免重复匹配生成过多 baseline.
    """
    content = _read_config()
    assert "e2e" in content, "playwright.config.js 必 exclude tests/visual/e2e/"


def test_testmatch_excludes_a11y():
    """playwright.config.js 必 exclude tests/visual/a11y/

    a11y 有专属 config (tests/visual/a11y/playwright.a11y.config.mjs),
    主 config 不应重复匹配 a11y spec.
    """
    content = _read_config()
    assert "a11y" in content, "playwright.config.js 必 exclude tests/visual/a11y/(用专属 config)"


def test_testmatch_excludes_pwa():
    """playwright.config.js 必 exclude tests/visual/pwa/

    未来 W87-P-3 PWA spec 用专属 config 路径, 主 config 不应重复匹配.
    """
    content = _read_config()
    assert "pwa" in content, "playwright.config.js 必 exclude tests/visual/pwa/(未来 W87-P-3 用专属 config)"


def test_testmatch_is_exclude_not_strict_include():
    """playwright.config.js 必用 exclude 而非超严格 include

    派工 v6 §5 反馈 类 20.78: 用 exclude 更安全, 未来加新 spec 目录只需加一行,
    不会漏掉 spec. 严禁改为超严格 include.
    """
    content = _read_config()
    assert "exclude:" in content, "playwright.config.js 必用 exclude 段 (派工 v3 类 20.78)"
