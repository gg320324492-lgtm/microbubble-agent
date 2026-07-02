"""2026-07-02 v2 PR6-P11 — Celery task retention 二次确认守卫单测

覆盖:
1. retention_days=None → 不触发守卫, proceed=True, delay=0
2. retention_days == default → 不触发守卫
3. retention_days != default → delay + warn + proceed=True
4. delay_sec=0 → 跳过 sleep, 仍 warn + proceed
5. confirm_retention_param_or_skip: 非默认时 return proceed=False
6. 3 个 Celery task 集成测试: 传 retention=0 → 立即 return skipped, 0 DELETE
"""

import logging
from unittest.mock import patch

from app.services.cleanup_safety import (
    confirm_retention_param,
    confirm_retention_param_or_skip,
    confirm_retention_param_auto,
    _is_critical_task,
)
from app.config import settings


# ============================================================
# confirm_retention_param 守卫核心测试
# ============================================================

class TestConfirmRetentionParam:
    """verify behavior across all combinations"""

    def test_none_does_not_trigger(self):
        """retention_days=None → 立即放行, 不 warn 不 sleep"""
        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            result = confirm_retention_param(
                retention_days=None,
                default=30,
                task_name="test_task",
            )
        assert result["proceed"] is True
        assert result["effective_days"] == 30
        assert result["delay_applied"] == 0.0
        assert result["reason"] is None
        m_sleep.assert_not_called()

    def test_equal_default_does_not_trigger(self):
        """retention_days == default → 立即放行"""
        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            result = confirm_retention_param(
                retention_days=30,
                default=30,
                task_name="test_task",
            )
        assert result["proceed"] is True
        assert result["effective_days"] == 30
        assert result["delay_applied"] == 0.0
        m_sleep.assert_not_called()

    def test_different_value_triggers_delay_and_warn(self, caplog):
        """retention_days != default → delay + warn + proceed (用户可手动 Ctrl+C)"""
        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            with caplog.at_level(logging.WARNING):
                result = confirm_retention_param(
                    retention_days=0,  # PR6-P9 误传值
                    default=30,
                    task_name="cleanup_old_mentions_task",
                )
        assert result["proceed"] is True
        assert result["effective_days"] == 0  # 用 caller 传入的值
        assert result["delay_applied"] == settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC
        assert result["reason"] is None
        # time.sleep 被调一次 (实际秒数)
        m_sleep.assert_called_once_with(settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC)
        # logger.warning 至少 2 条 (检测到 + 二次确认通过)
        assert any("非默认 retention_days=0" in r.message for r in caplog.records)
        assert any("cleanup_old_mentions_task" in r.message for r in caplog.records)
        assert any("二次确认已通过" in r.message for r in caplog.records)

    def test_delay_sec_zero_skips_sleep(self):
        """显式 delay_sec=0 → 跳过 sleep, 仍 warn"""
        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            result = confirm_retention_param(
                retention_days=0,
                default=30,
                task_name="test_task",
                delay_sec=0,
            )
        assert result["proceed"] is True
        assert result["delay_applied"] == 0.0
        m_sleep.assert_not_called()

    def test_explicit_delay_overrides_setting(self):
        """delay_sec 参数覆盖 settings 默认值"""
        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            result = confirm_retention_param(
                retention_days=7,  # 测试自定义值
                default=30,
                task_name="test_task",
                delay_sec=2.0,
            )
        assert result["proceed"] is True
        assert result["delay_applied"] == 2.0
        m_sleep.assert_called_once_with(2.0)

    def test_log_contains_task_name_and_values(self, caplog):
        """warn 日志必带 task 名 + retention 值 + 默认值"""
        with caplog.at_level(logging.WARNING):
            confirm_retention_param(
                retention_days=7,
                default=30,
                task_name="chat_history_cleanup_task",
                delay_sec=0,  # 测试专用, 不实际 sleep
            )
        log_text = " ".join(r.message for r in caplog.records)
        assert "chat_history_cleanup_task" in log_text
        assert "retention_days=7" in log_text
        assert "默认=30" in log_text


# ============================================================
# 严格版守卫 (or_skip) 测试
# ============================================================

