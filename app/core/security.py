"""安全认证模块 - JWT Token"""

from datetime import timedelta
from app.models.base import utcnow
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.models.member import Member

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer认证
security = HTTPBearer()

# JWT配置
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌

    Args:
        data: 令牌数据
        expires_delta: 过期时间

    Returns:
        JWT令牌字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = utcnow() + expires_delta
    else:
        expire = utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


DOWNLOAD_TOKEN_EXPIRE_SECONDS = 120


def create_download_token(member_id: int, file_id: int,
                          expires_seconds: int = DOWNLOAD_TOKEN_EXPIRE_SECONDS,
                          proxy: bool = False) -> str:
    """短时效下载 token (2026-11-15)。

    浏览器原生下载无法携带 Authorization 头；改用短 token 拼在 URL 上，
    下载端点以它代替登录态。有效期默认 120s，只够发起一次下载请求；
    请求一旦建立，后续字节流不受 token 过期影响。
    proxy=True 表示优先使用 knowledge.meta 里的播放代理（视频 720p H.264）。
    """
    payload = {
        "sub": str(member_id),
        "type": "download",
        "file_id": int(file_id),
        "proxy": bool(proxy),
        "exp": utcnow() + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_batch_download_token(member_id: int, ids=None, folder_id=None,
                                folder_ids=None,
                                expires_seconds: int = DOWNLOAD_TOKEN_EXPIRE_SECONDS) -> str:
    """批量 ZIP 下载 token (浏览器原生下载用, 120s)。"""
    payload = {
        "sub": str(member_id),
        "type": "batch_download",
        "ids": list(ids or []),
        "folder_id": folder_id,
        "folder_ids": list(folder_ids or []),
        "exp": utcnow() + timedelta(seconds=expires_seconds),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_batch_download_token(token: str) -> Optional[dict]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "batch_download":
        return None
    return payload


def decode_download_token(token: str) -> Optional[dict]:
    """校验下载 token；无效/过期/类型不符返回 None（不抛 401）。"""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != "download":
        return None
    return payload


def create_refresh_token(data: dict) -> str:
    """
    创建刷新令牌

    Args:
        data: 令牌数据

    Returns:
        JWT刷新令牌字符串
    """
    to_encode = data.copy()
    expire = utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    解码JWT令牌

    Args:
        token: JWT令牌字符串

    Returns:
        令牌数据

    Raises:
        HTTPException: 令牌无效或已过期
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Member:
    """
    获取当前认证用户

    Args:
        credentials: HTTP Bearer凭据
        db: 数据库会话

    Returns:
        当前用户对象

    Raises:
        HTTPException: 认证失败
    """
    # 解码令牌
    payload = decode_token(credentials.credentials)

    # 检查令牌类型
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌类型"
        )

    # 获取用户ID
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌"
        )

    # 查询用户
    result = await db.execute(
        select(Member).where(Member.id == int(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    return user


async def get_current_admin_user(
    current_user: Member = Depends(get_current_user)
) -> Member:
    """获取当前用户（原管理员门禁）

    2026-09-05 角色扁平化：课题组不再区分管理员/组长/成员的权限等级，
    所有登录成员等权。本函数保留为兼容依赖名，仅要求登录，不再校验 role。
    """
    return current_user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db)
) -> Optional[Member]:
    """
    可选认证 — v31.2 analytics 埋点用

    行为:
      - 未带 token → None (匿名)
      - 带无效 token → None (视为匿名)
      - 带有效 token + 用户存在 + is_active=True → Member
      - 带有效 token 但用户不存在 / is_active=False → None (防止被禁用户发埋点)

    与 get_current_user 的区别:
      - 不抛 401, 永远返回 Optional[Member]
      - 适合"埋点 / 公开统计"场景, 登录用户绑 user_id, 匿名写 NULL

    参考:
      - plan: v31.2 安全加固章节 (可选 auth 模式)
      - app/api/v1/analytics.py (POST search-event + PATCH click)
    """
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
    except HTTPException:
        return None  # 无效 token → 视为匿名
    if payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    result = await db.execute(
        select(Member).where(Member.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None
    return user


