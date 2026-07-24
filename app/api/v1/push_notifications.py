"""push_notifications — v3.2 PWA 浏览器推送 REST API (2026-07-24, W68 第 7 批 B-3)

端点:
  GET    /api/v1/push/vapid-public-key     → 返 VAPID 公钥 (客户端 subscribe 用)
  POST   /api/v1/push/subscribe            → 接收前端 subscription, 存 DB
  DELETE /api/v1/push/subscribe            → 取消订阅 (按 endpoint)
  POST   /api/v1/push/subscribe/heartbeat  → 更新 last_seen_at (前端定期)
  GET    /api/v1/push/subscriptions        → 列当前用户所有订阅 (settings 页)
  POST   /api/v1/push/admin/test           → admin 测试推送 (单用户 / topic)

限流: 走 write tier (30/min, 见 app/core/rate_limit.py)
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.security import get_current_admin_user, get_current_user
from app.models.member import Member
from app.services import push_service

router = APIRouter(prefix="/push", tags=["PWA 浏览器推送"])


# ==========================================================================
# Schemas
# ==========================================================================

class VAPIDPublicKeyResponse(BaseModel):
    """GET /push/vapid-public-key 响应"""
    public_key: str = Field(..., description="VAPID 公钥 (base64url, 客户端用)")


class SubscribeRequest(BaseModel):
    """POST /push/subscribe 请求"""
    endpoint: str = Field(..., min_length=10, max_length=512)
    keys: dict = Field(..., description="含 p256dh + auth")
    user_agent: Optional[str] = Field(None, max_length=512)
    topics: Optional[List[str]] = Field(None, description="订阅的 topic 列表 (例: ['meeting_reminder'])")


class SubscribeResponse(BaseModel):
    """POST /push/subscribe 响应"""
    id: int
    endpoint: str
    user_id: int
    last_seen_at: Optional[str] = None
    topics: List[str] = []


class UnsubscribeRequest(BaseModel):
    """DELETE /push/subscribe 请求"""
    endpoint: str = Field(..., min_length=10, max_length=512)


class HeartbeatRequest(BaseModel):
    """POST /push/subscribe/heartbeat 请求"""
    endpoint: str = Field(..., min_length=10, max_length=512)


class SubscriptionInfo(BaseModel):
    """GET /push/subscriptions 单条"""
    id: int
    endpoint: str
    user_agent: Optional[str] = None
    last_seen_at: Optional[str] = None
    created_at: Optional[str] = None


class SubscriptionListResponse(BaseModel):
    """GET /push/subscriptions 响应"""
    items: List[SubscriptionInfo]
    total: int


class AdminTestPushRequest(BaseModel):
    """POST /push/admin/test 请求"""
    user_id: Optional[int] = Field(None, description="指定用户 (与 topic 二选一)")
    topic: Optional[str] = Field(None, description="指定 topic 广播 (与 user_id 二选一)")
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    data: Optional[dict] = None


class AdminTestPushResponse(BaseModel):
    """POST /push/admin/test 响应"""
    delivered: int
    failed: int
    purged: int


# ==========================================================================
# Endpoints
# ==========================================================================

@router.get("/vapid-public-key", response_model=VAPIDPublicKeyResponse)
async def get_vapid_public_key():
    """GET /api/v1/push/vapid-public-key

    公开端点 (无需鉴权, 公钥本来就是公开的)
    客户端用此公钥 + pushManager.subscribe() 建立订阅
    """
    return VAPIDPublicKeyResponse(public_key=push_service.get_vapid_public_key())


@router.post("/subscribe", response_model=SubscribeResponse, status_code=201)
async def subscribe_to_push(
    payload: SubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """POST /api/v1/push/subscribe

    接收前端 navigator.serviceWorker.pushManager.subscribe() 的 subscription,
    持久化到 push_subscriptions 表 (1 用户多端).
    """
    p256dh = payload.keys.get("p256dh")
    auth = payload.keys.get("auth")
    if not p256dh or not auth:
        raise AppException(
            code="VALIDATION_ERROR",
            message="keys 必须含 p256dh 和 auth",
            status_code=400,
        )

    sub = await push_service.subscribe(
        db,
        user_id=current_user.id,
        endpoint=payload.endpoint,
        p256dh=p256dh,
        auth=auth,
        user_agent=payload.user_agent,
        topics=payload.topics,
    )

    # 拉 topic names (响应)
    topic_names: List[str] = []
    if sub.topic_bindings:
        from app.models.push_subscription import PushTopic
        topic_ids = [b.topic_id for b in sub.topic_bindings]
        topics = (await db.execute(
            __import__("sqlalchemy").select(PushTopic).where(PushTopic.id.in_(topic_ids))
        )).scalars().all()
        topic_names = [t.name for t in topics]

    return SubscribeResponse(
        id=sub.id,
        endpoint=sub.endpoint,
        user_id=sub.user_id,
        last_seen_at=sub.last_seen_at.isoformat() if sub.last_seen_at else None,
        topics=topic_names,
    )


@router.delete("/subscribe", status_code=204)
async def unsubscribe_from_push(
    payload: UnsubscribeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """DELETE /api/v1/push/subscribe

    按 endpoint 取消订阅 (越权 = 0 行)
    """
    success = await push_service.unsubscribe(
        db,
        user_id=current_user.id,
        endpoint=payload.endpoint,
    )
    if not success:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message="订阅不存在或无权访问",
            status_code=404,
        )
    return None


@router.post("/subscribe/heartbeat", status_code=204)
async def heartbeat_push(
    payload: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """POST /api/v1/push/subscribe/heartbeat

    前端定期 POST (例: 每 5min) 通知服务端订阅仍活跃
    防止 90 天未活跃被 purge
    """
    from sqlalchemy import and_, select
    from app.models.push_subscription import PushSubscription
    sub = (await db.execute(
        select(PushSubscription).where(
            and_(
                PushSubscription.user_id == current_user.id,
                PushSubscription.endpoint == payload.endpoint,
            )
        )
    )).scalar_one_or_none()
    if sub is None:
        raise AppException(
            code="RESOURCE_NOT_FOUND",
            message="订阅不存在",
            status_code=404,
        )
    await push_service.update_last_seen(db, subscription_id=sub.id)
    return None


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_my_subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """GET /api/v1/push/subscriptions

    列当前用户所有订阅 (settings 页用, 1 用户多端管理)
    """
    subs = await push_service.list_subscriptions_for_user(
        db, user_id=current_user.id,
    )
    return SubscriptionListResponse(
        items=[
            SubscriptionInfo(
                id=s.id,
                endpoint=s.endpoint,
                user_agent=s.user_agent,
                last_seen_at=s.last_seen_at.isoformat() if s.last_seen_at else None,
                created_at=s.created_at.isoformat() if s.created_at else None,
            )
            for s in subs
        ],
        total=len(subs),
    )


@router.post("/admin/test", response_model=AdminTestPushResponse)
async def admin_test_push(
    payload: AdminTestPushRequest,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(get_current_admin_user),
):
    """POST /api/v1/push/admin/test

    Admin 测试推送 (单用户 / topic 广播)
    用于验证 VAPID key + endpoint 联通性
    """
    if not payload.user_id and not payload.topic:
        raise AppException(
            code="VALIDATION_ERROR",
            message="user_id 或 topic 必填一个",
            status_code=400,
        )
    if payload.user_id and payload.topic:
        raise AppException(
            code="VALIDATION_ERROR",
            message="user_id 和 topic 互斥, 只能选一个",
            status_code=400,
        )

    if payload.user_id:
        result = await push_service.push_to_user(
            db,
            user_id=payload.user_id,
            title=payload.title,
            body=payload.body,
            data=payload.data,
        )
    else:
        result = await push_service.push_to_topic(
            db,
            topic_name=payload.topic,
            title=payload.title,
            body=payload.body,
            data=payload.data,
        )

    return AdminTestPushResponse(**result)
