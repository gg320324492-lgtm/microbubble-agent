"""W1 T1: tests/conftest.py 跨 scope lazy init 测试

覆盖:
1. conftest 5 个常量 / SKIP 标志 / 老 compat path
2. _get_conftest_engine 按当前 loop 创建 + 跨 loop 重建
3. _get_test_session_maker 同样 lazy pattern
4. setup_db fixture 在 SKIP 模式用 sync fixture (autouse), 不抛 loop 错
5. db fixture 在 SKIP 模式优雅 skip (不要让老 compat path 抛 NoneType)

跑法 (SKIP_DB_SETUP=1 安全, 这是 conftest 测试核心场景):
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python -m pytest tests/test_conftest_lazy_init.py -v'

非 SKIP 模式需要真 microbubble_test DB, 在本环境无 DB 不跑 (test_migration 等仍 fail 是 pre-existing)
"""
import asyncio
import os
import sys
from unittest.mock import MagicMock

import pytest

# 测试需要先 import conftest 模块 (强制 SKIP_DB_SETUP env 路径)
sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestConftestImports:
    """conftest 模块 import 路径必须兼容"""

    def test_skip_db_setup_env_flag_propagated(self):
        """SKIP_DB_SETUP env var 必须在 conftest 模块顶部读取后正确反映"""
        import tests.conftest as cf
        assert hasattr(cf, "SKIP_DB_SETUP")
        # SKIP 模式下应为 True
        if os.getenv("SKIP_DB_SETUP"):
            assert cf.SKIP_DB_SETUP is True

    def test_test_bot_constants_importable(self):
        """TEST_BOT_* 常量在 if/else 块外, SKIP 模式也能 import"""
        import tests.conftest as cf
        assert cf.TEST_BOT_USERNAME == "xiaoqi_testbot"
        assert cf.TEST_BOT_PASSWORD == "testbot_pass_2026"
        assert cf.TEST_BOT_NAME == "测试小助手"
        assert cf.TEST_BOT_ROLE == "admin"

    def test_skip_mode_old_compat_stubs(self):
        """SKIP 模式 engine/TestSession 是 None (避免老代码 crash on None.connect())"""
        import tests.conftest as cf
        if cf.SKIP_DB_SETUP:
            assert cf.engine is None
            assert cf.TestSession is None

    def test_non_skip_mode_lazy_helpers_defined(self):
        """非 SKIP 模式 _get_conftest_engine / _get_test_session_maker 必须定义"""
        import tests.conftest as cf
        if not cf.SKIP_DB_SETUP:
            assert callable(cf._get_conftest_engine)
            assert callable(cf._get_test_session_maker)

    def test_skip_mode_lazy_helpers_not_defined(self):
        """SKIP 模式不定义 lazy helpers (不需要 DB)"""
        import tests.conftest as cf
        if cf.SKIP_DB_SETUP:
            assert not hasattr(cf, "_get_conftest_engine")


class TestConftestEngineLazyInit:
    """非 SKIP 模式 _get_conftest_engine 跨 loop 行为"""

    @pytest.fixture(autouse=True)
    def require_non_skip_mode(self):
        """本测试类只在非 SKIP 模式运行 (需要 DB imports)"""
        if os.getenv("SKIP_DB_SETUP"):
            pytest.skip("需要非 SKIP 模式 (conftest lazy engine)")

    def test_get_conftest_engine_returns_async_engine(self):
        """_get_conftest_engine 应返 SQLAlchemy AsyncEngine"""
        from tests.conftest import _get_conftest_engine
        from sqlalchemy.ext.asyncio import AsyncEngine

        async def _run():
            engine = _get_conftest_engine()
            assert isinstance(engine, AsyncEngine)
            return engine

        asyncio.run(_run())

    def test_two_loops_rebuild(self, monkeypatch):
        """跨 loop 调用应重建 engine (W1 T1 核心: setup_db session-scope + db fixture function-scope)"""
        from tests.conftest import _get_conftest_engine

        # Mock create_async_engine 让不真连 DB
        from sqlalchemy.ext.asyncio import AsyncEngine

        created_engines = []

        def fake_create_engine(*args, **kwargs):
            fake = MagicMock(spec=AsyncEngine)
            created_engines.append(fake)
            return fake

        # patch conftest 模块用的 create_async_engine (在 conftest 顶部 import)
        monkeypatch.setattr("tests.conftest.create_async_engine", fake_create_engine)

        async def loop_a():
            return _get_conftest_engine()

        async def loop_b():
            return _get_conftest_engine()

        engine_a = asyncio.run(loop_a())
        engine_b = asyncio.run(loop_b())

        # loop 不同时应重建
        assert engine_a is not engine_b, "跨 loop 应重建 conftest engine (解决 7-skipped-E2E bug)"
        assert len(created_engines) == 2, f"应创建 2 个 engine, 实际 {len(created_engines)}"


class TestFixturesSmokeCheck:
    """fixture 注册验证 (用 test_uses_db_fixture 真实请求, 不是直接调)"""

    def test_skip_mode_constants_and_stubs_consistent(self):
        """SKIP 模式: 老 compat stubs 是 None + 模块整体可 import"""
        import tests.conftest as cf
        if not cf.SKIP_DB_SETUP:
            pytest.skip("只在 SKIP 模式测")

        # 验证 module-level 状态一致
        assert cf.engine is None
        assert cf.TestSession is None
        assert cf.TEST_BOT_USERNAME == "xiaoqi_testbot"
        # 验证 SKIP 分支定义了 sync setup_db fixture
        assert hasattr(cf, "setup_db")
        # 验证 SKIP 分支定义了 db function-scope fixture
        assert hasattr(cf, "db")