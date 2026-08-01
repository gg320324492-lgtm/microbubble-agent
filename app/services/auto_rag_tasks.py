"""Auto-RAG 异步后台检索任务 (W101 P2)

设计目标:
- 任务/会议/知识创建触发后, 后台异步检索背景知识
- Celery 任务: retrieve_and_cache_task
- Redis 24h TTL 缓存, key = auto_rag:{event_type}:{entity_id}
- 检索失败 best-effort, 不影响主流程
- importorskip 守护

W101 P2 commit:
- [W101 +4] AutoRAGService 异步后台检索 (Celery + Redis 24h TTL)
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.core.celery import celery_app
from app.config import settings
from app.services.auto_rag_service import (
    CACHE_KEY_PREFIX,
    _HAS_RETRIEVER,
)

logger = logging.getLogger("microbubble.auto_rag_tasks")


# ============================================================================
# 缓存 TTL (派工 v10 段 2.2: 24 小时)
# ============================================================================

CACHE_TTL_SECONDS = 24 * 3600  # 24h

# 检索 top_k
DEFAULT_TOP_K = 5


def _build_cache_key(event_type: str, entity_id: int) -> str:
    """构建 Redis 缓存 key"""
    return f"{CACHE_KEY_PREFIX}:{event_type}:{entity_id}"


async def _write_cache(cache_key: str, payload: Dict[str, Any]) -> bool:
    """写 Redis 缓存 (best-effort)"""
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        await redis.setex(
            cache_key,
            CACHE_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False, default=str),
        )
        return True
    except Exception as e:
        logger.warning(f"[W101 P2] redis cache write failed key={cache_key}: {e}")
        return False


async def _read_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """读 Redis 缓存 (best-effort)"""
    try:
        from app.core.redis import get_redis
        redis = await get_redis()
        raw = await redis.get(cache_key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"[W101 P2] redis cache read failed key={cache_key}: {e}")
        return None


async def _retrieve_chunks(query_hint: str, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
    """调 HybridRetriever 检索 (派工 v10 段 2.2)"""
    if not _HAS_RETRIEVER:
        return []
    try:
        from app.services.hybrid_retriever import get_hybrid_retriever
        from app.core.celery_db import create_celery_engine_and_session

        # Celery worker 端必须自建 session (不能复用 request-scoped db)
        engine, session_factory = create_celery_engine_and_session()
        async with session_factory() as db:
            retriever = get_hybrid_retriever(db)
            chunks = await retriever.retrieve(query_hint, top_k=top_k)
            return chunks or []
    except Exception as e:
        logger.warning(f"[W101 P2] hybrid retrieve failed query={query_hint[:50]}: {e}")
        return []


@celery_app.task(
    name="app.services.auto_rag_tasks.retrieve_and_cache_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
)
def retrieve_and_cache_task(
    self,
    event_type: str,
    entity_id: int,
    query_hint: str,
    priority: int = 5,
) -> Dict[str, Any]:
    """Auto-RAG 后台检索 + 缓存任务 (派工 v10 段 2.2)

    Args:
        event_type: 触发事件类型 (task.create / meeting.create / knowledge.upload)
        entity_id: 实体 ID (task.id / meeting.id / knowledge.id)
        query_hint: 检索 query (从 payload 提取的标题+描述)
        priority: 优先级 (knowledge.upload=10, meeting.create=8, task.create=6, task.update=4)

    Returns:
        dict: {event_type, entity_id, hits, cached, cache_key}
    """
    import asyncio

    async def _run():
        cache_key = _build_cache_key(event_type, entity_id)

        # 已有缓存 → 跳过检索
        existing = await _read_cache(cache_key)
        if existing is not None:
            logger.info(f"[W101 P2] cache hit skip retrieve: key={cache_key}")
            return {
                "event_type": event_type,
                "entity_id": entity_id,
                "hits": existing.get("hits", 0),
                "cached": True,
                "cache_key": cache_key,
            }

        # 检索
        chunks = await _retrieve_chunks(query_hint)
        payload = {
            "event_type": event_type,
            "entity_id": entity_id,
            "query_hint": query_hint,
            "priority": priority,
            "hits": len(chunks),
            "chunks": chunks[:DEFAULT_TOP_K],  # 缓存只存 top_k
        }

        cached = await _write_cache(cache_key, payload)
        logger.info(
            f"[W101 P2] auto-rag retrieve done: event={event_type} entity_id={entity_id} "
            f"hits={len(chunks)} cached={cached} priority={priority}"
        )
        return {
            "event_type": event_type,
            "entity_id": entity_id,
            "hits": len(chunks),
            "cached": cached,
            "cache_key": cache_key,
        }

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"[W101 P2] retrieve_and_cache_task failed: {e}", exc_info=True)
        # 重试 (派工 v10 E10: Celery 任务误实现 → 重试兜底)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {
                "event_type": event_type,
                "entity_id": entity_id,
                "hits": 0,
                "cached": False,
                "cache_key": _build_cache_key(event_type, entity_id),
                "error": str(e),
            }


async def get_cached_auto_rag(event_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
    """读 Auto-RAG 缓存 (派工 v10 段 2.2 API)

    Args:
        event_type: 触发事件类型
        entity_id: 实体 ID

    Returns:
        dict or None: 缓存 payload, 缓存不存在或读失败返回 None
    """
    cache_key = _build_cache_key(event_type, entity_id)
    return await _read_cache(cache_key)