class TestConfirmRetentionParamOrSkip:
    """严格版守卫: 非默认就拒绝执行"""

    def test_different_value_refuses_execution(self, caplog):
        """retention_days != default → proceed=False, 不 sleep (立即拒绝)"""
        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            with caplog.at_level(logging.WARNING):
                result = confirm_retention_param_or_skip(
                    retention_days=0,
                    default=30,
                    task_name="critical_task",
                )
        assert result["proceed"] is False
        assert result["effective_days"] == 0
        assert result["delay_applied"] == 0.0
        assert result["reason"] is not None
        assert "retention_days=0" in result["reason"]
        assert "default=30" in result["reason"]
        # 严格版本: 不 sleep, 立即拒绝
        m_sleep.assert_not_called()

    def test_none_does_not_trigger(self):
        """retention_days=None → 放行"""
        result = confirm_retention_param_or_skip(
            retention_days=None,
            default=30,
            task_name="critical_task",
        )
        assert result["proceed"] is True
        assert result["effective_days"] == 30

    def test_equal_default_does_not_trigger(self):
        """retention_days == default → 放行"""
        result = confirm_retention_param_or_skip(
            retention_days=30,
            default=30,
            task_name="critical_task",
        )
        assert result["proceed"] is True


# ============================================================
# Settings 验证
# ============================================================

class TestSettingsConstants:
    """PR6-P11 新增 setting"""

    def test_retention_override_confirm_delay_default(self):
        """RETENTION_OVERRIDE_CONFIRM_DELAY_SEC 默认 0.5 (足够人手按 Ctrl+C)"""
        assert settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC == 0.5


# ============================================================
# 3 个 Celery task 集成测试 — 验证守卫能阻断 retention=0 误传
# ============================================================

class TestCeleryTasksIntegration:
    """3 个 Celery task + 守卫: 验证 task 内的守卫被触发 (delay + warn)

    设计 (PR6-P11): confirm_retention_param 是"延迟 + warn + proceed=True"风格 (用户可在 0.5s 内 Ctrl+C).
    3 个 task 默认用 confirm_retention_param (用户友好), 所以 retention=0 时不会真跳过, 只会延迟 + warn.

    **关键陷阱**: 守卫 proceed=True 后 task 真跑 cleanup service → 真 DELETE 数据!
    之前测试失误误删 4 条 chat_sessions, 已用 PR6-P10 restore_from_backup.py 恢复.
    因此本测试只验证"守卫被触发" (time.sleep 被调), 不让 task 真跑 cleanup (直接 mock service 返 0).
    """

    def test_cleanup_old_mentions_task_triggers_delay_on_retention_zero(self):
        """file_mention task: retention_days=0 → 守卫触发 time.sleep"""
        from app.services.file_mention_tasks import cleanup_old_mentions_task

        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            # mock cleanup service 返 0 (不真删). 注意 service 是 async 函数, mock 也得 awaitable.
            async def mock_cleanup(db, cutoff):
                return 0
            with patch("app.services.notification_service.cleanup_old_mentions", side_effect=mock_cleanup):
                result = cleanup_old_mentions_task(retention_days=0)
        # 关键: 守卫延迟被触发了 (PR6-P11 设计意图)
        m_sleep.assert_called_once_with(settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC)
        # 守卫延迟 + warn 后 proceed=True, task 继续走 cleanup (mock 返 0)
        assert result["status"] == "ok"
        assert result["deleted_count"] == 0

    def test_cleanup_old_mentions_task_no_delay_on_default(self):
        """file_mention task: retention_days=None → 守卫不触发, 无延迟"""
        from app.services.file_mention_tasks import cleanup_old_mentions_task

        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            async def mock_cleanup(db, cutoff):
                return 0
            with patch("app.services.notification_service.cleanup_old_mentions", side_effect=mock_cleanup):
                result = cleanup_old_mentions_task(retention_days=None)
        # 默认值场景: 守卫不触发, 无 sleep
        m_sleep.assert_not_called()
        assert result["status"] == "ok"

    def test_cleanup_soft_deleted_sessions_task_triggers_delay_on_retention_zero(self):
        """chat_history task: retention_days=0 → 守卫触发 delay (注意: 不能真删数据!)"""
        from app.services.chat_history_tasks import cleanup_soft_deleted_sessions_task

        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            async def mock_cleanup(db, cutoff):
                return 0  # 删 0 条 (mock, 不真删 chat_sessions)
            with patch("app.services.chat_history_service.cleanup_soft_deleted_sessions", side_effect=mock_cleanup):
                result = cleanup_soft_deleted_sessions_task(retention_days=0)
        m_sleep.assert_called_once_with(settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC)
        assert result["status"] == "ok"
        assert result["deleted_count"] == 0

    def test_cleanup_expired_drive_files_task_triggers_delay_on_retention_zero(self):
        """drive_cleanup task: retention_days=0 → 守卫触发 delay"""
        from app.services.drive_cleanup_tasks import cleanup_expired_drive_files_task

        with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
            async def mock_backup(db, **kwargs):
                return (0, None)  # 不写备份, 返 (0 rows, None path)
            with patch("app.services.cleanup_backup.backup_rows_to_json", side_effect=mock_backup):
                result = cleanup_expired_drive_files_task(retention_days=0)
        # 守卫延迟必触发
        m_sleep.assert_called_once_with(settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC)
        # 守卫 proceed=True 后 cleanup 跑 (mock backup 返 0 + 真实 DB 查 deleted_at, 无数据返 deleted=0)
        assert result["status"] == "ok"
        assert result["deleted_files"] == 0
        assert result["deleted_folders"] == 0


