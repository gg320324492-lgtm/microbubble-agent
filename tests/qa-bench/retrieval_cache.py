"""
qa-bench/retrieval_cache.py — LRU + TTL 缓存 (qa-bench v3.1 D3)

设计:
1. key: hash(query_text + filters + model_name + thinking_mode)
2. value: (sse_events, timestamp, score_metadata)
3. TTL: env RETRIEVAL_CACHE_TTL (默认 1 hour)
4. max_size: env RETRIEVAL_CACHE_MAX_SIZE (默认 1000)
5. Thread-safe (threading.RLock)
6. 可选持久化: save/load to .retrieval_cache.json (atomic write + reload)

背景 (2026-07-22 D3 plan):
- 200 题 smoke 第 2 次跑期望 ≥ 50% 命中 cache (同一 question 复用)
- cache key 必须含 query + thinking_mode (防 mode 切换混淆)
- 默认 disabled (env RETRIEVAL_CACHE_ENABLED=False), 不破坏现有行为
- 持久化 atomic: 写 .tmp → rename → 防半截 JSON 损坏
"""
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class RetrievalCache:
    """LRU + TTL 缓存 (thread-safe) for retrieval/SSE results

    用法:
        cache = RetrievalCache(ttl=3600, max_size=1000)
        key = cache.make_key("今天王天志忙什么?", thinking_mode="balanced")
        if not (cached := cache.get(key)):
            events = await run_api(...)
            cache.set(key, events)
    """

    def __init__(
        self,
        ttl: int = 3600,
        max_size: int = 1000,
        persistence_path: Optional[str] = None,
    ):
        """初始化 cache.

        Args:
            ttl: 过期秒数 (默认 3600 = 1 hour)
            max_size: 最大 entry 数 (LRU 驱逐超量)
            persistence_path: 持久化文件路径 (None = 不持久化)
        """
        self.ttl = ttl
        self.max_size = max_size
        self.persistence_path = persistence_path
        # data: {key: (value, expire_at_monotonic)}
        self._data: Dict[str, Tuple[Any, float]] = {}
        # LRU order: list of keys, oldest first (index 0)
        self._lru_order: List[str] = []
        self._lock = threading.RLock()
        # 统计
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "expirations": 0,
        }

    @staticmethod
    def make_key(
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        model_name: str = "default",
        thinking_mode: str = "balanced",
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成确定性 cache key.

        Args:
            query_text: 原始问题文本
            filters: 过滤条件 (e.g. {"category": "knowledge"})
            model_name: 模型名 (防模型升级混淆)
            thinking_mode: thinking 模式 (balanced/fast/deep)
            extra: 其他 key 维度

        Returns:
            64 字符 hex sha256 (确定性, 跨进程一致)
        """
        payload = {
            "query": query_text.strip(),
            "filters": filters or {},
            "model": model_name,
            "thinking_mode": thinking_mode,
            "extra": extra or {},
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """读 cache.

        Returns:
            value 或 None (miss/expired)
        """
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None
            value, expire_at = entry
            if time.monotonic() > expire_at:
                # 过期 → 删除 + 记 expiration
                del self._data[key]
                if key in self._lru_order:
                    self._lru_order.remove(key)
                self._stats["expirations"] += 1
                self._stats["misses"] += 1
                return None
            # hit → 移到 LRU 末尾 (most recent)
            if key in self._lru_order:
                self._lru_order.remove(key)
            self._lru_order.append(key)
            self._stats["hits"] += 1
            return value

    def set(self, key: str, value: Any) -> None:
        """写 cache. 超 max_size 触发 LRU 驱逐."""
        with self._lock:
            expire_at = time.monotonic() + self.ttl
            # 已存在 → 更新 + 移到末尾
            if key in self._data:
                self._data[key] = (value, expire_at)
                if key in self._lru_order:
                    self._lru_order.remove(key)
                self._lru_order.append(key)
                self._stats["sets"] += 1
                return
            # 新 key → 检查 size
            if len(self._data) >= self.max_size:
                # LRU 驱逐最旧
                while len(self._data) >= self.max_size and self._lru_order:
                    evict_key = self._lru_order.pop(0)
                    if evict_key in self._data:
                        del self._data[evict_key]
                        self._stats["evictions"] += 1
            self._data[key] = (value, expire_at)
            self._lru_order.append(key)
            self._stats["sets"] += 1

    def clear(self) -> None:
        """清空 cache (含统计)."""
        with self._lock:
            self._data.clear()
            self._lru_order.clear()
            self._stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "evictions": 0,
                "expirations": 0,
            }

    def stats(self) -> Dict[str, Any]:
        """返回 cache 统计."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total else 0.0
            return {
                **self._stats,
                "size": len(self._data),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "hit_rate_pct": round(hit_rate, 2),
            }

    def save(self, path: Optional[str] = None) -> bool:
        """持久化 cache 到 JSON 文件 (atomic write).

        Returns:
            True 成功, False 失败
        """
        target = path or self.persistence_path
        if not target:
            return False
        try:
            target_path = Path(target)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # 序列化 (不含 expire_at, 改用 created_at + ttl)
            now = time.time()
            serializable = {
                "version": 1,
                "saved_at": now,
                "ttl_seconds": self.ttl,
                "entries": [
                    {
                        "key": k,
                        "value": v,
                        # monotonic → real time offset
                        "expire_at": e - time.monotonic() + now,
                    }
                    for k, (v, e) in self._data.items()
                ],
            }
            # atomic write: tmp → rename
            tmp_fd, tmp_path = tempfile.mkstemp(
                dir=target_path.parent, prefix=".retrieval_cache.", suffix=".tmp"
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(serializable, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, target_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
            return True
        except Exception:
            return False

    def load(self, path: Optional[str] = None) -> bool:
        """从 JSON 文件加载 cache. 已存在的 entries 保留 (新文件覆盖).

        Returns:
            True 成功, False 失败
        """
        target = path or self.persistence_path
        if not target or not Path(target).exists():
            return False
        try:
            with open(target, encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("version") != 1:
                return False
            now = time.time()
            loaded_count = 0
            expired_count = 0
            with self._lock:
                for entry in payload.get("entries", []):
                    key = entry["key"]
                    value = entry["value"]
                    expire_at = entry["expire_at"]
                    if now >= expire_at:
                        expired_count += 1
                        continue
                    # 转换为 monotonic
                    mono_expire = expire_at - now + time.monotonic()
                    self._data[key] = (value, mono_expire)
                    if key not in self._lru_order:
                        self._lru_order.append(key)
                    loaded_count += 1
                    # size 限制
                    if len(self._data) >= self.max_size:
                        while (
                            len(self._data) >= self.max_size and self._lru_order
                        ):
                            evict_key = self._lru_order.pop(0)
                            if evict_key in self._data:
                                del self._data[evict_key]
            return True
        except Exception:
            return False


# 全局默认 instance (lazy init)
_default_cache: Optional[RetrievalCache] = None
_default_lock = threading.Lock()


def get_default_cache() -> RetrievalCache:
    """获取默认 cache instance (从 env 读 ttl/max_size)."""
    global _default_cache
    if _default_cache is None:
        with _default_lock:
            if _default_cache is None:
                ttl = int(os.environ.get("RETRIEVAL_CACHE_TTL", "3600"))
                max_size = int(os.environ.get("RETRIEVAL_CACHE_MAX_SIZE", "1000"))
                _default_cache = RetrievalCache(ttl=ttl, max_size=max_size)
    return _default_cache


def reset_default_cache() -> None:
    """重置全局默认 instance (主要用于测试)."""
    global _default_cache
    with _default_lock:
        _default_cache = None