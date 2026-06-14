"""提醒策略工具函数（v2）

2026-06-15 提醒体系全面优化：把"什么时候发"的时区/窗口逻辑独立成纯函数，
方便单测，也避免在 ReminderService / handler / API 之间重复实现。

**核心模型**（用户决策）：
- 所有提醒统一在 11:00 AM 北京时间窗口发送（± 60 分钟容差）
- 每个任务只有 1 次 11AM 提醒机会：发完即结束，不重试
- 跨过今天的 11AM 还没发的 → 自动推迟到次日 11AM
"""
from datetime import datetime, timedelta, timezone, time as dtime
from typing import Optional

from app.models.base import BEIJING_TZ, utcnow

# 默认 digest 时间（北京时间 11:00）
DEFAULT_DIGEST_TIME = dtime(11, 0)

# 11AM 窗口容差：60 分钟（10:30-11:30）
DEFAULT_WINDOW_MINUTES = 60


def next_digest_slot(
    remind_at_utc: datetime,
    *,
    digest_time: dtime = DEFAULT_DIGEST_TIME,
    now_utc: Optional[datetime] = None,
) -> datetime:
    """根据 remind_at 计算下次 11AM 触发时间（naive UTC）

    规则：
    - remind_at < 今天 北京 digest_time → 今天 digest_time
    - 否则 → 次日 digest_time

    Args:
        remind_at_utc: naive UTC 时间
        digest_time: 目标 digest 时间（默认 11:00 北京）
        now_utc: 当前 UTC（注入便于测试）

    Returns:
        naive UTC 时间，下次 11AM 触发的实际时间
    """
    now = now_utc or utcnow()
    beijing_now = now.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
    today_slot_beijing = beijing_now.replace(
        hour=digest_time.hour,
        minute=digest_time.minute,
        second=0,
        microsecond=0,
    )
    today_slot_utc = (
        today_slot_beijing.astimezone(timezone.utc).replace(tzinfo=None)
    )
    if remind_at_utc < today_slot_utc:
        return today_slot_utc
    return today_slot_utc + timedelta(days=1)


def is_in_digest_window(
    now_utc: Optional[datetime] = None,
    *,
    digest_time: dtime = DEFAULT_DIGEST_TIME,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
) -> bool:
    """判断当前时间是否在 11AM 推送窗口内（10:30-11:30 北京）

    Celery beat 周期 10s，每 tick 调用一次。窗口外时一行 SQL 不查，
    避免半夜触发非预期推送。

    Args:
        now_utc: 当前 UTC（注入便于测试）
        digest_time: 目标 digest 时间
        window_minutes: 窗口容差分钟数

    Returns:
        bool — True 表示在窗口内
    """
    now = now_utc or utcnow()
    beijing_now = now.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
    slot = beijing_now.replace(
        hour=digest_time.hour,
        minute=digest_time.minute,
        second=0,
        microsecond=0,
    )
    diff_min = abs((beijing_now - slot).total_seconds()) / 60
    return diff_min <= window_minutes


def batch_date_for(remind_at_utc: datetime) -> str:
    """根据 remind_at 计算 11AM 批次日期 YYYY-MM-DD（北京时间）

    凌晨 0-12 点算作前一天批次（避免同日双批次：今天 11AM 发了，
    明天 11AM 还要发 → 同一 task 跨两天不会双批次）。

    Args:
        remind_at_utc: naive UTC 时间

    Returns:
        str — YYYY-MM-DD 格式
    """
    beijing = remind_at_utc.replace(tzinfo=timezone.utc).astimezone(BEIJING_TZ)
    if beijing.hour < 12:
        beijing = beijing - timedelta(days=1)
    return beijing.strftime("%Y-%m-%d")
