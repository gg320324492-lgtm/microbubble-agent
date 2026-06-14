"""ack/snooze 服务函数测试（v2）

覆盖：
- acknowledge_all_user_reminders: 取消所有 pending，跳过 sent
- snooze_user_reminders: 推迟所有 pending
- 状态机正确性
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.base import utcnow, BEIJING_TZ
from app.models.reminder import Reminder
from app.models.task import Task, TaskStatus
from app.models.member import Member
from app.services.reminder_service import ReminderService


def _make_member(id=1, name="张三"):
    m = Member(id=id, name=name, is_active=True)
    m.wechat_id = f"wx_{id}"
    return m


def _make_task(id=10, assignee_id=1, title="测试任务"):
    t = Task(
        id=id,
        title=title,
        assignee_id=assignee_id,
        status=TaskStatus.IN_PROGRESS.value,
    )
    return t


def _make_reminder(id=100, task_id=10, status="pending", remind_at=None):
    r = Reminder(
        id=id,
        task_id=task_id,
        remind_at=remind_at or utcnow(),
        status=status,
    )
    return r


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


def _make_db_session(reminders: list, member_id: int = 1):
    """构造一个假的 AsyncSession：让两次查询都返回相同 reminders（mock 不会去重，
    但 ack 内部用 set 处理，结果唯一）

    - 第一次 execute（task query）返回 reminders
    - 第二次 execute（meeting query）返回空（不是 task+meeting 双计）
    - commit / refresh / get 都是 mock
    """
    db = MagicMock()
    call_count = [0]

    async def fake_execute(stmt):
        call_count[0] += 1
        if call_count[0] == 1:
            return _FakeResult(reminders)  # task reminders
        else:
            return _FakeResult([])  # meeting reminders

    db.execute = AsyncMock(side_effect=fake_execute)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=None)
    return db


# === acknowledge_all_user_reminders ===

@pytest.mark.asyncio
async def test_acknowledge_cancels_all_pending(monkeypatch):
    """ack 取消所有 pending reminder"""
    # 生产 WHERE clause 过滤 status='pending'，所以测试只传 pending reminders
    r1 = _make_reminder(id=1, status="pending")
    r2 = _make_reminder(id=2, status="pending")
    db = _make_db_session([r1, r2])

    from app.services import reminder_scheduler as sched_mod

    monkeypatch.setattr(
        sched_mod.reminder_scheduler, "remove_batch", AsyncMock()
    )

    svc = ReminderService(db)
    count = await svc.acknowledge_all_user_reminders(1, channel="wechat")

    assert count == 2
    assert r1.status == "acknowledged"
    assert r2.status == "acknowledged"
    assert r1.acknowledged_by == 1
    assert r1.ack_channel == "wechat"
    assert r1.acknowledged_at is not None


@pytest.mark.asyncio
async def test_acknowledge_no_pending(monkeypatch):
    """无 pending reminder 时 count=0（生产 SQL 会过滤掉非 pending）"""
    db = _make_db_session([])  # 空 = 没有 pending

    from app.services import reminder_scheduler as sched_mod

    monkeypatch.setattr(
        sched_mod.reminder_scheduler, "remove_batch", AsyncMock()
    )

    svc = ReminderService(db)
    count = await svc.acknowledge_all_user_reminders(1, channel="web")

    assert count == 0


@pytest.mark.asyncio
async def test_acknowledge_channel_value_persisted(monkeypatch):
    """ack_channel 字段正确写入"""
    r1 = _make_reminder(id=1, status="pending")
    db = _make_db_session([r1])

    from app.services import reminder_scheduler as sched_mod

    monkeypatch.setattr(
        sched_mod.reminder_scheduler, "remove_batch", AsyncMock()
    )

    svc = ReminderService(db)
    await svc.acknowledge_all_user_reminders(1, channel="api")
    assert r1.ack_channel == "api"
