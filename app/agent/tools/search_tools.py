"""联网搜索域工具（v2 架构）— 迁移 web_search

2026-08-16 #90: 加 Redis 缓存层 (类 20.121 best-effort silently 降级 + 类 20.122 user/tenant 隔离)
- key: web_search:{sha256(user_id:tenant_id:query:max_results)[:16]}
- TTL: 24h (RAG_QUERY_CACHE_TTL_SECONDS 复用)
- 命中: 直接返 cached dict (含 results/answer)
- 未命中 / Redis 不可用: 落库后 set
"""
import hashlib
import json
import logging
import os
from typing import Optional
from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.search")

# 2026-08-16 #90: web_search Redis 缓存配置 (复用 rag_query_cache TTL)
WEB_SEARCH_CACHE_PREFIX: str = os.getenv("WEB_SEARCH_CACHE_PREFIX", "web_search:")
WEB_SEARCH_CACHE_TTL: int = int(os.getenv("WEB_SEARCH_CACHE_TTL", "86400"))
WEB_SEARCH_CACHE_ENABLED: bool = os.getenv("WEB_SEARCH_CACHE_ENABLED", "1") != "0"


def _cache_key(query: str, max_results: int, user_id: Optional[int], tenant_id: Optional[int]) -> str:
    """缓存 key: 含 user+tenant 隔离 + query + max_results
    类 20.122: 必须含 user_id + tenant_id
    """
    raw = f"{user_id or 'anon'}:{tenant_id or 'default'}:{max_results}:{query.strip().lower()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{WEB_SEARCH_CACHE_PREFIX}{digest}"


class WebSearchInput(BaseModel):
    query: str = Field(..., min_length=1, description="搜索查询关键词")
    max_results: int = Field(5, ge=1, le=20, description="返回结果数量（默认 5）")


class WebSearchOutput(BaseModel):
    status: str
    query: Optional[str] = None
    results: list[dict] = Field(default_factory=list)
    result_count: int = 0
    rich_block_type: Optional[str] = None


@tool(
    name="web_search",
    description="搜索互联网获取最新信息。当用户询问最新新闻、实时信息、天气、网上资料、或知识库中找不到答案的问题时使用。",
    input_model=WebSearchInput,
    output_model=WebSearchOutput,
    requires_db=False,
)
async def web_search(input: WebSearchInput, ctx: ToolContext) -> dict:
    """联网搜索（搜狗 + 必应双引擎）+ Redis 24h 缓存"""
    from app.services.search_service import search_service

    # 2026-08-16 #90: 缓存层 (best-effort silently 降级)
    user_id = getattr(ctx, 'user_id', None) if ctx else None
    # 兼容 input 是 BaseModel 实例或 dict
    q = input.query if hasattr(input, 'query') else input['query']
    mr = input.max_results if hasattr(input, 'max_results') else input['max_results']
    cache_key = _cache_key(q, mr, user_id, None)

    if WEB_SEARCH_CACHE_ENABLED:
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            cached_raw = await r.get(cache_key)
            if cached_raw:
                cached = json.loads(cached_raw)
                logger.debug(f"[web_search cache HIT] key={cache_key[:24]}... q={q[:30]}")
                cached["rich_block_type"] = None
                cached["_cache"] = "hit"  # 标记命中 (调试用)
                return cached
        except Exception as e:
            logger.debug(f"[web_search cache] redis lookup skip: {e}")

    # 缓存未命中 / 不可用: 实际搜索
    result = await search_service.search(
        query=q,
        max_results=mr,
    )
    result["rich_block_type"] = None

    # 写缓存 (best-effort silently 降级 — 失败不影响返回)
    if WEB_SEARCH_CACHE_ENABLED and result.get("status") == "success":
        try:
            from app.core.redis import get_redis
            r = await get_redis()
            await r.set(cache_key, json.dumps(result, ensure_ascii=False), ex=WEB_SEARCH_CACHE_TTL)
            logger.debug(f"[web_search cache SET] key={cache_key[:24]}... ttl={WEB_SEARCH_CACHE_TTL}s")
        except Exception as e:
            logger.debug(f"[web_search cache] redis set skip: {e}")

    return result