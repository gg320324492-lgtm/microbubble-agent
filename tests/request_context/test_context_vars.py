"""W87-H-1 — request_id + task_id ContextVar helper 测试

派工 v6 §5 反馈类 20.28:
- contextvars 必 request_id + task_id 双栈
- 不替换 stdlib logging

测试覆盖:
- 默认值 None
- set_request_id / set_task_id 设置后 get 正确
- reset_request_id / reset_task_id 还原 token
- 双 var 独立 (互不污染)
- clear_request_context 清空
"""
import pytest

from app.core.request_context import (
    request_id_var,
    task_id_var,
    get_request_id,
    get_task_id,
    set_request_id,
    set_task_id,
    reset_request_id,
    reset_task_id,
    clear_request_context,
)


class TestContextVarDefaults:
    def test_request_id_var_default_none(self):
        """未设过 request_id → get_request_id() 返回 None"""
        # 注: 测试顺序敏感, 用 reset_request_id 强制还原 (避免其他测试污染)
        token = set_request_id(None)
        reset_request_id(token)
        assert get_request_id() is None

    def test_task_id_var_default_none(self):
        """未设过 task_id → get_task_id() 返回 None"""
        token = set_task_id(None)
        reset_task_id(token)
        assert get_task_id() is None


class TestSetAndGet:
    def test_set_request_id_returns_token(self):
        """set_request_id 返回 token (ContextVar token 协议)"""
        token = set_request_id("test-rid-123")
        try:
            assert get_request_id() == "test-rid-123"
        finally:
            reset_request_id(token)

    def test_set_task_id_returns_token(self):
        """set_task_id 返回 token"""
        token = set_task_id("test-tid-abc")
        try:
            assert get_task_id() == "test-tid-abc"
        finally:
            reset_task_id(token)

    def test_set_request_id_idempotent(self):
        """连 set 两次, 第二次覆盖第一次"""
        token1 = set_request_id("rid-first")
        token2 = set_request_id("rid-second")
        try:
            assert get_request_id() == "rid-second"
        finally:
            reset_request_id(token2)
            reset_request_id(token1)


class TestReset:
    def test_reset_request_id_restores_previous(self):
        """reset_request_id 还原到上一个值"""
        token1 = set_request_id("rid-outer")
        token2 = set_request_id("rid-inner")
        assert get_request_id() == "rid-inner"

        reset_request_id(token2)
        assert get_request_id() == "rid-outer"

        reset_request_id(token1)
        assert get_request_id() is None

    def test_reset_task_id_restores_previous(self):
        """reset_task_id 还原到上一个值"""
        token1 = set_task_id("tid-outer")
        token2 = set_task_id("tid-inner")
        assert get_task_id() == "tid-inner"

        reset_task_id(token2)
        assert get_task_id() == "tid-outer"

        reset_task_id(token1)
        assert get_task_id() is None


class TestDualVarIsolation:
    def test_set_request_id_does_not_affect_task_id(self):
        """设 request_id 不影响 task_id (派工 v6 §5 反馈类 20.28 双栈独立)"""
        rid_token = set_request_id("rid-only")
        tid_token = set_task_id("tid-only")
        try:
            assert get_request_id() == "rid-only"
            assert get_task_id() == "tid-only"
        finally:
            reset_request_id(rid_token)
            reset_task_id(tid_token)

    def test_clear_request_context_clears_both(self):
        """clear_request_context 同时清两个"""
        rid_token = set_request_id("rid-clear")
        tid_token = set_task_id("tid-clear")
        try:
            clear_request_context()
            assert get_request_id() is None
            assert get_task_id() is None
        finally:
            # clean up even if assertions pass
            if rid_token is not None:
                try:
                    reset_request_id(rid_token)
                except ValueError:
                    pass  # 已 reset
            if tid_token is not None:
                try:
                    reset_task_id(tid_token)
                except ValueError:
                    pass


class TestContextVarInheritance:
    def test_set_in_one_context_does_not_leak_to_another(self):
        """ContextVar 在不同 context 隔离 (celery worker prefork 多进程安全)

        模拟场景: 用 contextvars.copy_context() 隔离两段代码
        """
        import contextvars

        outer_token = set_request_id("rid-parent")
        try:
            # 子 context 内 set, 不应污染 outer
            ctx = contextvars.copy_context()

            def inner():
                inner_token = set_request_id("rid-child")
                try:
                    assert get_request_id() == "rid-child"
                finally:
                    reset_request_id(inner_token)

            ctx.run(inner)

            # outer 仍是 parent
            assert get_request_id() == "rid-parent"
        finally:
            reset_request_id(outer_token)
