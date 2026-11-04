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
# 2026-11-04 P0: 会话历史净化 (防模型原生工具标记自我强化污染)
# 放 app/core 层: 本模块被 core/redis.py 与 agent/session_manager.py 共用,
# 放 agent 下会让 core 反向依赖 agent (分层倒置)。
from app.core.message_sanitizer import is_polluted_message, sanitize_messages

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
        """获取所有消息（**读时净化**：丢弃含原生工具标记的历史消息）。

        2026-11-04 P0: 一旦某轮把"文本形态的工具调用"写进了历史，之后每轮都会
        把它当示范喂给模型 ⇒ 工具永不执行且自我强化。读时过滤让已污染的老会话
        自动恢复，不需要人工清 Redis。
        """
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
        kept, dropped = sanitize_messages(result)
        if dropped:
            logger.warning(
                f"[净化] session {sid} 读取时丢弃 {dropped} 条含原生工具标记的消息"
            )
        return kept

    async def save_messages(self, sid: str, messages: List[Dict[str, Any]]):
        """整体覆盖（用于 chat() 一次性保存整个 session）。

        **存前净化**：含原生工具标记的消息不落历史，堵住新增污染。
        """
        kept, dropped = sanitize_messages(messages)
        if dropped:
            logger.warning(
                f"[净化] session {sid} 写入前丢弃 {dropped} 条含原生工具标记的消息"
            )
        r = await get_redis()
        msgs_key = self._msgs_key(sid)
        # 原子：DEL + RPUSH 多个 + EXPIRE
        pipe = r.pipeline()
        pipe.delete(msgs_key)
        if kept:
            pipe.rpush(msgs_key, *[
                json.dumps(m, ensure_ascii=False, default=str) for m in kept
            ])
        pipe.expire(msgs_key, self.ttl)
        await pipe.execute()

    async def append_message(self, sid: str, message: Dict[str, Any]) -> int:
        """追加单条消息，返回新消息的 index（O(1) RPUSH）。

        含原生工具标记的消息直接跳过写入（返回当前长度-1，不污染历史）。
        """
        if is_polluted_message(message):
            logger.warning(
                f"[净化] session {sid} 跳过 1 条含原生工具标记的追加消息"
                f" (role={message.get('role') if isinstance(message, dict) else '?'})"
            )
            r = await get_redis()
            return max(0, await r.llen(self._msgs_key(sid)) - 1)
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

    async def get_session_meta(self, sid: str, field: str) -> Any:
        """读取一个 JSON 编码的 session meta 字段。

        业务态（如 ``last_turn``）与基础字段共用 ``agent_session:{sid}:meta``
        Redis Hash；不存在时返回 ``None``，非 JSON 的历史值保持原样返回。
        """
        r = await get_redis()
        raw = await r.hget(self._meta_key(sid), field)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set_session_meta(self, sid: str, field: str, value: Any) -> None:
        """JSON 编码并写入一个 session meta 字段，同时续期 session TTL。"""
        r = await get_redis()
        meta_key = self._meta_key(sid)
        payload = json.dumps(value, ensure_ascii=False, default=str)
        await r.hset(meta_key, field, payload)
        await r.expire(meta_key, self.ttl)

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
