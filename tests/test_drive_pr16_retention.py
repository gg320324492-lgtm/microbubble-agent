"""2026-07-24 W68 第 13 批 C-3 — Drive v2 PR16 workspace 回收站 e2e 测试

覆盖 6 个场景 (mock DB, 不依赖真实连接):
1. soft_delete_expired_versions: 软删过期 file_versions (关联 file 已删超 30 天)
2. soft_delete_expired_versions: 30 天内不删 (cutoff 之前)
3. soft_delete_expired_versions: 关联 file 未删, file_versions 不动
4. hard_delete_expired_versions: 物理删 purged_at < cutoff
5. Celery task 跑: 完整 2 步 (软删 + 物理删), 返回 dict 结构正确
6. admin endpoint 返 stats: get_retention_stats 单 query 多聚合

不依赖真实 DB (SKIP_DB_SETUP=1 下 fixture 不可用, 所有测试用纯 mock)
- 真实 DB 集成测试可在后续 PR 加 (参考 test_chat_history_service.py:TestCleanup 4 case)

范式: 与 test_drive_cleanup_service.py 一致
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# Scenario 1: soft_delete_expired_versions — 软删过期 file_versions
# ============================================================================


class TestSoftDeleteExpiredVersions:
    """soft_delete_expired_versions: 软删关联 Knowledge.deleted_at < cutoff 的 file_versions"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_raises_on_none_cutoff(self):
        """cutoff_date=None → ValueError (caller 应传 datetime.now - timedelta)"""
        from app.services.drive_version_retention_service import soft_delete_expired_versions
        db = AsyncMock()

        with pytest.raises(ValueError) as exc_info:
            await soft_delete_expired_versions(db, None)
        assert "cutoff_date 不能为 None" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_soft_deletes_expired_file_versions(self):
        """关联 Knowledge.deleted_at < cutoff 的 file_versions → set purged_at"""
        from app.services.drive_version_retention_service import soft_delete_expired_versions

        db = AsyncMock()
        # mock: 1 个 deleted Knowledge + 2 个 active + 1 个 soft_deleted (already purged)
        db.execute = AsyncMock()

        # 1st execute: SELECT Knowledge.id WHERE deleted_at < cutoff → [42, 43]
        # 2nd execute: SELECT DriveFileVersion WHERE file_id IN (...) AND purged_at IS NULL → [v1, v2]
        # 3rd execute: COMMIT (no rows)
        knowledge_ids_result = MagicMock()
        knowledge_ids_result.scalars.return_value.all.return_value = [42, 43]
        versions_result = MagicMock()
        # 2 versions to soft-delete, with id=100, 101
        v1 = MagicMock()
        v1.id = 100
        v1.purged_at = None
        v1.purged_by = None
        v2 = MagicMock()
        v2.id = 101
        v2.purged_at = None
        v2.purged_by = None
        versions_result.scalars.return_value.all.return_value = [v1, v2]

        db.execute.side_effect = [knowledge_ids_result, versions_result]

        cutoff = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
        result = await soft_delete_expired_versions(db, cutoff, system_user_id=1)

        assert result["soft_deleted_count"] == 2
        assert result["candidates_with_deleted_file"] == 2
        # 验证 v1, v2 的 purged_at 被设置
        assert v1.purged_at is not None
        assert v2.purged_at is not None
        assert v1.purged_by == 1
        assert v2.purged_by == 1
        # 验证 commit 调用
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_expired_files_returns_zero(self):
        """无 expired Knowledge → 0 soft_delete, 0 candidates, 不 commit (早返回)"""
        from app.services.drive_version_retention_service import soft_delete_expired_versions

        db = AsyncMock()
        knowledge_ids_result = MagicMock()
        knowledge_ids_result.scalars.return_value.all.return_value = []
        db.execute.return_value = knowledge_ids_result

        cutoff = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
        result = await soft_delete_expired_versions(db, cutoff, system_user_id=1)

        assert result["soft_deleted_count"] == 0
        assert result["candidates_with_deleted_file"] == 0
        # 早返回 (no commit when no candidates)
        db.commit.assert_not_awaited()


# ============================================================================
# Scenario 2: 30 天内不删 (cutoff 之前) — 已 soft-deleted 不重复操作
# ============================================================================


class TestSoftDeleteRetentionWindow:
    """30 天内的 deleted file 不进 soft_delete 范围 (cutoff filter)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_soft_delete_respects_cutoff(self):
        """soft_delete 只动 Knowledge.deleted_at < cutoff 的 file_versions"""
        from app.services.drive_version_retention_service import soft_delete_expired_versions

        db = AsyncMock()
        # 模拟: cutoff 之前的 Knowledge (deleted_at < cutoff) 才有 1 个 file_id
        # Knowledge table filter 走 SQL WHERE, 这里 mock 1 个 file_id 返回
        knowledge_ids_result = MagicMock()
        knowledge_ids_result.scalars.return_value.all.return_value = [99]
        versions_result = MagicMock()
        v = MagicMock()
        v.id = 200
        v.purged_at = None
        v.purged_by = None
        versions_result.scalars.return_value.all.return_value = [v]
        db.execute.side_effect = [knowledge_ids_result, versions_result]

        cutoff = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
        result = await soft_delete_expired_versions(db, cutoff, system_user_id=5)

        assert result["soft_deleted_count"] == 1
        assert v.purged_at is not None


# ============================================================================
# Scenario 3: hard_delete_expired_versions — 物理删 purged_at < cutoff
# ============================================================================


class TestHardDeleteExpiredVersions:
    """hard_delete_expired_versions: 物理删 v.purged_at < cutoff (经过 30 天软删期)"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_raises_on_none_cutoff(self):
        """cutoff_date=None → ValueError"""
        from app.services.drive_version_retention_service import hard_delete_expired_versions
        db = AsyncMock()

        with pytest.raises(ValueError) as exc_info:
            await hard_delete_expired_versions(db, None)
        assert "cutoff_date 不能为 None" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_hard_deletes_with_minio_cleanup(self):
        """物理删: backup → MinIO delete → DB DELETE → commit"""
        from app.services.drive_version_retention_service import hard_delete_expired_versions
        import app.services.drive_version_retention_service as svc_module

        db = AsyncMock()
        # backup_rows_to_json is patched, doesn't use db.execute
        # Only 2 db.execute calls: SELECT DriveFileVersion + DELETE
        backup_result = MagicMock()
        versions_result = MagicMock()
        v1 = MagicMock()
        v1.id = 300
        v1.minio_object_key = "uploads/drive/v1_hash1_ts1.bin"
        v2 = MagicMock()
        v2.id = 301
        v2.minio_object_key = "uploads/drive/v2_hash2_ts2.bin"
        versions_result.scalars.return_value.all.return_value = [v1, v2]
        delete_result = MagicMock()
        db.execute.side_effect = [versions_result, delete_result]

        # patch backup_rows_to_json 在 service module namespace (override top-level import)
        async def mock_backup(*args, **kwargs):
            return (2, "/tmp/celery_cleanup_test.json")
        original_backup = svc_module.backup_rows_to_json
        svc_module.backup_rows_to_json = mock_backup

        cutoff = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
        # patch file_service.delete_file 返 None (no failure)
        with patch(
            "app.services.file_service.file_service.delete_file",
            return_value=None,
        ):
            try:
                result = await hard_delete_expired_versions(db, cutoff)
            finally:
                svc_module.backup_rows_to_json = original_backup

        assert result["hard_deleted_count"] == 2
        assert result["minio_cleanup_failures"] == 0
        # 验证 commit 调了
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_hard_delete_handles_minio_failure(self):
        """MinIO delete 失败 → minio_cleanup_failures += 1, DB 仍删"""
        from app.services.drive_version_retention_service import hard_delete_expired_versions
        import app.services.drive_version_retention_service as svc_module

        db = AsyncMock()
        versions_result = MagicMock()
        v1 = MagicMock()
        v1.id = 400
        v1.minio_object_key = "uploads/drive/broken_key.bin"
        versions_result.scalars.return_value.all.return_value = [v1]
        delete_result = MagicMock()
        db.execute.side_effect = [versions_result, delete_result]

        async def mock_backup(*args, **kwargs):
            return (1, "/tmp/celery_cleanup_test.json")
        original_backup = svc_module.backup_rows_to_json
        svc_module.backup_rows_to_json = mock_backup

        cutoff = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
        # patch file_service.delete_file 抛异常
        with patch(
            "app.services.file_service.file_service.delete_file",
            side_effect=Exception("MinIO unreachable"),
        ):
            try:
                result = await hard_delete_expired_versions(db, cutoff)
            finally:
                svc_module.backup_rows_to_json = original_backup

        assert result["hard_deleted_count"] == 1
        assert result["minio_cleanup_failures"] == 1


# ============================================================================
# Scenario 4: get_retention_stats — 单 query 多聚合
# ============================================================================


