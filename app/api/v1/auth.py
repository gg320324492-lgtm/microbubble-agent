"""认证相关API"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_current_admin_user,
)
from app.core.rate_limit import login_limiter, pwreset_limiter, get_client_ip
from app.core.exceptions import AuthException, ValidationException, NotFoundException, ForbiddenException
from app.models.member import Member
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    UserInfo,
    ChangePasswordRequest,
    ResetPasswordRequest,
    ProfileUpdateRequest,
    RecoveryCodeResponse,
    RecoveryCodeStatusResponse,
    SelfResetPasswordRequest,
)

from app.config import settings
from app.services.file_service import file_service
from app.services import recovery_code_service

logger = logging.getLogger("microbubble.api.auth")

router = APIRouter(prefix="/auth", tags=["认证"])


def _resolve_avatar_url(member: Member) -> str | None:
    """将 avatar 转为公网可访问的 URL（通过 Nginx /minio/ 代理）"""
    avatar = member.avatar
    if not avatar:
        return None

    # 如果已经是本站可访问的 URL，直接返回（DB 中已存储的解析后 URL）
    site_prefix = f"https://{settings.SITE_DOMAIN}/minio/"
    if avatar.startswith(site_prefix):
        return avatar

    # 兼容旧数据：从 presigned URL 提取 object_name
    if avatar.startswith("http"):
        from urllib.parse import urlparse
        path = urlparse(avatar).path
        parts = path.lstrip("/").split("/", 1)
        if len(parts) == 2:
            object_name = parts[1]
        else:
            return avatar  # fallback
    else:
        object_name = avatar

    # Nginx proxy_pass http://127.0.0.1:9000/; 会去掉 /minio/ 前缀，
    # 因此路径中需要保留 bucket 名让 MinIO 正确路由
    return f"https://{settings.SITE_DOMAIN}/minio/{settings.MINIO_BUCKET}/{object_name}"


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """用户登录（5分钟内最多5次尝试）

    v31.2.6: 限流器切到 Redis ZSET (抗 docker restart / 跨 worker 共享).
    触发 429 时响应自动带 Retry-After: 300 头 (来自 AsyncRedisRateLimiter).
    """
    client_ip = get_client_ip(request)
    await login_limiter.check(f"login:{client_ip}")  # v31.2.6: await + "login:" 前缀

    # 查询用户
    result = await db.execute(
        select(Member).where(Member.username == login_data.username)
    )
    user = result.scalar_one_or_none()

    # 验证用户存在且密码正确
    if not user or not user.password_hash:
        await login_limiter.record(f"login:{client_ip}")  # v31.2.6
        raise AuthException("用户名或密码错误")

    if not verify_password(login_data.password, user.password_hash):
        await login_limiter.record(f"login:{client_ip}")  # v31.2.6
        raise AuthException("用户名或密码错误")

    # 检查用户是否被禁用
    if not user.is_active:
        raise ForbiddenException("用户已被禁用，请联系管理员")

    # 生成令牌
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # 构建用户信息
    user_info = UserInfo(
        id=user.id,
        name=user.name,
        role=user.role,
        grade=user.grade,
        research_area=user.research_area,
        email=user.email,
        phone=user.phone,
        bio=user.bio,
        avatar=_resolve_avatar_url(user),
        is_active=user.is_active
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_info
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """
    刷新访问令牌

    Args:
        request: 刷新令牌请求
        db: 数据库会话

    Returns:
        新的访问令牌

    Raises:
        HTTPException: 刷新令牌无效或已过期
    """
    try:
        payload = decode_token(request.refresh_token)

        # 验证令牌类型
        if payload.get("type") != "refresh":
            raise AuthException("无效的刷新令牌")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthException("无效的令牌")

        # 验证用户存在
        result = await db.execute(
            select(Member).where(Member.id == int(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthException("用户不存在或已被禁用")

        # 生成新的访问令牌
        new_access_token = create_access_token(data={"sub": str(user.id)})

        return RefreshTokenResponse(access_token=new_access_token)

    except AuthException:
        raise
    except Exception:
        raise AuthException("无效的刷新令牌")


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: Member = Depends(get_current_user)):
    """
    获取当前用户信息

    Args:
        current_user: 当前认证用户

    Returns:
        用户信息
    """
    return UserInfo(
        id=current_user.id,
        name=current_user.name,
        role=current_user.role,
        grade=current_user.grade,
        research_area=current_user.research_area,
        email=current_user.email,
        phone=current_user.phone,
        bio=current_user.bio,
        avatar=_resolve_avatar_url(current_user),
        is_active=current_user.is_active
    )


@router.put("/profile", response_model=UserInfo)
async def update_profile(
    request: ProfileUpdateRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新个人资料

    Args:
        request: 更新请求
        current_user: 当前认证用户
        db: 数据库会话

    Returns:
        更新后的用户信息
    """
    # 更新字段
    if request.name is not None:
        current_user.name = request.name
    if request.email is not None:
        current_user.email = request.email
    if request.phone is not None:
        current_user.phone = request.phone
    if request.bio is not None:
        current_user.bio = request.bio
    if request.avatar is not None:
        current_user.avatar = request.avatar

    await db.commit()
    await db.refresh(current_user)

    return UserInfo(
        id=current_user.id,
        name=current_user.name,
        role=current_user.role,
        grade=current_user.grade,
        research_area=current_user.research_area,
        email=current_user.email,
        phone=current_user.phone,
        bio=current_user.bio,
        avatar=_resolve_avatar_url(current_user),
        is_active=current_user.is_active
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    修改密码

    Args:
        request: 修改密码请求
        current_user: 当前认证用户
        db: 数据库会话

    Returns:
        成功消息

    Raises:
        HTTPException: 旧密码错误
    """
    # 验证旧密码
    if not current_user.password_hash or not verify_password(request.old_password, current_user.password_hash):
        raise ValidationException("旧密码错误")

    # 更新密码
    current_user.password_hash = get_password_hash(request.new_password)
    await db.commit()

    return {"message": "密码修改成功"}


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    admin: Member = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    重置用户密码（管理员专用）

    Args:
        request: 重置密码请求
        admin: 当前管理员用户
        db: 数据库会话

    Returns:
        成功消息

    Raises:
        HTTPException: 用户不存在
    """
    # 查询目标用户
    result = await db.execute(
        select(Member).where(Member.id == request.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundException("用户")

    # 重置密码
    user.password_hash = get_password_hash(request.new_password)
    await db.commit()

    return {"message": f"用户 {user.name} 的密码已重置"}


@router.post("/init-password")
async def init_password(
    request: ChangePasswordRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    初始化密码（用于没有密码的用户首次设置密码）

    Args:
        request: 包含旧密码（可为空）和新密码
        current_user: 当前认证用户
        db: 数据库会话

    Returns:
        成功消息
    """
    # 如果用户已有密码，需要验证旧密码
    if current_user.password_hash:
        if not verify_password(request.old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码错误"
            )

    # 设置新密码
    current_user.password_hash = get_password_hash(request.new_password)
    await db.commit()

    return {"message": "密码设置成功"}


# ==================== 用户自助重置密码 (恢复码, 2026-09-02) ====================
# 背景: agent 曾静默改掉用户密码, 用户被锁死只能找管理员。恢复码让重置全程自助:
# 能登录时在设置页生成 (明文仅显示一次) → 锁定后在登录页 用户名+恢复码+新密码 重置。
# 明文永不落库; DB 只存 SHA-256; 单次使用; pwreset_limiter 5次/15分钟 防爆破。


@router.get("/recovery-code/status", response_model=RecoveryCodeStatusResponse)
async def get_recovery_code_status(
    current_user: Member = Depends(get_current_user),
):
    """查询当前用户恢复码状态 (设置页展示"已生成/未生成 + 时间")"""
    has_code = bool(current_user.recovery_code_hash)
    generated_at = None
    if has_code and current_user.recovery_code_generated_at:
        generated_at = current_user.recovery_code_generated_at.isoformat()
    return RecoveryCodeStatusResponse(has_code=has_code, generated_at=generated_at)


@router.post("/recovery-code", response_model=RecoveryCodeResponse)
async def generate_recovery_code(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成/轮换当前用户恢复码 — 明文仅在本响应出现一次, 必须立即保存"""
    code = recovery_code_service.rotate_member_recovery_code(current_user)
    await db.commit()
    logger.info(f"recovery code rotated: user={current_user.username}")
    return RecoveryCodeResponse(
        code=code,
        message="恢复码仅显示这一次，请立即保存到个人微信收藏等安全位置",
    )


@router.post("/reset-password-self")
async def reset_password_self(
    request: SelfResetPasswordRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
):
    """登录页自助重置密码 (无登录态): 用户名 + 恢复码 + 新密码, 不经过管理员

    - 用户名/码任一错误 → 同一文案 (防用户名枚举)
    - 成功后恢复码立即失效 (单次使用), 用户可登录后重新生成
    - 限流 5 次/15 分钟 per ip+username (pwreset_limiter, Redis ZSET)
    - JWT 无状态无法吊销旧 token, 但攻击者持有旧密码+恢复码的场景已消除
    """
    client_ip = get_client_ip(req)
    limiter_key = f"pwreset:{client_ip}:{request.username.lower()}"
    await pwreset_limiter.check(limiter_key)

    result = await db.execute(
        select(Member).where(Member.username == request.username)
    )
    user = result.scalar_one_or_none()

    if (
        not user
        or not user.is_active
        or not user.recovery_code_hash
        or not recovery_code_service.verify_recovery_code(
            request.recovery_code, user.recovery_code_hash
        )
    ):
        await pwreset_limiter.record(limiter_key)
        logger.warning(
            f"self password reset FAILED: username={request.username!r} ip={client_ip}"
        )
        raise AuthException("用户名或恢复码错误")

    user.password_hash = get_password_hash(request.new_password)
    recovery_code_service.clear_member_recovery_code(user)
    await db.commit()
    logger.info(f"self password reset OK: user={user.username} ip={client_ip}")
    return {"message": "密码重置成功，请使用新密码登录"}
