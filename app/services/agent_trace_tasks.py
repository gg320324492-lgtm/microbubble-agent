"""AgentTrace Celery 任务 — 异步写入 agent_traces 表

设计：
- TraceCollector 在 chat() 完成后调用 persist_trace_task.delay(dict)
- Celery worker 独立 NullPool 引擎（不绑定主 app 事件循环）
- 写入失败 max_retries=2 自动重试
- 全部失败时降级到 logger（trace 数据不阻塞 chat）
"""

import json
import logging
from typing import Any

from app.config import settings
from app.core.celery import celery_app

logger = logging.getLogger("microbubble.agent_trace")


@celery_app.task(
    name="app.services.agent_trace_tasks.persist_trace_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
)
def persist_trace_task(self, trace_dict: dict):
    """Celery 任务：把 trace dict 写入 agent_traces 表"""
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.models.agent_trace import AgentTrace

    async def _write():
        db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(db_url, poolclass=NullPool)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with Session() as db:
                trace = AgentTrace(
                    user_id=trace_dict.get("user_id", 0),
                    session_id=trace_dict.get("session_id", ""),
                    message=trace_dict.get("message", "")[:1000],
                    tool_calls=trace_dict.get("tool_calls", []),
                    rich_blocks=trace_dict.get("rich_blocks", []),
                    brief=trace_dict.get("brief"),
                    detail=trace_dict.get("detail"),
                    input_tokens=trace_dict.get("usage", {}).get("input_tokens"),
                    output_tokens=trace_dict.get("usage", {}).get("output_tokens"),
                    total_tokens=trace_dict.get("usage", {}).get("total_tokens"),
                    total_duration_ms=trace_dict.get("total_duration_ms"),
                    error=trace_dict.get("error"),
                )
                db.add(trace)
                await db.commit()
                return trace.id
        finally:
            await engine.dispose()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            trace_id = loop.run_until_complete(_write())
            logger.info(f"AgentTrace #{trace_id} 写入成功")
            return trace_id
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"AgentTrace 写入失败: {e}")
        try:
            raise self.retry(exc=e, countdown=10)
        except Exception:
            # 重试仍失败，降级到 log
            logger.error(f"AgentTrace 最终写入失败（已降级 log）: {e}")
            return None
