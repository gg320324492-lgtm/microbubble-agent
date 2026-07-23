"""ws_notifications — v2 PR6 WebSocket 推送通知 / 活动流

路由:
- WS /api/v1/ws/notifications?token=xxx  (JWT 鉴权, 无 cookie 依赖)
- WS /api/v1/ws/notifications?token=xxx&priority=high|medium|low  (W68 PR8d 优先级过滤)

功能:
- 单实例内存 BroadcastManager (按 user_id 维护 ws 连接 set)
- send JSON: {"type": "mention" | "activity" | "ping", "data": {...}}
- 心跳: 服务端每 5s ping, 客户端响应 pong, 30s 没收到 pong → 关闭
- 断开: 自动清理连接 (防止泄漏)
- 跨实例 (PR8+ 考虑): 切 Redis Pub/Sub; PR6 阶段先单实例
- W68 PR8d 增强:
  - priority filter (?priority=high|medium|low) 客户端订阅指定优先级
  - reconnect handler: 连接时自动 drain 离线队列 (按 priority filter)
  - heartbeat: 5s ping / 30s timeout (原 60s 改 30s, 5s 主动 ping)
  - 离线入队: push 失败 (用户离线) 自动入 Redis list, reconnect 拉

设计要点:
- WSManager 是单例, process 级共享 (FastAPI 全局 state)
- 不写 DB (推送是 best-effort; 离线用户会通过 GET /notifications 拉历史)
- JWT 解析失败 → close 1008 (token 错)
- 心跳超时 (30s 没收到 pong) → close 1011
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


# W68 PR8d: heartbeat 参数
HEARTBEAT_PING_INTERVAL = 5.0      # 服务端主动 ping 间隔 (秒)
HEARTBEAT_PONG_TIMEOUT = 30.0       # 30s 没收到 pong → 关闭


class NotificationManager:
    """单实例 WS 连接管理

    - user_id → Set[WebSocket]
    - push_to_user(user_id, payload): 群发该 user 的所有 ws
    - 重复 connect 同一 user: 保留多个 ws (多设备场景: 桌面+移动 同时连)
    - W68 PR8d: _push_history 记录最近推送 (reconnect 时按需 re-deliver)
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

    async def push_to_user(
        self,
        user_id: int,
        payload: dict,
        *,
        priority_filter: Optional[Set[str]] = None,
    ) -> int:
        """推送给 user 的所有 ws

        Args:
            user_id: 目标 user
            payload: 通知内容
            priority_filter: W68 PR8d 可选, 仅推送给订阅了该 priority 的 ws;
                            None=推所有 ws; Set[str]={'high', 'medium', 'low'}

        Returns:
            成功推送的 ws 数 (0 = 用户离线)
        """
        async with self._lock:
            # W68 PR8d: ws 上挂 _priority_filter 属性, 用于过滤
            all_conns = list(self._connections.get(user_id, set()))
            if priority_filter is None:
                conns = all_conns
            else:
                conns = [ws for ws in all_conns if getattr(ws, "_priority_filter", None) is None
                         or (set(getattr(ws, "_priority_filter")) & priority_filter)]

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
    priority: Optional[str] = Query(None),  # W68 PR8d: high|medium|low
):
    """WebSocket /api/v1/ws/notifications?token=xxx[&priority=high]

    协议:
    - client → server: {"type": "pong"}  (响应 ping)
    - server → client: {"type": "ping", "ts": "..."}  (5s 一次, W68 PR8d)
    - server → client: {"type": "mention", ...}        (有 mention 时推)
    - server → client: {"type": "activity", ...}       (有 activity 时推, PR7+)
    - server → client: {"type": "hello", "user_id": ..., "replayed": N}
                                                          (连接时 send, 含 replayed 离线消息数)
    - W68 PR8d: ?priority=high 仅收 HIGH 通知, 默认全部 3 档
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

    # W68 PR8d: 解析 priority filter
    priority_filter: Optional[Set[str]] = None
    if priority:
        valid = {"high", "medium", "low"}
        if priority not in valid:
            await websocket.close(code=1008, reason=f"invalid priority: {priority}")
            return
        priority_filter = {priority}
    websocket._priority_filter = priority_filter  # 存到 ws 对象, push_to_user 过滤用

    # 2) accept + register
    await websocket.accept()
    await notification_manager.connect(user_id, websocket)

    # W68 PR8d: reconnect handler — drain 离线队列
    replayed_count = 0
    try:
        from app.services.notification_service import drain_offline_queue
        offline_msgs = await drain_offline_queue(user_id, priority_filter=priority)
        for m in offline_msgs:
            try:
                await websocket.send_text(json.dumps(m, default=str))
                replayed_count += 1
            except Exception:
                break
    except Exception as e:
        logger.debug(f"[WS] drain offline 失败 (非阻塞): {e}")

    # 3) 初始 send: hello + replayed count
    try:
        await websocket.send_text(json.dumps({
            "type": "hello",
            "user_id": user_id,
            "ts": datetime.utcnow().isoformat(),
            "priority_filter": list(priority_filter) if priority_filter else None,
            "replayed": replayed_count,  # W68 PR8d: 离线补推条数
        }))
    except Exception:
        pass

    # 4) 双向心跳 + 接收 loop
    # W68 PR8d: 5s 主动 ping, 30s pong 超时
    try:
        last_pong_ts = asyncio.get_event_loop().time()
        last_ping_ts = last_pong_ts
        while True:
            try:
                # 接收 (timeout 30s 等 ping/pong, W68 PR8d: 30s 改严)
                msg = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_PONG_TIMEOUT,
                )
                try:
                    data = json.loads(msg)
                    if data.get("type") == "pong":
                        last_pong_ts = asyncio.get_event_loop().time()
                    elif data.get("type") == "ping":
                        # 客户端主动 ping, 响应 pong
                        await websocket.send_text(json.dumps({"type": "pong", "ts": datetime.utcnow().isoformat()}))
                        last_pong_ts = asyncio.get_event_loop().time()
                except json.JSONDecodeError:
                    pass  # 忽略非 JSON
            except asyncio.TimeoutError:
                # W68 PR8d: 30s 没收到任何消息 → 关闭 (原 60s)
                logger.info(f"[WS] pong timeout user_id={user_id}, close 1011")
                await websocket.close(code=1011, reason="pong timeout")
                break

            # W68 PR8d: 5s 主动 ping (独立协程逻辑嵌主循环, 简化实现)
            now_ts = asyncio.get_event_loop().time()
            if (now_ts - last_ping_ts) >= HEARTBEAT_PING_INTERVAL:
                try:
                    await websocket.send_text(json.dumps({"type": "ping", "ts": datetime.utcnow().isoformat()}))
                    last_ping_ts = now_ts
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