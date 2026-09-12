"""alembic 019 迁移测试（v2 reminder 字段 + members JSON）

验证 upgrade 后 reminders 6 列 + members 1 JSON 列就位。

2026-09-12 生产库测试迁移:
- engine 改 tests.conftest.get_test_engine (原 app.core.database.engine 直连生产库)
- 检查方式从 sync inspect 改 async run_sync — sync 路径对 async engine 的
  连接池必抛 MissingGreenlet (旧版在真库上同样报错, 非本次迁移引入)
- reminder_indexes 加 ALEMBIC_VERIFY=1 门禁: idx_reminder_* 3 个索引由
  alembic 019 迁移创建 (模型未声明), create_all 测试库不存在; 列校验是
  模型驱动的, 保持常开。
SKIP_DB_SETUP=1 时整文件 skip。
"""
import os
import pytest
from sqlalchemy import inspect


# SKIP_DB_SETUP=1 时整文件跳过 (跟 conftest db fixture 跳过逻辑一致)
SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))
ALEMBIC_VERIFY = bool(os.getenv("ALEMBIC_VERIFY"))
NEED_MIGRATED_DB = pytest.mark.skipif(
    not ALEMBIC_VERIFY,
    reason=(
        "迁移专属索引 (alembic 019 建, 模型未声明) 在 create_all 测试库不存在; "
        "ALEMBIC_VERIFY=1 且 TEST_DATABASE_URL 指向 alembic-migrated 库时开启"
    ),
)

pytestmark = pytest.mark.skipif(
    SKIP_DB_SETUP,
    reason="SKIP_DB_SETUP=1：migration 验证测试需要真 DB, 整文件 skip",
)


async def _get_columns(table: str) -> set:
    from tests.conftest import get_test_engine  # 2026-09-12 测试库隔离
    engine = get_test_engine()
    async with engine.connect() as conn:
        rows = await conn.run_sync(
            lambda c: [col["name"] for col in inspect(c).get_columns(table)]
        )
    return set(rows)


async def _get_indexes(table: str) -> set:
    from tests.conftest import get_test_engine  # 2026-09-12 测试库隔离
    engine = get_test_engine()
    async with engine.connect() as conn:
        rows = await conn.run_sync(
            lambda c: [ix["name"] for ix in inspect(c).get_indexes(table)]
        )
    return set(rows)


async def test_migration_019_reminder_columns():
    """验证 reminders 表新增 6 列 (模型驱动, 测试库常开)"""
    cols = await _get_columns("reminders")
    expected = {
        "acknowledged_at",
        "acknowledged_by",
        "ack_channel",
        "snoozed_until",
        "reminder_batch_date",
        "policy_version",
    }
    missing = expected - cols
    assert not missing, f"reminders 表缺列: {missing}"


@NEED_MIGRATED_DB
async def test_migration_019_reminder_indexes():
    """验证 reminders 表新建 3 个索引 (迁移专属, 需 alembic-migrated 库)"""
    indexes = await _get_indexes("reminders")
    expected = {
        "idx_reminder_ack_at",
        "idx_reminder_batch_date",
        "idx_reminder_snoozed_until",
    }
    missing = expected - indexes
    assert not missing, f"reminders 表缺索引: {missing}"


async def test_migration_019_members_json():
    """验证 members 表新增 notification_preferences JSON 列 (模型驱动, 常开)"""
    cols = await _get_columns("members")
    assert "notification_preferences" in cols, (
        "members 表缺 notification_preferences JSON 列"
    )