# ============================================================
# PR6-P12 守卫模式开关化 — confirm_retention_param_auto 统一入口
# ============================================================

class TestIsCriticalTask:
    """_is_critical_task: 解析 settings.CLEANUP_CRITICAL_GUARDED_TASKS 逗号分隔列表"""

    def test_empty_setting_returns_false(self):
        with patch.object(settings, "CLEANUP_CRITICAL_GUARDED_TASKS", ""):
            assert _is_critical_task("any.task") is False

    def test_single_task_in_list(self):
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.X.tasks.critical_task",
        ):
            assert _is_critical_task("app.services.X.tasks.critical_task") is True
            assert _is_critical_task("app.services.Y.tasks.other_task") is False

    def test_multiple_tasks_with_whitespace(self):
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            " task.a , task.b ,task.c  ",  # 故意加空白 + 不规范分隔
        ):
            assert _is_critical_task("task.a") is True
            assert _is_critical_task("task.b") is True
            assert _is_critical_task("task.c") is True
            assert _is_critical_task("task.d") is False

    def test_case_sensitive(self):
        """大小写敏感 — task_name 注册名严格匹配"""
        with patch.object(
            settings, "CLEANUP_CRITICAL_GUARDED_TASKS", "Cleanup_Task"
        ):
            assert _is_critical_task("cleanup_task") is False  # 小写不匹配
            assert _is_critical_task("Cleanup_Task") is True


class TestConfirmRetentionParamAuto:
    """confirm_retention_param_auto: 根据 settings 自动选 friendly/strict 模式"""

    def test_default_mode_is_friendly(self):
        """settings 空时所有 task 走 friendly (延迟 + warn)"""
        with patch.object(settings, "CLEANUP_CRITICAL_GUARDED_TASKS", ""):
            with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
                result = confirm_retention_param_auto(
                    retention_days=0, default=30, task_name="any.task"
                )
        assert result["proceed"] is True
        assert result["mode"] == "friendly"
        assert result["delay_applied"] == settings.RETENTION_OVERRIDE_CONFIRM_DELAY_SEC
        m_sleep.assert_called_once()

    def test_critical_mode_routes_to_strict(self):
        """task_name 在 critical 名单时 → strict (or_skip) → proceed=False + 无 sleep"""
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.critical_task.run",
        ):
            with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
                result = confirm_retention_param_auto(
                    retention_days=0,
                    default=30,
                    task_name="app.services.critical_task.run",
                )
        assert result["proceed"] is False
        assert result["mode"] == "strict"
        assert result["delay_applied"] == 0.0
        assert result["reason"] is not None
        m_sleep.assert_not_called()  # strict 模式不 sleep

    def test_non_critical_task_in_mixed_list_falls_through_to_friendly(self):
        """critical 名单里有 A, 但传 B → B 走 friendly (只名单内 task 才 strict)"""
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.A.run",
        ):
            with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
                result = confirm_retention_param_auto(
                    retention_days=0,
                    default=30,
                    task_name="app.services.B.run",
                )
        assert result["proceed"] is True
        assert result["mode"] == "friendly"
        m_sleep.assert_called_once()

    def test_default_value_skips_guard_regardless_of_mode(self):
        """retention == default 时两种模式都放行 (无延迟无 sleep)"""
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "any.task",
        ):
            with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
                result = confirm_retention_param_auto(
                    retention_days=30, default=30, task_name="any.task"
                )
        assert result["proceed"] is True
        assert result["effective_days"] == 30
        assert result["delay_applied"] == 0.0
        m_sleep.assert_not_called()

    def test_none_value_skips_guard_regardless_of_mode(self):
        """retention=None (用默认) 时两种模式都放行"""
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "any.task",
        ):
            with patch("app.services.cleanup_safety.time.sleep") as m_sleep:
                result = confirm_retention_param_auto(
                    retention_days=None, default=30, task_name="any.task"
                )
        assert result["proceed"] is True
        assert result["effective_days"] == 30
        assert result["delay_applied"] == 0.0
        m_sleep.assert_not_called()

    def test_critical_mode_log_emits_strict_marker(self, caplog):
        """strict 模式 logger.warning 必带 🛑 标记 (审计追溯)"""
        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "critical.task",
        ):
            with caplog.at_level(logging.WARNING):
                confirm_retention_param_auto(
                    retention_days=7, default=30, task_name="critical.task"
                )
        log_text = " ".join(r.message for r in caplog.records)
        assert "🛑" in log_text  # strict marker
        assert "拒绝执行" in log_text


