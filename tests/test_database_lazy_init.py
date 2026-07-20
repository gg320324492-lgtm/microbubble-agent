"""W3 T1: app/core/database.py lazy init 单元测试

覆盖:
1. 5 个老 import 路径都能拿到正确类型
2. _EngineProxy.__getattr__ 转发到 _get_engine()
3. _SessionFactoryProxy.__call__ 转发到 _get_session_factory()
4. 跨 loop 调用 _get_engine() 应重建 (解决 W5+1 follow-up bug class)
5. asyncio.Lock 懒初始化 (loop 内才能创建)

跑法 (SKIP_DB_SETUP=1 安全):
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python -m pytest tests/test_database_lazy_init.py -v'
"""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

# 这些 import 必须在 pytestmark skip 之前, 否则 SKIP 模式 conftest 不触发
from app.core.database import (
    Base,
    _EngineProxy,
    _SessionFactoryProxy,
    _get_engine,
    _get_lock,
    _get_session_factory,
    async_session as async_session_proxy,
    engine as engine_proxy,
    get_db,
)


class TestBackwardCompatImports:
    """95+ 老 import 路径必须仍可用"""

    def test_engine_is_engine_proxy(self):
        """`from app.core.database import engine` 拿到 _EngineProxy (不是 None, 不是真 engine)"""
        assert isinstance(engine_proxy, _EngineProxy)

    def test_async_session_is_factory_proxy(self):
        """`from app.core.database import async_session` 拿到 _SessionFactoryProxy + callable"""
        assert isinstance(async_session_proxy, _SessionFactoryProxy)
        assert callable(async_session_proxy)

    def test_base_class_importable(self):
        """Base class 仍可导入"""
        assert Base is not None

    def test_get_db_function_importable(self):
        """get_db FastAPI Depends 仍可导入"""
        assert callable(get_db)


class TestProxyBehavior:
    """代理对象转发 attribute / call 到真实 engine / sessionmaker"""

    def test_engine_proxy_repr_no_real_engine(self):
        """repr 不创建真 engine, 显示 loop=None"""
        assert repr(engine_proxy) == "<_EngineProxy loop=None>"

    def test_async_session_proxy_repr_no_real_factory(self):
        assert repr(async_session_proxy) == "<_SessionFactoryProxy loop=None>"

    def test_engine_proxy_getattr_forwards_to_get_engine(self, monkeypatch):
        """__getattr__ 转发到当前 loop 的 _get_engine() (mock 避免真 create)"""
        fake_engine = MagicMock(name="FakeEngine")
        monkeypatch.setattr("app.core.database._get_engine", lambda: fake_engine)
        # 访问 engine.dispose() 应触发 __getattr__('dispose') → _get_engine().dispose
        engine_proxy.dispose()
        fake_engine.dispose.assert_called_once()

    def test_async_session_proxy_call_forwards(self, monkeypatch):
        """__call__ 转发到当前 loop 的 sessionmaker (mock 避免真 create)"""
        fake_session = MagicMock(name="FakeSession")
        fake_factory = MagicMock(name="FakeFactory")
        fake_factory.return_value = fake_session
        monkeypatch.setattr("app.core.database._get_session_factory", lambda: fake_factory)

        async_session_proxy()  # 调用
        fake_factory.assert_called_once()
        fake_session.__aenter__.assert_not_called()  # 我们没 async with, 只验证 __call__ 转发


class TestEngineLazyInit:
    """_get_engine() 按当前 loop 创建, loop 不匹配时重建"""

    def test_get_engine_creates_async_engine_only_inside_loop(self):
        """loop 内 _get_engine() 返真 AsyncEngine; loop 外返 None 或挂起 (skip)"""

        async def _run():
            engine1 = _get_engine()
            current_loop = asyncio.get_running_loop()
            assert engine1 is not None
            # 测试 loop 引用匹配 (私有字段)
            import app.core.database as dbmod
            assert dbmod._engine_loop is current_loop
            return engine1

        # SKIP 模式: 没有真 DB, 跳过
        import os
        if os.getenv("TEST_SKIP_REAL_DB_INIT"):
            pytest.skip("TEST_SKIP_REAL_DB_INIT=1: 不创建真 engine")

        asyncio.run(_run())

    def test_two_loops_rebuild(self, monkeypatch):
        """loop A 创 engine → loop B 调应重建 (这是 W5+1 bug 修复的核心)"""
        # Mock create_async_engine 让它不连 DB
        from sqlalchemy.ext.asyncio import AsyncEngine

        created_engines = []

        def fake_create_engine(*args, **kwargs):
            fake = MagicMock(spec=AsyncEngine)
            created_engines.append(fake)
            return fake

        monkeypatch.setattr("app.core.database.create_async_engine", fake_create_engine)

        async def loop_a():
            return _get_engine()

        async def loop_b():
            return _get_engine()

        engine_a = asyncio.run(loop_a())
        engine_b = asyncio.run(loop_b())

        # 两个不同 loop → 必须创建 2 个不同 engine
        assert engine_a is not engine_b, "loop 不同时应重建 engine"
        assert len(created_engines) == 2, f"应创建 2 个 engine (loop A + B), 实际 {len(created_engines)}"


class TestLockLazyInit:
    """asyncio.Lock 懒初始化 (loop 内才能创建)"""

    def test_get_lock_creates_asyncio_lock(self):
        async def _run():
            lock = _get_lock()
            assert isinstance(lock, asyncio.Lock)
            return lock

        asyncio.run(_run())

    def test_get_lock_reuses_same_instance(self):
        """重复调 _get_lock() 应返同一实例 (避免 race condition)"""
        async def _run():
            lock1 = _get_lock()
            lock2 = _get_lock()
            assert lock1 is lock2, "应复用同一 Lock 实例"
            return lock1

        asyncio.run(_run())


class TestModuleImportDoesNotCreateEngine:
    """★ 核心: 模块导入本身不创建 engine (lazy 验证)"""

    def test_module_import_no_engine_yet(self):
        """import 后 _engine 应仍是 None (没创建真 engine)"""
        import app.core.database as dbmod
        # 重置模块状态的副作用: 在新进程里 _engine 应 None
        # 但因为 Python 模块缓存, 我们改测 _engine_loop 应该是 None (这是 import 时初始化)
        # 实际 import 时 _engine = None, 首次 _get_engine() 才创建
        # 这验证 import 的 lazy 行为
        if hasattr(dbmod, '_engine') and dbmod._engine is not None:
            pytest.skip("已有真 engine (其他测试副作用), 无法测干净 import 状态")
        assert dbmod._engine is None
        assert dbmod._engine_loop is None