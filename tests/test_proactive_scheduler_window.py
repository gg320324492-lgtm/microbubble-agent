"""proactive scheduler 11AM 窗口守卫测试（2026-06-15 修复）

场景：
- 用户凌晨 2:48 收到"分配已超过24小时"提醒
- 根因：app/wechat/scheduler.py 的 check_unconfirmed / check_overdue / check_due_soon
  完全绕过 v2 11AM 窗口限制，Celery beat 每 15 分钟触发即推送
- 修复：3 个 check 方法顶部都加 is_in_digest_window() 守卫，窗口外 return 0

覆盖：
- check_unconfirmed 窗口外 return 0 不查 DB
- check_due_soon 窗口外 return 0 不查 DB
- check_overdue 窗口外 return 0 不查 DB
- check_unconfirmed 窗口内查 DB 但无任务时 return 0（无副作用）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.wechat.scheduler import ProactiveScheduler


def _patch_outside_window(monkeypatch):
    """monkeypatch is_in_digest_window → False（窗口外）"""
    from app.services import reminder_policy
    from app.wechat import scheduler as sched_mod

    monkeypatch.setattr(reminder_policy, "is_in_digest_window", lambda: False)
    monkeypatch.setattr(sched_mod, "is_in_digest_window", lambda: False)


def _patch_inside_window(monkeypatch):
    """monkeypatch is_in_digest_window → True（窗口内）"""
    from app.services import reminder_policy
    from app.wechat import scheduler as sched_mod

    monkeypatch.setattr(reminder_policy, "is_in_digest_window", lambda: True)
    monkeypatch.setattr(sched_mod, "is_in_digest_window", lambda: True)


@pytest.mark.asyncio
async def test_check_unconfirmed_skips_outside_window(monkeypatch):
    """凌晨 2:48 修复：check_unconfirmed 窗口外必须 return 0，不查 DB 不发微信"""
    _patch_outside_window(monkeypatch)

    db = MagicMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()

    scheduler = ProactiveScheduler()
    count = await scheduler.check_unconfirmed(db, redis_client=MagicMock())

    assert count == 0
    # 窗口外时不查 DB（避免半夜跑 SQL）
    assert db.execute.await_count == 0
    assert db.get.await_count == 0


@pytest.mark.asyncio
async def test_check_due_soon_skips_outside_window(monkeypatch):
    """check_due_soon 窗口外必须 return 0"""
    _patch_outside_window(monkeypatch)

    db = MagicMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()

    scheduler = ProactiveScheduler()
    count = await scheduler.check_due_soon(db, redis_client=MagicMock())

    assert count == 0
    assert db.execute.await_count == 0


@pytest.mark.asyncio
async def test_check_overdue_skips_outside_window(monkeypatch):
    """check_overdue 窗口外必须 return 0"""
    _patch_outside_window(monkeypatch)

    db = MagicMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()

    scheduler = ProactiveScheduler()
    count = await scheduler.check_overdue(db, redis_client=MagicMock())

    assert count == 0
    assert db.execute.await_count == 0


@pytest.mark.asyncio
async def test_run_all_checks_skips_outside_window(monkeypatch):
    """run_all_checks 是 Celery beat 入口，窗口外应全部 return 0"""
    _patch_outside_window(monkeypatch)

    db = MagicMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()

    scheduler = ProactiveScheduler()
    results = await scheduler.run_all_checks(db, redis_client=MagicMock())

    assert results["due_soon"] == 0
    assert results["overdue"] == 0
    assert results["unconfirmed"] == 0
    # 三个 check 都没查 DB
    assert db.execute.await_count == 0


@pytest.mark.asyncio
async def test_check_unconfirmed_inside_window_no_tasks(monkeypatch):
    """窗口内但无任务时正常 return 0，不副作用"""
    from sqlalchemy.ext.asyncio import AsyncSession

    _patch_inside_window(monkeypatch)

    # 构造空查询结果
    db = MagicMock(spec=AsyncSession)
    db.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
    db.get = AsyncMock(return_value=None)

    # Redis 无重复通知
    redis_client = MagicMock()
    redis_client.sismember = AsyncMock(return_value=False)
    redis_client.sadd = AsyncMock()
    redis_client.expire = AsyncMock()

    scheduler = ProactiveScheduler()
    count = await scheduler.check_unconfirmed(db, redis_client=redis_client)

    assert count == 0
    # 窗口内会查一次 DB（SELECT tasks）
    assert db.execute.await_count >= 1


@pytest.mark.asyncio
async def test_proactive_checks_integration_with_v2_reminder(monkeypatch):
    """集成测试：v2 reminder_system + scheduler 共享 is_in_digest_window 策略

    模拟生产中两个独立调度器（reminder_service.process_reminders 和
    scheduler.run_all_checks）共享同一个窗口判断函数。
    """
    from app.services.reminder_service import ReminderService
    from app.wechat.scheduler import ProactiveScheduler

    # 假设现在 02:48（北京）→ 窗口外
    _patch_outside_window(monkeypatch)

    # v2 reminder: 不会触发
    db1 = MagicMock()
    db1.execute = AsyncMock()
    svc = ReminderService(db1)
    res1 = await svc.process_reminders()
    assert res1["total"] == 0

    # proactive scheduler: 也不会触发
    db2 = MagicMock()
    db2.execute = AsyncMock()
    db2.get = AsyncMock()
    sched = ProactiveScheduler()
    res2 = await sched.run_all_checks(db2, redis_client=MagicMock())
    assert res2["due_soon"] == 0
    assert res2["overdue"] == 0
    assert res2["unconfirmed"] == 0

    # 两个系统都不查 DB（最关键的验证：没有任何半夜推送）
    assert db1.execute.await_count == 0
    assert db2.execute.await_count == 0
