"""app/core/database.py — SQLAlchemy AsyncEngine + session factory (lazy init)

W5+1 follow-up 第 5 层闭环 (2026-07-20):
- W5  → Redis LTRIM 200 契约回归
- W8  → monkeypatch 跨文件泄露
- W9  → pytest.ini loop_scope=function
- W1 round 2 → app/core/redis.py lazy init (commit ca0fb0a3)
- W3 (本任务) → app/core/database.py lazy init — 闭环!

## Bug class
模块加载时 `create_async_engine(...)` 创建 AsyncEngine 绑首次访问的 event loop。
后续跨 loop 调用 (pytest-asyncio loop_scope=function 每个 test 新 loop, 或 Celery worker
跨 event loop 复用全局 engine) 抛 "Future attached to a different loop" / "Event loop is closed"。

## 修复
按当前 event loop 懒创建 + 缓存, loop 不匹配时重建。

## 向后兼容
95 个老 import 路径保留:
- `from app.core.database import engine`  → _EngineProxy (动态代理)
- `from app.core.database import async_session` → _SessionFactoryProxy
- `from app.core.database import Base, get_db` → 直接导出

PEP 562 `__getattr__` 在 module 层面拦截 `module.engine` 访问, 动态返回 _get_engine()
的真实 engine 引用。runtime 调用 engine.connect() / dispose() 时才解析, 无副作用。
"""
import asyncio
from typing import Any, Optional, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ============================================================================
# Lazy init: 模块导入时不创建 engine, 首次 _get_engine() 时按当前 loop 创建
# ============================================================================

_engine: Optional[AsyncEngine] = None
_engine_loop: Optional[asyncio.AbstractEventLoop] = None
_session_factory = None  # type: Optional[async_sessionmaker[AsyncSession]]
_session_factory_loop: Optional[asyncio.AbstractEventLoop] = None
_engine_lock = None  # type: Optional[asyncio.Lock]  # lazy (asyncio.Lock 必须在 loop 内)


def _get_lock() -> asyncio.Lock:
    """asyncio.Lock 必须在 running loop 内创建, 懒初始化."""
    global _engine_lock
    if _engine_lock is None:
        _engine_lock = asyncio.Lock()
    return _engine_lock


def _build_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.APP_DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        connect_args={"server_settings": {"client_encoding": "utf8"}},  # v31.2.4: 修 raw text() 中文乱码
    )


def _build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _get_engine() -> AsyncEngine:
    """按当前 event loop 创建或重建 engine (loop 不匹配时重建).

    pytest-asyncio loop_scope=function 每个 test 一个新 loop,
    engine 必须重新创建才能绑到新 loop 的 event source 上。
    """
    global _engine, _engine_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _engine is None or _engine_loop is not current_loop:
        _engine = _build_engine()
        _engine_loop = current_loop
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """异步懒版本: 复用 _get_engine() + 同 loop 缓存."""
    global _session_factory, _session_factory_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _session_factory is None or _session_factory_loop is not current_loop:
        _session_factory = _build_session_factory(_get_engine())
        _session_factory_loop = current_loop
    return _session_factory


# ============================================================================
# Base ORM class
# ============================================================================

class Base(DeclarativeBase):
    """基础模型类"""
    pass


# ============================================================================
# FastAPI Depends 注入 (主路径)
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 路由依赖注入: 每请求独立 session."""
    SessionFactory = _get_session_factory()
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# 向后兼容代理 (PEP 562 module __getattr__)
# ============================================================================
# 95+ 老 import 路径:
#   from app.core.database import engine, async_session
#   from app.core.database import engine, Base, async_session
# 不能直接 def engine = None (老代码立刻 crash on engine.connect()).
# 用 _EngineProxy / _SessionFactoryProxy 动态转发到 _get_engine() / _get_session_factory().

class _EngineProxy:
    """module-level 'engine' 代理对象 (PEP 562 __getattr__ 返回).

    任何属性/方法访问都转发到按当前 loop 创建的真实 engine.
    老代码 `engine.connect()` / `engine.dispose()` / `engine.begin()` 都正常工作。
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_engine(), name)

    def __repr__(self) -> str:
        return f"<_EngineProxy loop={_engine_loop}>"


class _SessionFactoryProxy:
    """module-level 'async_session' 代理对象 (PEP 562 __getattr__ 返回).

    老代码 `async with async_session() as session:` 走的 __call__ 必须转发到当前 loop 的真 sessionmaker.
    """

    def __call__(self, *args, **kwargs):
        return _get_session_factory()(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_session_factory(), name)

    def __repr__(self) -> str:
        return f"<_SessionFactoryProxy loop={_session_factory_loop}>"


# 模块级代理对象 (老 import 拿到这些, 不是 None, 避免 AttributeError)
engine = _EngineProxy()
async_session = _SessionFactoryProxy()
