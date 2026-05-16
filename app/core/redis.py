import json
from typing import List, Dict, Any
import redis.asyncio as redis
from app.config import settings

# 创建Redis连接池
redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True
)


async def get_redis() -> redis.Redis:
    """获取Redis连接"""
    return redis.Redis(connection_pool=redis_pool)


async def close_redis():
    """关闭Redis连接"""
    await redis_pool.disconnect()


class RedisSessionStore:
    """基于 Redis 的会话存储，替代内存 dict"""

    def __init__(self, prefix: str = "session", ttl: int = 86400):
        self.prefix = prefix
        self.ttl = ttl

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


session_store = RedisSessionStore()
