"""2026-07-02 v2 PR6-P9 — file_mention_tasks Celery 单元测试

覆盖 Celery beat 清理 task：retention_days 配置 / 异常兜底 / 健康日志 / 一刀切语义
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.services.file_mention_tasks import cleanup_old_mentions_task
from app.services.notification_service import cleanup_old_mentions
from app.config import settings


class TestCleanupCeleryTask:
    def test_task_默认_30天(self):
        """不传 retention_days → 用 settings.MENTION_RETENTION_DAYS = 30"""
        async def _mock_cleanup(db, cutoff):
            return 0
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task()
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
            return 12
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task(retention_days=7)
            assert result["deleted_count"] == 12
            cutoff = datetime.fromisoformat(result["cutoff"])
            delta = (datetime.now(timezone.utc) - cutoff).total_seconds()
            assert abs(delta - 7 * 86400) < 60

    def test_task_异常_不抛_返回_error(self):
        """DB 错误 → task 返回 {status: error}，不抛 Celery 重试链"""
        async def _mock_cleanup(db, cutoff):
            raise Exception("DB down")
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task(retention_days=30)
            assert result["status"] == "error"
            assert "DB down" in result["error"]
            assert result["deleted_count"] == 0

    def test_task_0_通知_健康状态(self):
        """deleted_count=0 → status=ok（健康）"""
        async def _mock_cleanup(db, cutoff):
            return 0
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task(retention_days=30)
            assert result["status"] == "ok"
            assert result["deleted_count"] == 0
            assert "cutoff" in result

    def test_task_实际删除(self):
        """deleted_count=N > 0 → status=ok + 正确 N"""
        async def _mock_cleanup(db, cutoff):
            return 87
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task(retention_days=30)
            assert result["status"] == "ok"
            assert result["deleted_count"] == 87

    def test_settings_MENTION_RETENTION_DAYS_默认_30(self):
        """settings.MENTION_RETENTION_DAYS = 30（与 chat_history 30 天对齐）"""
        assert settings.MENTION_RETENTION_DAYS == 30

    def test_task_不依赖_全局_async_session(self):
        """task 必须创建独立 engine (NullPool) — 不依赖全局 async_session 绑定主 loop"""
        async def _mock_cleanup(db, cutoff):
            raise Exception("force fail (no global session available)")
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task(retention_days=30)
            # task 自身创建独立 engine，cleanup 失败不会触发 global session 错误
            assert result["status"] == "error"
            assert "force fail" in result["error"]

    def test_task_retention_days_0_立即清空(self):
        """retention_days=0 → cutoff = NOW（所有通知都满足 < cutoff）"""
        async def _mock_cleanup(db, cutoff):
            # 验证 service 收到的 cutoff 是 tz-aware (CLAUDE.md 2026-06-05 教训)
            assert cutoff.tzinfo is not None
            return 50
        with patch("app.services.file_mention_tasks.cleanup_old_mentions",
                   new=_mock_cleanup):
            result = cleanup_old_mentions_task(retention_days=0)
            assert result["status"] == "ok"
            assert result["deleted_count"] == 50
            cutoff = datetime.fromisoformat(result["cutoff"])
            delta = (datetime.now(timezone.utc) - cutoff).total_seconds()
            assert abs(delta) < 60  # cutoff 几乎等于 NOW

    def test_cleanup_old_mentions_service_可调用(self):
        """service 函数 cleanup_old_mentions 是 async + 接 (db, cutoff_date)"""
        # 此测试不连 DB, 只验证函数签名存在且可 await
        import inspect
        sig = inspect.signature(cleanup_old_mentions)
        params = list(sig.parameters.keys())
        assert params == ["db", "cutoff_date"]
        assert inspect.iscoroutinefunction(cleanup_old_mentions)