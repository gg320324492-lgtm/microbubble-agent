"""2026-07-27 W71 B-3 — qa_bench_tasks Celery 单元测试

覆盖 Celery beat 7 天 auto_intake_rollback task: 注册 / beat schedule / 7 天前 rollback / 7 天内不 rollback
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.core.celery import celery_app
from app.services.qa_bench_tasks import auto_intake_rollback_task


class TestRollbackCeleryTask:
    def test_task_默认_7天(self):
        """不传 retention_days → 默认 7 天"""

        with patch("app.services.qa_bench_tasks.create_celery_engine_and_session") as mock_factory:
            mock_engine = MagicMock()
            mock_factory.return_value = (mock_engine, MagicMock())

            with patch("app.services.qa_bench_tasks.asyncio.run") as mock_run:
                mock_run.return_value = []
                result = auto_intake_rollback_task()
                assert result["status"] == "ok"
                assert result["rolled_back"] == 0
                assert result["retention_days"] == 7

    def test_task_自定义_retention_days(self):
        """传 retention_days=14 → 默认 14 天"""

        with patch("app.services.qa_bench_tasks.create_celery_engine_and_session") as mock_factory:
            mock_engine = MagicMock()
            mock_factory.return_value = (mock_engine, MagicMock())

            with patch("app.services.qa_bench_tasks.asyncio.run") as mock_run:
                mock_run.return_value = [(42, "test entry", datetime.now(timezone.utc))]
                result = auto_intake_rollback_task(retention_days=14)
                assert result["status"] == "ok"
                assert result["rolled_back"] == 1
                assert result["retention_days"] == 14

    def test_task_异常_不抛_返回_error(self):
        """DB 错误 → task 返回 {status: error}，不抛 Celery 重试链"""
        with patch("app.services.qa_bench_tasks.create_celery_engine_and_session") as mock_factory:
            mock_engine = MagicMock()
            mock_factory.return_value = (mock_engine, MagicMock())

            with patch("app.services.qa_bench_tasks.asyncio.run") as mock_run:
                mock_run.side_effect = Exception("DB down")
                result = auto_intake_rollback_task()
                assert result["status"] == "error"
                assert "DB down" in result["error"]
                assert result["rolled_back"] == 0

    def test_beat_schedule_包含_qa_bench_rollback(self):
        """Celery beat schedule 必须含 'qa-bench-auto-intake-rollback-daily' entry"""
        beat = celery_app.conf.beat_schedule
        assert "qa-bench-auto-intake-rollback-daily" in beat, \
            f"beat_schedule keys: {list(beat.keys())}"
        entry = beat["qa-bench-auto-intake-rollback-daily"]
        assert entry["task"] == "app.services.qa_bench_tasks.auto_intake_rollback_task"
        assert entry["schedule"] == 24 * 3600.0

    def test_task_注册成功(self):
        """Celery app.tasks 必须含 auto_intake_rollback_task"""
        from app.services.qa_bench_tasks import auto_intake_rollback_task
        assert auto_intake_rollback_task.name == "app.services.qa_bench_tasks.auto_intake_rollback_task"

    def test_task_软删除而非物理删除(self):
        """必须用 is_active=False (软删除), 不能物理 DELETE"""
        import inspect
        from app.services.qa_bench_tasks import auto_intake_rollback_task
        source = inspect.getsource(auto_intake_rollback_task)
        # 禁止物理 DELETE FROM knowledge (应软删除 is_active=False)
        assert "DELETE FROM knowledge" not in source, \
            "rollback 必须软删除 (is_active=False), 禁止物理 DELETE FROM knowledge"
        assert "is_active" in source, "rollback 必须改 is_active 字段"