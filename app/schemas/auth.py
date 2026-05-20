"""认证相关Schema"""

from pydantic import BaseModel, EmailStr
from typing import Optional


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
    """用户信息"""
    id: int
    name: str
    role: str
    grade: Optional[str] = None
    research_area: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


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
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None


# 更新LoginResponse的引用
LoginResponse.model_rebuild()
