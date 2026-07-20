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
    """创建成员

    PR6-P17 留尾: wechat_id 改为 required, 与 DB NOT NULL 约束同步 (2026-07-20)
    - DB `members.wechat_id` alembic 057 已 NOT NULL
    - 模型 `Member.wechat_id` 已 nullable=False
    - MemberCreate 仍 Optional → 缺传 silently 写入 '' 触发 UNIQUE 冲突
    - 改为 required: 缺传 → Pydantic 422 fail loud
    - 个人/admin 后台必须传 wechat_id (PR6-P18 fill_wechat_id_placeholders.py 已就绪)
    """
    username: str
    password: Optional[str] = None
    wechat_id: str
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
