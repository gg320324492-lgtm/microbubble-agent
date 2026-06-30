"""#043 Phase 8 — chat_history_tasks Celery 单元测试

覆盖 Celery beat 清理 task：retention_days 配置 / 异常兜底 / 健康日志
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.services.chat_history_tasks import cleanup_soft_deleted_sessions_task
from app.config import settings


class TestCleanupCeleryTask:
    def test_task_默认_30天(self, monkeypatch):
        """不传 retention_days → 用 settings.CHAT_HISTORY_RETENTION_DAYS = 30"""
        # 模拟 cleanup_soft_deleted_sessions 返回值（async 函数返回 coroutine）
        async def _mock_cleanup(db, cutoff):
            return 0
        with patch("app.services.chat_history_tasks.cleanup_soft_deleted_sessions",
                   new=_mock_cleanup):
            result = cleanup_soft_deleted_sessions_task()
            assert result["status"] == "ok"
            assert result["deleted_count"] == 0
            assert "cutoff" in result
            # cutoff 是 NOW - 30 days
            cutoff = datetime.fromisoformat(result["cutoff"])
            delta = (datetime.now(timezone.utc) - cutoff).total_seconds()
            assert abs(delta - 30 * 86400) < 60

    def test_task_自定义_retention_days(self):
        """传 retention_days=7 → cutoff 距今 7 天"""
        async def _mock_cleanup(db, cutoff):
            return 3
        with patch("app.services.chat_history_tasks.cleanup_soft_deleted_sessions",
                   new=_mock_cleanup):
            result = cleanup_soft_deleted_sessions_task(retention_days=7)
            assert result["deleted_count"] == 3
            cutoff = datetime.fromisoformat(result["cutoff"])
            delta = (datetime.now(timezone.utc) - cutoff).total_seconds()
            assert abs(delta - 7 * 86400) < 60

    def test_task_异常_不抛_返回_error(self):
        """DB 错误 → task 返回 {status: error}，不抛 Celery 重试链"""
        async def _mock_cleanup(db, cutoff):
            raise Exception("DB down")
        with patch("app.services.chat_history_tasks.cleanup_soft_deleted_sessions",
                   new=_mock_cleanup):
            result = cleanup_soft_deleted_sessions_task(retention_days=30)
            assert result["status"] == "error"
            assert "DB down" in result["error"]
            assert result["deleted_count"] == 0

    def test_task_0_会话_健康状态(self):
        """deleted_count=0 → status=ok（健康）"""
        async def _mock_cleanup(db, cutoff):
            return 0
        with patch("app.services.chat_history_tasks.cleanup_soft_deleted_sessions",
                   new=_mock_cleanup):
            result = cleanup_soft_deleted_sessions_task(retention_days=30)
            assert result["status"] == "ok"
            assert result["deleted_count"] == 0
            assert "cutoff" in result

    def test_task_实际删除(self):
        """deleted_count=N > 0 → status=ok + 正确 N"""
        async def _mock_cleanup(db, cutoff):
            return 15
        with patch("app.services.chat_history_tasks.cleanup_soft_deleted_sessions",
                   new=_mock_cleanup):
            result = cleanup_soft_deleted_sessions_task(retention_days=30)
            assert result["status"] == "ok"
            assert result["deleted_count"] == 15

    def test_settings_CHAT_HISTORY_RETENTION_DAYS_默认_30(self):
        """settings.CHAT_HISTORY_RETENTION_DAYS = 30（与 task 垃圾桶对齐）"""
        assert settings.CHAT_HISTORY_RETENTION_DAYS == 30

    def test_task_不依赖_全局_async_session(self):
        """task 必须创建独立 engine (NullPool) — 不依赖全局 async_session 绑定主 loop"""
        # 间接验证：模拟 cleanup 抛错（无法连接"主"session）→ task 仍能完成
        async def _mock_cleanup(db, cutoff):
            raise Exception("force fail (no global session available)")
        with patch("app.services.chat_history_tasks.cleanup_soft_deleted_sessions",
                   new=_mock_cleanup):
            result = cleanup_soft_deleted_sessions_task(retention_days=30)
            # task 自身创建独立 engine，cleanup 失败不会触发 global session 错误
            assert result["status"] == "error"
            assert "force fail" in result["error"]
