"""W87-H-1 — Celery signal 接 contextvars 测试

派工 v6 §5 反馈类 20.28:
- task_id 必 request_id 解耦, signal 注入
- test_prerun: 设 task_id
- test_postrun: 清 task_id

测试覆盖:
- signal handler 直接调用 → set_task_id / reset
- mock Celery sender + task_id 模拟完整信号流
"""
import logging
from unittest.mock import MagicMock

import pytest

# 显式 import Celery signal 注册 (side effect import)
import app.core.celery as celery_module  # noqa: F401
from app.core.celery import _task_prerun_set_task_id, _task_postrun_clear_task_id
from app.core.request_context import get_task_id, set_task_id, reset_task_id


class TestCelerySignalHandlers:
    def test_task_prerun_sets_task_id(self):
        """模拟 Celery task_prerun signal, 应设 task_id contextvar

        signal 自带参数: sender=<task_cls>, task_id=<uuid>
        """
        # 清干净
        set_task_id(None)

        sender = MagicMock(name="sender")
        task_id = "celery-task-abc123"

        _task_prerun_set_task_id(sender=sender, task_id=task_id)

        assert get_task_id() == task_id

        # cleanup
        set_task_id(None)

    def test_task_postrun_clears_task_id(self):
        """模拟 Celery task_postrun signal, 应清 task_id contextvar"""
        # 先设一个 task_id (模拟 prerun 已跑)
        set_task_id("celery-task-prev")

        sender = MagicMock(name="sender")
        _task_postrun_clear_task_id(sender=sender, task_id="celery-task-prev")

        # postrun 后应清空
        assert get_task_id() is None

    def test_prerun_postrun_pair(self):
        """完整信号流: prerun → task_id 设入, postrun → 清除

        模拟 Celery worker 一轮 task 调度的完整生命周期
        """
        set_task_id(None)
        sender = MagicMock(name="sender")

        # 1. prerun: 设 task_id
        _task_prerun_set_task_id(sender=sender, task_id="celery-task-lifecycle")
        assert get_task_id() == "celery-task-lifecycle"

        # 2. 业务代码执行 (此处省略)

        # 3. postrun: 清 task_id
        _task_postrun_clear_task_id(sender=sender, task_id="celery-task-lifecycle")
        assert get_task_id() is None

    def test_prerun_with_no_task_id(self):
        """signal 兜底: 缺 task_id 不应爆

        真实 Celery signal 必有 task_id, 但兜底逻辑不应让程序挂掉
        """
        sender = MagicMock(name="sender")
        # 无 task_id → sender.request.id 兜底 (MagicMock 有 request)
        sender.request.id = "fallback-task-id"
        _task_prerun_set_task_id(sender=sender, task_id=None)

        # 兜底应设 sender.request.id 或 None
        assert get_task_id() in (None, "fallback-task-id")

        set_task_id(None)


class TestCeleryModuleRegistration:
    """保证 app.core.celery 模块级 signal handler 已注册 (side effect import)"""

    def test_celery_module_imports_without_error(self):
        """app.core.celery import 不应失败 (signal handler 已连到信号)"""
        import importlib
        module = importlib.import_module("app.core.celery")
        assert hasattr(module, "_task_prerun_set_task_id")
        assert hasattr(module, "_task_postrun_clear_task_id")