# ============================================================
# PR6-P12 端到端: Celery task + critical 模式集成
# ============================================================

class TestCeleryTaskCriticalMode:
    """3 个 Celery task + critical 模式: 验证 task 在白名单内时 strict 拒绝

    关键陷阱: strict 模式 proceed=False, task 必须 return skipped dict,
    不能继续跑 destructive cleanup. (与 friendly 模式不同!)
    """

    def test_file_mention_task_skips_when_critical_and_retention_zero(self):
        """file_mention task: 加入 critical 名单 + retention=0 → skipped, 0 DELETE"""
        from app.services.file_mention_tasks import cleanup_old_mentions_task

        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.file_mention_tasks.cleanup_old_mentions_task",
        ):
            # service 应该**永远**不被调 (strict 模式早 return)
            with patch("app.services.notification_service.cleanup_old_mentions") as m_cleanup:
                result = cleanup_old_mentions_task(retention_days=0)
        # strict 模式: 立即跳过, 不调 service
        m_cleanup.assert_not_called()
        assert result["status"] == "skipped"
        assert result["deleted_count"] == 0
        assert "refused" in result["reason"]
        assert "retention_days=0" in result["reason"]

    def test_chat_history_task_skips_when_critical_and_retention_zero(self):
        """chat_history task: 加入 critical + retention=0 → skipped"""
        from app.services.chat_history_tasks import cleanup_soft_deleted_sessions_task

        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.chat_history_tasks.cleanup_soft_deleted_sessions_task",
        ):
            with patch(
                "app.services.chat_history_service.cleanup_soft_deleted_sessions"
            ) as m_cleanup:
                result = cleanup_soft_deleted_sessions_task(retention_days=0)
        m_cleanup.assert_not_called()
        assert result["status"] == "skipped"
        assert result["deleted_count"] == 0

    def test_drive_cleanup_task_skips_when_critical_and_retention_zero(self):
        """drive_cleanup task: 加入 critical + retention=0 → skipped"""
        from app.services.drive_cleanup_tasks import cleanup_expired_drive_files_task

        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task",
        ):
            with patch("app.services.cleanup_backup.backup_rows_to_json") as m_backup:
                result = cleanup_expired_drive_files_task(retention_days=0)
        # strict 模式: backup service 也不该被调
        m_backup.assert_not_called()
        assert result["status"] == "skipped"
        assert result["deleted_files"] == 0
        assert result["deleted_folders"] == 0

    def test_critical_task_default_retention_passes_through(self):
        """critical task + retention_days=None → 放行 (默认值场景不受 critical 影响)"""
        from app.services.file_mention_tasks import cleanup_old_mentions_task

        with patch.object(
            settings,
            "CLEANUP_CRITICAL_GUARDED_TASKS",
            "app.services.file_mention_tasks.cleanup_old_mentions_task",
        ):
            async def mock_cleanup(db, cutoff):
                return 0
            with patch(
                "app.services.notification_service.cleanup_old_mentions",
                side_effect=mock_cleanup,
            ):
                result = cleanup_old_mentions_task(retention_days=None)
        # 默认值场景: 走 friendly / strict 都直接放行, task 正常执行 (mock 返 0)
        assert result["status"] == "ok"
        assert result["deleted_count"] == 0


# ============================================================
# PR6-P12 Settings 验证
# ============================================================

class TestSettingsCriticalGuardedTasks:
    """PR6-P12 新增 setting"""

    def test_default_empty_string(self):
        """CLEANUP_CRITICAL_GUARDED_TASKS 默认空 = 全部 task 走 friendly"""
        assert settings.CLEANUP_CRITICAL_GUARDED_TASKS == ""
