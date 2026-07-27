"""
Webhook 处理 (W74 第 1 批 B-2 真支付接入)

派工 v6 段 5 反馈 #6 实战:
- 异步处理 3 支付渠道 webhook 事件 (mock)
- 签名验证 (仅 mock, 真接入主拍拍板)
- 幂等性: webhook_event_id 去重

不破坏老路径: 仅在 app/services/billing/webhook_handler.py 新增.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.services.billing_gateway import (
    get_billing_gateway,
    list_supported_providers,
)

logger = logging.getLogger(__name__)

# 进程级内存存储 (webhook 事件去重)
_PROCESSED_WEBHOOK_IDS: set[str] = set()
_WEBHOOK_EVENTS: dict[str, dict] = {}


def _generate_webhook_event_id() -> str:
    """生成 webhook event id."""
    import secrets
    return "evt_" + secrets.token_hex(12)


async def handle_webhook_event(
    provider: str,
    payload: bytes,
    signature: str,
    event_type: str,
    event_id: Optional[str] = None,
) -> dict:
    """处理 webhook 事件 (异步).

    Returns:
        dict with event_id, status, provider, event_type, processed
    """
    if provider not in list_supported_providers():
        return {
            "event_id": None,
            "status": "rejected",
            "provider": provider,
            "event_type": event_type,
            "error": f"unsupported provider '{provider}'",
        }

    # 签名验证 (mock)
    gateway = get_billing_gateway(provider)
    if not gateway.verify_webhook_signature(payload, signature):
        logger.warning("webhook signature verification failed: provider=%s", provider)
        return {
            "event_id": None,
            "status": "rejected",
            "provider": provider,
            "event_type": event_type,
            "error": "signature verification failed",
        }

    # 幂等性: event_id 去重
    evt_id = event_id or _generate_webhook_event_id()
    if evt_id in _PROCESSED_WEBHOOK_IDS:
        logger.info("webhook event already processed: id=%s provider=%s", evt_id, provider)
        return {
            "event_id": evt_id,
            "status": "duplicate",
            "provider": provider,
            "event_type": event_type,
        }

    # 记录
    _PROCESSED_WEBHOOK_IDS.add(evt_id)
    _WEBHOOK_EVENTS[evt_id] = {
        "event_id": evt_id,
        "provider": provider,
        "event_type": event_type,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload_size": len(payload),
    }
    logger.info("webhook processed: id=%s provider=%s type=%s", evt_id, provider, event_type)
    return {
        "event_id": evt_id,
        "status": "processed",
        "provider": provider,
        "event_type": event_type,
    }


async def get_webhook_event(event_id: str) -> Optional[dict]:
    """查询 webhook 事件."""
    return _WEBHOOK_EVENTS.get(event_id)


def clear_webhook_history() -> None:
    """清空 webhook 历史 (测试用)."""
    _PROCESSED_WEBHOOK_IDS.clear()
    _WEBHOOK_EVENTS.clear()