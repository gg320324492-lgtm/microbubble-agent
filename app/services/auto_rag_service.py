"""Auto-RAG 主动触发服务 (W101 P2)

设计目标:
- 任务/会议/知识创建时主动触发背景知识检索 (沿用派工顺序表 W101 P2)
- 4 类触发事件: task.create / task.update / meeting.create / knowledge.upload
- 触发信号检测 (should_auto_retrieve) + 异步 Celery 后台检索 + Redis 24h TTL 缓存
- importorskip 守护 (hybrid_retriever / celery_app 未装时降级)

W101 P2 4 commits:
- [W101 +3] AutoRAGService 触发信号检测 (4 事件类型)
- [W101 +4] AutoRAGService 异步后台检索 (Celery + Redis 24h TTL)
- [W101 +5] task/meeting/knowledge service 集成 Auto-RAG (fire-and-forget)
- [W101 +6] Auto-RAG 8/8 PASS + e2e 铁证
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("microbubble.auto_rag")


# ============================================================================
# 阈值常量 (派工 v10 段 2.1)
# ============================================================================

# 触发事件类型 (派工 v10 段 2.1)
EVENT_TASK_CREATE = "task.create"
EVENT_TASK_UPDATE = "task.update"
EVENT_MEETING_CREATE = "meeting.create"
EVENT_KNOWLEDGE_UPLOAD = "knowledge.upload"

ALL_TRIGGER_EVENTS = frozenset({
    EVENT_TASK_CREATE,
    EVENT_TASK_UPDATE,
    EVENT_MEETING_CREATE,
    EVENT_KNOWLEDGE_UPLOAD,
})

# query_hint 最小长度 (< 不触发)
MIN_QUERY_HINT_LENGTH = 3

# task.update 触发条件 (派工 v10 段 2.1: 状态变化或描述变化才触发)
TASK_UPDATE_STATUS_FIELDS = frozenset({"status", "description", "title", "priority"})

# 缓存 key 前缀 (派工 v10 段 2.2)
CACHE_KEY_PREFIX = "auto_rag"


# ============================================================================
# 依赖守护 (派工 v10 段 2.1 importorskip 守护)
# ============================================================================

try:
    from app.services.hybrid_retriever import get_hybrid_retriever
    _HAS_RETRIEVER = True
except ImportError:
    _HAS_RETRIEVER = False

try:
    from app.core.celery import celery_app
    _HAS_CELERY = True
except ImportError:
    _HAS_CELERY = False


def _is_available() -> bool:
    """Auto-RAG 服务可用性检查 — 缺 hybrid_retriever 或 celery 时降级"""
    return _HAS_RETRIEVER and _HAS_CELERY


# ============================================================================
# AutoRAGService
# ============================================================================

class AutoRAGService:
    """Auto-RAG 主动触发服务 — 任务/会议/知识创建时自动检索背景知识"""

    def should_auto_retrieve(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """判断是否触发自动检索 — 派工 v10 段 2.1

        Args:
            event_type: 触发事件类型 (task.create / task.update / meeting.create / knowledge.upload)
            payload: 事件 payload (dict, 用于 task.update 判断字段变化)

        Returns:
            dict: {"should_retrieve": bool, "query_hint": str, "priority": int}
        """
        payload = payload or {}

        # 不在白名单的事件类型 → 不触发
        if event_type not in ALL_TRIGGER_EVENTS:
            return {"should_retrieve": False, "query_hint": "", "priority": 0}

        # 提取 query_hint
        query_hint = self._extract_query_hint(event_type, payload)

        # query_hint 太短 → 不触发
        if len(query_hint.strip()) < MIN_QUERY_HINT_LENGTH:
            return {"should_retrieve": False, "query_hint": query_hint, "priority": 0}

        # task.update 额外判断 (派工 v10 段 2.1: 状态变化或描述变化才触发)
        if event_type == EVENT_TASK_UPDATE:
            if not self._should_trigger_task_update(payload):
                return {"should_retrieve": False, "query_hint": query_hint, "priority": 0}

        # 优先级: knowledge.upload > meeting.create > task.create > task.update
        priority_map = {
            EVENT_KNOWLEDGE_UPLOAD: 10,
            EVENT_MEETING_CREATE: 8,
            EVENT_TASK_CREATE: 6,
            EVENT_TASK_UPDATE: 4,
        }

        return {
            "should_retrieve": True,
            "query_hint": query_hint.strip(),
            "priority": priority_map.get(event_type, 5),
        }

    def _extract_query_hint(
        self,
        event_type: str,
        payload: Dict[str, Any],
    ) -> str:
        """从 payload 提取 query hint"""
        parts = []

        if event_type in (EVENT_TASK_CREATE, EVENT_TASK_UPDATE):
            title = payload.get("title") or ""
            description = payload.get("description") or ""
            if title:
                parts.append(title)
            if description:
                parts.append(description[:200])

        elif event_type == EVENT_MEETING_CREATE:
            title = payload.get("title") or ""
            description = payload.get("description") or ""
            agenda = payload.get("agenda")
            if title:
                parts.append(title)
            if description:
                parts.append(description[:200])
            if isinstance(agenda, list) and agenda:
                parts.append(" ".join(str(a) for a in agenda[:5]))

        elif event_type == EVENT_KNOWLEDGE_UPLOAD:
            title = payload.get("title") or ""
            content = payload.get("content") or ""
            tags = payload.get("tags")
            if title:
                parts.append(title)
            if content:
                parts.append(content[:500])
            if isinstance(tags, list) and tags:
                parts.append(" ".join(str(t) for t in tags[:10]))

        return " ".join(parts)

    def _should_trigger_task_update(self, payload: Dict[str, Any]) -> bool:
        """task.update 触发条件: 状态变化或描述变化"""
        changed_fields = payload.get("changed_fields") or []
        if not changed_fields:
            # 没传 changed_fields → 默认触发 (兼容老调用)
            return True
        return any(f in TASK_UPDATE_STATUS_FIELDS for f in changed_fields)

    async def trigger_and_dispatch(
        self,
        event_type: str,
        entity_id: int,
        query_hint: str,
    ) -> bool:
        """触发并 dispatch Celery 任务 (派工 v10 段 2.3 fire-and-forget)

        Returns:
            bool: True if dispatched, False if skipped
        """
        # 依赖不可用 → 降级 no-op
        if not _is_available():
            logger.debug(f"[W101 P2] auto-rag unavailable (retriever={_HAS_RETRIEVER}, celery={_HAS_CELERY})")
            return False

        decision = self.should_auto_retrieve(
            event_type,
            {"title": query_hint, "content": query_hint},
        )

        if not decision["should_retrieve"]:
            return False

        try:
            from app.services.auto_rag_tasks import retrieve_and_cache_task
            retrieve_and_cache_task.delay(
                event_type=event_type,
                entity_id=entity_id,
                query_hint=decision["query_hint"],
                priority=decision["priority"],
            )
            logger.info(
                f"[W101 P2] auto-rag dispatched: event={event_type} entity_id={entity_id} "
                f"priority={decision['priority']}"
            )
            return True
        except Exception as e:
            # fire-and-forget — 失败不阻塞主流程
            logger.warning(f"[W101 P2] auto-rag dispatch failed: {e}")
            return False


# 模块级 singleton (派工 v10 段 2.3 fire-and-forget 调用约定)
auto_rag_service = AutoRAGService()