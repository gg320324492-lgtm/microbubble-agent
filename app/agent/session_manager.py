"""会话管理 — Redis List + WS dirty flag

设计：
- session:{sid}:msgs  List 消息（RPUSH 追加 O(1)）
- session:{sid}:meta  Hash 元信息（user_id / created_at / last_active）
- session:{sid}:dirty String WS 断连标志（TTL 1h）

改进点（vs 旧的 RedisSessionStore）：
- `append_message` 真正的 O(1)（RPUSH 不需要先 GET 全部）
- 独立的 meta 字段
- dirty flag 替代 clear_session
- 兼容旧接口名
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from app.core.redis import get_redis
from app.config import settings

logger = logging.getLogger("microbubble.agent.session")


class SessionManager:
    """Redis-backed session 管理"""

    PREFIX = "agent_session"

    def __init__(self, ttl: Optional[int] = None):
        self.ttl = ttl if ttl is not None else settings.SESSION_TTL

    def _msgs_key(self, sid: str) -> str:
        return f"{self.PREFIX}:{sid}:msgs"

    def _meta_key(self, sid: str) -> str:
        return f"{self.PREFIX}:{sid}:meta"

    def _dirty_key(self, sid: str) -> str:
        return f"{self.PREFIX}:{sid}:dirty"

    # ---- 消息 CRUD ----

    async def get_messages(self, sid: str) -> List[Dict[str, Any]]:
        """获取所有消息"""
        r = await get_redis()
        raw = await r.lrange(self._msgs_key(sid), 0, -1)
        if not raw:
            return []
        result = []
        for msg_json in raw:
            try:
                result.append(json.loads(msg_json))
            except json.JSONDecodeError:
                logger.warning(f"session {sid} 消息反序列化失败")
        return result

    async def save_messages(self, sid: str, messages: List[Dict[str, Any]]):
        """整体覆盖（用于 chat() 一次性保存整个 session）"""
        r = await get_redis()
        msgs_key = self._msgs_key(sid)
        # 原子：DEL + RPUSH 多个 + EXPIRE
        pipe = r.pipeline()
        pipe.delete(msgs_key)
        if messages:
            pipe.rpush(msgs_key, *[
                json.dumps(m, ensure_ascii=False, default=str) for m in messages
            ])
        pipe.expire(msgs_key, self.ttl)
        await pipe.execute()

    async def append_message(self, sid: str, message: Dict[str, Any]) -> int:
        """追加单条消息，返回新消息的 index（O(1) RPUSH）"""
        r = await get_redis()
        msgs_key = self._msgs_key(sid)
        new_len = await r.rpush(
            msgs_key, json.dumps(message, ensure_ascii=False, default=str)
        )
        await r.expire(msgs_key, self.ttl)
        return new_len - 1  # index 从 0 开始

    async def delete(self, sid: str):
        """删除整个 session"""
        r = await get_redis()
        await r.delete(
            self._msgs_key(sid),
            self._meta_key(sid),
            self._dirty_key(sid),
        )

    # ---- 元信息 ----

    async def update_meta(self, sid: str, user_id: Optional[int] = None):
        """更新 session 元信息"""
        r = await get_redis()
        now = int(time.time())
        meta_key = self._meta_key(sid)
        updates = {"last_active": now}
        if user_id is not None:
            updates["user_id"] = user_id
        await r.hset(meta_key, mapping=updates)
        # created_at 仅首次设置
        if not await r.hexists(meta_key, "created_at"):
            await r.hset(meta_key, "created_at", now)
        await r.expire(meta_key, self.ttl)

    async def get_meta(self, sid: str) -> Dict[str, Any]:
        """获取 session 元信息"""
        r = await get_redis()
        raw = await r.hgetall(self._meta_key(sid))
        if not raw:
            return {}
        result = {}
        for k, v in raw.items():
            if k in ("user_id", "created_at", "last_active"):
                try:
                    result[k] = int(v)
                except (ValueError, TypeError):
                    result[k] = v
            else:
                result[k] = v
        return result

    # ---- Dirty flag（WS 断连标志，替代 clear_session） ----

    async def mark_dirty(self, sid: str, reason: str = "ws_disconnect"):
        """标记 session 为 dirty（WS 断连等异常中断）"""
        r = await get_redis()
        await r.set(self._dirty_key(sid), reason, ex=3600)

    async def is_dirty(self, sid: str) -> Optional[str]:
        """检查是否 dirty，返回 dirty 原因；无 dirty 返回 None"""
        r = await get_redis()
        return await r.get(self._dirty_key(sid))

    async def clear_dirty(self, sid: str):
        """清除 dirty 标志（用户重新对话时调用）"""
        r = await get_redis()
        await r.delete(self._dirty_key(sid))


# 全局单例
session_manager = SessionManager()


# 兼容旧接口
class RedisSessionStoreCompat:
    """兼容旧的 RedisSessionStore API（get_messages/save_messages/delete/append_message）

    旧代码（app/api/v1/chat.py）用了 session_store 这个名字。
    新代码统一用 session_manager。
    """

    def __init__(self, manager: Optional[SessionManager] = None):
        self.mgr = manager or session_manager

    async def get_messages(self, sid: str) -> List[Dict[str, Any]]:
        return await self.mgr.get_messages(sid)

    async def save_messages(self, sid: str, messages: List[Dict[str, Any]]):
        await self.mgr.save_messages(sid, messages)

    async def delete(self, sid: str):
        await self.mgr.delete(sid)

    async def append_message(self, sid: str, message: Dict[str, Any]):
        await self.mgr.append_message(sid, message)
