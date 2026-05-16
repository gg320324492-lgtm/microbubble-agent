"""辅助工具函数"""

from datetime import datetime, timedelta
from typing import Optional


def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M") -> str:
    """格式化日期时间"""
    if not dt:
        return "-"
    return dt.strftime(format_str)


def format_date(dt: Optional[datetime]) -> str:
    """格式化日期"""
    return format_datetime(dt, "%Y-%m-%d")


def format_time(dt: Optional[datetime]) -> str:
    """格式化时间"""
    return format_datetime(dt, "%H:%M")


def get_relative_time(dt: datetime) -> str:
    """获取相对时间描述"""
    now = datetime.utcnow()
    diff = now - dt

    if diff.days > 365:
        return f"{diff.days // 365}年前"
    elif diff.days > 30:
        return f"{diff.days // 30}个月前"
    elif diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}小时前"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}分钟前"
    else:
        return "刚刚"


def is_overdue(due_date: Optional[datetime], status: str = "todo") -> bool:
    """判断是否逾期"""
    if not due_date or status in ["done", "cancelled"]:
        return False
    return due_date < datetime.utcnow()


def get_days_remaining(due_date: Optional[datetime]) -> Optional[int]:
    """获取剩余天数"""
    if not due_date:
        return None
    diff = due_date - datetime.utcnow()
    return diff.days


def calculate_progress(completed: int, total: int) -> int:
    """计算进度百分比"""
    if total == 0:
        return 0
    return min(round(completed / total * 100), 100)


def truncate_text(text: str, max_length: int = 100) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """验证手机号格式"""
    import re
    pattern = r'^1[3-9]\d{9}$'
    return bool(re.match(pattern, phone))