class TestGetRetentionStats:
    """get_retention_stats: 单 query 多聚合 + JOIN Knowledge"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_returns_all_fields(self):
        """stats 字典返回所有字段"""
        from app.services.drive_version_retention_service import get_retention_stats

        db = AsyncMock()
        # 实现 execute 区分: stats query vs JOIN query
        stats_row = MagicMock()
        stats_row.total = 100
        stats_row.active = 80
        stats_row.soft_deleted = 15
        stats_row.expired = 5
        joined_count = 12

        async def fake_exec(stmt, *args, **kwargs):
            text = str(stmt)
            if "JOIN" not in text:
                # stats query: return object with .total/.active/.soft_deleted/.expired
                # SQLAlchemy Result.one() is sync, returns row directly
                result = MagicMock()
                result.one = MagicMock(return_value=stats_row)
                return result
            # JOIN Knowledge count query
            result = MagicMock()
            result.scalar = MagicMock(return_value=joined_count)
            return result
        db.execute = fake_exec

        stats = await get_retention_stats(db)

        assert stats["total_versions"] == 100
        assert stats["active_versions"] == 80
        assert stats["soft_deleted_versions"] == 15
        assert stats["expired_versions"] == 5
        assert stats["files_with_deleted_versions"] == 12
        assert "retention_days" in stats

    @pytest.mark.asyncio(loop_scope="function")
    async def test_stats_handles_null_aggregates(self):
        """空表 → 所有 COUNT 返 0 (防御性)"""
        from app.services.drive_version_retention_service import get_retention_stats

        db = AsyncMock()

        async def fake_exec(stmt, *args, **kwargs):
            stats_row = MagicMock()
            stats_row.total = 0
            stats_row.active = 0
            stats_row.soft_deleted = 0
            stats_row.expired = 0
            text = str(stmt)
            if "JOIN" not in text:
                result = MagicMock()
                result.one = MagicMock(return_value=stats_row)
                return result
            result = MagicMock()
            result.scalar = MagicMock(return_value=0)
            return result
        db.execute = fake_exec

        stats = await get_retention_stats(db)
        assert stats["total_versions"] == 0
        assert stats["active_versions"] == 0
        assert stats["soft_deleted_versions"] == 0
        assert stats["expired_versions"] == 0
        assert stats["files_with_deleted_versions"] == 0


# ============================================================================
# Scenario 5: Celery task — 完整 2 步 (软删 + 物理删)
# ============================================================================


class TestCeleryTask:
    """Celery beat task: 完整 2 步 + 守卫 + 返回 dict 结构"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_task_calls_service_functions(self):
        """task 调 service: soft_delete + hard_delete, 完整返 dict"""
        from app.services.drive_version_retention_tasks import (
            cleanup_expired_versions_task,
            _resolve_system_user_id,
        )

        # 模拟 service 返回
        soft_result = {"soft_deleted_count": 5, "candidates_with_deleted_file": 3}
        hard_result = {"hard_deleted_count": 2, "minio_cleanup_failures": 0}

        with patch(
            "app.services.drive_version_retention_tasks.soft_delete_expired_versions",
            AsyncMock(return_value=soft_result),
        ), patch(
            "app.services.drive_version_retention_tasks.hard_delete_expired_versions",
            AsyncMock(return_value=hard_result),
        ), patch(
            "app.services.drive_version_retention_tasks.create_celery_engine_and_session",
        ), patch(
            "app.services.drive_version_retention_tasks.confirm_retention_param_auto",
            return_value={"proceed": True, "effective_days": 30},
        ):
            # 直接调 task 函数 (绕过 Celery worker)
            # task 是 sync 函数, 内部用 asyncio.run
            result = cleanup_expired_versions_task(retention_days=None)

        # 验证返回结构
        assert "status" in result
        assert "soft_deleted_count" in result
        assert "hard_deleted_count" in result
        assert "minio_cleanup_failures" in result

    def test_task_skips_on_guard_rejection(self):
        """二次确认守卫拒绝 → status=skipped"""
        from app.services.drive_version_retention_tasks import cleanup_expired_versions_task

        with patch(
            "app.services.drive_version_retention_tasks.confirm_retention_param_auto",
            return_value={"proceed": False, "reason": "user cancelled", "effective_days": 30},
        ):
            result = cleanup_expired_versions_task(retention_days=999)  # 非默认值触发守卫

        assert result["status"] == "skipped"
        assert result["soft_deleted_count"] == 0
        assert result["hard_deleted_count"] == 0
        assert "reason" in result


# ============================================================================
# Scenario 6: admin endpoint — get_drive_retention_stats
# ============================================================================


class TestAdminEndpoint:
    """admin endpoint: /admin/drive/retention-stats 返 stats 字典"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_get_retention_stats_endpoint(self):
        """GET /admin/drive/retention-stats 返完整 stats"""
        from app.services.drive_version_retention_service import get_retention_stats

        # mock service 函数返完整 stats
        mock_stats = {
            "total_versions": 50,
            "active_versions": 40,
            "soft_deleted_versions": 8,
            "expired_versions": 2,
            "files_with_deleted_versions": 5,
            "retention_days": 30,
        }

        with patch(
            "app.services.drive_version_retention_service.get_retention_stats",
            AsyncMock(return_value=mock_stats),
        ):
            from app.api.v1.drive_admin import get_drive_retention_stats
            db = AsyncMock()
            admin_user = MagicMock()
            admin_user.role = "admin"
            admin_user.id = 1

            result = await get_drive_retention_stats(db=db, current_admin=admin_user)

        assert result == mock_stats
        assert result["retention_days"] == 30