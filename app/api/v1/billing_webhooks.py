"""
计费 Webhook 端点 (W74 第 1 批 B-2 真支付接入)

3 支付渠道 webhook 端点:
- /api/v1/billing/webhooks/stripe
- /api/v1/billing/webhooks/alipay
- /api/v1/billing/webhooks/wechat_pay

派工 v6 段 5 反馈 #6 实战:
- 签名验证仅 mock (真接入主拍拍板)
- 异步处理 webhook 事件 (Celery task 留位)
- 幂等性: webhook_event_id 去重
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request, Header, status, HTTPException
from pydantic import BaseModel, Field

from app.services.billing.webhook_handler import (
    handle_webhook_event,
    get_webhook_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/webhooks", tags=["billing-webhooks"])


class WebhookResponse(BaseModel):
    """Webhook 响应."""
    event_id: Optional[str]
    status: str
    provider: str
    event_type: Optional[str] = None
    error: Optional[str] = None


@router.post("/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> WebhookResponse:
    """Stripe webhook 端点 (mock 签名验证)."""
    body = await request.body()
    event_type = request.headers.get("X-Event-Type", "unknown")
    event_id = request.headers.get("X-Event-ID")
    result = await handle_webhook_event(
        provider="stripe",
        payload=body,
        signature=stripe_signature,
        event_type=event_type,
        event_id=event_id,
    )
    if result["status"] == "rejected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return WebhookResponse(**result)


@router.post("/alipay", response_model=WebhookResponse)
async def alipay_webhook(
    request: Request,
    signature: str = Header(..., alias="X-Alipay-Signature"),
) -> WebhookResponse:
    """支付宝 webhook 端点 (mock 签名验证)."""
    body = await request.body()
    event_type = request.headers.get("X-Event-Type", "unknown")
    event_id = request.headers.get("X-Event-ID")
    result = await handle_webhook_event(
        provider="alipay",
        payload=body,
        signature=signature,
        event_type=event_type,
        event_id=event_id,
    )
    if result["status"] == "rejected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return WebhookResponse(**result)


@router.post("/wechat_pay", response_model=WebhookResponse)
async def wechat_pay_webhook(
    request: Request,
    signature: str = Header(..., alias="X-Wechatpay-Signature"),
) -> WebhookResponse:
    """微信支付 webhook 端点 (mock 签名验证)."""
    body = await request.body()
    event_type = request.headers.get("X-Event-Type", "unknown")
    event_id = request.headers.get("X-Event-ID")
    result = await handle_webhook_event(
        provider="wechat_pay",
        payload=body,
        signature=signature,
        event_type=event_type,
        event_id=event_id,
    )
    if result["status"] == "rejected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
    return WebhookResponse(**result)


@router.get("/events/{event_id}", response_model=WebhookResponse)
async def get_event(event_id: str) -> WebhookResponse:
    """查询 webhook 事件 (调试用)."""
    evt = await get_webhook_event(event_id)
    if not evt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"webhook event '{event_id}' not found",
        )
    return WebhookResponse(**evt)