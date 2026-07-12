"""Celery task database utilities — 独立 async engine + sessionmaker

提取自 18+ 个 Celery task 文件 (chat_history_tasks / drive_cleanup_tasks /
file_mention_tasks / knowledge_evolution_tasks / post_meeting_tasks /
reminder_service / storage_tasks / thumbnail_tasks / task_service /
agent_trace_tasks / orphan_meeting_cleanup / embedding_recalc /
content_formatter_service / drive_cleanup_service / knowledge_service /
memory_service / paper_layout_service / tracing.py / wechat/scheduler 等).

原文件各自 inline 重复:
  from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
  from sqlalchemy.pool import NullPool
  engine = create_async_engine(
      settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
      poolclass=NullPool,
  )
  SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

## 设计要点
① **NullPool 强制** — Celery worker 主 loop 与 asyncio.run() 新 loop 冲突,
   必须每任务新建连接避免跨 loop 复用
② **expire_on_commit=False** — async session 默认 commit 后 expire ORM 对象,
   跨 await 访问属性会触发 lazy load → MissingGreenlet 报错
③ **DATABASE_URL postgresql:// → postgresql+asyncpg://** — SQLAlchemy async 强制要求
④ **engine 句柄返回** — 调用方负责 finally engine.dispose() 关闭连接池
⑤ **Redis client 单独提供** — 不是所有 Celery task 都需要 Redis (可选)

## 铁律 (永久沉淀)
① **Celery task 禁止复用主进程 async_session** — 主进程 loop 绑定 session,
   asyncio.run() 新 loop 触发 "Future attached to different loop" 错误
② **每个 task 必须 engine.dispose()** — 否则 asyncpg 连接泄漏到 worker 主 loop
   (下一任务新建连接时可能拿 stale connection)
③ **DATABASE_URL 必须 replace("postgresql://", "postgresql+asyncpg://")** —
   SQLAlchemy 默认 sync driver, async 必须显式指定 asyncpg
"""
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import AsyncEngine
from sqlalchemy.pool import NullPool

from app.config import settings


def create_celery_engine_and_session() -> Tuple[AsyncEngine, "async_sessionmaker[AsyncSession]"]:
    """为 Celery task 创建独立 async engine + sessionmaker (NullPool, 跨 loop 安全)

    Returns:
        (engine, session_factory) — engine 用完记得 dispose

    Example:
        from app.core.celery_db import create_celery_engine_and_session

        async def my_task():
            engine, SessionFactory = create_celery_engine_and_session()
            try:
                async with SessionFactory() as session:
                    # ... do work ...
                    await session.commit()
            finally:
                await engine.dispose()
    """
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory