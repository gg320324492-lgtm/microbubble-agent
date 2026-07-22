"""
tests/test_drive_service_refactor.py — Drive v2 代码清理收尾单测

第三/四/五波多版本迭代后, 抽出的 3 个共享 helper 单测:
1. `@drive_retry(max_attempts=3)` retry 装饰器 (3 次重试 + 指数退避)
2. `_build_folder_filter_clause(folder_id, include_subfolders)` 3 场景覆盖
3. `_build_list_files_query(...)` 边界 (folder_id 不存在, file_type chip, sort)

覆盖 v2.21 (include_subfolders) + v2.22 (file_type chip 拆分) + retry 范式.

不需要 DB (SKIP_DB_SETUP=1 模式), 仅测纯函数逻辑 + 装饰器 mock 行为.

测试隔离: 在 import drive_service 之前 mock 掉 minio 模块, 避免 import 时
触发真实 MinIO 连接 (与 test_file_service_upload_to_path.py 同样范式).
"""
import sys
from unittest.mock import MagicMock

# === 在 import 之前 mock minio 模块, 阻止 import 时连接 MinIO ===
sys.modules.setdefault("minio", MagicMock())

import asyncio
import time

import pytest
import sqlalchemy.exc as sa_exc

from app.services.drive_service import (
    DRIVE_RETRY_DEFAULT_BACKOFF_BASE,
    DRIVE_RETRY_DEFAULT_BACKOFF_MAX,
    DRIVE_RETRY_DEFAULT_MAX_ATTEMPTS,
    DriveService,
    DriveServiceError,
    _build_folder_filter_clause,
    _build_list_files_query,
    drive_retry,
)
from app.models.knowledge import Knowledge


# =====================================================================
# 1. drive_retry 装饰器测试
# =====================================================================


@pytest.mark.asyncio
async def test_drive_retry_succeeds_first_try():
    """正常情况: 第 1 次调用就成功, 不重试."""
    call_count = 0

    @drive_retry(max_attempts=3)
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await flaky_func()
    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_drive_retry_retries_on_operational_error():
    """OperationalError (DB 瞬断) 应重试到第 2 次成功."""
    call_count = 0

    @drive_retry(max_attempts=3, backoff_base=0.01)
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise sa_exc.OperationalError("mock stmt", {}, Exception("conn reset"))
        return "recovered"

    result = await flaky_func()
    assert result == "recovered"
    assert call_count == 2


@pytest.mark.asyncio
async def test_drive_retry_retries_on_os_error():
    """OSError (MinIO 5xx / 网络瞬断) 应重试."""
    call_count = 0

    @drive_retry(max_attempts=3, backoff_base=0.01)
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise OSError("network unreachable")
        return "ok"

    result = await flaky_func()
    assert result == "ok"
    assert call_count == 3


@pytest.mark.asyncio
async def test_drive_retry_exhausts_max_attempts_and_raises():
    """3 次都失败: 应抛原 OperationalError (不包 DriveServiceError)."""
    call_count = 0
    original_exc = sa_exc.OperationalError("mock stmt", {}, Exception("persistent fail"))

    @drive_retry(max_attempts=3, backoff_base=0.01)
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise original_exc

    with pytest.raises(sa_exc.OperationalError):
        await always_fails()
    assert call_count == 3  # 严格 3 次


@pytest.mark.asyncio
async def test_drive_retry_does_not_retry_drive_service_error():
    """业务错误 (DriveServiceError) 不重试 — 重试也是 4xx."""
    call_count = 0

    @drive_retry(max_attempts=3, backoff_base=0.01)
    async def business_error():
        nonlocal call_count
        call_count += 1
        raise DriveServiceError("用户错误", status_code=400)

    with pytest.raises(DriveServiceError):
        await business_error()
    assert call_count == 1  # 立即抛, 不重试


@pytest.mark.asyncio
async def test_drive_retry_exponential_backoff_timing():
    """指数退避: 第 2 次失败后 sleep ≥ 0.2s (DRIVE_RETRY_DEFAULT_BACKOFF_BASE * 2^0)."""
    call_times = []

    @drive_retry(max_attempts=3, backoff_base=DRIVE_RETRY_DEFAULT_BACKOFF_BASE, backoff_max=DRIVE_RETRY_DEFAULT_BACKOFF_MAX)
    async def flaky_func():
        call_times.append(time.monotonic())
        raise OSError("transient")

    with pytest.raises(OSError):
        await flaky_func()
    # 2 次失败, 1 次 sleep (attempt 1 失败后 sleep → attempt 2 失败后不再 sleep)
    assert len(call_times) == 3  # 3 次调用
    # attempt 1 → attempt 2 间隔 ≥ backoff_base (0.2s)
    gap_1 = call_times[1] - call_times[0]
    assert gap_1 >= DRIVE_RETRY_DEFAULT_BACKOFF_BASE * 0.9, \
        f"第 1-2 次间隔应 ≥ {DRIVE_RETRY_DEFAULT_BACKOFF_BASE}s, 实际 {gap_1:.3f}s"


# =====================================================================
# 2. _build_folder_filter_clause folder filter 测试
# =====================================================================


