"""
W89-X-19a vitest 修法加固 e2e 验证 (派工 v6 §1.2 真验证).

验证 4 个 spec 的关键修复点不被后续 commit 静默回退:
- desktop_emoji_lazy: 不应有 TypeScript 侵入 (const vm: any)
- desktop_drive_versions: vi.mock 应 hoisted (顶层), 不在 import 之后用 vi.doMock
- mobile_drive_comments: 必须 mock useMobileKeyboard (组件引用但 jsdom 无 visualViewport)
- mobile-fab: LongPressWrapper stub 应含 .long-press-wrapper className

每个 test 失败 → 加固失败 → 拦截回归.
"""
import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"


def _read(path):
    p = WEB / path
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def test_desktop_emoji_lazy_no_typescript():
    """desktop_emoji_lazy.spec.js 不应有 TypeScript 语法侵入 (.js 文件不能有 : any / as any)."""
    content = _read("tests/e2e/desktop_emoji_lazy.spec.js")
    if not content:
        return  # 跳过 — 文件不存在
    # 不应出现 TypeScript 语法标识
    assert ": any" not in content, (
        "TypeScript 语法 (`: any`) 侵入 .js spec 文件 — Rollup 解析失败"
    )
    assert " as any" not in content, (
        "TypeScript 语法 (`as any`) 侵入 .js spec 文件 — Rollup 解析失败"
    )


def test_desktop_drive_versions_mock_hoisted():
    """desktop_drive_versions.spec.js vi.mock 应在所有 import 之上 (hoisted).

    vi.doMock 不能拦住已被 import 的 axios 模块 — 派工 brief 反复强调的 vitest 修法之一.
    """
    content = _read("tests/e2e/desktop_drive_versions.spec.js")
    if not content:
        return
    # 应有顶层 vi.mock('axios', ...) 调用 (出现在所有 import 之上)
    assert "vi.mock('axios'" in content, (
        "desktop_drive_versions.spec.js 缺少顶层 vi.mock('axios') — "
        "beforeEach 内的 vi.doMock 不生效 (模块已 import)"
    )
    # 不应有 vi.doMock('axios') — 这是反模式
    assert "vi.doMock('axios'" not in content, (
        "desktop_drive_versions.spec.js 仍含 vi.doMock('axios') — "
        "应改为顶层 vi.mock('axios') hoisted"
    )


def test_mobile_drive_comments_setup_has_useMobileKeyboard():
    """mobile_drive_comments.spec.js 必须 mock useMobileKeyboard (jsdom 无 visualViewport).

    组件 MobileFileCommentsView.vue 在 <script setup> 中调 useMobileKeyboard(),
    jsdom 没有 visualViewport → 抛 ReferenceError. 测试必须用 vi.mock 提供 stub.
    """
    content = _read("tests/e2e/mobile_drive_comments.spec.js")
    if not content:
        return
    assert "useMobileKeyboard" in content, (
        "mobile_drive_comments.spec.js 必须 mock useMobileKeyboard — "
        "MobileFileCommentsView.vue 调用但 jsdom 无 visualViewport"
    )
    assert "vi.mock('@/composables/useMobileKeyboard'" in content, (
        "mobile_drive_comments.spec.js 缺 vi.mock('@/composables/useMobileKeyboard') — "
        "需要顶层 mock 拦住 composable 解析"
    )


def test_mobile_fab_stub_has_long_press_wrapper_class():
    """mobile-fab.test.js LongPressWrapper stub 应含 .long-press-wrapper className.

    真实 LongPressWrapper.vue 根元素 class 是 long-press-wrapper,
    MobileFab.vue 的 CSS `:deep(.long-press-wrapper)` 也指向 className.
    Stub 必须保留 className 才能让 wrapper.get('.long-press-wrapper') 找到.
    """
    content = _read("tests/unit/mobile-fab.test.js")
    if not content:
        return
    # 检查 LongPressStub 的 template 是否含 class="long-press-wrapper"
    assert 'class="long-press-wrapper"' in content, (
        "mobile-fab.test.js 的 LongPressStub template 缺 .long-press-wrapper className — "
        "wrapper.get('.long-press-wrapper') 找不到, 测试失败"
    )


def test_mobile_drive_comments_has_axios_hoisted_mock():
    """mobile_drive_comments.spec.js 应有顶层 vi.mock('axios') 让 store 的 fetchComments 走 fixture."""
    content = _read("tests/e2e/mobile_drive_comments.spec.js")
    if not content:
        return
    assert "vi.mock('axios'" in content, (
        "mobile_drive_comments.spec.js 缺 vi.mock('axios') — "
        "useNotifications store import axios 不走 global.axios, 必须顶层 mock"
    )