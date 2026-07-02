"""2026-07-02 v2 PR6-P12+ 增量 — drive_cleanup_service 拆分单测

覆盖:
1. _to_naive_datetime: tz-aware / naive / None 转换
2. clean_old_drive_files: 多表清理 + MinIO 删除 + 孤儿 folder 防御
3. 集成范式: 真实 DB 集成测试 (与 chat_history_service.TestCleanup 范式一致)

不依赖真实 DB (mock DB, 与 cleanup_backup / cleanup_safety 范式一致)
- SKIP_DB_SETUP=1 下 fixture 不可用, 所有测试用纯 mock
- 真实 DB 集成测试可在后续 PR 加 (参考 test_chat_history_service.py:TestCleanup 4 case)
"""
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 跳过重型 import (conftest.py 同模式)
SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))


# ============================================================================
# _to_naive_datetime 单元测试
# ============================================================================

class TestToNaiveDatetime:
    """_to_naive_datetime: tz-aware / naive / None 转换 (PG TIMESTAMP 列要求)"""

    def test_naive_passthrough(self):
        """naive → naive (透传)"""
        from app.services.drive_cleanup_service import _to_naive_datetime
        naive = datetime(2026, 7, 2, 12, 0, 0)
        assert _to_naive_datetime(naive) is naive  # 同一对象透传

    def test_aware_strips_tzinfo(self):
        """tz-aware UTC → naive (strip tzinfo, 保留 UTC 时刻值)"""
        from app.services.drive_cleanup_service import _to_naive_datetime
        aware = datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc)
        result = _to_naive_datetime(aware)
        assert result.tzinfo is None
        assert result == datetime(2026, 7, 2, 12, 0, 0)

    def test_none_returns_none(self):
        """None → None (防御性 fallback)"""
        from app.services.drive_cleanup_service import _to_naive_datetime
        assert _to_naive_datetime(None) is None


# ============================================================================
# clean_old_drive_files 单元测试 (纯 mock)
# ============================================================================