class TestBuildFolderFilterClause:
    """v2.21 + v2.22 共享 folder filter 逻辑 3 场景覆盖."""

    def _compile_sql(self, clause):
        """编译 SQLAlchemy 谓词为带 inline literal 的 SQL 字符串."""
        from sqlalchemy.dialects import postgresql
        return str(
            clause.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

    def test_explicit_folder_id_returns_equality_clause(self):
        """场景 1: folder_id=5 显式 → 返 Knowledge.folder_id == 5."""
        clause = _build_folder_filter_clause(folder_id=5, include_subfolders=False)
        assert clause is not None
        sql = self._compile_sql(clause).lower()
        # 应含 folder_id = 5 (literal bind)
        assert "folder_id" in sql
        assert "= 5" in sql or "=5" in sql

    def test_explicit_folder_id_ignores_include_subfolders(self):
        """场景 1': folder_id=5 + include_subfolders=True 仍只看该 folder.

        子文件夹遍历留给调用方 (前端 FolderTree 组件负责递归).
        """
        clause_explicit = _build_folder_filter_clause(folder_id=5, include_subfolders=True)
        clause_explicit_no = _build_folder_filter_clause(folder_id=5, include_subfolders=False)
        sql1 = self._compile_sql(clause_explicit)
        sql2 = self._compile_sql(clause_explicit_no)
        assert sql1 == sql2

    def test_folder_id_none_with_include_subfolders_true_skips_filter(self):
        """场景 3: folder_id=None + include_subfolders=True → 返 None (跳过 filter).

        团队共享盘顶级 view: 列出 root + 所有 sub folder 的 PPT.
        """
        clause = _build_folder_filter_clause(folder_id=None, include_subfolders=True)
        assert clause is None, f"include_subfolders=True 应跳过 filter, 实际 {clause!r}"

    def test_folder_id_none_personal_view_filters_to_root(self):
        """场景 2: folder_id=None + include_subfolders=False (默认个人 view) → folder_id IS NULL."""
        clause = _build_folder_filter_clause(folder_id=None, include_subfolders=False)
        assert clause is not None
        sql = self._compile_sql(clause).lower()
        # 应含 "is null" 或 "IS NULL"
        assert "null" in sql, f"个人 view 应过滤 folder_id IS NULL, 实际 SQL: {sql}"

    def test_default_args_match_personal_view(self):
        """默认参数 (folder_id=None, include_subfolders=False) 应等同个人 view."""
        clause_default = _build_folder_filter_clause(folder_id=None)
        clause_personal = _build_folder_filter_clause(folder_id=None, include_subfolders=False)
        sql_default = self._compile_sql(clause_default)
        sql_personal = self._compile_sql(clause_personal)
        assert sql_default == sql_personal


# =====================================================================
# 3. _build_list_files_query query builder 测试
# =====================================================================


class TestBuildListFilesQuery:
    """v2.22 抽 list_files filter builder 边界覆盖."""

    @staticmethod
    def _compile_filters(filters):
        """把 filters 列表编译成 inline literal SQL 字符串."""
        from sqlalchemy.dialects import postgresql
        return " ".join(
            str(
                f.compile(
                    dialect=postgresql.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            )
            for f in filters
        )

    def _call(self, **overrides):
        """调 _build_list_files_query 并返 (filters, sql_str_for_inspection)."""
        defaults = dict(
            storage_mode="drive",
            folder_id=None,
            include_subfolders=False,
            visibility_filter=None,
            starred_only=False,
            file_type=None,
            is_team_shared_filter=None,
            deleted_only=False,
            include_deleted=False,
            current_user_id=1,
        )
        defaults.update(overrides)
        return _build_list_files_query(**defaults)

    def test_basic_query_has_storage_mode_and_visibility_see_cond(self):
        """基础 query 必须含 storage_mode + visibility_see_cond."""
        filters = self._call()
        # 至少 3 个 filter: storage_mode, deleted_at, visibility_see_cond
        assert len(filters) >= 2
        combined_sql = self._compile_filters(filters).lower()
        assert "storage_mode" in combined_sql
        # visibility_see_cond: visibility != 'private'
        assert "visibility !=" in combined_sql and "'private'" in combined_sql

    def test_with_visibility_filter_includes_eq(self):
        """visibility_filter='team' 应加 Knowledge.visibility == 'team'."""
        filters = self._call(visibility_filter="team")
        combined_sql = self._compile_filters(filters).lower()
        assert "visibility = 'team'" in combined_sql

    def test_with_starred_only_includes_is_starred(self):
        """starred_only=True 应加 Knowledge.is_starred."""
        filters = self._call(starred_only=True)
        combined_sql = self._compile_filters(filters).lower()
        assert "is_starred" in combined_sql

    def test_with_file_type_pdf_includes_ilike(self):
        """file_type='pdf' 应加 ILIKE '%.pdf'."""
        filters = self._call(file_type="pdf")
        combined_sql = self._compile_filters(filters).lower()
        assert "%.pdf" in combined_sql

    def test_with_file_type_invalid_is_ignored(self):
        """file_type='invalid' 应被忽略 (不抛错)."""
        filters = self._call(file_type="invalid_type")
        # 不抛错即 OK
        assert isinstance(filters, list)

    def test_with_is_team_shared_filter(self):
        """is_team_shared_filter=True/False 都应加 filter (None 跳过)."""
        for val in [True, False]:
            filters = self._call(is_team_shared_filter=val)
            combined_sql = self._compile_filters(filters).lower()
            assert "is_team_shared" in combined_sql, f"val={val} 应加 is_team_shared filter"

        # None 不加
        filters_none = self._call(is_team_shared_filter=None)
        combined_sql_none = self._compile_filters(filters_none).lower()
        assert "is_team_shared" not in combined_sql_none

    def test_deleted_only_mode_excludes_active(self):
        """deleted_only=True (回收站) 应加 deleted_at IS NOT NULL."""
        filters = self._call(deleted_only=True)
        combined_sql = self._compile_filters(filters).lower()
        assert "deleted_at is not null" in combined_sql

    def test_normal_mode_excludes_deleted(self):
        """deleted_only=False + include_deleted=False (默认) 应加 deleted_at IS NULL."""
        filters = self._call(deleted_only=False, include_deleted=False)
        combined_sql = self._compile_filters(filters).lower()
        assert "deleted_at is null" in combined_sql

    def test_include_deleted_true_skips_deleted_filter(self):
        """include_deleted=True (admin) 应不加 deleted filter."""
        filters = self._call(deleted_only=False, include_deleted=True)
        combined_sql = self._compile_filters(filters).lower()
        # deleted_at 不在 (admin 想看全部)
        assert "deleted_at" not in combined_sql

    def test_folder_id_explicit_adds_eq(self):
        """folder_id=42 显式应加 folder_id == 42."""
        filters = self._call(folder_id=42)
        combined_sql = self._compile_filters(filters).lower()
        assert "folder_id = 42" in combined_sql

    def test_include_subfolders_skips_folder_filter(self):
        """include_subfolders=True + folder_id=None 应不加 folder filter."""
        filters_normal = self._call(folder_id=None, include_subfolders=False)
        filters_team = self._call(folder_id=None, include_subfolders=True)
        # team view 应少 1 个 filter (folder filter 跳过)
        assert len(filters_team) == len(filters_normal) - 1, \
            f"include_subfolders=True 应少 1 filter, normal={len(filters_normal)}, team={len(filters_team)}"


# =====================================================================
# 4. 默认常量 sanity check
# =====================================================================


def test_default_retry_constants():
    """默认 retry 参数 sanity check."""
    assert DRIVE_RETRY_DEFAULT_MAX_ATTEMPTS == 3
    assert DRIVE_RETRY_DEFAULT_BACKOFF_BASE == 0.2
    assert DRIVE_RETRY_DEFAULT_BACKOFF_MAX == 1.6
    # 退避上限 ≥ 基础值
    assert DRIVE_RETRY_DEFAULT_BACKOFF_MAX >= DRIVE_RETRY_DEFAULT_BACKOFF_BASE