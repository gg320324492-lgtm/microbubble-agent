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
