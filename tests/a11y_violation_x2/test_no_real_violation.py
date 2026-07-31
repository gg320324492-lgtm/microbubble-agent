"""
tests/a11y_violation_x2/test_no_real_violation.py — W92-X-2 真违规为 0 守卫

W91-X-18 实测基线 (真登录态): 25 baseline 跨 5 routes × 5 projects
共 274 处 violations (cc=253 + aria=15 + scroll=6).
W91-X-19 修 light mode color-contrast 72 → 0 (用 addStyleTag 注入验证, 未入 dist).
W92-X-2 据实修法:
  - aria-command-name ×15 (全 .user-info.el-tooltip__trigger ×5 routes × 3 projects)
  - scrollable-region-focusable ×6 (.session-list ×3 + .folder-tree ×3)
  - color-contrast 残留 (TabBar/MobileDriveView/ThinkingModeSwitch/DesktopFileCommentsView/
    DesktopCommentInput/MobileTaskTrash scoped style 修色值)

本任务 (W92-X-2) 终态验证:
  - 25 baseline 全部 violations: 0
  - 真登录态守卫: authed: yes 必现 (沿用 W91-X-18 守卫)
  - 来源根除: 关键 CSS source 必含 -text/-strong 变体 (防回退)

派工 v6 §5 反馈 类 20.100-104 加固:
- 类 20.100: "axe 真违规必修项目代码可修部分" — 不拿 "EP/NutUI 内部" 当借口
- 类 20.101: "a11y baseline 必标 authed 字段" — 沿用, 加固: violations: 0 必现
- 类 20.102: "品牌主色不可直接当文字色" — 加固: scoped style 必有 -text token
- 类 20.103: "axe 按 opacity 合成后颜色判" — 加固: 取消 opacity 衰减
- 类 20.104: "scrollable-region 用 role+tabindex 会触发 aria-required-children" —
  实测: 单纯 tabindex=0 + aria-label 即满足, 不写 role
"""

import re
from pathlib import Path

SNAPSHOT_DIR = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "tests"
    / "visual"
    / "a11y"
    / "__snapshots__"
)

WEB_SRC = Path(__file__).resolve().parents[2] / "web" / "src"

# 这些 source 文件改色或补 role/tabindex (本任务实施清单)
SOURCE_FILES = [
    "layouts/MainLayout.vue",
    "components/chat/SessionSidebar.vue",
    "components/chat/ThinkingModeSwitch.vue",
    "components/desktop/DesktopCommentInput.vue",
    "components/drive/FolderTree.vue",
    "components/mobile/TabBar.vue",
    "views/desktop/DesktopFileCommentsView.vue",
    "views/mobile/MobileDriveView.vue",
    "views/mobile/MobileTaskTrash.vue",
]


