"""回归测试: meeting_ai_polish.py logger.warning 字面 % 触发 ValueError 修复

W2-6 polish log fix: app/services/meeting_ai_polish.py:203-209 字面 `>10%` 触发
logger `%` 格式化异常, ValueError: unsupported format character '?'.
修复方案: `%` 转义为 `%%`, 字面文本从 `>10%差异` 改为 `差异超过 10%`。

本测试:
1. 验证修复前 _validate_polish_result 在过改写场景不再触发 ValueError
2. 验证 logger.warning 可正常落日志（不抛 + 实际消息含 %s 替换结果）
3. 验证回退逻辑：原文保留 + polished 段保留原始 speaker/text
"""
import logging
import pytest

from app.services.meeting_ai_polish import _validate_polish_result


def _silent_handler():
    """silent logger handler: 不污染测试 stdout"""
    h = logging.NullHandler()
    return h


def test_validate_polish_result_rewrite_does_not_explode(caplog):
    """回归测试 1: 过改写场景必须回退原文,logger.warning 不能抛 ValueError.

    修复前: logger.warning('AI 润色疑似改写（>10%差异）...') 中字面 '%' 被
    logging 误读为 format specifier → getMessage 时 `msg % self.args` 抛
    ValueError: unsupported format character '?' (0x5dee).
    修复后: % 转义为 %%, logging 正常落日志, getMessage 返回带 %s 替换的真实文本。
    """
    original = [
        {"speaker": "张三", "text": "今天是6月5号然后我们看任务管理", "ts": 1.0},
    ]
    # 显著改写 (semantic 完全不同, 与 existing test_meeting_ai_polish.py:47 一致)
    # _is_reasonable_edit 返回 False → 走 logger.warning 回退路径
    llm_result = {
        "polished": [
            {"speaker": "张三", "text": "今天介绍任务管理模块", "ts": 1.0},
        ],
        "key_points": [],
        "boundary_after_index": None,
        "summary": None,
    }

    # 关键: caplog 绑到 module logger, 强制 propagate=True 抛错时测试失败
    logger = logging.getLogger("microbubble.meeting_polish")
    logger.addHandler(_silent_handler())
    logger.setLevel(logging.WARNING)

    try:
        with caplog.at_level(logging.WARNING, logger="microbubble.meeting_polish"):
            # 修复前这里会抛 ValueError
            result = _validate_polish_result(llm_result, original)
    finally:
        logger.removeHandler(_silent_handler())

    # 断言 1: 不抛异常,结果回退到原文
    assert result["polished"][0]["text"] == original[0]["text"]
    assert result["polished"][0]["speaker"] == original[0]["speaker"]

    # 断言 2: logger 实际落了一条 warning (没抛说明日志 pipeline 完整跑完)
    rewrite_warnings = [
        r for r in caplog.records
        if r.levelname == "WARNING"
        and "已回退原文" in r.getMessage()
    ]
    assert len(rewrite_warnings) >= 1, (
        "期望 logger.warning 至少落一条 '已回退原文' warning, "
        f"实际 records: {[r.getMessage() for r in caplog.records]}"
    )

    # 断言 3: 消息含 %s 替换后的真实值, 证明 % 被正确处理成字符而非 format spec
    msg = rewrite_warnings[0].getMessage()
    assert "今天是" in msg or "今天介绍" in msg, (
        f"期望 warning message 含原文前缀, 实际: {msg!r}"
    )


def test_validate_polish_result_no_rewrite_keeps_polish(caplog):
    """回归测试 2: 标点级润色 (改写 < 10%) 必须保留 polished 版本, 不触发 warning."""
    original = [
        {"speaker": "张三", "text": "今天是6月5号然后我们看任务管理", "ts": 1.0},
    ]
    # 仅加标点, 改写 < 10%
    llm_result = {
        "polished": [
            {"speaker": "张三", "text": "今天是6月5号，然后我们看任务管理。", "ts": 1.0},
        ],
        "key_points": [],
        "boundary_after_index": None,
        "summary": None,
    }

    logger = logging.getLogger("microbubble.meeting_polish")
    logger.addHandler(_silent_handler())
    logger.setLevel(logging.WARNING)

    try:
        with caplog.at_level(logging.WARNING, logger="microbubble.meeting_polish"):
            result = _validate_polish_result(llm_result, original)
    finally:
        logger.removeHandler(_silent_handler())

    # 标点级润色被接受, 不回退
    assert result["polished"][0]["text"] == "今天是6月5号，然后我们看任务管理。"

    # 没触发警告
    rewrite_warnings = [
        r for r in caplog.records
        if r.levelname == "WARNING" and "已回退原文" in r.getMessage()
    ]
    assert len(rewrite_warnings) == 0


def test_logger_warning_with_literal_percent_is_safe():
    """回归测试 3: 直接验证 logger.warning 路径不再爆 ValueError.

    与文件级修复 (line 206) 解耦, 验证转义后 '差异超过 10%%' 在 logging 格式化时
    能正确把 %% 还原成单 %, 并且 args 的 %s 占位正常替换。
    """
    logger = logging.getLogger("microbubble.meeting_polish")
    logger.addHandler(_silent_handler())
    logger.setLevel(logging.WARNING)

    captured = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record):
            captured.append(record.getMessage())

    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        # 这条字符串风格必须与修复后的 meeting_ai_polish.py:206 字面一致
        logger.warning(
            "AI 润色疑似改写（差异超过 10%%），已回退原文: original=%s polished=%s",
            "原文aaaa",
            "润色后bbbb",
        )
    finally:
        logger.removeHandler(handler)
        logger.removeHandler(_silent_handler())

    assert len(captured) == 1
    msg = captured[0]
    # %% 还原为单个 %, %s 替换为真实值
    assert "差异超过 10%" in msg
    assert "原文aaaa" in msg
    assert "润色后bbbb" in msg
    # 关键: format residue 检测 — 不应有 leftover %( 之类的未替换 token
    assert "%(" not in msg, f"logger 输出残留未替换 format token: {msg!r}"
    assert "%%" not in msg, f"logger 输出还含 %% escape: {msg!r}"
