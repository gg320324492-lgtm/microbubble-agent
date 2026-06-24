"""Embedding 全量重算 Celery 任务 (v29 Qwen3-Embedding 切换)

背景:
  v29 把 embedding 模型从 shibing624/text2vec-base-chinese (768d) 切换到
  Qwen3-Embedding-0.6B (1024d)。已通过 alembic 030 迁移加 embedding 列 (双列并存),
  ORM 也加了 embedding 字段。本模块负责把现有数据的 embedding 重算到新列。

策略:
  - recalc_one_embedding(table, row_id): 单条重算 (幂等: WHERE embedding IS NULL)
  - recalc_all_embeddings(table, batch_size): 全表入口, 找 IS NULL 行分批派发
  - 进度写 Redis key embedding_recompute:progress:{table} = {done, total, percent}
  - 重算覆盖率 100% 后手工 ALTER TABLE ... DROP COLUMN embedding + RENAME embedding TO embedding

Celery 跨 event loop 修复:
  reminder_service.py:548-583 的标准模板 — 每个 Celery 任务内创建独立的
  async engine (NullPool) + 独立 redis client, asyncio.run() 后 dispose.
  否则 asyncpg 连接绑旧 loop 会报 "another operation is in progress".

参考:
  - alembic 030_qwen3_embedding_1024.py (迁移)
  - app/services/post_meeting_tasks.py (Celery 任务模板)
  - app/services/reminder_service.py (NullPool 跨 loop 模式)
"""

import asyncio
import json
import logging
import os
from typing import Optional

from app.core.celery import celery_app

logger = logging.getLogger("microbubble.embedding_recalc")


# 4 张表 + 内容字段名映射 (用于提取待重算文本)
TABLE_TO_MODEL = {
    "knowledge": ("Knowledge", "content"),
    "memories": ("Memory", "content"),
    "meetings": ("Meeting", "summary"),  # meeting 用 summary 作为嵌入源
    "knowledge_entities": ("KnowledgeEntity", "subject"),  # entity 用三元组拼接
}


def _import_model_class(table: str):
    """懒加载 model class (避免 celery 启动时 import 全部 ORM)"""
    from app.models.knowledge import Knowledge
    from app.models.memory import Memory
    from app.models.meeting import Meeting
    from app.models.knowledge_entity import KnowledgeEntity

    return {
        "knowledge": Knowledge,
        "memories": Memory,
        "meetings": Meeting,
        "knowledge_entities": KnowledgeEntity,
    }[table]


def _get_embedding_text(table: str, row) -> Optional[str]:
    """从行对象提取待重算文本"""
    if table == "knowledge_entities":
        parts = [row.subject, row.predicate, row.object]
        if row.condition:
            parts.append(f"({row.condition})")
        return " ".join([p for p in parts if p])
    elif table == "meetings":
        parts = []
        if row.title:
            parts.append(row.title)
        if row.summary:
            parts.append(row.summary)
        if row.key_points and isinstance(row.key_points, list):
            parts.append(" ".join(row.key_points[:5]))
        return " ".join(parts) if parts else (row.summary or row.title or "")
    else:
        return row.content or ""


def _setup_independent_async_env():
    """为 Celery 任务创建独立的 async engine + redis client (NullPool, 跨 loop 安全)

    模式来自 reminder_service.py:548-583. 必须 with-finally dispose,
    否则 asyncpg 连接泄漏到 Celery worker 主 loop.
    """
    from sqlalchemy.ext.asyncio import (
        create_async_engine,
        AsyncSession,
        async_sessionmaker,
    )
    from sqlalchemy.pool import NullPool
    import redis.asyncio as aioredis
    from app.config import settings

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, redis_client, session_factory