class TestCleanOldDriveFiles:
    """clean_old_drive_files: 多表清理 + MinIO 删除 + 孤儿 folder 防御

    与 chat_history_service.cleanup_soft_deleted_sessions 关键差异:
    - drive 多张表 (Knowledge + Folder), chat_history 单表
    - drive 拆 backup_rows_to_json + 显式 DELETE (folder 表需先 SELECT 检查)
    - drive MinIO 物理删除 (失败不阻塞 DB 硬删)
    """

    @pytest.mark.asyncio(loop_scope="function")
    async def test_clean_old_drive_files_raises_on_none_cutoff(self):
        """cutoff_date=None → ValueError (caller 应传 datetime.now - timedelta)"""
        from app.services.drive_cleanup_service import clean_old_drive_files
        db = AsyncMock()

        with pytest.raises(ValueError) as exc_info:
            await clean_old_drive_files(db, None)
        assert "cutoff_date 不能为 None" in str(exc_info.value)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_clean_old_drive_files_naive_cutoff_works(self):
        """cutoff_date 接受 naive datetime (内部统一 .replace(tzinfo=None))"""
        from app.services.drive_cleanup_service import clean_old_drive_files
        import app.services.drive_cleanup_service as svc_module

        db = MagicMock()
        # mock execute 返回空结果 (0 行场景)
        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result_empty)
        db.commit = AsyncMock()

        cutoff_naive = datetime(2026, 7, 2, 12, 0, 0)  # naive
        # patch 在 service module namespace (override local import binding)
        async def mock_backup(*args, **kwargs):
            return (0, None)
        original_backup = svc_module.backup_rows_to_json
        svc_module.backup_rows_to_json = mock_backup
        try:
            result = await clean_old_drive_files(db, cutoff_naive)
        finally:
            svc_module.backup_rows_to_json = original_backup

        assert result["deleted_files"] == 0
        assert result["deleted_folders"] == 0
        assert result["skipped_folders"] == 0
        assert result["minio_cleanup_failures"] == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_clean_old_drive_files_aware_cutoff_stripped(self):
        """tz-aware UTC cutoff → 内部统一 strip tzinfo (PG TIMESTAMP 列要求)"""
        from app.services.drive_cleanup_service import clean_old_drive_files
        import app.services.drive_cleanup_service as svc_module

        db = MagicMock()
        mock_result_empty = MagicMock()
        mock_result_empty.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result_empty)
        db.commit = AsyncMock()

        cutoff_aware = datetime.now(timezone.utc) - timedelta(days=3)  # tz-aware
        # patch 在 service module namespace
        async def mock_backup(*args, **kwargs):
            return (0, None)
        original_backup = svc_module.backup_rows_to_json
        svc_module.backup_rows_to_json = mock_backup
        try:
            # 不应抛 "can't subtract offset-naive and offset-aware datetimes" 错
            result = await clean_old_drive_files(db, cutoff_aware)
        finally:
            svc_module.backup_rows_to_json = original_backup
        assert result["deleted_files"] == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_clean_old_drive_files_minio_failure_does_not_block_db(self):
        """MinIO 删除失败 → minio_cleanup_failures += 1, DB 行仍硬删 (防御性)"""
        from app.services.drive_cleanup_service import clean_old_drive_files
        import app.services.drive_cleanup_service as svc_module

        # mock expired files: 1 个 file_path, MinIO delete 抛异常
        class FakeFile:
            id = 100
            file_path = "drive/100/test.pdf"

        mock_files_result = MagicMock()
        mock_files_result.scalars.return_value.all.return_value = [FakeFile()]
        mock_empty = MagicMock()
        mock_empty.scalars.return_value.all.return_value = []

        # service 顺序: backup_files (call 1, mock_backup 内部 0 execute) → 返 (1, ...)
        # → if deleted > 0: DELETE files (call 2) → mock_files_result
        # → SELECT files (call 3) → mock_files_result (1 file)
        # → MinIO delete_file 抛 IOError (mock patch) → minio_cleanup_failures=1
        # → backup_folder (call 4, mock_backup 内部 0 execute) → 返 (0, None)
        # → SELECT folder (call 5) → mock_empty (0 folders)
        # → scalar 不调 (loop 0 次)
        call_count = {"n": 0}
        async def execute_seq(*args, **kwargs):
            call_count["n"] += 1
            # call 1: DELETE files (返 mock_files_result, 不需要数据)
            # call 2: SELECT files (返 1 file → MinIO 失败路径)
            # call 3: SELECT folder (返 0 folders)
            if call_count["n"] in (1, 2):
                return mock_files_result
            return mock_empty

        async def mock_backup(*args, **kwargs):
            # 第一次 (files backup) 返 1, 第二次 (folder backup) 返 0
            if not hasattr(mock_backup, "call_count"):
                mock_backup.call_count = 0
            mock_backup.call_count += 1
            if mock_backup.call_count == 1:
                return (1, "/tmp/test.json")
            return (0, None)

        db = MagicMock()
        db.execute = AsyncMock(side_effect=execute_seq)
        db.scalar = AsyncMock(return_value=0)
        db.commit = AsyncMock()

        original_backup = svc_module.backup_rows_to_json
        svc_module.backup_rows_to_json = mock_backup
        try:
            # mock file_service.delete_file 抛 IOError
            with patch("app.services.file_service.file_service") as mock_fs:
                mock_fs.delete_file.side_effect = IOError("MinIO connection refused")
                result = await clean_old_drive_files(db, datetime.now(timezone.utc) - timedelta(days=3))
        finally:
            svc_module.backup_rows_to_json = original_backup

        # MinIO 失败计数 1, 但 DB 已硬删 (deleted_files=1)
        assert result["deleted_files"] == 1
        assert result["minio_cleanup_failures"] == 1
        assert result["deleted_folders"] == 0
        # commit 仍被调用 (DB 行硬删已生效)
        db.commit.assert_called_once()

    @pytest.mark.asyncio(loop_scope="function")
    async def test_clean_old_drive_files_skips_folders_with_children(self):
        """folder 有未清理子文件 → 跳过 (skipped_folders += 1)"""
        from app.services.drive_cleanup_service import clean_old_drive_files
        import app.services.drive_cleanup_service as svc_module

        # mock 2 folders: 1 个孤儿 (safe_to_delete), 1 个有子 (skipped)
        class FakeFolder:
            def __init__(self, id):
                self.id = id

        folder_orphan = FakeFolder(10)
        folder_with_child = FakeFolder(20)

        mock_folders_list = [folder_orphan, folder_with_child]

        # mock execute 序列 (按 service 实际调用顺序):
        # call 1: backup_files (mock_backup 返 0 → 跳过 DELETE call 2)
        # call 2: SELECT files (返 mock_empty, mock_backup 返 0 跳过 DELETE)
        # call 3: backup_folder (mock_backup 返 0 → backup helper 内部不调 execute, 直接 count)
        # call 4: SELECT folder (返 2 folders, 然后 loop 中调 scalar 2 次 × 2 folders = 4 次)
        async def execute_side_effect(*args, **kwargs):
            # 单个 MagicMock 用来记录调用顺序
            if not hasattr(execute_side_effect, "calls"):
                execute_side_effect.calls = []
            execute_side_effect.calls.append("execute")
            return mock_empty  # 默认返空 (backup_files, SELECT_files)

        # 让 backup 返 (0, None), 模拟真实流程
        # mock backup 直接返 0 count, 不需要 mock execute
        async def mock_backup(*args, **kwargs):
            return (0, None)  # 0 files, 0 folders

        # SELECT folder 需要返 2 folders, 必须在 mock_backup 之后再 mock execute
        # service 顺序: backup_files (call 1) → mock_backup 内部 0 execute → SELECT files (call 2)
        # → backup_folder (call 3) → mock_backup 内部 0 execute → SELECT folder (call 4) → 2 folders
        # scalar loop: 2 folders × 2 scalar = 4 次

        # 但 backup_rows_to_json 在 SKIP_DB_SETUP 模式下 mock 后不会真调 db.execute
        # 所以 service 真调 db.execute 的次数 = 2 (SELECT files + SELECT folder)
        # 加上 if deleted_file_count > 0: DELETE (这里 deleted=0 跳过)

        mock_empty = MagicMock()
        mock_empty.scalars.return_value.all.return_value = []
        mock_folders_result = MagicMock()
        mock_folders_result.scalars.return_value.all.return_value = mock_folders_list

        call_count = {"n": 0}
        async def execute_seq(*args, **kwargs):
            call_count["n"] += 1
            # call 1: SELECT files (0 files)
            # call 2: SELECT folder (2 folders)
            if call_count["n"] == 1:
                return mock_empty
            return mock_folders_result

        # scalar 顺序: orphan folder (2 scalar: child_folder=0, child_file=0)
        #              with_child folder (2 scalar: child_folder=1, child_file=0)
        scalar_count = {"n": 0}
        async def scalar_seq(*args, **kwargs):
            scalar_count["n"] += 1
            if scalar_count["n"] in (1, 2):
                return 0  # orphan: no children
            elif scalar_count["n"] == 3:
                return 1  # with_child: has child folder
            return 0  # with_child: no child file

        db = MagicMock()
        db.execute = AsyncMock(side_effect=execute_seq)
        db.scalar = AsyncMock(side_effect=scalar_seq)
        db.commit = AsyncMock()

        original_backup = svc_module.backup_rows_to_json
        svc_module.backup_rows_to_json = mock_backup
        try:
            result = await clean_old_drive_files(db, datetime.now(timezone.utc) - timedelta(days=3))
        finally:
            svc_module.backup_rows_to_json = original_backup

        # orphan (id=10) 应被删, with_child (id=20) 跳过
        assert result["deleted_files"] == 0
        assert result["deleted_folders"] == 1
        assert result["skipped_folders"] == 1


