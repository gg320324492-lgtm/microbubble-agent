from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, DateTime
from app.core.database import Base

# 北京时间时区（东八区）
BEIJING_TZ = timezone(timedelta(hours=8))


def utcnow():
    """返回 naive UTC 时间（与数据库 DateTime 列兼容）"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    """时间戳混入类"""
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
