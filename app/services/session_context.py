"""会话上下文公共函数 (W98 P2-F 抽公共, 微信 + Web 统一调用)

设计 (2026-09-12 起 PG 单一事实源):
- 复用 chat_history_service.list_messages (只读, 不改)
- 登录会话每轮从 PG 全量回填最近 N 条 (12 轮 = 24 条) 并镜像进 Redis
  (旧 last_pg_id 增量分支结构性丢轮, 见 ensure_session_context 注释)
- best-effort: 任何 PG/Redis 异常 → 返回现有 Redis 消息, 绝不阻塞 chat
- user_id 为 None (匿名 webchat) → 不加载 DB 历史, 越权铁律, 走纯 Redis

对外函数:
    ensure_session_context(db, user_id, session_id) -> List[Dict]
        返回 [{"role": "user"/"assistant", "content": str}, ...]

    set_last_pg_id(session_id, message_id) -> None
        保留: micro_bubble_agent 导入 + last_turn meta 语义兼容, 不再参与回填
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
            entry: Dict = {"role": m.role, "content": content}
            # 2026-09-10 指代锚定升级: 透传 tool_trace 给下游实体提取
            # (tool_use.input 里的 assignee_name/title_keyword 是模型自己解析过的
            # 权威实体, 比正则抠回答文本可靠)
            tt = getattr(m, "tool_trace", None)
            if tt:
                entry["tool_trace"] = tt
            out.append(entry)
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
        # 2026-09-12 P0 根治: 登录会话一律以 PG 为单一事实源全量回填最近窗口。
        # 旧 "Redis 非空 → last_pg_id 增量" 分支有结构性丢轮 bug: chat_stream 只把
        # 消息落 PG + 推进 last_pg_id, 从不写回 Redis — 上一轮 ensure 之后才持久化的
        # 那一对 exchange (user + assistant) 既不在 Redis 里, 又被新游标跳过,
        # 永久丢失。实测 session vtql §7 "他手上" 锚到陈天祥、§9 失忆答
        # "找到 95 个相关任务", 全部由此 (模型看到的 history 少了最近一轮)。
        # PG 表有 (session_id, id) 索引, 每轮多一次 24 行窗口查询成本可忽略。
        pg_msgs = await _fetch_pg_messages(
            db, user_id, session_id,
            after_id=0,
            limit=SESSION_CONTEXT_MAX_MSGS,
        )
        if pg_msgs:
            if pg_msgs != redis_msgs:
                await session_manager.save_messages(session_id, pg_msgs)
            return pg_msgs
        return redis_msgs
    except Exception as e:
        logger.warning(f"ensure_session_context failed (best-effort 现有 Redis 消息): {e}")
        return redis_msgs