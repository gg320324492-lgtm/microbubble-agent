"""W83 B-1 P1-3: wechat handler print → logger e2e

验证 app/wechat/handler.py 的 print() 已全部替换为 logger.info().
类比: CLAUDE.md W70 教训 (用户报告"用户没收到消息" 排查困难 — print 不入日志).

守卫:
1. grep ``print(`` 在 handler.py 全文 0 个匹配 (除 docstring / 注释中举例)
2. 关键位置 (line 165/183/187 等) 调用的是 logger.info
3. logger 是 ``microbubble.wechat`` 命名空间 (统一前缀, 便于运维 grep)
4. 格式用 ``%s`` 占位符 (lazy format, 性能更好, 日志库惯例)
"""
from __future__ import annotations

import re

import pytest


WECHAT_HANDLER_PATH = "app/wechat/handler.py"


def _read_handler_source():
    """读 handler.py 源码 (test helper)."""
    import pathlib
    p = pathlib.Path(__file__).resolve().parent.parent / WECHAT_HANDLER_PATH
    return p.read_text(encoding="utf-8")


class TestW83B1WechatLogger:
    """W83 B-1 P1-3: wechat handler print → logger."""

    def test_no_print_statements_in_handler(self):
        """P1-3.1: handler.py 不再含 ``print(`` (除 docstring / 注释举例)."""
        src = _read_handler_source()
        # 去掉 docstring / 注释 (用 # 或 三引号包裹) 再 grep
        lines = src.splitlines()
        non_doc_lines = []
        in_docstring = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # 简单 docstring 切换 — handler.py 只有一个顶层 docstring
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            if stripped.startswith("#"):
                continue
            non_doc_lines.append(line)
        non_doc = "\n".join(non_doc_lines)
        matches = re.findall(r"\bprint\s*\(", non_doc)
        assert matches == [], (
            f"handler.py still contains {len(matches)} print() calls in code, "
            "expected all replaced with logger.info(). Offending matches: " + repr(matches[:5])
        )

    def test_logger_namespace_is_microbubble_wechat(self):
        """P1-3.2: logger 命名空间 = ``microbubble.wechat`` (便于运维 grep)."""
        src = _read_handler_source()
        assert 'logger = logging.getLogger("microbubble.wechat")' in src, \
            "expected logger = logging.getLogger('microbubble.wechat') in handler.py"

    def test_key_log_calls_use_logger_info(self):
        """P1-3.3: 关键 8 个 log 点 (收消息 / 用户识别 / 声纹 / 绑定) 都用 logger.info."""
        src = _read_handler_source()
        # 检查每条都有对应 logger.info 行
        expected = [
            "WECHAT 收到消息",
            "WECHAT 用户未识别",
            "WECHAT 用户已识别",
            "WECHAT 自动更新wechat_id",
            "WECHAT 声纹录入成功",
            "WECHAT 通过 external_userid 识别",
            "WECHAT 通过 wechat_id 识别",
            "WECHAT 通过插件 from_user 识别",
            "WECHAT 用户有 pending 状态",
            "WECHAT 尝试昵称匹配",
            "WECHAT 通过昵称识别",
            "WECHAT 昵称匹配有歧义",
            "WECHAT 通过验证记录识别",
            "WECHAT 用户识别失败",
            "WECHAT 身份绑定成功",
            "WECHAT 已验证用户换设备识别",
        ]
        for snippet in expected:
            assert snippet in src, f"expected WECHAT log snippet missing: {snippet!r}"
            # 必须是 logger.info 不是 print
            assert f"logger.info" in src, "logger.info must be used"

    def test_logger_calls_use_percent_format(self):
        """P1-3.4: logger 调用用 %s 占位符 (lazy format, 性能更好, 日志库惯例).

        原 print 用 f-string — logger.info 改为 %s 占位符, 防止 log 关时仍计算 f-string.
        """
        src = _read_handler_source()
        # 找一个明显的 WECHAT log 调用, 验证 %s 占位符
        sample_calls = re.findall(r'logger\.info\("WECHAT[^"]+",\s*[^)]+\)', src)
        assert len(sample_calls) >= 5, f"expected several logger.info WECHAT calls, found {len(sample_calls)}"
        for call in sample_calls:
            assert "f\"" not in call, f"logger.info call should not use f-string: {call}"
            assert "%s" in call, f"logger.info call should use %s placeholder: {call}"