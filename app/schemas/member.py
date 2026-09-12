from pydantic import BaseModel, EmailStr, computed_field
from typing import Optional, List
from datetime import datetime

from app.core.member_identity import member_status


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

    (2026-09 企业微信下线: 原 wechat_id required + 5 个微信 identifier 字段
    已随 alembic 139 删列一并移除)
    """
    username: str
    password: Optional[str] = None
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


class MemberResponse(MemberBase):
    """成员响应"""
    id: int
    avatar: Optional[str] = None
    is_active: bool
    role: str
    created_at: datetime
    voice_enrolled_at: Optional[datetime] = None  # 声纹录入时间（None = 未录入）
    voice_sample_count: Optional[int] = None  # 声纹采样次数

    class Config:
        from_attributes = True

    @computed_field
    @property
    def title(self) -> str:
        """统一身份称谓 (导师/博士/硕士/本科生/校友)，由 grade 派生 (2026-09-05 角色扁平化)"""
        return member_status(self.grade)


class MemberList(BaseModel):
    """成员列表"""
    items: List[MemberResponse]
    total: int