# ============================================================================
# drive_cleanup_tasks 拆分 sanity check (Celery task 调 service 集成)
# ============================================================================

class TestDriveCleanupTasksWrapper:
    """drive_cleanup_tasks.py 是 thin Celery wrapper, 调 clean_old_drive_files()

    验证:
    1. cleanup_expired_drive_files_task 仍是 @celery_app.task (Celery 调度不断)
    2. task 函数体调用 clean_old_drive_files() (不再内联 SQL)
    3. 保留 NullPool + 二次确认守卫 + asyncio.run + logger.warning 输出
    """

    def test_task_is_celery_registered(self):
        """cleanup_expired_drive_files_task 仍是 Celery task (调度不断)"""
        from app.services.drive_cleanup_tasks import cleanup_expired_drive_files_task
        # Celery task 有 .name 属性 (注册到 Celery app)
        assert hasattr(cleanup_expired_drive_files_task, "name")
        assert cleanup_expired_drive_files_task.name == "app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task"

    def test_task_body_calls_service_function(self):
        """task 函数源码应调 clean_old_drive_files (不再内联 SQL)"""
        import inspect
        from app.services import drive_cleanup_tasks
        source = inspect.getsource(drive_cleanup_tasks)
        # 必须调 service 函数
        assert "clean_old_drive_files" in source
        # 不应内联 SELECT / DELETE SQL (避免重复逻辑)
        assert "select(Knowledge)" not in source
        assert "delete(Knowledge)" not in source
        assert "delete(Folder)" not in source
        assert "backup_rows_to_json" not in source  # 移到 service 内

    def test_task_keeps_guard_and_nullpool(self):
        """task 仍保留 PR6-P11+ 守卫 + NullPool 引擎 (不回归)"""
        import inspect
        from app.services import drive_cleanup_tasks
        source = inspect.getsource(drive_cleanup_tasks)
        # PR6-P11+ 二次确认守卫
        assert "confirm_retention_param_auto" in source
        # NullPool 引擎范式
        assert "NullPool" in source
        assert "create_async_engine" in source
        # asyncio.run 范式
        assert "asyncio.run" in source
        # Celery beat schedule 入口
        assert 'name="app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task"' in source

    def test_task_keeps_logger_output(self):
        """task 仍保留 logger.warning 输出 (健康监控 + 审计追溯)"""
        import inspect
        from app.services import drive_cleanup_tasks
        source = inspect.getsource(drive_cleanup_tasks)
        # 健康日志
        assert "🗑️ [drive_cleanup]" in source or "drive_cleanup" in source
        assert "logger.warning" in source
        assert "logger.info" in source
        assert "logger.error" in source


