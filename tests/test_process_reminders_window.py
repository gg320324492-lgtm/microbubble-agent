"""process_reminders 11AM 窗口行为测试（v2）

覆盖：
- 窗口外立即 return（半夜不触发）
- 窗口内查 pending → 聚合推送 → 失败也标 sent
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from app.models.base import utcnow
from app.models.reminder import Reminder
from app.services.reminder_service import ReminderService


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


class _MagicResultWithScalarOne:
    """支持 scalar_one_or_none() 的 fake result"""
    def __init__(self, scalar_value):
        self._scalar = scalar_value

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _FakeScalars([self._scalar])


def _make_reminder(id=1, status="pending", assignee_id=1):
    r = Reminder(
        id=id,
        task_id=10,
        remind_at=utcnow(),
        status=status,
        reminder_batch_date="2026-06-15",
        policy_version=2,
    )
    # 模拟 r.task.assignee_id
    r.task = MagicMock()
    r.task.assignee_id = assignee_id
    r.task_id = 10
    return r


@pytest.mark.asyncio
async def test_process_reminders_skips_outside_window(monkeypatch):
    """窗口外（半夜）立即 return"""
    from app.services import reminder_policy
    from app.services import reminder_service as rs_mod

    # 必须同时 patch rs_mod 的引用（reminder_service 顶部已 import）
    monkeypatch.setattr(reminder_policy, "is_in_digest_window", lambda: False)
    monkeypatch.setattr(rs_mod, "is_in_digest_window", lambda: False)

    db = MagicMock()
    db.execute = AsyncMock()

    svc = ReminderService(db)
    result = await svc.process_reminders()

    assert result["total"] == 0
    assert result["success"] == 0
    assert result["fail"] == 0
    assert result["skipped"] == 0
    # 窗口外时不查 DB
    assert db.execute.await_count == 0


@pytest.mark.asyncio
async def test_process_reminders_no_pending(monkeypatch):
    """窗口内但无 pending reminder"""
    from app.services import reminder_policy
    from app.services import reminder_service as rs_mod

    monkeypatch.setattr(reminder_policy, "is_in_digest_window", lambda: True)
    monkeypatch.setattr(rs_mod, "is_in_digest_window", lambda: True)

    db = MagicMock()
    db.execute = AsyncMock(return_value=_FakeResult([]))

    svc = ReminderService(db)
    result = await svc.process_reminders()

    assert result["total"] == 0
    assert result["skipped"] == 0


@pytest.mark.asyncio
async def test_process_reminders_failed_marked_as_sent(monkeypatch):
    """窗口内查 pending → 标 sent（one-shot 行为验证）"""
    from app.services import reminder_policy
    from app.services import reminder_service as rs_mod
    from app.services import reminder_scheduler as sched_mod

    # patch 两处：reminder_policy 模块 + reminder_service 已 import 的引用
    monkeypatch.setattr(reminder_policy, "is_in_digest_window", lambda: True)
    monkeypatch.setattr(rs_mod, "is_in_digest_window", lambda: True)
    monkeypatch.setattr(
        sched_mod.reminder_scheduler, "remove_batch", AsyncMock()
    )

    # mock wechat_bot 返回 errcode=-1（失败）
    async def fake_smart_send(*a, **k):
        return {"errcode": -1, "errmsg": "fake fail"}

    monkeypatch.setattr(rs_mod.wechat_bot, "smart_send", fake_smart_send)

    r1 = _make_reminder(id=1, status="pending", assignee_id=1)

    member = MagicMock()
    member.id = 1
    member.name = "张三"
    member.wechat_id = "wx_1"
    member.external_userid = None

    db = MagicMock()
    call_count = [0]

    async def fake_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return _FakeResult([r1])
        return _MagicResultWithScalarOne(member)

    db.execute = AsyncMock(side_effect=fake_execute)
    db.commit = AsyncMock()

    svc = ReminderService(db)
    result = await svc.process_reminders()

    # 不管成功失败，都标 sent（one-shot 核心）
    assert r1.status == "sent"
    assert r1.sent_at is not None
    assert result["total"] == 1
    assert (result["success"] + result["fail"]) == 1
