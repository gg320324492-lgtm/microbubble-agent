"""tests/axe_violation_x19/test_no_real_violation.py — W91-X-19 真违规 axe rule 修门禁

背景 (派工纪律 3 "真登录态, 匿名态 0 violations 是假绿"):
  W89-P-6 / W89-X-29 sync 的 25 个 baseline .txt 全部是**匿名态** —
  `authed: no   redirected-to-login: yes`, 扫的是 /login 登录页而不是目标路由,
  只有 3 处 color-contrast. W91-X-19 用真 TEST_TOKEN 跑同一 config, 实测:

    01-chat          color-contrast ×26 + scrollable-region-focusable ×1
    02-drive         color-contrast ×9  + scrollable-region-focusable ×1
    03-mobile-chat   color-contrast ×26 + scrollable-region-focusable ×1
    04-task-trash    color-contrast ×4
    05-file-comments color-contrast ×7
    ── color-contrast 合计 72, 而非派工 brief 写的 6.

  派工 brief 还写了 "aria-command-name ×1" —— 真登录态**实测 0 命中**
  (W89-X-20 #4 已给 DesktopDriveView 3 个 icon-only toggle 补 aria-label,
  cherry-pick 进本分支后不再复现). 据实上报, 不为凑 brief 数字造违规.

本文件的门禁 (静态, 不依赖跑 playwright):
  1. variables.css 必须含 W91-X-19 light 修补段 + 3 个新 token
  2. 每个新 token 的色值必须真过 WCAG AA 4.5:1 (本文件自算对比度, 不信注释)
  3. 72 处 color-contrast 的 5 类根因选择器必须都被覆盖

为什么不在这里跑 playwright:
  跑一次 5 路由 × 5 project 需要 nginx dist 与源码同步. 而 base main 上
  `npm run build` 有 **pre-existing** 失败 (src/views/admin/RAGEvalPanel.vue:24
  `"Play" is not exported by @element-plus/icons-vue` — cb5c98498 引入, 与本任务
  无关, 干净 main 上同样失败), dist 无法重建. 故真跑验证用
  `page.addStyleTag()` 注入本段 CSS 完成 (见 memory 文件的真跑记录:
  color-contrast 72 → 0), 本文件锁源码不回退.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VARIABLES_CSS = REPO / "web" / "src" / "assets" / "variables.css"

# W91-X-19 段起始锚点
SEGMENT_MARK = "W91-X-19: light mode a11y contrast 真修"

# axe 实测背景色 (真登录态 desktop-chrome 命中的全部底色)
BACKGROUNDS = {
    "#ffffff": "card / 主内容底",
    "#fff8f5": "--color-bg-warm 暖底",
    "#fff0ed": "--color-primary-bg 激活底 (最差)",
    "#fef5f1": "sidebar 底",
    "#f5f7fa": "--color-bg-page",
    "#fdf6ec": "--color-warning-bg",
}

WCAG_AA_NORMAL = 4.5


def _relative_luminance(hex_color: str) -> float:
    """WCAG 2.1 相对亮度 (https://www.w3.org/TR/WCAG21/#dfn-relative-luminance)"""
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 对比度 (1.0 ~ 21.0)"""
    lum_a, lum_b = _relative_luminance(fg), _relative_luminance(bg)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.fixture(scope="module")
def css_text() -> str:
    assert VARIABLES_CSS.exists(), f"variables.css 不存在: {VARIABLES_CSS}"
    return VARIABLES_CSS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def x19_segment(css_text: str) -> str:
    """只取 W91-X-19 段, 避免匹配到 W89-X-20 的 dark 段"""
    assert SEGMENT_MARK in css_text, "variables.css 缺 W91-X-19 light 修补段"
    return css_text[css_text.index(SEGMENT_MARK) :]


def _token_value(segment: str, token: str) -> str:
    """从 :root 块里读 token 的 hex 值"""
    m = re.search(rf"{re.escape(token)}\s*:\s*(#[0-9a-fA-F]{{6}})\s*;", segment)
    assert m, f"W91-X-19 段里找不到 token 定义: {token}"
    return m.group(1).lower()


# ---------------------------------------------------------------- 对比度真算


def test_text_secondary_passes_aa_on_every_background(x19_segment):
    """--color-text-secondary 是 72 处违规里最大的一类 (#909399 全线 2.78~3.08 fail).

    提暗后必须在**所有** axe 实测过的底色上都 ≥ 4.5:1 — 尤其是最差的
    #fff0ed (会话激活态暖底).
    """
    value = _token_value(x19_segment, "--color-text-secondary")
    assert value != "#909399", "--color-text-secondary 仍是原值 #909399 (2.78~3.08, fail AA)"

    failures = {
        bg: round(contrast_ratio(value, bg), 2)
        for bg in BACKGROUNDS
        if contrast_ratio(value, bg) < WCAG_AA_NORMAL
    }
    assert not failures, (
        f"--color-text-secondary={value} 在这些底色上仍 < {WCAG_AA_NORMAL}:1 → {failures}"
    )


def test_primary_text_token_passes_aa(x19_segment):
    """--color-primary-text: 主色 #FF7A5C 当文字用永远 2.56 (fail).

    新 token 必须在白底 + 主色浅底上都过 AA.
    """
    value = _token_value(x19_segment, "--color-primary-text")
    for bg in ("#ffffff", "#fff0ed", "#fff8f5"):
        ratio = contrast_ratio(value, bg)
        assert ratio >= WCAG_AA_NORMAL, (
            f"--color-primary-text={value} on {bg} = {ratio:.2f} < {WCAG_AA_NORMAL}"
        )


def test_primary_strong_carries_white_text(x19_segment):
    """--color-primary-strong 是实底色, 上面压白字 — 白字对它必须过 AA.

    原 --color-primary #FF7A5C 上压白字只有 2.56.
    """
    value = _token_value(x19_segment, "--color-primary-strong")
    ratio = contrast_ratio("#ffffff", value)
    assert ratio >= WCAG_AA_NORMAL, (
        f"white on --color-primary-strong={value} = {ratio:.2f} < {WCAG_AA_NORMAL}"
    )


def test_warning_text_token_passes_aa(x19_segment):
    """--color-warning-text: #E6A23C on #FDF6EC = 2.04 是全场最差的一处."""
    value = _token_value(x19_segment, "--color-warning-text")
    ratio = contrast_ratio(value, "#fdf6ec")
    assert ratio >= WCAG_AA_NORMAL, (
        f"--color-warning-text={value} on #fdf6ec = {ratio:.2f} < {WCAG_AA_NORMAL}"
    )


def test_no_regression_to_failing_colors(x19_segment):
    """负向对照 (类 20.23 'e2e 必含负向对照'):

    W91-X-19 段里不允许再出现这些**已证明 fail AA** 的色值当文字色.
    """
    banned = {
        "#909399": "text-secondary 原值, 2.78~3.08",
        "#ff7a5c": "主色, 当文字 2.56",
        "#e6a23c": "warning 原值, on #fdf6ec 仅 2.04",
        "#c0c4cc": "placeholder, on 白底仅 1.74",
    }
    lowered = x19_segment.lower()
    for color, why in banned.items():
        # 允许出现在注释里 (说明"原值是多少"), 只禁出现在 color: 声明的值位置
        bad = re.findall(rf"color\s*:\s*{re.escape(color)}\s*[;!]", lowered)
        assert not bad, f"W91-X-19 段把 fail AA 的 {color} ({why}) 用作 color 值: {bad}"


# ---------------------------------------------------------------- 覆盖面


@pytest.mark.parametrize(
    "selector,rule_source",
    [
        ("#chat-jump-to-top", "01-chat: #ff7a5c on #ffffff = 2.56"),
        (".mode-option.active", "01-chat: ThinkingModeSwitch 选中项 2.56"),
        (".el-menu-item.is-active", "01/02: 侧栏激活项 white on #ff7a5c = 2.56"),
        (".new-btn-text", "01-chat: 新对话按钮白字 2.56"),
        ('.el-breadcrumb__item[aria-current="page"]', "02-drive: 面包屑当前页 2.56"),
        (".trash-hint", "04-task-trash: #e6a23c on #fdf6ec = 2.04"),
        (".countdown-urgent", "04-task-trash: 倒计时 warning"),
        (".dfcv-tab-btn.active", "05-file-comments: #ff7a5c on #fff0ed = 2.31"),
        (".dci-hint", "05-file-comments: #c0c4cc on #ffffff = 1.74"),
        (".dfcv-empty .empty-hint", "05-file-comments: opacity .75 合成 #8e9097 = 2.97"),
    ],
)
def test_each_measured_violation_selector_is_covered(x19_segment, selector, rule_source):
    """每一处真登录态实测到的违规选择器都必须在 W91-X-19 段里被处理.

    这是"真修"与"改个 token 就说修好了"的分界线 — 有些违规来自 scoped style
    直接写 var(--color-primary) 当文字色, 光提暗 text-secondary 治不了.
    """
    assert selector in x19_segment, f"未覆盖实测违规选择器 {selector} (来源: {rule_source})"


def test_dark_mode_segment_untouched(css_text):
    """W89-X-20 的 dark 段必须原样保留 — 本任务只修 light, 不动 dark."""
    assert "W89-X-20: dark mode a11y contrast 修补" in css_text, "W89-X-20 dark 段被删了"
    assert '[data-theme="dark"] .el-button--primary > span' in css_text, (
        "W89-X-20 dark 段内容被改动"
    )


def test_x19_segment_declared_after_dark_segment(css_text):
    """层叠顺序: light 修补段必须在 dark 段之后, 但只用 :root 前缀,
    不带 [data-theme="dark"] — 保证不覆盖 dark 主题的规则."""
    dark_idx = css_text.index("W89-X-20: dark mode a11y contrast 修补")
    light_idx = css_text.index(SEGMENT_MARK)
    assert light_idx > dark_idx, "W91-X-19 段必须在 W89-X-20 段之后 (层叠顺序)"

    segment = css_text[light_idx:]
    assert '[data-theme="dark"]' not in segment, (
        "W91-X-19 段不应含 [data-theme=\"dark\"] 选择器 — dark 归 W89-X-20 管"
    )
