"""会话上下文公共函数 (W98 P2-F 抽公共, 微信 + Web 统一调用)

设计:
- 复用 chat_history_service.list_messages (只读, 不改)
- Redis 空 → PG 全量回填最近 N 条 (12 轮 = 24 条)
- Redis 非空 → last_pg_id 增量回填 (session_meta 存 Redis hash)
- best-effort: 任何 PG/Redis 异常 → 返回现有 Redis 消息, 绝不阻塞 chat
- user_id 为 None (匿名 webchat) → 不加载 DB 历史, 越权铁律

对外函数:
    ensure_session_context(db, user_id, session_id) -> List[Dict]
        返回 [{"role": "user"/"assistant", "content": str}, ...]

    set_last_pg_id(session_id, message_id) -> None
        写 Redis meta hash 的 last_pg_id (best-effort)
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.agent.session_manager import session_manager

logger = logging.getLogger("microbubble.session_context")

# 回填窗口: 取最近 12 轮 (24 条) 进 LLM messages
SESSION_CONTEXT_MAX_TURNS = 12
SESSION_CONTEXT_MAX_MSGS = SESSION_CONTEXT_MAX_TURNS * 2
# Redis meta hash 字段
META_LAST_PG_ID_FIELD = "last_pg_id"


async def _fetch_pg_messages(
    db,
    user_id: int,
    session_id: str,
    *,
    after_id: int = 0,
    limit: int = SESSION_CONTEXT_MAX_MSGS,
) -> Optional[List[Dict]]:
    """从 PG 拉取会话消息 (复用 chat_history_service.list_messages)"""
    try:
        from app.services import chat_history_service as chat_svc
        msgs, _has_more = await chat_svc.list_messages(
            db, user_id, session_id,
            page_size=limit,
            after_id=after_id,
        )
        out: List[Dict] = []
        for m in msgs:
            if m.role not in ("user", "assistant"):
                continue
            if getattr(m, "is_partial", False) or getattr(m, "is_deleted", False):
                continue
            content = m.content or ""
            out.append({"role": m.role, "content": content})
        return out or None
    except Exception as e:
        logger.warning(
            f"_fetch_pg_messages failed (best-effort None): {e}", exc_info=True
        )
        return None


async def _get_last_pg_id(session_id: str) -> Optional[int]:
    """从 Redis meta hash 读 last_pg_id"""
    try:
        meta = await session_manager.get_meta(session_id)
        val = meta.get(META_LAST_PG_ID_FIELD)
        return int(val) if val is not None else None
    except Exception as e:
        logger.warning(f"_get_last_pg_id failed (best-effort None): {e}")
        return None


async def set_last_pg_id(session_id: str, message_id: int) -> None:
    """写 Redis meta hash 的 last_pg_id (best-effort, 失败只告警不抛)"""
    if not message_id:
        return
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        await r.hset(session_manager._meta_key(session_id), META_LAST_PG_ID_FIELD, message_id)
        await r.expire(session_manager._meta_key(session_id), session_manager.ttl)
    except Exception as e:
        logger.warning(f"set_last_pg_id failed (best-effort): {e}")


async def ensure_session_context(
    db,
    user_id: Optional[int],
    session_id: str,
) -> List[Dict]:
    """确保会话上下文完整 (PG 回填 Redis)

    - Redis 空 → PG 全量回填最近 N 条
    - Redis 非空 → last_pg_id 增量回填 (只补 PG 新增消息, 追加到 Redis 尾部)
    - user_id 为 None (匿名 webchat 等) → 不加载 DB 历史 (越权铁律: list_messages
      必须先验证 session 归属) → 直接返回现有 Redis 消息
    - 任何 PG/Redis 异常 → best-effort 返回现有 Redis 消息, 绝不阻塞 chat
    """
    try:
        redis_msgs = await session_manager.get_messages(session_id)
    except Exception as e:
        logger.warning(f"ensure_session_context: Redis 读取失败 (best-effort 空): {e}")
        redis_msgs = []

    if not user_id or not db:
        return redis_msgs

    try:
        if redis_msgs:
            last_pg_id = await _get_last_pg_id(session_id)
            if last_pg_id:
                new_msgs = await _fetch_pg_messages(
                    db, user_id, session_id,
                    after_id=last_pg_id,
                    limit=SESSION_CONTEXT_MAX_MSGS,
                )
                if new_msgs:
                    redis_msgs = redis_msgs + new_msgs
                    await session_manager.save_messages(session_id, redis_msgs)
            return redis_msgs

        pg_msgs = await _fetch_pg_messages(
            db, user_id, session_id,
            after_id=0,
            limit=SESSION_CONTEXT_MAX_MSGS,
        )
        if pg_msgs:
            await session_manager.save_messages(session_id, pg_msgs)
            return pg_msgs
        return redis_msgs
    except Exception as e:
        logger.warning(f"ensure_session_context failed (best-effort 现有 Redis 消息): {e}")
        return redis_msgs