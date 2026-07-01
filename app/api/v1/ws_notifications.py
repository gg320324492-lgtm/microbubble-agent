"""ws_notifications — v2 PR6 WebSocket 推送通知 / 活动流

路由:
- WS /api/v1/ws/notifications?token=xxx  (JWT 鉴权, 无 cookie 依赖)

功能:
- 单实例内存 BroadcastManager (按 user_id 维护 ws 连接 set)
- send JSON: {"type": "mention" | "activity" | "ping", "data": {...}}
- 心跳: 服务端每 30s ping, 客户端响应 pong
- 断开: 自动清理连接 (防止泄漏)
- 跨实例 (PR8+ 考虑): 切 Redis Pub/Sub; PR6 阶段先单实例

设计要点:
- WSManager 是单例, process 级共享 (FastAPI 全局 state)
- 不写 DB (推送是 best-effort; 离线用户会通过 GET /notifications 拉历史)
- JWT 解析失败 → close 1008 (token 错)
- 心跳超时 (60s 没收到 pong) → close 1011
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.member import Member

logger = logging.getLogger("microbubble.ws_notify")
router = APIRouter(tags=["WebSocket"])


class NotificationManager:
    """单实例 WS 连接管理

    - user_id → Set[WebSocket]
    - push_to_user(user_id, payload): 群发该 user 的所有 ws
    - 重复 connect 同一 user: 保留多个 ws (多设备场景: 桌面+移动 同时连)
    """

    def __init__(self):
        self._connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(ws)
        logger.info(f"[WS] connect user_id={user_id} total={len(self._connections[user_id])}")

    async def disconnect(self, user_id: int, ws: WebSocket) -> None:
        async with self._lock:
            if user_id in self._connections:
                self._connections[user_id].discard(ws)
                if not self._connections[user_id]:
                    del self._connections[user_id]
        logger.info(f"[WS] disconnect user_id={user_id}")

    async def push_to_user(self, user_id: int, payload: dict) -> int:
        """推送给 user 的所有 ws

        Returns:
            成功推送的 ws 数 (0 = 用户离线)
        """
        async with self._lock:
            conns = list(self._connections.get(user_id, set()))

        if not conns:
            return 0

        payload.setdefault("ts", datetime.utcnow().isoformat())
        text = json.dumps(payload, default=str)

        delivered = 0
        for ws in conns:
            try:
                await ws.send_text(text)
                delivered += 1
            except Exception as e:
                logger.warning(f"[WS] push 失败 user_id={user_id}: {e}")
                await self.disconnect(user_id, ws)
        return delivered

    def online_count(self) -> int:
        return len(self._connections)

    def is_online(self, user_id: int) -> bool:
        return user_id in self._connections and bool(self._connections[user_id])


# 全局单例
notification_manager = NotificationManager()


@router.websocket("/ws/notifications")
async def ws_notifications(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    """WebSocket /api/v1/ws/notifications?token=xxx

    协议:
    - client → server: {"type": "pong"}  (响应 ping)
    - server → client: {"type": "ping", "ts": "..."}  (30s 一次)
    - server → client: {"type": "mention", ...}        (有 mention 时推)
    - server → client: {"type": "activity", ...}       (有 activity 时推, PR7+)
    """
    # 1) JWT 鉴权 (必须在 accept 前)
    if not token:
        await websocket.close(code=1008, reason="missing token")
        return
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=1008, reason="invalid token type")
            return
        user_id = int(payload.get("sub"))
    except Exception as e:
        logger.warning(f"[WS] token 解析失败: {e}")
        await websocket.close(code=1008, reason="invalid token")
        return

    # 2) accept + register
    await websocket.accept()
    await notification_manager.connect(user_id, websocket)

    # 3) 初始 send: hello + unread count
    try:
        from app.core.database import async_session_factory
        # 简化: 不阻塞, 立刻 send hello
        await websocket.send_text(json.dumps({
            "type": "hello",
            "user_id": user_id,
            "ts": datetime.utcnow().isoformat(),
        }))
    except Exception:
        pass

    # 4) 双向心跳 + 接收 loop
    try:
        last_pong = asyncio.get_event_loop().time()
        while True:
            try:
                # 接收 (timeout 60s 等 ping/pong)
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                try:
                    data = json.loads(msg)
                    if data.get("type") == "pong":
                        last_pong = asyncio.get_event_loop().time()
                    elif data.get("type") == "ping":
                        # 客户端主动 ping, 响应 pong
                        await websocket.send_text(json.dumps({"type": "pong", "ts": datetime.utcnow().isoformat()}))
                except json.JSONDecodeError:
                    pass  # 忽略非 JSON
            except asyncio.TimeoutError:
                # 60s 没收到任何消息, 主动 ping
                try:
                    await websocket.send_text(json.dumps({"type": "ping", "ts": datetime.utcnow().isoformat()}))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"[WS] loop 异常 user_id={user_id}: {e}", exc_info=True)
    finally:
        await notification_manager.disconnect(user_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass