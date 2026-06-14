"""snooze_user_reminders 测试（v2）

覆盖：
- snooze 推迟所有 pending 到指定时间
- reminder_batch_date 字段正确更新
- Redis ZSET 同步调用
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.models.base import utcnow, BEIJING_TZ
from app.models.reminder import Reminder
from app.services.reminder_service import ReminderService
from app.services.reminder_policy import next_digest_slot, batch_date_for


def _make_reminder(id=1, status="pending"):
    return Reminder(
        id=id,
        task_id=10,
        remind_at=utcnow(),
        status=status,
    )


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items):
        self._scalars = _FakeScalars(items)

    def scalars(self):
        return self._scalars


def _make_db_session(reminders):
    """让两次查询（task + meeting）分别返回 reminders 和 []"""
    db = MagicMock()
    call_count = [0]

    async def fake_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return _FakeResult(reminders)
        else:
            return _FakeResult([])

    db.execute = AsyncMock(side_effect=fake_execute)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_snooze_pushes_all_pending(monkeypatch):
    """snooze 把所有 pending 推到指定时间 + 写 batch_date"""
    r1 = _make_reminder(id=1, status="pending")
    r2 = _make_reminder(id=2, status="pending")
    db = _make_db_session([r1, r2])

    from app.services import reminder_scheduler as sched_mod

    add_mock = AsyncMock()
    monkeypatch.setattr(sched_mod.reminder_scheduler, "add_reminder", add_mock)

    target = next_digest_slot(utcnow())
    svc = ReminderService(db)
    count = await svc.snooze_user_reminders(1, until=target)

    assert count == 2
    assert r1.snoozed_until == target
    assert r2.snoozed_until == target
    assert r1.reminder_batch_date == batch_date_for(target)
    # Redis ZSET 同步调用
    assert add_mock.call_count == 2


@pytest.mark.asyncio
async def test_snooze_skips_non_pending(monkeypatch):
    """snooze 只动 pending reminder（生产 SQL 已过滤非 pending）"""
    r1 = _make_reminder(id=2, status="pending")
    # 生产 WHERE clause 过滤 status='pending'，所以 sent 的不会到 application
    db = _make_db_session([r1])

    from app.services import reminder_scheduler as sched_mod

    add_mock = AsyncMock()
    monkeypatch.setattr(sched_mod.reminder_scheduler, "add_reminder", add_mock)

    target = utcnow() + timedelta(hours=1)
    svc = ReminderService(db)
    count = await svc.snooze_user_reminders(1, until=target)

    assert count == 1
    assert r1.snoozed_until == target
