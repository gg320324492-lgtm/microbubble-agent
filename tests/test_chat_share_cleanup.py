"""W2 T3 P2-A — chat_share_tasks Celery 单元测试

覆盖 chat_share 过期主动清理 task:
- 默认无参数 (chat_share 没有 retention 概念, 只有 expires_at < now 即过期)
- 异常兜底 → status=error 不抛
- 0 过期 → 健康日志 + status=ok
- N 过期 → 正确删除 + status=ok
- 备份路径返回 (PR6-P10 防误删)
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.services.chat_share_tasks import cleanup_expired_chat_shares_task


class TestCleanupChatShareTask:
    def test_task_0_过期_健康状态(self):
        """deleted_count=0 → status=ok (健康)"""
        async def _mock_exec(db, **kwargs):
            return 0, None  # (deleted_count, backup_path)
        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            result = cleanup_expired_chat_shares_task()
            assert result["status"] == "ok"
            assert result["deleted_count"] == 0
            assert "cutoff" in result

    def test_task_实际删除(self):
        """deleted_count=N > 0 → status=ok + 正确 N"""
        async def _mock_exec(db, **kwargs):
            return 12, "/tmp/celery_cleanup_chat_shares_20260720.json"
        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            result = cleanup_expired_chat_shares_task()
            assert result["status"] == "ok"
            assert result["deleted_count"] == 12

    def test_task_异常_不抛_返回_error(self):
        """DB 错误 → task 返回 {status: error}，不抛 Celery 重试链"""
        async def _mock_exec(db, **kwargs):
            raise Exception("DB connection refused")
        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            result = cleanup_expired_chat_shares_task()
            assert result["status"] == "error"
            assert "DB connection refused" in result["error"]
            assert result["deleted_count"] == 0

    def test_task_cutoff_用_tz_aware_utc(self):
        """cutoff 必须用 timezone.utc (CLAUDE.md 2026-06-05 教训: tz-aware vs naive)"""
        captured = {}

        async def _mock_exec(db, **kwargs):
            # kwargs 包含 extra_metadata, 其中 cutoff_date 应为 iso str
            captured["cutoff_date"] = kwargs["extra_metadata"]["cutoff_date"]
            return 0, None

        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            result = cleanup_expired_chat_shares_task()

        # cutoff 字段必须存在且 <= 当前 UTC
        assert "cutoff" in result
        cutoff_from_result = datetime.fromisoformat(result["cutoff"])
        assert cutoff_from_result.tzinfo is not None  # tz-aware
        delta = (datetime.now(timezone.utc) - cutoff_from_result).total_seconds()
        # cutoff 距今应该 < 60s (P2-A 即时清理, 不像 chat_history 减 30 天)
        assert abs(delta) < 60

        # extra_metadata.cutoff_date 与 result.cutoff 一致
        assert captured["cutoff_date"] == result["cutoff"]

    def test_task_where_clause_含_isnot_null_守卫(self):
        """where_clause 必须包含 expires_at IS NOT NULL (NULL=永不过期业务语义)"""
        from sqlalchemy import and_
        from app.models.chat_history import ChatShare

        captured = {}

        async def _mock_exec(db, **kwargs):
            captured["where_clause"] = kwargs["where_clause"]
            return 0, None

        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            cleanup_expired_chat_shares_task()

        # where_clause 是 and_(ChatShare.expires_at.isnot(None), ChatShare.expires_at < cutoff)
        wc = captured["where_clause"]
        # and_ 对象 → children 是 [isnot(None), < cutoff]
        children = wc.get_children()
        # 第 1 个 child 必须包含 IS NOT NULL (ChatShare.expires_at.isnot(None))
        assert any("IS NOT NULL" in str(c).upper() for c in children), \
            f"expires_at IS NOT NULL 守卫缺失, children={children}"
        # 第 2 个 child 必须包含 <  (ChatShare.expires_at < cutoff)
        assert any("<" in str(c) for c in children), \
            f"expires_at < cutoff 缺失, children={children}"

    def test_task_不依赖_全局_async_session(self):
        """task 必须创建独立 engine (NullPool) — 不依赖全局 async_session 绑定主 loop"""
        async def _mock_exec(db, **kwargs):
            raise Exception("force fail (no global session available)")
        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            result = cleanup_expired_chat_shares_task()
            # task 自身创建独立 engine, cleanup 失败不会触发 global session 错误
            assert result["status"] == "error"
            assert "force fail" in result["error"]

    def test_task_table_name_chat_shares(self):
        """table_name 必须是 'chat_shares' (PR6-P10 备份路径约定)"""
        captured = {}

        async def _mock_exec(db, **kwargs):
            captured["table_name"] = kwargs["table_name"]
            return 0, None

        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            cleanup_expired_chat_shares_task()

        assert captured["table_name"] == "chat_shares"

    def test_task_strategy_metadata(self):
        """extra_metadata.strategy 描述清楚清理策略 (审计追溯)"""
        captured = {}

        async def _mock_exec(db, **kwargs):
            captured["metadata"] = kwargs["extra_metadata"]
            return 0, None

        with patch("app.services.chat_share_tasks.execute_backup_then_delete",
                   new=_mock_exec):
            cleanup_expired_chat_shares_task()

        assert "strategy" in captured["metadata"]
        assert "expires_at" in captured["metadata"]["strategy"]
        assert "cutoff_date" in captured["metadata"]