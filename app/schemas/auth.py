"""认证相关Schema"""

from pydantic import BaseModel, computed_field, field_validator
from typing import Optional

from app.core.member_identity import member_status


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """刷新令牌响应"""
    access_token: str
    token_type: str = "bearer"


class UserInfo(BaseModel):
    """用户信息

    2026-09-05 角色扁平化: role 字段退役 (历史保留, 恒为 'member'),
    成员统一用身份称谓 title (导师/博士/硕士/本科生/校友, 由 grade 派生)。
    """
    id: int
    name: str
    role: str
    grade: Optional[str] = None
    research_area: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

    @computed_field
    @property
    def title(self) -> str:
        return member_status(self.grade)


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    user_id: int
    new_password: str


class ProfileUpdateRequest(BaseModel):
    """更新个人资料请求"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None


class RecoveryCodeResponse(BaseModel):
    """恢复码生成响应 — 明文仅在本响应出现一次, 用户自行保存"""
    code: str
    message: str


class RecoveryCodeStatusResponse(BaseModel):
    """恢复码状态查询 (设置页展示"是否已生成/生成时间")"""
    has_code: bool
    generated_at: Optional[str] = None


class SelfResetPasswordRequest(BaseModel):
    """登录页自助重置密码请求 (无登录态): 用户名 + 恢复码 + 新密码"""
    username: str
    recovery_code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码长度不能少于6位")
        return v


# 更新LoginResponse的引用
LoginResponse.model_rebuild()
