"""Drive v2 PR10 — 协同编辑 API 端点 (2026-07-24, W68 第 7 批 B-1)

3 类端点:
1. WS   /api/v1/drive/files/{file_id}/collab?token=<jwt>
   - Yjs 同步协议: init → op 双向 → 广播 (Redis pub/sub 扇出)
2. REST GET  /api/v1/drive/files/{file_id}/snapshot
   - 返最新全量 Y.Doc update 字节 (application/octet-stream)
3. REST POST /api/v1/drive/files/{file_id}/op
   - 提交单条 op bytes (供无 WS 的场景 / 移动端简化写)

鉴权 (CLAUDE.md chat-history 铁律 8 越权防护):
- WS: JWT token 走 query string (WS 协议 Header 复杂), decode → user_id
- REST: get_current_user (JWT Header)
- 权限: DrivePermissionService.check_file_owner_or_folder_admin (W68 第 4 批复用)
  - 读 (WS 连入 / snapshot): 走 _can_see_file? 本 PR MVP 用 check_file_owner_or_folder_admin
    统一门槛 (编辑权限隐含读权限); W71 细分 read/write
  - 写 (op): check_file_owner_or_folder_admin

跨 event loop 安全 (方案 C 铁律 1):
- redis client 由 WS handler 内 get_redis() 按当前 loop 创建, 不在模块顶部创建全局

Redis pub/sub 房间 (设计 doc §2.1):
- 每个 file_id 一个频道 drive:collab:room:{file_id}
- 客户端 A 发 op → apply_remote_op 落库 → publish_op_to_room 广播
- 客户端 B/C subscribe_to_room 收到 → 转发到各自 WS (跳过自己 origin)

参考:
- app/api/v1/ws_notifications.py (WS 鉴权 + 心跳模式)
- app/api/v1/drive_versions.py (REST + 权限模式)
- app/services/drive_collab_service.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_token, get_current_user
from app.models.member import Member
from app.services.drive_collab_service import (
    DriveCollabService,
    InvalidOpError,
)
from app.services.drive_permission_service import DrivePermissionService

logger = logging.getLogger("microbubble.drive_collab_api")

router = APIRouter(tags=["网盘协同编辑"])


# ============================================================
# Pydantic schemas (REST)
# ============================================================
class CollabOpRequest(BaseModel):
    """POST /op 请求体"""

    op_base64: str = Field(..., description="Yjs update 字节的 base64 编码")
    client_id: int = Field(..., description="Yjs client_id (uint32)")


class CollabOpResponse(BaseModel):
    """POST /op 响应"""

    file_id: int
    ops_count_delta: int = Field(1, description="本次应用的 op 数")
    snapshot_base64: str = Field(..., description="应用后最新全量 Y.Doc update 的 base64")
    broadcast_subscribers: int = Field(0, description="广播到的订阅者数")


class CollabSnapshotMeta(BaseModel):
    """GET /snapshot 元信息 (当 ?meta=1 时返 JSON 而非二进制)"""

    file_id: int
    snapshot_bytes: int
    active_users: int


# ============================================================
# 1. WebSocket 协同编辑端点
# ============================================================
@router.websocket("/drive/files/{file_id}/collab")
async def ws_collab(
    websocket: WebSocket,
    file_id: int,
    token: Optional[str] = Query(None),
):
    """WebSocket /api/v1/drive/files/{file_id}/collab?token=<jwt>

    Yjs 同步协议 (JSON 消息, op 走 base64):
    - client → server:
        {"type": "op", "payload": "<base64>", "client_id": <uint32>}
        {"type": "ping"}
    - server → client:
        {"type": "init", "state": "<base64>", "version": 0}    (连接时首发)
        {"type": "op", "payload": "<base64>", "origin": <client_id>}  (其他客户端 op)
        {"type": "pong"}
        {"type": "error", "code": "...", "message": "..."}

    鉴权 (在 accept 前):
    - 无 token → close 4401
    - token 无效 → close 4401
    - 无文件权限 → close 4403
    """
    # 1) JWT 鉴权 (accept 前)
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4401, reason="invalid token type")
            return
        user_id = int(payload.get("sub"))
    except Exception as e:
        logger.warning("[collab-ws] token 解析失败: %s", e)
        await websocket.close(code=4401, reason="invalid token")
        return

    # 2) 文件权限 (复用 W68 第 4 批 DrivePermissionService)
    #    需要独立 db session (WS 生命周期长, 不能用 Depends(get_db) 的请求级 session)
    from app.core.database import async_session

    async with async_session() as perm_db:
        perm_svc = DrivePermissionService(perm_db)
        allowed = await perm_svc.check_file_owner_or_folder_admin(user_id, file_id)
    if not allowed:
        await websocket.close(code=4403, reason="permission denied")
        return

    # 3) accept + 初始 sync
    await websocket.accept()

    # 按当前 WS loop 创建 redis (方案 C 铁律 1: 不用模块顶部全局 client)
    redis = await get_redis()

    # init: 发送当前全量 snapshot
    try:
        async with async_session() as db:
            snapshot = await DriveCollabService.get_snapshot(db, file_id)
        await websocket.send_text(json.dumps({
            "type": "init",
            "state": base64.b64encode(snapshot).decode("ascii"),
            "version": 0,
        }))
    except Exception as e:
        logger.error("[collab-ws] init 失败 file_id=%d: %s", file_id, e, exc_info=True)
        await websocket.close(code=1011, reason="init failed")
        return

    # 4) 后台订阅 Redis 房间, 把其他客户端的 op 转发给本连接
    my_client_id_holder = {"cid": None}  # 记录本连接的 client_id, 跳过自己的 op 回声

    async def _fanout_task():
        try:
            async for origin_cid, op_bytes in DriveCollabService.subscribe_to_room(redis, file_id):
                if my_client_id_holder["cid"] is not None and origin_cid == my_client_id_holder["cid"]:
                    continue  # 跳过自己发的 op (已在本地 apply)
                try:
                    await websocket.send_text(json.dumps({
                        "type": "op",
                        "payload": base64.b64encode(op_bytes).decode("ascii"),
                        "origin": origin_cid,
                    }))
                except Exception:
                    break
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug("[collab-ws] fanout 结束 file_id=%d: %s", file_id, e)

    fanout = asyncio.create_task(_fanout_task())

    # 5) 接收 loop
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if msg_type == "op":
                client_id = data.get("client_id")
                payload_b64 = data.get("payload")
                if client_id is None or not payload_b64:
                    await websocket.send_text(json.dumps({
                        "type": "error", "code": "INVALID_OP",
                        "message": "op requires client_id + payload",
                    }))
                    continue
                my_client_id_holder["cid"] = int(client_id)
                try:
                    op_bytes = base64.b64decode(payload_b64)
                except Exception:
                    await websocket.send_text(json.dumps({
                        "type": "error", "code": "INVALID_OP",
                        "message": "payload not valid base64",
                    }))
                    continue

                # apply + persist (独立 session)
                try:
                    async with async_session() as db:
                        await DriveCollabService.apply_remote_op(
                            db, file_id, op_bytes, int(client_id), user_id=user_id,
                        )
                except InvalidOpError as e:
                    await websocket.send_text(json.dumps({
                        "type": "error", "code": "INVALID_OP", "message": str(e),
                    }))
                    continue
                except Exception as e:
                    logger.error("[collab-ws] apply_op 失败 file_id=%d: %s", file_id, e, exc_info=True)
                    await websocket.send_text(json.dumps({
                        "type": "error", "code": "APPLY_FAILED", "message": "internal error",
                    }))
                    continue

                # 广播给房间其他客户端
                await DriveCollabService.publish_op_to_room(
                    redis, file_id, op_bytes, int(client_id),
                )
                continue

            # 未知类型忽略
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("[collab-ws] loop 异常 file_id=%d: %s", file_id, e, exc_info=True)
    finally:
        fanout.cancel()
        try:
            await fanout
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await websocket.close()
        except Exception:
            pass


# ============================================================
# 2. REST GET /snapshot — 返最新全量 Y.Doc
# ============================================================
@router.get("/drive/files/{file_id}/snapshot")
async def get_snapshot(
    file_id: int,
    meta: int = Query(0, description="1=返 JSON 元信息, 0=返二进制 octet-stream"),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """GET /api/v1/drive/files/{file_id}/snapshot

    权限: check_file_owner_or_folder_admin (编辑权限隐含读)
    返回:
    - meta=0 (默认): application/octet-stream 二进制全量 Y.Doc update
    - meta=1: JSON {file_id, snapshot_bytes, active_users}
    """
    perm_svc = DrivePermissionService(db)
    if not await perm_svc.check_file_owner_or_folder_admin(user.id, file_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该文件")

    snapshot = await DriveCollabService.get_snapshot(db, file_id)

    if meta:
        active = await DriveCollabService.get_active_users(db, file_id)
        return CollabSnapshotMeta(
            file_id=file_id, snapshot_bytes=len(snapshot), active_users=active,
        )

    return Response(
        content=snapshot,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="ydoc_{file_id}.bin"'},
    )


# ============================================================
# 3. REST POST /op — 提交单条 op bytes
# ============================================================
@router.post("/drive/files/{file_id}/op", response_model=CollabOpResponse)
async def submit_op(
    file_id: int,
    body: CollabOpRequest,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """POST /api/v1/drive/files/{file_id}/op

    供无 WS 连接的场景 (移动端简化写 / 脚本批量导入).
    apply + persist + 广播到房间 (使 WS 客户端也收到).

    权限: check_file_owner_or_folder_admin
    """
    perm_svc = DrivePermissionService(db)
    if not await perm_svc.check_file_owner_or_folder_admin(user.id, file_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权编辑该文件")

    try:
        op_bytes = base64.b64decode(body.op_base64)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="op_base64 非法")

    try:
        new_state = await DriveCollabService.apply_remote_op(
            db, file_id, op_bytes, body.client_id, user_id=user.id,
        )
    except InvalidOpError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 广播到 WS 房间 (best-effort)
    subscribers = 0
    try:
        redis = await get_redis()
        subscribers = await DriveCollabService.publish_op_to_room(
            redis, file_id, op_bytes, body.client_id,
        )
    except Exception:
        logger.debug("[collab] POST /op 广播失败 file_id=%d (非阻塞)", file_id)

    return CollabOpResponse(
        file_id=file_id,
        ops_count_delta=1,
        snapshot_base64=base64.b64encode(new_state).decode("ascii"),
        broadcast_subscribers=subscribers,
    )
