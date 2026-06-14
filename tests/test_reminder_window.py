"""reminder_policy 纯函数测试（v2 11AM 单一窗口）

覆盖：
- next_digest_slot: 6 case
- is_in_digest_window: 2 case
- batch_date_for: 2 case
"""
from datetime import datetime, timezone, time as dtime

from app.services.reminder_policy import (
    next_digest_slot,
    is_in_digest_window,
    batch_date_for,
    DEFAULT_DIGEST_TIME,
)
from app.models.base import BEIJING_TZ


# === next_digest_slot ===

def test_next_digest_slot_today_11am():
    """remind_at < 今天 北京 11AM → 今天 11AM"""
    # 北京 09:00 = UTC 01:00
    remind_at_utc = datetime(2026, 6, 15, 1, 0)
    # 当前 UTC 03:00 = 北京 11:00（已过 11AM 边界）
    now_utc = datetime(2026, 6, 15, 3, 0)
    result = next_digest_slot(remind_at_utc, now_utc=now_utc)
    # 当前 11:00AM 已过，remind_at 在 11AM 之前，所以用今天的 11AM
    assert result == datetime(2026, 6, 15, 3, 0)


def test_next_digest_slot_today_11am_before_window():
    """remind_at < 今天 北京 11AM，当前在 11AM 之前 → 今天 11AM"""
    # 北京 10:00 = UTC 02:00
    remind_at_utc = datetime(2026, 6, 15, 2, 0)
    # 当前 UTC 00:00 = 北京 08:00（11AM 之前）
    now_utc = datetime(2026, 6, 15, 0, 0)
    result = next_digest_slot(remind_at_utc, now_utc=now_utc)
    # 今天 11AM UTC = 03:00
    assert result == datetime(2026, 6, 15, 3, 0)


def test_next_digest_slot_tomorrow_11am():
    """remind_at >= 今天 北京 11AM → 次日 11AM"""
    # remind_at = 北京 14:00 = UTC 06:00
    remind_at_utc = datetime(2026, 6, 15, 6, 0)
    # 当前 UTC 03:00 = 北京 11:00
    now_utc = datetime(2026, 6, 15, 3, 0)
    result = next_digest_slot(remind_at_utc, now_utc=now_utc)
    # 次日 11AM UTC = 2026-06-16 03:00
    assert result == datetime(2026, 6, 16, 3, 0)


def test_next_digest_slot_user_changed_9am():
    """用户改 digest_time=09:00 → 落点到 09:00（如果 remind_at 早于今天的 9:00）"""
    # remind_at = 北京 08:00 = UTC 00:00（早于今天 9:00）
    remind_at_utc = datetime(2026, 6, 15, 0, 0)
    # 当前 UTC 03:00 = 北京 11:00（已过 09:00）
    now_utc = datetime(2026, 6, 15, 3, 0)
    result = next_digest_slot(
        remind_at_utc, digest_time=dtime(9, 0), now_utc=now_utc
    )
    # remind_at (00:00) < today_slot (01:00) → 返回 today_slot
    assert result == datetime(2026, 6, 15, 1, 0)


def test_next_digest_slot_user_changed_9am_after():
    """用户改 09:00 但 remind_at 已过今天 09:00 → 次日 09:00"""
    # remind_at = 北京 10:00 = UTC 02:00（晚于今天 9:00）
    remind_at_utc = datetime(2026, 6, 15, 2, 0)
    # 当前 UTC 03:00 = 北京 11:00
    now_utc = datetime(2026, 6, 15, 3, 0)
    result = next_digest_slot(
        remind_at_utc, digest_time=dtime(9, 0), now_utc=now_utc
    )
    # remind_at (02:00) > today_slot (01:00) → 返回次日 slot
    assert result == datetime(2026, 6, 16, 1, 0)


def test_next_digest_slot_default_arg():
    """默认参数 digest_time=11:00（DEFAULT_DIGEST_TIME）"""
    assert DEFAULT_DIGEST_TIME == dtime(11, 0)


def test_next_digest_slot_cross_midnight():
    """跨午夜的边界：remind_at = 23:59 北京（已过 11AM）→ 次日 11AM"""
    # remind_at = 北京 23:00 = UTC 15:00
    remind_at_utc = datetime(2026, 6, 15, 15, 0)
    now_utc = datetime(2026, 6, 15, 0, 0)  # 任意当前时间
    result = next_digest_slot(remind_at_utc, now_utc=now_utc)
    # 次日 11AM UTC
    assert result == datetime(2026, 6, 16, 3, 0)


# === is_in_digest_window ===

def test_is_in_digest_window_inside():
    """11AM 整点 = 窗口中心"""
    # 北京 11:00 = UTC 03:00
    now_utc = datetime(2026, 6, 15, 3, 0)
    assert is_in_digest_window(now_utc) is True


def test_is_in_digest_window_outside():
    """15:00 北京 = 窗口外"""
    # 北京 15:00 = UTC 07:00
    now_utc = datetime(2026, 6, 15, 7, 0)
    assert is_in_digest_window(now_utc) is False


def test_is_in_digest_window_edge():
    """10:30 北京（窗口左边界）= 窗口内"""
    # 北京 10:30 = UTC 02:30
    now_utc = datetime(2026, 6, 15, 2, 30)
    assert is_in_digest_window(now_utc) is True


# === batch_date_for ===

def test_batch_date_for_morning():
    """凌晨 2:00 北京（< 12:00）→ 前一天批次"""
    # 北京 2026-06-15 02:00 = UTC 2026-06-14 18:00
    remind_at_utc = datetime(2026, 6, 14, 18, 0)
    assert batch_date_for(remind_at_utc) == "2026-06-14"


def test_batch_date_for_afternoon():
    """14:00 北京（>= 12:00）→ 当天批次"""
    # 北京 2026-06-15 14:00 = UTC 2026-06-15 06:00
    remind_at_utc = datetime(2026, 6, 15, 6, 0)
    assert batch_date_for(remind_at_utc) == "2026-06-15"
