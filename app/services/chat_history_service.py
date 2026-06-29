"""#043 账号持久化聊天历史 — service 层

设计要点：
- 所有 query 必须过滤 user_id（防越权铁律）
- 异步 session 模式（AsyncSession + async/await）
- 软删除 / 硬删除支持
- 分享链接独立权限（public endpoint 不需 JWT）
- 跨会话搜索用 PostgreSQL ILIKE（MVP 阶段，避免 tsvector 物化视图过度设计）
- 旧数据迁移：dedup by client_msg_id（幂等键）+ last_synced_at 增量

注意：
- relationships 默认 lazy="selectin"（避免 async 懒加载触发 MissingGreenlet，CLAUDE.md 2026-06-02 教训）
- 操作 ChatSession.message_count 时必须 +1（避免 COUNT(*) 全表扫描）
- 操作 last_message_at 必须刷新（侧栏排序字段）
- deleted_at 设值时同步 is_archived=False（软删除隐含从主列表移除）
"""

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, delete, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_history import (
    ChatSession, ChatMessage, ChatShare,
    ROLE_USER, ROLE_ASSISTANT, ROLE_SYSTEM, ROLE_TOOL,
    VALID_ROLES, SHARE_PERMISSION_READ, VALID_SHARE_PERMISSIONS,
)
from app.core.exceptions import NotFoundException, ValidationException, ForbiddenException

logger = logging.getLogger("microbubble.service.chat_history")


# ============================================================================
# 异常：跨用户访问防御
# ============================================================================

def _ensure_owned(session: ChatSession, user_id: int):
    """确保会话属于当前用户（防越权）"""
    if session.user_id != user_id:
        # 用 NotFoundException 而非 ForbiddenException 避免泄漏存在性
        raise NotFoundException("会话不存在或已删除")


# ============================================================================
# Session CRUD
# ============================================================================

async def list_sessions(
    db: AsyncSession,
    user_id: int,
    *,
    archived: bool = False,
    pinned_only: bool = False,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Tuple[List[ChatSession], int]:
    """列出会话（按 last_message_at 倒序）"""
    page = max(1, page)
    page_size = min(max(1, page_size), 200)

    conditions = [
        ChatSession.user_id == user_id,
        ChatSession.is_archived == archived,
        ChatSession.deleted_at.is_(None),
    ]
    if pinned_only:
        conditions.append(ChatSession.is_pinned.is_(True))
    if tag:
        # PostgreSQL ARRAY 包含：tags @> ARRAY[tag]
        conditions.append(ChatSession.tags.op("@>")([tag]))
    if search:
        # 标题 + preview 模糊匹配
        search_pattern = f"%{search}%"
        conditions.append(or_(
            ChatSession.title.ilike(search_pattern),
            ChatSession.preview.ilike(search_pattern),
        ))

    # 总数
    total_stmt = select(func.count(ChatSession.id)).where(and_(*conditions))
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    # 列表
    stmt = (
        select(ChatSession)
        .where(and_(*conditions))
        .order_by(
            desc(ChatSession.is_pinned),  # 收藏置顶
            desc(ChatSession.last_message_at),  # 最近活跃
            desc(ChatSession.created_at),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    sessions = list(result.scalars().all())
    return sessions, total


async def get_session(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    *,
    include_messages: bool = False,
    include_deleted: bool = False,
) -> Optional[ChatSession]:
    """获取单个会话（user_id 越权防护）"""
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    if not include_deleted:
        stmt = stmt.where(ChatSession.deleted_at.is_(None))
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        return None
    _ensure_owned(session, user_id)
    if include_messages and session:
        # 显式加载 messages（避免 N+1）
        await db.refresh(session, attribute_names=["messages"])
    return session


async def create_session(
    db: AsyncSession,
    user_id: int,
    *,
    title: Optional[str] = None,
    first_message: Optional[str] = None,
    client_session_id: Optional[str] = None,
) -> ChatSession:
    """创建会话（可选同时创建首条 user 消息）"""
    # session_id：优先用 client_session_id（localStorage 兼容），否则后端生成
    if client_session_id:
        # 检查是否已存在（幂等）
        existing = await get_session(db, user_id, client_session_id, include_deleted=True)
        if existing:
            return existing
        session_id = client_session_id
    else:
        # 生成 "user_<ts>_<8hex>" 格式
        import time
        ts = int(time.time())
        rand = secrets.token_hex(4)
        session_id = f"user_{ts}_{rand}"

    # 标题：第一条消息前 30 字（前端可能再调 PATCH 改）
    if not title and first_message:
        title = first_message[:30] + ("..." if len(first_message) > 30 else "")
    if not title:
        title = "新对话"

    session = ChatSession(
        id=session_id,
        user_id=user_id,
        title=title,
        preview=first_message[:200] if first_message else "",
    )
    db.add(session)
    await db.flush()  # 拿 session.id

    # 首条 user 消息
    if first_message:
        msg = ChatMessage(
            session_id=session_id,
            role=ROLE_USER,
            content=first_message,
        )
        db.add(msg)
        session.message_count = 1
        session.last_message_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)
    logger.info(f"创建会话: sid={session_id} user={user_id} msg_count={session.message_count}")
    return session


async def update_session(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    *,
    title: Optional[str] = None,
    is_pinned: Optional[bool] = None,
    is_archived: Optional[bool] = None,
    tags: Optional[List[str]] = None,
) -> Optional[ChatSession]:
    """更新会话元信息"""
    session = await get_session(db, user_id, session_id, include_deleted=True)
    if session is None:
        return None

    if title is not None:
        if len(title) > 200:
            raise ValidationException("title 不能超过 200 字符")
        session.title = title
    if is_pinned is not None:
        session.is_pinned = is_pinned
    if is_archived is not None:
        session.is_archived = is_archived
    if tags is not None:
        # 单标签 20 字符限制
        for t in tags:
            if len(t) > 20:
                raise ValidationException(f"标签 '{t}' 超过 20 字符")
        session.tags = tags

    await db.commit()
    await db.refresh(session)
    return session


async def delete_session(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    *,
    hard: bool = False,
) -> bool:
    """删除会话（默认软删除，30 天后 Celery 物理清除）"""
    session = await get_session(db, user_id, session_id, include_deleted=True)
    if session is None:
        return False

    if hard:
        # 物理删除（CASCADE 会自动删 messages + shares）
        await db.delete(session)
    else:
        session.deleted_at = datetime.utcnow()
        # 软删除同时归档（从主列表移除）
        session.is_archived = True

    await db.commit()
    logger.info(f"删除会话: sid={session_id} hard={hard} user={user_id}")
    return True


# ============================================================================
# Message CRUD
# ============================================================================

async def list_messages(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    *,
    page: int = 1,
    page_size: int = 100,
    after_id: int = 0,
    include_deleted: bool = False,
) -> Tuple[List[ChatMessage], bool]:
    """列出会话消息（按 created_at 正序 + 游标分页）"""
    # 越权防护：先验证 session 归属
    await get_session(db, user_id, session_id)

    page = max(1, page)
    page_size = min(max(1, page_size), 500)

    conditions = [ChatMessage.session_id == session_id]
    if after_id > 0:
        conditions.append(ChatMessage.id > after_id)
    if not include_deleted:
        conditions.append(ChatMessage.is_deleted.is_(False))

    # 多取 1 条判断 has_more
    stmt = (
        select(ChatMessage)
        .where(and_(*conditions))
        .order_by(asc(ChatMessage.id))
        .limit(page_size + 1)
    )
    if page > 1 and after_id == 0:
        # 简单 offset 分页
        stmt = stmt.offset((page - 1) * page_size)

    result = await db.execute(stmt)
    msgs = list(result.scalars().all())

    has_more = len(msgs) > page_size
    if has_more:
        msgs = msgs[:page_size]

    return msgs, has_more


async def append_message(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    *,
    role: str,
    content: str,
    rich_blocks: Optional[List[Dict[str, Any]]] = None,
    tool_trace: Optional[Dict[str, Any]] = None,
    message_metadata: Optional[Dict[str, Any]] = None,
    is_partial: bool = False,
    client_msg_id: Optional[str] = None,
) -> ChatMessage:
    """追加单条消息（自动维护 message_count + last_message_at）"""
    if role not in VALID_ROLES:
        raise ValidationException(f"role 必须是 {VALID_ROLES} 之一")
    if len(content) > 1_048_576:  # 1MB
        logger.warning(f"消息超过 1MB: len={len(content)} sid={session_id}")
    if not content:
        raise ValidationException("content 不能为空")

    # 越权防护 + 拿 session（更新计数）
    session = await get_session(db, user_id, session_id, include_deleted=True)
    if session is None:
        raise NotFoundException("会话不存在或已删除")
    if session.deleted_at is not None:
        raise ValidationException("已删除会话不能追加消息")

    # 幂等键：client_msg_id 已存在则不重复写
    if client_msg_id:
        existing_stmt = select(ChatMessage).where(
            and_(
                ChatMessage.session_id == session_id,
                ChatMessage.client_msg_id == client_msg_id,
            )
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing:
            logger.debug(f"幂等键命中，跳过重复写: client_msg_id={client_msg_id}")
            return existing

    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        rich_blocks=rich_blocks or [],
        tool_trace=tool_trace or {},
        message_metadata=message_metadata or {},
        is_partial=is_partial,
        client_msg_id=client_msg_id,
    )
    db.add(msg)
    # 维护冗余字段
    session.message_count = (session.message_count or 0) + 1
    session.last_message_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg


async def soft_delete_message(
    db: AsyncSession,
    user_id: int,
    message_id: int,
) -> bool:
    """单条消息软删除（前端"重新生成"用）"""
    stmt = select(ChatMessage).where(ChatMessage.id == message_id)
    msg = (await db.execute(stmt)).scalar_one_or_none()
    if msg is None:
        return False
    # 越权防护
    await get_session(db, user_id, msg.session_id)
    msg.is_deleted = True
    await db.commit()
    return True


# ============================================================================
# 分享
# ============================================================================

async def create_share(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    *,
    permission: str = SHARE_PERMISSION_READ,
    expires_hours: Optional[int] = None,
) -> ChatShare:
    """创建分享链接"""
    if permission not in VALID_SHARE_PERMISSIONS:
        raise ValidationException(f"permission 必须是 {VALID_SHARE_PERMISSIONS}")
    if expires_hours is not None and not (1 <= expires_hours <= 8760):
        raise ValidationException("expires_hours 范围 1-8760")

    # 越权防护
    await get_session(db, user_id, session_id)

    share_id = secrets.token_urlsafe(16)[:32]  # 32 字符短 token
    expires_at = None
    if expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)

    share = ChatShare(
        id=share_id,
        session_id=session_id,
        shared_by=user_id,
        permission=permission,
        expires_at=expires_at,
    )
    db.add(share)
    await db.commit()
    await db.refresh(share)
    return share


async def get_share_public(
    db: AsyncSession,
    token: str,
) -> Optional[Tuple[ChatSession, ChatShare]]:
    """公开访问（无 JWT），按 token 取分享 + 会话"""
    stmt = select(ChatShare).where(ChatShare.id == token)
    share = (await db.execute(stmt)).scalar_one_or_none()
    if share is None:
        return None
    # 过期检查
    if share.expires_at and share.expires_at < datetime.utcnow():
        return None
    # 取会话（含消息）
    session_stmt = select(ChatSession).where(ChatSession.id == share.session_id)
    session = (await db.execute(session_stmt)).scalar_one_or_none()
    if session is None or session.deleted_at is not None:
        return None
    # 加载消息
    await db.refresh(session, attribute_names=["messages"])
    # 增加 view_count
    share.view_count = (share.view_count or 0) + 1
    await db.commit()
    return session, share


async def list_shares(
    db: AsyncSession,
    user_id: int,
    session_id: str,
) -> List[ChatShare]:
    """列出会话的所有分享链接（仅创建者可见）"""
    await get_session(db, user_id, session_id)
    stmt = (
        select(ChatShare)
        .where(ChatShare.session_id == session_id)
        .order_by(desc(ChatShare.created_at))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_share(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    share_id: str,
) -> bool:
    """撤销分享链接"""
    await get_session(db, user_id, session_id)
    stmt = select(ChatShare).where(
        and_(
            ChatShare.id == share_id,
            ChatShare.session_id == session_id,
        )
    )
    share = (await db.execute(stmt)).scalar_one_or_none()
    if share is None:
        return False
    await db.delete(share)
    await db.commit()
    return True


# ============================================================================
# 搜索（跨会话）
# ============================================================================

async def search_sessions(
    db: AsyncSession,
    user_id: int,
    query: str,
    *,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """跨会话搜索（按消息内容 + 会话标题）"""
    if not query or len(query.strip()) < 2:
        return [], 0
    query = query.strip()
    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    search_pattern = f"%{query}%"

    # 搜索消息
    msg_stmt = (
        select(ChatMessage, ChatSession)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.deleted_at.is_(None),
                ChatMessage.is_deleted.is_(False),
                ChatMessage.content.ilike(search_pattern),
            )
        )
        .order_by(desc(ChatMessage.created_at))
        .limit(page_size * 2)  # 多取一些再做 session 分组
    )
    result = await db.execute(msg_stmt)
    rows = result.all()

    # 构造 snippet（query 前后各 50 字符）
    items = []
    seen_sessions = set()
    for msg, session in rows:
        if len(items) >= page_size:
            break
        content = msg.content
        idx = content.lower().find(query.lower())
        if idx >= 0:
            start = max(0, idx - 50)
            end = min(len(content), idx + len(query) + 50)
            snippet = ("..." if start > 0 else "") + content[start:end] + ("..." if end < len(content) else "")
        else:
            snippet = content[:120] + ("..." if len(content) > 120 else "")
        items.append({
            "session_id": session.id,
            "session_title": session.title,
            "message_id": msg.id,
            "role": msg.role,
            "snippet": snippet,
            "created_at": msg.created_at,
        })
        seen_sessions.add(session.id)

    # 总数（粗略估计）
    total_stmt = (
        select(func.count(ChatMessage.id))
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .where(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.deleted_at.is_(None),
                ChatMessage.is_deleted.is_(False),
                ChatMessage.content.ilike(search_pattern),
            )
        )
    )
    total = (await db.execute(total_stmt)).scalar() or 0

    return items, total


