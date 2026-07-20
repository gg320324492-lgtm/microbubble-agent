"""alembic 019 迁移测试（v2 reminder 字段 + members JSON）

验证 upgrade 后 reminders 6 列 + members 1 JSON 列就位。
注意: 这些测试需要真 microbubble_test DB,SKIP_DB_SETUP=1 时应 skip。
"""
import os
import pytest
from sqlalchemy import inspect


# SKIP_DB_SETUP=1 时整文件跳过 (跟 conftest db fixture 跳过逻辑一致)
SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))

pytestmark = pytest.mark.skipif(
    SKIP_DB_SETUP,
    reason="SKIP_DB_SETUP=1：migration 验证测试需要真 DB, 整文件 skip",
)


def test_migration_019_reminder_columns():
    """验证 reminders 表新增 6 列 (sync,避免 async DB connect 失败)"""
    from app.core.database import engine
    insp = inspect(engine.sync_engine)
    cols = {c["name"] for c in insp.get_columns("reminders")}
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


def test_migration_019_reminder_indexes():
    """验证 reminders 表新建 3 个索引 (sync)"""
    from app.core.database import engine
    insp = inspect(engine.sync_engine)
    indexes = {ix["name"] for ix in insp.get_indexes("reminders")}
    expected = {
        "idx_reminder_ack_at",
        "idx_reminder_batch_date",
        "idx_reminder_snoozed_until",
    }
    missing = expected - indexes
    assert not missing, f"reminders 表缺索引: {missing}"


def test_migration_019_members_json():
    """验证 members 表新增 notification_preferences JSON 列 (sync)"""
    from app.core.database import engine
    insp = inspect(engine.sync_engine)
    cols = {c["name"] for c in insp.get_columns("members")}
    assert "notification_preferences" in cols, (
        "members 表缺 notification_preferences JSON 列"
    )
