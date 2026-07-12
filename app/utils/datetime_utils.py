"""Date/time utilities — 共享时间工具

提取自:
- app/services/chat_history_service.py::_to_naive_datetime (2026-07-12)
- app/services/drive_cleanup_service.py::_to_naive_datetime (2026-07-12)
- app/services/drive_service.py::_to_naive_dt (2026-07-12)

3 处实现曾独立 inline (CLAUDE.md 2026-06-05 tz-aware 教训复用),
但 chat_history 版本用 astimezone(UTC) 更严格 (其他 2 处假设输入已是 UTC),
统一用 chat_history 版本语义, 避免 non-UTC 输入产生歧义.

## 铁律 (永久沉淀)
① **Naive datetime 必须 strip tzinfo** — PG TIMESTAMP WITHOUT TIME ZONE 列
   不能直接接受 tz-aware datetime, 否则 asyncpg 报
   "can't subtract offset-naive and offset-aware datetimes" 500
② **Aware → naive 必须先 astimezone(UTC)** — 直接 replace(tzinfo=None) 会保留
   原时区时刻值 (例如北京时间 14:00 → naive 14:00 而非 UTC 6:00),
   比较/排序会乱
③ **None 输入必须返回 None** — service 边界 fallback, 勿抛 TypeError
"""
from datetime import datetime, timezone
from typing import Optional


def to_naive_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    """tz-aware datetime 转 naive (PG TIMESTAMP WITHOUT TIME ZONE 列)

    行为:
    - None → None (调用方可 fallback 到 datetime.utcnow())
    - naive → naive (透传)
    - aware (任意时区) → 转 UTC 再 strip tzinfo (保留 UTC 时刻值)

    Args:
        dt: Optional[datetime] — 任意 tz-aware / naive / None datetime

    Returns:
        Optional[datetime] — naive datetime 或 None

    Examples:
        >>> from datetime import datetime, timezone, timedelta
        >>> to_naive_datetime(None)
        None
        >>> to_naive_datetime(datetime(2026, 7, 12, 14, 0))
        datetime.datetime(2026, 7, 12, 14, 0)
        >>> to_naive_datetime(datetime(2026, 7, 12, 14, 0, tzinfo=timezone.utc))
        datetime.datetime(2026, 7, 12, 14, 0)
        >>> beijing = timezone(timedelta(hours=8))
        >>> to_naive_datetime(datetime(2026, 7, 12, 14, 0, tzinfo=beijing))
        datetime.datetime(2026, 7, 12, 6, 0)  # 北京 14:00 → UTC 06:00
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)