"""进程内 FakeRedis，足够支撑 progress_service 等测试（无需真 Redis）

支持能力：
- 字符串：get / set (ex, nx) / delete
- Hash：hset(mapping=...) / hgetall / delete
- Key：expire（仅记录，无实际过期）
- Pub/Sub：pubsub() 返回 FakePubSub，支持 subscribe / unsubscribe / get_message / aclose
- publish：把消息发到对应 channel 的订阅队列
"""
import asyncio
import json
from collections import defaultdict, deque


class FakePubSub:
    """进程内 fake PubSub，行为对齐 redis-py 的 aioredis PubSub"""
    def __init__(self, redis: "FakeRedis"):
        self._redis = redis
        self._subscribed: set[str] = set()
        self._pending: dict[str, deque] = defaultdict(deque)
        self._closed = False

    async def subscribe(self, *channels):
        for ch in channels:
            self._subscribed.add(ch)
            self._redis._pubsub_subscribe(ch, self._pending[ch])

    async def unsubscribe(self, *channels):
        for ch in channels:
            self._subscribed.discard(ch)
            self._redis._pubsub_unsubscribe(ch, self._pending.pop(ch, None))

    async def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 0.0):
        if not self._subscribed:
            return None
        # 轮询所有订阅 channel
        for ch in list(self._subscribed):
            queue = self._pending.get(ch)
            if not queue:
                continue
            if queue:
                return queue.popleft()
        if timeout > 0:
            try:
                await asyncio.wait_for(self._wait_for_message(), timeout=timeout)
            except asyncio.TimeoutError:
                return None
            for ch in list(self._subscribed):
                queue = self._pending.get(ch)
                if queue:
                    return queue.popleft()
        return None

    async def _wait_for_message(self):
        # 简单 sleep 让 publish 有机会把消息塞进队列
        while True:
            for ch in list(self._subscribed):
                if self._pending.get(ch):
                    return
            await asyncio.sleep(0.01)

    async def aclose(self):
        self._closed = True
        for ch in list(self._subscribed):
            self._redis._pubsub_unsubscribe(ch, self._pending.pop(ch, None))
        self._subscribed.clear()


class FakeRedis:
    """进程内 fake Redis，足够支撑 progress_service / cache_hit / concurrent_lock 测试"""
    def __init__(self):
        self.store: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self._pubsub_listeners: dict[str, list[deque]] = defaultdict(list)

    # --- string ops ---
    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ex=None, nx=False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    # --- hash ops ---
    async def hset(self, key: str, field=None, value=None, mapping=None):
        if key not in self.hashes:
            self.hashes[key] = {}
        if mapping:
            for k, v in mapping.items():
                # redis-py HSET 接受 str/int/float
                self.hashes[key][k] = v
            return len(mapping)
        if field is not None:
            self.hashes[key][field] = value
            return 1
        return 0

    async def hgetall(self, key: str):
        return dict(self.hashes.get(key, {}))

    # --- key ops ---
    async def expire(self, key: str, ttl: int):
        # FakeRedis 不实现实际过期，仅记录
        return 1

    async def delete(self, key: str):
        existed = 1 if (key in self.store or key in self.hashes) else 0
        self.store.pop(key, None)
        self.hashes.pop(key, None)
        return existed

    # --- pub/sub ops ---
    def pubsub(self):
        return FakePubSub(self)

    async def publish(self, channel: str, message):
        # message 可能是 str 或 bytes（redis-py 默认 decode_responses=True 时是 str）
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        payload = {"type": "message", "channel": channel, "data": message}
        for queue in list(self._pubsub_listeners.get(channel, [])):
            queue.append(payload)
        return len(self._pubsub_listeners.get(channel, []))

    def _pubsub_subscribe(self, channel: str, queue: deque):
        self._pubsub_listeners[channel].append(queue)

    def _pubsub_unsubscribe(self, channel: str, queue: deque):
        if queue in self._pubsub_listeners.get(channel, []):
            self._pubsub_listeners[channel].remove(queue)
