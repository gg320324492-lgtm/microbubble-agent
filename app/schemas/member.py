from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


class MemberBase(BaseModel):
    """成员基础信息"""
    name: str
    grade: Optional[str] = None
    research_area: Optional[str] = None
    skills: Optional[List[str]] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


class MemberCreate(MemberBase):
    """创建成员"""
    username: str
    password: Optional[str] = None
    wechat_id: Optional[str] = None
    wechat_nickname: Optional[str] = None
    wechat_remark: Optional[str] = None
    personal_wechat_id: Optional[str] = None
    wechat_mobile: Optional[str] = None
    external_userid: Optional[str] = None
    role: str = "member"


class MemberUpdate(BaseModel):
    """更新成员"""
    name: Optional[str] = None
    grade: Optional[str] = None
    research_area: Optional[str] = None
    skills: Optional[List[str]] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None
    wechat_id: Optional[str] = None
    wechat_nickname: Optional[str] = None
    wechat_remark: Optional[str] = None
    personal_wechat_id: Optional[str] = None
    wechat_mobile: Optional[str] = None
    external_userid: Optional[str] = None


class MemberResponse(MemberBase):
    """成员响应"""
    id: int
    wechat_id: Optional[str] = None
    wechat_nickname: Optional[str] = None
    wechat_remark: Optional[str] = None
    personal_wechat_id: Optional[str] = None
    external_userid: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool
    role: str
    created_at: datetime
    voice_enrolled_at: Optional[datetime] = None  # 声纹录入时间（None = 未录入）
    voice_sample_count: Optional[int] = None  # 声纹采样次数

    class Config:
        from_attributes = True


class MemberList(BaseModel):
    """成员列表"""
    items: List[MemberResponse]
    total: int
