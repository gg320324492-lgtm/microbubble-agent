from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class MeetingBase(BaseModel):
    """会议基础信息"""
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    location: Optional[str] = None


class MeetingCreate(MeetingBase):
    """创建会议"""
    meeting_url: Optional[str] = None
    meeting_id: Optional[str] = None
    participants: Optional[List[int]] = None


class MeetingUpdate(BaseModel):
    """更新会议"""
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    decisions: Optional[List[str]] = None


class MeetingResponse(MeetingBase):
    """会议响应"""
    id: int
    meeting_url: Optional[str] = None
    meeting_id: Optional[str] = None
    transcript: Optional[Any] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    decisions: Optional[List[str]] = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingList(BaseModel):
    """会议列表"""
    items: List[MeetingResponse]
    total: int


class MeetingMinutes(BaseModel):
    """会议纪要"""
    summary: str
    key_points: List[str]
    decisions: List[str]
    action_items: List[Dict[str, Any]]
    next_meeting: Optional[str] = None


