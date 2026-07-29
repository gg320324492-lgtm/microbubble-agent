"""W87-H-1 — RequestContextFilter 测试

派工 v6 §5 反馈类 20.28:
- Filter 不替换 stdlib logging, 仅追加 request_id + task_id 字段
- 测试 mock LogRecord + RequestContextFilter 互不干扰

测试覆盖:
- Filter 读 contextvars 填 record.request_id / record.task_id
- 默认值 None → '-' fallback (向后兼容)
- context 设值后 filter 输出对应字段
"""
import logging

import pytest

from app.core.request_context import set_request_id, reset_request_id, set_task_id, reset_task_id
from app.core.logging import RequestContextFilter, JSONFormatter


class TestRequestContextFilter:
    def test_filter_sets_request_id(self):
        """Filter 从 contextvars 取 request_id 填入 record"""
        rid_token = set_request_id("rid-abc")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            f = RequestContextFilter()
            result = f.filter(record)
            assert result is True
            assert record.request_id == "rid-abc"
            assert record.task_id == "-"  # default fallback
        finally:
            reset_request_id(rid_token)

    def test_filter_sets_task_id(self):
        """Filter 从 contextvars 取 task_id 填入 record"""
        tid_token = set_task_id("tid-xyz")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            f = RequestContextFilter()
            f.filter(record)
            assert record.task_id == "tid-xyz"
            assert record.request_id == "-"  # default fallback
        finally:
            reset_task_id(tid_token)

    def test_filter_default_dashes_when_no_context(self):
        """未设 context vars → record.request_id / task_id = '-' (向后兼容)"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        f = RequestContextFilter()
        f.filter(record)
        assert record.request_id == "-"
        assert record.task_id == "-"


class TestJSONFormatterIntegration:
    """JSONFormatter 必须输出 request_id + task_id (W87-H-1 新增字段)"""

    def test_json_formatter_outputs_request_id_and_task_id(self):
        rid_token = set_request_id("rid-json")
        tid_token = set_task_id("tid-json")
        try:
            record = logging.LogRecord(
                name="microbubble.test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="hello world",
                args=(),
                exc_info=None,
            )
            f = RequestContextFilter()
            f.filter(record)

            formatter = JSONFormatter()
            output = formatter.format(record)

            # JSON parse + field check
            import json
            parsed = json.loads(output)
            assert parsed["request_id"] == "rid-json"
            assert parsed["task_id"] == "tid-json"
            assert parsed["message"] == "hello world"
            assert parsed["level"] == "INFO"
        finally:
            reset_request_id(rid_token)
            reset_task_id(tid_token)

    def test_json_formatter_dash_fallback(self):
        """未设 context → JSON 输出 request_id='-' / task_id='-'"""
        record = logging.LogRecord(
            name="microbubble.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="no context",
            args=(),
            exc_info=None,
        )
        RequestContextFilter().filter(record)

        formatter = JSONFormatter()
        output = formatter.format(record)
        import json
        parsed = json.loads(output)
        assert parsed["request_id"] == "-"
        assert parsed["task_id"] == "-"
