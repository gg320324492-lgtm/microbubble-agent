"""回退门控端到端测试 — 每种异常场景至少 1 个断言"""

import pytest
from unittest.mock import AsyncMock, patch

from app.rag.gate import framework_gate


@pytest.fixture
def fallback_fn():
    return AsyncMock(return_value={"source": "fallback"})


@pytest.fixture
def framework_fn():
    async def _fn(*args, **kwargs):
        return {"source": "framework"}
    return _fn


class TestFrameworkGate:
    """框架门控装饰器 — 4 场景"""

    async def test_flag_off_uses_fallback(self, fallback_fn):
        """场景 1: 开关关闭 → 直接走 fallback"""
        @framework_gate(feature_flag=False, fallback_fn=fallback_fn)
        async def impl():
            return {"source": "framework"}
        result = await impl()
        assert result == {"source": "fallback"}
        fallback_fn.assert_awaited_once()

    async def test_flag_on_uses_framework(self, framework_fn):
        """场景 2: 开关开启 → 走 framework"""
        @framework_gate(feature_flag=True, fallback_fn=AsyncMock())
        async def impl():
            return await framework_fn()
        result = await impl()
        assert result == {"source": "framework"}

    async def test_import_error_falls_back(self, fallback_fn):
        """场景 3: ImportError → 回退"""
        @framework_gate(feature_flag=True, fallback_fn=fallback_fn)
        async def impl():
            raise ImportError("No module named 'langchain'")
        result = await impl()
        assert result == {"source": "fallback"}
        fallback_fn.assert_awaited_once()

    async def test_runtime_error_falls_back(self, fallback_fn):
        """场景 4: 运行时异常 → 回退"""
        @framework_gate(feature_flag=True, fallback_fn=fallback_fn)
        async def impl():
            raise TimeoutError("LLM timeout")
        result = await impl()
        assert result == {"source": "fallback"}
        fallback_fn.assert_awaited_once()

    async def test_no_fallback_returns_none(self):
        """场景 5: 无 fallback_fn 时返回 None"""
        @framework_gate(feature_flag=True)
        async def impl():
            raise Exception("boom")
        result = await impl()
        assert result is None
