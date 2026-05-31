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
    presenter_ids: Optional[List[int]] = None


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
    participants: Optional[List[int]] = None
    presenter_ids: Optional[List[int]] = None


class ParticipantInfo(BaseModel):
    """参与者简要信息"""
    member_id: int
    name: str = ""
    role: str = "participant"

    class Config:
        from_attributes = True


class MeetingResponse(MeetingBase):
    """会议响应"""
    id: int
    meeting_url: Optional[str] = None
    meeting_id: Optional[str] = None
    transcript: Optional[Any] = None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    decisions: Optional[List[str]] = None
    speaker_mapping: Optional[Any] = None
    speaker_stats: Optional[Any] = None
    presenter_ids: Optional[Any] = None
    participants: Optional[List[ParticipantInfo]] = None
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


# === 发言者检测与分析 ===

class SpeakerDetectRequest(BaseModel):
    """发言者检测请求"""
    transcript_text: str


class DetectedSpeaker(BaseModel):
    """检测到的发言者"""
    original_label: str
    suggested_name: Optional[str] = None
    turn_count: int
    sample_lines: List[str]


class SpeakerDetectResponse(BaseModel):
    """发言者检测响应"""
    phase: str = "speaker_detection"
    detected_speakers: List[DetectedSpeaker]
    total_turns: int
    confidence: str  # high / medium / low
    format_type: str  # marked / plain / mixed


class TranscriptAnalyzeRequest(BaseModel):
    """转录分析请求"""
    title: Optional[str] = None  # 留空则自动生成
    start_time: datetime
    transcript_text: str
    speaker_mapping: Optional[Dict[str, str]] = None
    participants: Optional[List[int]] = None


class TranscriptAnalyzeResponse(BaseModel):
    """转录分析响应"""
    phase: str = "complete"
    meeting_id: int
    summary: str
    key_points: List[str]
    decisions: List[str]
    tasks_created: List[Dict[str, Any]]
    speaker_stats: Optional[Any] = None


class SpeakerStatsItem(BaseModel):
    """单个发言者统计"""
    name: str
    turn_count: int
    word_count: int
    speaking_ratio: float
    avg_turn_length: int
    topics: Optional[List[str]] = None


class MeetingAnalyticsResponse(BaseModel):
    """会议分析统计响应"""
    speaker_stats: List[SpeakerStatsItem]
    meeting_stats: Dict[str, Any]


class SpeakerMapRequest(BaseModel):
    """发言者映射请求"""
    speaker_mapping: Dict[str, str]


