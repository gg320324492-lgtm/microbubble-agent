import json
import asyncio
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
from app.config import settings

# Lazy-init pool: 模块导入时不创建 ConnectionPool,
# 而是首次 get_redis() 时按当前 event loop 创建。
# 这样多个 test loop (pytest-asyncio loop_scope=function) 各自拿到独立 pool,
# 避免 "Future attached to a different loop" / "Event loop is closed"。
_redis_pool: Optional[redis.ConnectionPool] = None
_redis_pool_loop: Optional[asyncio.AbstractEventLoop] = None
_pool_lock = asyncio.Lock()


def _build_pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )


def _get_pool() -> redis.ConnectionPool:
    """按当前 event loop 创建或重建 pool(loop 不匹配时重建)。

    pytest-asyncio loop_scope=function 每个 test 一个新 loop,
    pool 必须重新创建才能绑到新 loop 的 event source 上。
    """
    global _redis_pool, _redis_pool_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _redis_pool is None or _redis_pool_loop is not current_loop:
        _redis_pool = _build_pool()
        _redis_pool_loop = current_loop
    return _redis_pool


async def get_redis() -> redis.Redis:
    """获取Redis连接(loop-aware lazy pool)"""
    return redis.Redis(connection_pool=_get_pool())


async def close_redis():
    """关闭Redis连接"""
    global _redis_pool, _redis_pool_loop
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
        _redis_pool_loop = None


class RedisSessionStore:
    """基于 Redis 的会话存储，替代内存 dict"""

    def __init__(self, prefix: str = "session", ttl: int = None):
        self.prefix = prefix
        self.ttl = ttl if ttl is not None else settings.SESSION_TTL

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}:{session_id}"

    async def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        r = await get_redis()
        data = await r.get(self._key(session_id))
        if not data:
            return []
        return json.loads(data)

    async def save_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        r = await get_redis()
        await r.set(
            self._key(session_id),
            json.dumps(messages, ensure_ascii=False, default=str),
            ex=self.ttl
        )

    async def delete(self, session_id: str):
        r = await get_redis()
        await r.delete(self._key(session_id))

    async def append_message(self, session_id: str, message: Dict[str, Any]):
        """追加单条消息到会话"""
        r = await get_redis()
        messages = await self.get_messages(session_id)
        messages.append(message)
        await r.set(
            self._key(session_id),
            json.dumps(messages, ensure_ascii=False, default=str),
            ex=self.ttl
        )


session_store = RedisSessionStore()


async def invalidate_verified_cache_for_member(member_id: int) -> None:
    """清除指向该 member_id 的所有 wechat:verified:* 缓存"""
    r = await get_redis()
    cursor = 0
    while True:
        cursor, keys = await r.scan(cursor=cursor, match="wechat:verified:*", count=100)
        for key in keys:
            val = await r.get(key)
            if val and int(val) == member_id:
                await r.delete(key)
        if cursor == 0:
            break