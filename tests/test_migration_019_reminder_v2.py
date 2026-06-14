"""alembic 019 迁移测试（v2 reminder 字段 + members JSON）

验证 upgrade 后 reminders 6 列 + members 1 JSON 列就位。
"""
import pytest
from sqlalchemy import inspect

from app.core.database import engine


@pytest.mark.asyncio
async def test_migration_019_reminder_columns():
    """验证 reminders 表新增 6 列"""
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


@pytest.mark.asyncio
async def test_migration_019_reminder_indexes():
    """验证 reminders 表新建 3 个索引"""
    insp = inspect(engine.sync_engine)
    indexes = {ix["name"] for ix in insp.get_indexes("reminders")}
    expected = {
        "idx_reminder_ack_at",
        "idx_reminder_batch_date",
        "idx_reminder_snoozed_until",
    }
    missing = expected - indexes
    assert not missing, f"reminders 表缺索引: {missing}"


@pytest.mark.asyncio
async def test_migration_019_members_json():
    """验证 members 表新增 notification_preferences JSON 列"""
    insp = inspect(engine.sync_engine)
    cols = {c["name"] for c in insp.get_columns("members")}
    assert "notification_preferences" in cols, (
        "members 表缺 notification_preferences JSON 列"
    )
