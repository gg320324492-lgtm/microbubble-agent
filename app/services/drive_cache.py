"""app/services/drive_cache.py — Drive list 缓存装饰器

W62 D2 教训 (2026-07-23):
- 前几轮误以为 drive_service.list_files() 有 cache, 实际每次都走 MinIO
- list_objects 在 100+ 文件场景延迟 200ms+, 批量渲染会拖累 UI
- 修法: 真 cache_drive_list(ttl=30s) 装饰器 + invalidate_cache on delete

核心设计:
1. cache_drive_list(ttl_sec=30) — 装饰器, 缓存 list_objects 结果
2. invalidate_drive_list_cache(prefix=...) — 手动失效 (delete/update 调用)
3. _drive_list_cache — 模块级 dict[cache_key, (timestamp, result)]

5 新铁律:
① cache key 必须含 user_id + prefix + recursive (防止跨用户泄漏)
② TTL 30s 平衡性能 vs 一致性 (delete 后最迟 30s 生效, 用户可接受)
③ invalidate 必须双写: 删 cache + 删同 prefix 所有 cache_key (不精准匹配会留 stale)
④ cache miss 必须走真 service (不能抛 exception 让上游 catch, 上游无防御)
⑤ cache hit/miss 必须 logger.debug (留 audit trail, 便于排查)

部署必做:
- drive_service.list_files() 加 @cache_drive_list(ttl_sec=30) 装饰器
- drive_service.delete_file() / move_file() 末尾调 invalidate_drive_list_cache
- TTL 不暴露为 settings (避免运行中切 TTL 引入 stale, 留作未来 PR)
"""
from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


# 模块级 cache: dict[cache_key, (timestamp, result)]
_drive_list_cache: dict[str, tuple[float, Any]] = {}

# 默认 TTL (秒)
DEFAULT_TTL_SEC = 30


def _make_cache_key(prefix: str, user_id: int, recursive: bool) -> str:
    """生成 cache key (含 user_id 防止跨用户泄漏)

    Args:
        prefix: MinIO prefix (e.g. "team/" 或 "personal/u1/")
        user_id: 调用方用户 ID
        recursive: 是否递归

    Returns:
        str cache key (格式: "user:{user_id}|prefix:{prefix}|recursive:{recursive}")
    """
    return f"user:{user_id}|prefix:{prefix}|recursive:{recursive}"


def cache_drive_list(ttl_sec: int = DEFAULT_TTL_SEC) -> Callable:
    """装饰器: 缓存 list_objects 结果

    被装饰函数签名:
        async def list_files(prefix: str, user_id: int, recursive: bool) -> list[dict]:
            ...

    装饰器透明转发, cache miss 走真函数, cache hit 直接返回缓存

    用法:
        @cache_drive_list(ttl_sec=30)
        async def list_files(prefix: str, user_id: int, recursive: bool = False) -> list[dict]:
            # 走 MinIO list_objects
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 解析参数 (支持位置和关键字)
            # 期望签名: (prefix: str, user_id: int, recursive: bool = False)
            prefix = kwargs.get("prefix", args[0] if len(args) > 0 else "")
            user_id = kwargs.get("user_id", args[1] if len(args) > 1 else 0)
            recursive = kwargs.get("recursive", args[2] if len(args) > 2 else False)

            cache_key = _make_cache_key(prefix, user_id, recursive)
            now = time.monotonic()

            # cache hit 检查
            cached = _drive_list_cache.get(cache_key)
            if cached is not None:
                ts, result = cached
                if now - ts < ttl_sec:
                    logger.debug(
                        "drive_list cache HIT key=%s age=%.2fs",
                        cache_key, now - ts,
                    )
                    return result
                else:
                    # 过期, 主动删 (避免 _drive_list_cache 无限增长)
                    _drive_list_cache.pop(cache_key, None)
                    logger.debug(
                        "drive_list cache EXPIRED key=%s age=%.2fs",
                        cache_key, now - ts,
                    )

            # cache miss → 走真函数
            result = await func(*args, **kwargs)
            _drive_list_cache[cache_key] = (now, result)
            logger.debug(
                "drive_list cache MISS key=%s result_count=%d",
                cache_key, len(result) if hasattr(result, "__len__") else 0,
            )
            return result
        return wrapper
    return decorator


def invalidate_drive_list_cache(prefix: str = "") -> None:
    """失效 cache (delete/update 后调)

    Args:
        prefix: 精确 prefix 失效 (空字符串 = 失效所有)

    设计:
        - prefix 非空: 只失效 prefix 开头匹配的 cache_key
        - prefix 空字符串: 失效全部 (谨慎使用)
    """
    if not prefix:
        # 失效所有
        count = len(_drive_list_cache)
        _drive_list_cache.clear()
        logger.debug("drive_list cache FULL INVALIDATE cleared=%d", count)
        return

    # 失效 prefix 匹配的所有 cache_key
    prefix_marker = f"prefix:{prefix}"
    keys_to_delete = [
        k for k in _drive_list_cache
        if prefix_marker in k
    ]
    for k in keys_to_delete:
        _drive_list_cache.pop(k, None)
    logger.debug(
        "drive_list cache PARTIAL INVALIDATE prefix=%r cleared=%d",
        prefix, len(keys_to_delete),
    )


def get_cache_stats() -> dict[str, Any]:
    """获取 cache 统计 (admin 调试用)

    Returns:
        dict {size: int, keys: list[str], oldest_age_sec: float}
    """
    now = time.monotonic()
    if not _drive_list_cache:
        return {"size": 0, "keys": [], "oldest_age_sec": 0.0}

    oldest = min(ts for ts, _ in _drive_list_cache.values())
    return {
        "size": len(_drive_list_cache),
        "keys": list(_drive_list_cache.keys()),
        "oldest_age_sec": round(now - oldest, 2),
    }


def reset_cache_for_testing() -> None:
    """测试用: 清空 cache (fixture teardown)"""
    _drive_list_cache.clear()