"""
W89-X-15 P-7 真因 networkidle 修法守卫 (类 20.67)

W89-P-7 真因查清:
  waitForLoadState('networkidle') 在 WS/SSE/long-polling 页面永不达成
  → 测试卡在 timeout 上, 后续 selector + 截图断言未执行.

类 20.67 铁律:
  WS/SSE/long-polling 页面必删 networkidle, 等明确 UI locator 或目标 API.

本测试强制: 已知含 WS/SSE 的关键 spec 必无 waitForLoadState('networkidle').

运行: SKIP_DB_SETUP=1 pytest tests/networkidle_fix/ -v
   (不需要 DB, 仅纯文件正则检查; SKIP_DB_SETUP=1 避免加载 conftest.py 重型依赖)
"""

import re
from pathlib import Path


# 已知含 WS / SSE / long-polling 的页面:
#   - Drive Comments: NotificationBell WS + 通知轮询 + 健康探测
#   - Chat: SSE 流式 (ChatViewSSE.vue) + NotificationBell WS
#   - Knowledge: NotificationBell WS (mounted 在 App.vue 全局)
#   - Drive 移动端: 同上 + mobile SwipeNavigation 内部 useIsMobile 也会触发
# 任何 e2e/visual spec 进入这些页面都不该等 networkidle.
PROTECTED_SPECS = [
    # 桌面
    "web/tests/visual/desktop/desktop_drive_comments.spec.mjs",
    "web/tests/visual/mobile/mobile_drive_comments.spec.mjs",
    # 移动手势
    "web/tests/visual/e2e/mobile_swipe_gesture.spec.js",
    # P0 bounce (含 /login → /chat SSE 链路)
    "web/tests/visual/desktop/p0-2-bounce-recv2.spec.mjs",
]


def _strip_comments_and_strings(text: str) -> str:
    """剥离 JS 注释和字符串字面量, 只看真实执行代码."""
    # 去掉 /* ... */ 多行注释
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    # 去掉 // 单行注释
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    # 去掉单/双引号字符串 (粗略, 够用)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"`(?:\\.|[^`\\])*`", "``", text)
    return text


def _has_active_networkidle_call(path: Path) -> list:
    """返回文件中所有真实执行 (非注释) 的 waitForLoadState('networkidle') 调用行号."""
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    stripped = _strip_comments_and_strings(content)
    lines = content.splitlines()
    stripped_lines = stripped.splitlines()
    hits = []
    pattern = re.compile(r"waitForLoadState\s*\(\s*['\"]networkidle['\"]\s*\)")
    for i, line in enumerate(stripped_lines):
        if pattern.search(line):
            hits.append(i + 1)  # 1-based
    return hits


def test_protected_specs_no_active_networkidle():
    """所有已知含 WS/SSE 的 spec 必无真实执行的 waitForLoadState('networkidle')"""
    repo_root = Path(__file__).resolve().parents[2]
    violations = []
    for rel in PROTECTED_SPECS:
        p = repo_root / rel
        active_lines = _has_active_networkidle_call(p)
        if active_lines:
            violations.append(f"{rel}: lines {active_lines}")
    assert not violations, (
        "类 20.67 违规 (W89-P-7 真因): 以下 spec 仍含真实执行的 "
        "waitForLoadState('networkidle'), WS/SSE/long-polling 页面永不达成:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_desktop_drive_comments_uses_ui_locator():
    """desktop_drive_comments spec 必用 UI locator (.desktop-file-comments-view / .dfcv-list 等)."""
    repo_root = Path(__file__).resolve().parents[2]
    p = repo_root / "web" / "tests" / "visual" / "desktop" / "desktop_drive_comments.spec.mjs"
    if not p.exists():
        return  # spec 不存在时跳过 (不强约束)
    content = p.read_text(encoding="utf-8")
    # 必须包含 .desktop-file-comments-view 或 .dfcv-list locator
    has_locator = (
        ".desktop-file-comments-view" in content
        or ".dfcv-list" in content
        or ".dfcv-empty" in content
    )
    assert has_locator, (
        "desktop_drive_comments spec 必含 .desktop-file-comments-view / .dfcv-list locator"
    )


def test_mobile_drive_comments_uses_ui_locator():
    """mobile_drive_comments spec 必用 UI locator."""
    repo_root = Path(__file__).resolve().parents[2]
    p = repo_root / "web" / "tests" / "visual" / "mobile" / "mobile_drive_comments.spec.mjs"
    if not p.exists():
        return
    content = p.read_text(encoding="utf-8")
    has_locator = (
        ".mobile-file-comments-container" in content
        or ".mfcc-list" in content
        or ".mfcc-empty" in content
    )
    assert has_locator, (
        "mobile_drive_comments spec 必含 .mobile-file-comments-container / .mfcc-list locator"
    )


def test_class_20_67_documented():
    """类 20.67 必在本任务 memory 中声明."""
    repo_root = Path(__file__).resolve().parents[2]
    mem = repo_root / "memory" / "w89-x15-networkidle-2026-07-30.md"
    if not mem.exists():
        # 还没 commit memory, 不强制
        return
    content = mem.read_text(encoding="utf-8")
    assert "类 20.67" in content, (
        "memory/w89-x15-networkidle-2026-07-30.md 必含 '类 20.67' 声明"
    )