# ============================================================================
# drive_cleanup_service 公共 API 签名验证 (import + callability)
# ============================================================================

class TestDriveCleanupServiceAPI:
    """验证 drive_cleanup_service 暴露的公共 API 与 chat_history_service 范式一致"""

    def test_service_module_importable(self):
        """drive_cleanup_service 可独立 import (不依赖 Celery / FastAPI)"""
        if SKIP_DB_SETUP:
            pytest.skip("SKIP_DB_SETUP=1：service 模块依赖重型 app.models, 跳过 import 测试")
        from app.services.drive_cleanup_service import clean_old_drive_files, _to_naive_datetime
        assert callable(clean_old_drive_files)
        assert callable(_to_naive_datetime)

    def test_service_signature_matches_chat_history_paradigm(self):
        """service 签名与 chat_history_service.cleanup_soft_deleted_sessions 范式一致
        (async def X(db: AsyncSession, cutoff_date: datetime) -> dict|int)
        """
        if SKIP_DB_SETUP:
            pytest.skip("SKIP_DB_SETUP=1：跳过签名检查")
        import inspect
        from app.services.drive_cleanup_service import clean_old_drive_files
        sig = inspect.signature(clean_old_drive_files)
        params = list(sig.parameters.keys())
        # 必须有 db 和 cutoff_date
        assert "db" in params
        assert "cutoff_date" in params
        # 返回类型注解应该是 dict (drive 多张表, 不是 int)
        assert sig.return_annotation is dict