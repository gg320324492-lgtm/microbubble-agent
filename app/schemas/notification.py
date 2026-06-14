"""通知偏好 Schema（v2）

2026-06-15 任务提醒体系全面优化：
- 用户可在 SettingsView 调 digest_time
- 用户可关闭/启用提醒
- 用户可设 snoozed_until 临时关闭
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# HH:MM 24-hour format pattern
_HHMM_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"


class NotificationPreferenceResponse(BaseModel):
    """GET /members/me/notification-preferences 响应"""
    enabled: bool
    digest_time: str = Field("11:00", pattern=_HHMM_PATTERN)
    channels: List[str] = Field(default_factory=lambda: ["wechat"])
    snoozed_until: Optional[datetime] = None
    # 运行时信息（不入库）
    in_digest_window: bool = False
    next_digest_at: Optional[datetime] = None


class NotificationPreferenceUpdate(BaseModel):
    """PUT /members/me/notification-preferences 请求体"""
    enabled: Optional[bool] = None
    digest_time: Optional[str] = Field(None, pattern=_HHMM_PATTERN)
    channels: Optional[List[str]] = None
    snoozed_until: Optional[datetime] = None
