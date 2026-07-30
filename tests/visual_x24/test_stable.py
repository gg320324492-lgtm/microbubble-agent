"""
tests/visual_x24/test_stable.py — W89-X-24 visual-regression flaky 修加固 e2e

派工 v6 §5 反馈 类 20.79 沉淀:
  "visual-regression flaky 修法: 必等明确 UI locator / data-testid,
  禁 networkidle 或裸 timeout"

本测试目的:
  1. 静态检查 visual-regression.spec.mjs 必含 waitForSelector(state: 'visible')
  2. 静态检查 visual-regression.spec.mjs 必不含 waitUntil: 'networkidle'
  3. 静态检查每条 CORE_ROUTES 配 selector 字段 (派工 brief v3 双锚定纪律)
  4. 静态检查 CORE_ROUTES 长度 ≥ 9 (v78 + /project-stats)

注意:
  - 不实际跑 Playwright (依赖 dev server 3000, CI 不一定有)
  - 静态检查是"W89-X-24 fix 落地"的可重复验证手段
  - 真 e2e 跑由本地 dev 跑, CI 维持禁用 (W76 §v77 决定)

派工 brief v3: 只验证 spec 改了等待, 不验业务代码改动 (派工 brief 禁改业务)
"""
from pathlib import Path

import pytest

VISUAL_SPEC = (
    Path(__file__).resolve().parents[2]
    / "web"
    / "tests"
    / "visual"
    / "mobile"
    / "visual-regression.spec.mjs"
)


def _read_spec() -> str:
    assert VISUAL_SPEC.exists(), f"spec 不存在: {VISUAL_SPEC}"
    return VISUAL_SPEC.read_text(encoding="utf-8")


class TestVisualRegressionX24:
    """W89-X-24 类 20.79 静态门禁"""

    def test_spec_uses_wait_for_selector_visible(self):
        """派工 v6 §5 反馈 类 20.79: 必含 waitForSelector(state: 'visible')"""
        text = _read_spec()
        assert "waitForSelector(" in text, "spec 必含 waitForSelector( 改用明确 UI locator"
        assert "state: 'visible'" in text, "spec 必用 state: 'visible' 等可见, 非仅 attached"

    def test_spec_no_networkidle(self):
        """派工 v6 §5 反馈 类 20.79: 禁 waitUntil: 'networkidle' (空态竞态根因)

        只检查代码区(无注释), 允许 docstring 和行注释里出现 networkidle 文字
        (作为禁止警告)。
        """
        text = _read_spec()
        import re
        # 移除 /** ... */ 块
        code = re.sub(r"/\*\*[\s\S]*?\*/", "", text)
        # 移除 // 行注释
        code_no_comments = "\n".join(
            re.sub(r"//.*$", "", line) for line in code.splitlines()
        )
        assert "waitUntil: 'networkidle'" not in code_no_comments, (
            "spec 代码区(去注释)残留 waitUntil: 'networkidle' — "
            "W89-X-10 报告真因, 必须删"
        )
        # 也禁 waitForLoadState('networkidle')
        assert "waitForLoadState('networkidle')" not in code_no_comments, (
            "spec 代码区(去注释)残留 waitForLoadState('networkidle') — 同样空态竞态"
        )

    def test_spec_no_bare_timeout_replacing_locator(self):
        """派工 v6 §5 反馈 类 20.79: 禁裸 timeout 替代 locator 等待

        允许保留小量 waitForTimeout 用于动画/transition 收尾 (≤ 500ms),
        但 locator 必先到 visible (前面已 assert, 这里额外防退化)
        """
        text = _read_spec()
        # 允许 ≤ 1 个 waitForTimeout (用于动画), 但禁 ≥ 2 个暗示退化到裸 timeout
        timeout_count = text.count("waitForTimeout(")
        assert timeout_count <= 1, (
            f"waitForTimeout 出现 {timeout_count} 次 — 暗示退化到裸 timeout "
            f"(派工 v6 §5 反馈 类 20.79)"
        )

    def test_core_routes_have_selector(self):
        """每条 CORE_ROUTES 必配 selector 字段 (派工 brief v3 双锚定纪律)

        允许逗号分隔的多 selector (mobile 优先 + desktop 退路)
        """
        text = _read_spec()
        # 简单 grep 检查每条 route 都配 selector
        for needle in [
            "'/dashboard',",
            "'/knowledge',",
            "'/chat',",
            "'/tasks',",
            "'/meetings',",
            "'/settings',",
            "'/workspace?tab=projects',",
            "'/workspace?tab=members',",
            "'/project-stats',",
        ]:
            assert needle in text, f"路由缺失: {needle}"
        # 检查 selector 字段 (每条 route 第 3 字段)
        # 允许 mobile 优先, desktop 退路 (逗号分隔)
        for selector in [
            ".mobile-dashboard",  # dashboard
            ".mobile-knowledge-view",  # knowledge
            ".mobile-chat-root",  # chat
            ".mobile-task-view",  # tasks
            ".mobile-meeting-view",  # meetings
            ".mobile-settings-view",  # settings
            ".mobile-workspace-view",  # workspace
            ".mobile-project-stats",  # project-stats
        ]:
            assert selector in text, f"mobile 优先 selector 缺失: {selector}"

    def test_spec_docstring_records_class20_79(self):
        """spec 顶部 docstring 必含 W89-X-24 关键纪律 (类 20.79 实战锚点)"""
        text = _read_spec()
        assert "W89-X-24" in text, "spec docstring 必含 W89-X-24 关键纪律标识"
        assert "类 20.79" in text, "spec docstring 必含 类 20.79 引用 (派工 v6 §5 反馈)"
        assert "networkidle" in text, "spec docstring 必提 networkidle (避后人重蹈覆辙)"

    def test_no_business_code_modified(self):
        """派工 brief 禁改业务代码 — 复检本任务不误改 web/src/views/mobile/

        注: 此断言只覆盖本任务 commit 的文件, 不追溯历史。
        实际由 git diff main..HEAD --name-only 兜底 (主指挥合并时再校核)。
        """
        # 静态层只验证 spec 没引用到业务代码 import
        text = _read_spec()
        # 禁 from '@/views/mobile/' 业务代码 import (派工 brief 禁)
        assert "from '@/views/mobile/" not in text, (
            "spec 禁止 import 业务代码 — 派工 brief 明确禁改业务"
        )
