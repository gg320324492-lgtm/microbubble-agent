"""#043 账号持久化聊天历史 — API 路由

端点（11 个）：
- GET    /chat/sessions                列表（分页 + 过滤）
- POST   /chat/sessions                创建
- GET    /chat/sessions/{id}           详情（含 messages）
- PATCH  /chat/sessions/{id}           更新元信息
- DELETE /chat/sessions/{id}           软删除
- GET    /chat/sessions/{id}/messages  消息列表（分页）
- POST   /chat/sessions/{id}/messages  追加消息
- GET    /chat/sessions/{id}/export    导出（md/json）
- POST   /chat/sessions/{id}/share     创建分享
- GET    /chat/sessions/search?q=...   跨会话搜索
- POST   /chat/sync                    旧 localStorage 数据迁移
- GET    /chat/shares/{token}          公开访问分享（无 JWT）
- GET    /chat/sessions/{id}/shares    列出会话分享（仅创建者）
- DELETE /chat/sessions/{id}/shares/{share_id}  撤销分享

设计原则：
- 所有受保护端点用 Depends(get_current_user)，user_id 注入防越权
- service 层做所有业务逻辑，API 层只做参数解析 + 出参构造
- service 越权时抛 NotFoundException（不泄漏存在性）
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.models.member import Member
from app.schemas.chat_history import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionOut, ChatSessionListItem, ChatSessionListResponse,
    ChatMessageCreate, ChatMessageOut, ChatMessagesPage,
    ChatShareCreate, ChatShareOut, ChatSharePublicOut,
    ChatSyncRequest, ChatSyncResponse,
    ChatSearchResponse,
)
from app.services import chat_history_service as svc

logger = logging.getLogger("microbubble.api.chat_history")
router = APIRouter()


# ============================================================================
# Helper：ORM → Pydantic
# ============================================================================

def _session_to_out(session) -> ChatSessionOut:
    return ChatSessionOut.model_validate(session)


def _session_to_list_item(session) -> ChatSessionListItem:
    return ChatSessionListItem.model_validate(session)


def _message_to_out(msg) -> ChatMessageOut:
    return ChatMessageOut.model_validate(msg)


def _share_to_out(share) -> ChatShareOut:
    """构造 ChatShareOut + share_url"""
    base = ChatShareOut.model_validate(share)
    base.share_url = f"/api/v1/chat/shares/{share.id}"
    return base


# ============================================================================
# 1. GET /chat/sessions — 列表
# ============================================================================

@router.get("/chat/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    archived: bool = Query(False, description="默认拉活跃会话，True=拉归档"),
    pinned: bool = Query(False, description="仅拉收藏会话"),
    tag: Optional[str] = Query(None, max_length=20, description="按标签过滤"),
    search: Optional[str] = Query(None, max_length=100, description="标题/preview 模糊匹配"),
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(50, ge=1, le=200),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出会话（按 last_message_at 倒序，收藏置顶）"""
    sessions, total = await svc.list_sessions(
        db, current_user.id,
        archived=archived, pinned_only=pinned, tag=tag, search=search,
        page=page, page_size=page_size,
    )
    return ChatSessionListResponse(
        items=[_session_to_list_item(s) for s in sessions],
        total=total,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# 2. POST /chat/sessions — 创建
# ============================================================================

@router.post("/chat/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(
    body: ChatSessionCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建会话（可选同时创建首条 user 消息）"""
    session = await svc.create_session(
        db, current_user.id,
        title=body.title,
        first_message=body.first_message,
        client_session_id=body.client_session_id,
    )
    return _session_to_out(session)


# ============================================================================
# 3. GET /chat/sessions/search — 跨会话搜索 (必须在 /{session_id} 之前注册, 否则被拦截)
# ============================================================================

@router.get("/chat/sessions/search", response_model=ChatSearchResponse)
async def search_sessions(
    q: str = Query(..., min_length=2, max_length=200, description="搜索关键词，最少 2 字符"),
    page: int = Query(1, ge=1, le=100),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """跨会话搜索（按消息内容 + 会话标题）

    路由顺序铁律: /chat/sessions/search 是静态路径, 必须先于 /chat/sessions/{session_id}
    这种 dynamic path 注册, 否则 "search" 会被当 session_id, 返回 404 (CLAUDE.md 2026-06-04 教训)
    """
    items, total = await svc.search_sessions(
        db, current_user.id, q, page=page, page_size=page_size,
    )
    return ChatSearchResponse(
        items=items,
        total=total,
        query=q,
        page=page,
        page_size=page_size,
    )


# ============================================================================
# 4. GET /chat/sessions/{id} — 详情（含 messages）
# ============================================================================

@router.get("/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(
    session_id: str,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话详情（包含所有 messages）"""
    session = await svc.get_session(
        db, current_user.id, session_id, include_messages=True,
    )
    if session is None:
        raise NotFoundException("会话不存在或已删除")
    return _session_to_out(session)


# ============================================================================
# 4. PATCH /chat/sessions/{id} — 更新元信息
# ============================================================================

@router.patch("/chat/sessions/{session_id}", response_model=ChatSessionOut)
async def update_session(
    session_id: str,
    body: ChatSessionUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新会话元信息（title / is_pinned / is_archived / tags）"""
    session = await svc.update_session(
        db, current_user.id, session_id,
        title=body.title,
        is_pinned=body.is_pinned,
        is_archived=body.is_archived,
        tags=body.tags,
    )
    if session is None:
        raise NotFoundException("会话不存在或已删除")
    return _session_to_out(session)


# ============================================================================
# 5. DELETE /chat/sessions/{id} — 删除
# ============================================================================

@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    hard: bool = Query(False, description="True=物理删除（不可恢复），False=软删除（30天清理）"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话（默认软删除，30 天后 Celery 物理清除）"""
    ok = await svc.delete_session(db, current_user.id, session_id, hard=hard)
    if not ok:
        raise NotFoundException("会话不存在或已删除")
    return {"ok": True, "hard": hard, "session_id": session_id}


# ============================================================================
# 6. GET /chat/sessions/{id}/messages — 消息列表
# ============================================================================

@router.get("/chat/sessions/{session_id}/messages", response_model=ChatMessagesPage)
async def list_messages(
    session_id: str,
    after_id: int = Query(0, ge=0, description="增量游标：只返回 id > after_id 的消息"),
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(100, ge=1, le=500),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出会话消息（按 created_at 正序）"""
    msgs, has_more = await svc.list_messages(
        db, current_user.id, session_id,
        page=page, page_size=page_size, after_id=after_id,
    )
    next_after_id = msgs[-1].id if has_more and msgs else None
    return ChatMessagesPage(
        items=[_message_to_out(m) for m in msgs],
        has_more=has_more,
        next_after_id=next_after_id,
    )


# ============================================================================
# 7. POST /chat/sessions/{id}/messages — 追加消息
# ============================================================================

@router.post("/chat/sessions/{session_id}/messages", response_model=ChatMessageOut, status_code=201)
async def append_message(
    session_id: str,
    body: ChatMessageCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """追加单条消息（幂等键 client_msg_id 防重复写）"""
    msg = await svc.append_message(
        db, current_user.id, session_id,
        role=body.role,
        content=body.content,
        rich_blocks=body.rich_blocks,
        tool_trace=body.tool_trace,
        message_metadata=body.message_metadata,
        is_partial=body.is_partial,
        client_msg_id=body.client_msg_id,
    )
    return _message_to_out(msg)


# ============================================================================
# 8. GET /chat/sessions/{id}/export — 导出
# ============================================================================

@router.get("/chat/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("md", pattern="^(md|json)$"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出会话为 Markdown 或 JSON 文件下载"""
    content = await svc.export_session(db, current_user.id, session_id, format=format)
    # 触发浏览器下载
    if format == "json":
        media_type = "application/json; charset=utf-8"
        suffix = "json"
    else:
        media_type = "text/markdown; charset=utf-8"
        suffix = "md"
    headers = {
        "Content-Disposition": f'attachment; filename="chat_{session_id[:20]}_{datetime.now().strftime("%Y%m%d")}.{suffix}"',
    }
    return Response(content=content, media_type=media_type, headers=headers)


# ============================================================================
# 9. POST /chat/sessions/{id}/share — 创建分享
# ============================================================================

@router.post("/chat/sessions/{session_id}/share", response_model=ChatShareOut, status_code=201)
async def create_share(
    session_id: str,
    body: ChatShareCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建分享链接（短 token，可设过期时间）"""
    share = await svc.create_share(
        db, current_user.id, session_id,
        permission=body.permission,
        expires_hours=body.expires_hours,
    )
    return _share_to_out(share)


@router.get("/chat/sessions/{session_id}/shares", response_model=list[ChatShareOut])
async def list_shares(
    session_id: str,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出会话的所有分享链接"""
    shares = await svc.list_shares(db, current_user.id, session_id)
    return [_share_to_out(s) for s in shares]


@router.delete("/chat/sessions/{session_id}/shares/{share_id}")
async def revoke_share(
    session_id: str,
    share_id: str,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """撤销分享链接"""
    ok = await svc.revoke_share(db, current_user.id, session_id, share_id)
    if not ok:
        raise NotFoundException("分享链接不存在")
    return {"ok": True, "share_id": share_id}


# ============================================================================
# 10. POST /chat/sync — 旧 localStorage 数据迁移
# ============================================================================

@router.post("/chat/sync", response_model=ChatSyncResponse)
async def sync_from_local(
    body: ChatSyncRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """首次登录自动迁移：localStorage → server

    幂等性：client_msg_id 唯一约束保证不重复
    """
    # 序列化消息（Pydantic → dict）
    local_dicts = []
    for ls in body.local_sessions:
        local_dicts.append({
            "id": ls.id,
            "title": ls.title,
            "preview": ls.preview or "",
            "is_pinned": ls.is_pinned or False,
            "is_archived": ls.is_archived or False,
            "tags": ls.tags or [],
            "created_at": ls.created_at,
            "updated_at": ls.updated_at,
            "last_message_at": ls.last_message_at,
            "messages": [
                {
                    "client_msg_id": m.client_msg_id or m.client_msg_id_dedup,
                    "role": m.role,
                    "content": m.content,
                    "rich_blocks": m.rich_blocks or [],
                    "tool_trace": m.tool_trace or {},
                    "message_metadata": m.message_metadata,
                    "created_at": m.created_at,
                }
                for m in ls.messages
            ],
        })

    result = await svc.sync_from_local(
        db, current_user.id, local_dicts, last_synced_at=body.last_synced_at,
    )
    return ChatSyncResponse(**result)


# ============================================================================
# 12. GET /chat/shares/{token} — 公开访问（无 JWT）
# ============================================================================

@router.get("/chat/shares/{token}", response_model=ChatSharePublicOut)
async def get_share_public(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """公开访问分享（按 token 取只读会话）

    注意：无 Depends(get_current_user)，任何人凭 token 访问
    """
    result = await svc.get_share_public(db, token)
    if result is None:
        raise NotFoundException("分享链接不存在或已过期")
    session, share = result
    return ChatSharePublicOut(
        id=session.id,
        title=session.title,
        preview=session.preview,
        created_at=session.created_at,
        messages=[_message_to_out(m) for m in session.messages if not m.is_deleted],
    )