# ============================================================================
# 旧数据迁移（localStorage → server）
# ============================================================================

async def sync_from_local(
    db: AsyncSession,
    user_id: int,
    local_sessions: List[Dict[str, Any]],
    last_synced_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """接收 localStorage 数据，dedup 写入 server

    幂等：client_msg_id 唯一约束保证不重复
    冲突：last_synced_at 之后 server 已更新 → 标记 conflicts
    """
    server_sessions = []
    conflicts = []
    deleted_sids = []
    migrated = 0

    for local in local_sessions:
        sid = local["id"]
        title = local.get("title", "新对话")
        preview = local.get("preview", "")
        is_pinned = local.get("is_pinned", False)
        is_archived = local.get("is_archived", False)
        tags = local.get("tags", [])
        local_messages = local.get("messages", [])

        # 检查 server 是否已有
        stmt = select(ChatSession).where(
            and_(
                ChatSession.id == sid,
                ChatSession.user_id == user_id,
            )
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing is None:
            # 新建
            now = datetime.utcnow()
            session = ChatSession(
                id=sid,
                user_id=user_id,
                title=title[:200] if title else "新对话",
                preview=preview,
                is_pinned=is_pinned,
                is_archived=is_archived,
                tags=tags or [],
                message_count=0,
                last_message_at=None,
                created_at=local.get("created_at") or now,
                updated_at=local.get("updated_at") or now,
            )
            db.add(session)
            await db.flush()
            migrated += 1
        else:
            # 冲突检测（last_synced_at 之后两端都改）
            if last_synced_at and existing.updated_at and existing.updated_at > last_synced_at:
                conflicts.append({
                    "session_id": sid,
                    "reason": "server_updated_after_last_sync",
                    "server_updated_at": existing.updated_at.isoformat(),
                })
            # 增量更新元信息
            existing.title = title[:200] if title else existing.title
            if preview:
                existing.preview = preview
            existing.is_pinned = is_pinned
            existing.is_archived = is_archived
            if tags:
                existing.tags = tags

        # 写消息（幂等 by client_msg_id）
        for local_msg in local_messages:
            client_msg_id = local_msg.get("client_msg_id")
            if not client_msg_id:
                # 兼容老 localStorage 消息（无 client_msg_id）
                import hashlib
                content = local_msg.get("content", "")
                role = local_msg.get("role", "user")
                ts = local_msg.get("created_at", "")
                client_msg_id = hashlib.md5(f"{sid}:{role}:{ts}:{content[:50]}".encode()).hexdigest()[:32]

            # 检查是否已存在
            msg_existing_stmt = select(ChatMessage).where(
                and_(
                    ChatMessage.session_id == sid,
                    ChatMessage.client_msg_id == client_msg_id,
                )
            )
            msg_existing = (await db.execute(msg_existing_stmt)).scalar_one_or_none()
            if msg_existing:
                continue

            msg = ChatMessage(
                session_id=sid,
                role=local_msg.get("role", ROLE_USER),
                content=local_msg.get("content", ""),
                rich_blocks=local_msg.get("rich_blocks", []),
                tool_trace=local_msg.get("tool_trace", {}),
                message_metadata=local_msg.get("message_metadata") or local_msg.get("metadata", {}),
                client_msg_id=client_msg_id,
                created_at=local_msg.get("created_at") or datetime.utcnow(),
            )
            db.add(msg)
            migrated += 1

    await db.commit()

    # 返回最新 server 列表
    server_sessions_list, _ = await list_sessions(
        db, user_id, page=1, page_size=200,
    )
    server_sessions = [
        {
            "id": s.id,
            "title": s.title,
            "preview": s.preview,
            "is_pinned": s.is_pinned,
            "is_archived": s.is_archived,
            "tags": s.tags,
            "message_count": s.message_count,
            "last_message_at": s.last_message_at,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in server_sessions_list
    ]

    return {
        "ok": True,
        "server_sessions": server_sessions,
        "conflicts": conflicts,
        "deleted_sids": deleted_sids,
        "migrated_count": migrated,
    }


# ============================================================================
# 导出（Markdown / JSON）
# ============================================================================

async def export_session(
    db: AsyncSession,
    user_id: int,
    session_id: str,
    format: str = "md",
) -> str:
    """导出会话为 Markdown / JSON 字符串"""
    if format not in ("md", "json"):
        raise ValidationException("format 必须是 md 或 json")

    session = await get_session(db, user_id, session_id, include_messages=True)
    if session is None:
        raise NotFoundException("会话不存在")
    # 拿消息
    msgs, _ = await list_messages(db, user_id, session_id, page_size=1000)
    # 过滤掉软删除的
    msgs = [m for m in msgs if not m.is_deleted]

    if format == "json":
        import json
        return json.dumps(
            {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "tags": session.tags,
                "messages": [
                    {
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in msgs
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    # Markdown
    lines = [
        f"# {session.title}",
        "",
        f"**会话 ID**: `{session.id}`  ",
        f"**创建时间**: {session.created_at.isoformat() if session.created_at else 'N/A'}  ",
        f"**消息数**: {len(msgs)}  ",
        f"**标签**: {', '.join(session.tags) if session.tags else '无'}  ",
        "",
        "---",
        "",
    ]
    for m in msgs:
        role_emoji = {"user": "🙋", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}.get(m.role, "•")
        ts = m.created_at.isoformat() if m.created_at else ""
        lines.append(f"## {role_emoji} {m.role} {ts}")
        lines.append("")
        lines.append(m.content)
        lines.append("")

    return "\n".join(lines)


# ============================================================================
# Celery 清理任务
# ============================================================================

async def cleanup_soft_deleted_sessions(db: AsyncSession, cutoff_date: datetime) -> int:
    """物理清除 30 天前软删除的会话（CASCADE 自动清 messages + shares）"""
    stmt = delete(ChatSession).where(
        and_(
            ChatSession.deleted_at.isnot(None),
            ChatSession.deleted_at < cutoff_date,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