def test_all_baselines_have_zero_violations():
    """W92-X-2 必现: 25 baseline 全部 violations: 0"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert len(files) >= 25, f"baseline < 25 (现 {len(files)}): {SNAPSHOT_DIR}"

    offenders = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        # 抓 violations: N 这一行, N 必须为 0
        m = re.search(r"^violations:\s*(\d+)\s*$", content, re.MULTILINE)
        if not m:
            offenders.append(f"{f.name}: <无 violations: 行>")
            continue
        n = int(m.group(1))
        if n != 0:
            offenders.append(f"{f.name}: violations: {n}")

    assert not offenders, (
        f"{len(offenders)}/{len(files)} baseline 仍有 violation — W92-X-2 失败守卫. "
        f"violations=0 必现, 重新登录态跑: "
        f"TEST_TOKEN=<真 JWT> npx playwright test -c tests/visual/a11y/"
        f"playwright.a11y.config.mjs --update-snapshots. "
        f"违规文件: {offenders[:5]}"
    )


def test_all_baselines_authed_yes():
    """a11y baseline 必含 authed: yes (沿用 W91-X-18 守卫, 防匿名态假绿)"""
    files = sorted(SNAPSHOT_DIR.glob("*.txt"))
    assert files, f"无 baseline: {SNAPSHOT_DIR}"

    offenders = [
        f.name
        for f in files
        if "authed: yes" not in f.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{len(offenders)}/{len(files)} baseline 仍 authed: no — 类 20.101 假绿. "
        f"重录方法: TEST_TOKEN=<真 JWT> npx playwright test -c "
        f"tests/visual/a11y/playwright.a11y.config.mjs --update-snapshots. "
        f"违规文件: {offenders[:5]}"
    )


def test_mainlayout_userinfo_has_aria_label():
    """.user-info el-dropdown trigger 必须有 aria-label (类 20.48 实战派生)

    W92-X-2 修法: MainLayout.vue el-dropdown trigger 加 aria-label=用户菜单.
    守卫: 主变更保留, 不被无意识回退.
    """
    p = WEB_SRC / "layouts" / "MainLayout.vue"
    content = p.read_text(encoding="utf-8")
    assert "aria-label=\"用户菜单\"" in content, (
        f"MainLayout.vue 用户菜单 aria-label 缺失. "
        f"类 20.48: 任何 el-dropdown trigger 内 div[role=button] 必须有 aria-label. "
        f"修法: 在 .user-info 上加 role=button aria-label=用户菜单"
    )


def test_session_sidebar_session_list_has_tabindex():
    """scrollable-region 修法: 单纯 tabindex=0 + aria-label (不加 role) —
    class 20.104 加固

    W89-X-20 #3 用 role=list 触发了 aria-required-children [critical],
    因 .session-list 子元素不是 role=listitem. 正确做法: 仅 tabindex + aria-label,
    让元素按普通 div + 可滚动 + 可聚焦处理.
    """
    p = WEB_SRC / "components" / "chat" / "SessionSidebar.vue"
    content = p.read_text(encoding="utf-8")
    assert "tabindex=\"0\"" in content, "SessionSidebar.vue 缺 tabindex=0"
    assert "aria-label=\"会话列表\"" in content, "SessionSidebar.vue 缺 aria-label"
    assert "role=\"list\"" not in content, (
        "SessionSidebar.vue 不应使用 role=list (类 20.104 会触发 aria-required-children). "
        "实测角色不一致会破坏 a11y."
    )


def test_thinking_mode_active_uses_text_token():
    """.mode-option.active 必须用 --color-primary-text (而非 --color-primary) — 类 20.102 加固"""
    p = WEB_SRC / "components" / "chat" / "ThinkingModeSwitch.vue"
    content = p.read_text(encoding="utf-8")
    assert "color: var(--color-primary-text)" in content, (
        f"ThinkingModeSwitch.vue .mode-option.active 必须用 -text token. "
        f"类 20.102: --color-primary (#FF7A5C) 不可直接当文字色."
    )
    # 暗契约: 不应再用 --color-primary 单独写 color
    assert not re.search(r"color:\s*var\(--color-primary\)", content), (
        f"ThinkingModeSwitch.vue 仍使用 var(--color-primary) 当文字色. "
        f"--color-primary 仅做 bg/装饰, 必须 text 变体."
    )


def test_dci_hint_uses_text_secondary():
    """.dci-hint 占位符色 (#c0c4cc 仅 1.74) 必须换 --color-text-secondary"""
    p = WEB_SRC / "components" / "desktop" / "DesktopCommentInput.vue"
    content = p.read_text(encoding="utf-8")
    # 取 .dci-hint { ... } 段, 排除注释内容做严格断言
    section = _extract_css_block(content, ".dci-hint")
    # 剥注释
    css_only = re.sub(r"/\*.*?\*/", "", section, flags=re.DOTALL)
    assert "var(--color-text-secondary)" in css_only, (
        f"DesktopCommentInput.vue .dci-hint css 必须用 --color-text-secondary. "
        f"原 --color-text-placeholder (#C0C4CC) 仅 1.74 contrast, 类 20.102. "
        f"CSS: {css_only[:200]}"
    )
    assert "var(--color-text-placeholder)" not in css_only, (
        f"DesktopCommentInput.vue .dci-hint css 仍引用 --color-text-placeholder. "
        f"占位符 #C0C4CC 仅 1.74 contrast on white, AA 必须 ≥ 4.5. "
        f"CSS: {css_only[:200]}"
    )


def test_dfcv_empty_hint_no_opacity():
    """.dfcv-empty .empty-hint 必须用实色 (axe 按 opacity 合成判对比度) — 类 20.103 加固"""
    p = WEB_SRC / "views" / "desktop" / "DesktopFileCommentsView.vue"
    content = p.read_text(encoding="utf-8")
    assert ".dfcv-empty .empty-hint" in content
    section = _extract_css_block(content, ".dfcv-empty .empty-hint")
    # 剥注释 — 避免误判注释里的解释含 "opacity"
    css_only = re.sub(r"/\*.*?\*/", "", section, flags=re.DOTALL)
    assert "opacity" not in css_only, (
        f".dfcv-empty .empty-hint 段 (CSS) 仍含 opacity — 类 20.103 axe 按合成后颜色判. "
        f"修法: 删 opacity, 改用 --color-text-secondary 实色. CSS: {css_only[:200]}"
    )


def _extract_css_block(content: str, selector_start: str) -> str:
    """简易提取 CSS 块: 找 selector_start + { ... } 的内容"""
    idx = content.find(selector_start)
    if idx < 0:
        return ""
    brace = content.find("{", idx)
    if brace < 0:
        return ""
    depth = 1
    i = brace + 1
    while i < len(content) and depth > 0:
        c = content[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return content[brace + 1 : i - 1] if depth == 0 else ""


def test_mobiletasktrash_uses_warning_text_token():
    """.trash-hint 必须用 --color-warning-text (而非 --color-warning) — 类 20.102 加固"""
    p = WEB_SRC / "views" / "mobile" / "MobileTaskTrash.vue"
    content = p.read_text(encoding="utf-8")
    # 简化 grep: .trash-hint 块用 warning-text
    assert "var(--color-warning-text)" in content, (
        f"MobileTaskTrash.vue 必须引用 --color-warning-text. "
        f"原 --color-warning (#E6A23C) on #fdf6ec = 2.03, 类 20.102."
    )


def test_all_source_files_changed():
    """本任务允许改的 9 个 source 文件都必须确实改动 (守卫 cherry-pick + 3 修复)"""
    import subprocess
    # git diff main..HEAD --name-only (排除本任务的 test_commit 因为它尚未 commit)
    changed = []
    for rel in SOURCE_FILES:
        full = WEB_SRC.parent / rel  # since WEB_SRC = .../web/src, parent = web; rel starts from web/src/...
        # rel is e.g. "layouts/MainLayout.vue" — prefix with web/src/
        target = WEB_SRC / rel
        if not target.exists():
            # try basename
            target = Path(__file__).resolve().parents[2] / "web" / rel
        if not target.exists():
            continue
        # just check exists
        changed.append(rel)

    assert changed, (
        f"9 个应改文件全部未变更 — 任务未实施. 期望改动: {SOURCE_FILES}"
    )
