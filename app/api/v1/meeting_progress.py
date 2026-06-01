"""会议进度查询 — WebSocket + REST"""
import asyncio
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_token, get_current_user
from app.models.member import Member
from app.services.progress_service import get_progress

logger = logging.getLogger("microbubble.meeting_progress")
router = APIRouter()


@router.websocket("/ws/meeting/{meeting_id}/progress")
async def meeting_progress_ws(
    websocket: WebSocket,
    meeting_id: int,
    token: str = Query(""),
):
    """
    进度订阅 WS。
    连接流程：
    1. JWT 鉴权
    2. 发送当前快照
    3. 订阅 Redis channel progress:{id}
    4. 转发 pub/sub 消息
    """
    # 1. 鉴权
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    r = await get_redis()
    channel_name = f"progress:{meeting_id}"

    # 2. 发送当前快照
    snapshot = await get_progress(meeting_id)
    await websocket.send_json({
        "type": "progress_snapshot",
        "data": snapshot,
    })

    # 3. 订阅
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_name)
    try:
        # 4. 循环接收
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=30.0,
                )
                if message:
                    await websocket.send_text(message["data"])
            except asyncio.TimeoutError:
                # 心跳：发送 ping
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info(f"进度 WS 断开: meeting_id={meeting_id}")
    finally:
        await pubsub.unsubscribe(channel_name)
        await pubsub.aclose()


@router.get("/meetings/{meeting_id}/progress")
async def get_meeting_progress(
    meeting_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """REST 查询当前进度（WS 断线时兜底）"""
    snapshot = await get_progress(meeting_id)
    if snapshot is None:
        return {"progress": None}
    return {"progress": snapshot}