async def _update_progress(redis_client, table: str, done: int, total: int) -> None:
    """写 Redis 进度键 (前端可读)"""
    try:
        percent = round(done / total * 100, 1) if total > 0 else 0
        await redis_client.set(
            f"embedding_recompute:progress:{table}",
            json.dumps({"table": table, "done": done, "total": total, "percent": percent}),
            ex=86400,  # 24h TTL
        )
    except Exception as e:
        logger.warning(f"更新进度失败 {table}: {e}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30, name="app.services.embedding_recalc.recalc_one_embedding")
def recalc_one_embedding(self, table: str, row_id: int):
    """单条 embedding 重算 (幂等: WHERE embedding IS NULL)

    Args:
        table: 表名 (knowledge / memories / meetings / knowledge_entities)
        row_id: 主键 ID

    Returns:
        {"status": "done"|"skipped", "table": str, "row_id": int}
    """
    from app.services.embedding_service import generate_embedding

    async def _run():
        Model = _import_model_class(table)
        engine, redis_client, session_factory = _setup_independent_async_env()
        try:
            async with session_factory() as db:
                row = await db.get(Model, row_id)
                if row is None:
                    return {"status": "skipped", "table": table, "row_id": row_id, "reason": "not_found"}
                if row.embedding is not None:
                    return {"status": "skipped", "table": table, "row_id": row_id, "reason": "already_done"}
                text = _get_embedding_text(table, row)
                if not text:
                    logger.warning(f"{table}:{row_id} 文本为空, 跳过")
                    return {"status": "skipped", "table": table, "row_id": row_id, "reason": "empty_text"}
                # 截断超长文本 (Qwen3 max_length=2048 token, 中文 ~6000 字)
                text = text[:6000]
                embedding = await generate_embedding(text)
                if embedding:
                    row.embedding = embedding
                    await db.commit()
                    return {"status": "done", "table": table, "row_id": row_id, "dim": len(embedding)}
                else:
                    return {"status": "skipped", "table": table, "row_id": row_id, "reason": "embedding_failed"}
        finally:
            await engine.dispose()
            await redis_client.aclose()

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"recalc_one_embedding({table}:{row_id}) 失败: {e}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(name="app.services.embedding_recalc.recalc_all_embeddings")
def recalc_all_embeddings(table: str, batch_size: int = 50):
    """全表重算入口: 找出 embedding IS NULL 的行, 分批派发到 recalc_one_embedding.

    Args:
        table: 表名 (字符串, 必填)
        batch_size: 一次派发多少条任务 (整数, 默认 50)

    Returns:
        {"dispatched": int, "table": str, "total": int, "pending": int}
    """
    from sqlalchemy import select, func

    async def _run():
        Model = _import_model_class(table)
        engine, redis_client, session_factory = _setup_independent_async_env()
        try:
            async with session_factory() as db:
                total = await db.scalar(select(func.count(Model.id)))
                pending = await db.scalar(
                    select(func.count(Model.id)).where(Model.embedding.is_(None))
                )
                result = await db.execute(
                    select(Model.id).where(Model.embedding.is_(None)).limit(batch_size)
                )
                row_ids = [r[0] for r in result.fetchall()]
                for row_id in row_ids:
                    recalc_one_embedding.delay(table, row_id)
                # 写初始进度 (done = 还没人更新过)
                await _update_progress(
                    redis_client, table,
                    done=(total - pending) if total else 0,
                    total=total or 0,
                )
                logger.info(
                    f"recalc_all_embeddings({table}): 派发 {len(row_ids)} 条 "
                    f"(总 {total}, 待 {pending}, batch_size={batch_size})"
                )
                return {
                    "dispatched": len(row_ids),
                    "table": table,
                    "total": total or 0,
                    "pending": pending or 0,
                }
        finally:
            await engine.dispose()
            await redis_client.aclose()

    try:
        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"recalc_all_embeddings({table}) 失败: {e}", exc_info=True)
        return {"error": str(e), "table": table}


@celery_app.task(name="app.services.embedding_recalc.get_progress")
def get_progress(table: str):
    """查询某表的重算进度 (从 Redis)"""
    async def _run():
        engine, redis_client, session_factory = _setup_independent_async_env()
        try:
            data = await redis_client.get(f"embedding_recompute:progress:{table}")
            if data:
                return json.loads(data)
            return {"table": table, "status": "no_data"}
        finally:
            await engine.dispose()
            await redis_client.aclose()

    try:
        return asyncio.run(_run())
    except Exception as e:
        return {"table": table, "error": str(e)}
