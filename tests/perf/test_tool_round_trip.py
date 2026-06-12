"""工具调用往返延迟

单工具 dispatch 从注册表查找 → handler 委托 service → 输出校验
目标：< 5s（含 LLM 调用时可能会慢，但纯 dispatcher 应 < 100ms）
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import app.agent.tools  # noqa: F401  触发 @tool 装饰器注册
import time
import pytest

from app.agent.tool_registry import (
    ToolContext,
    dispatch_tool,
    TOOL_REGISTRY,
)


@pytest.mark.asyncio
async def test_dispatch_latency_pure():
    """纯 dispatch 性能（不调 LLM/DB）：< 5ms（avg）"""
    # 用 query_meetings（需 DB，但前置校验返回 error，不抛）
    if "query_meetings" not in TOOL_REGISTRY:
        pytest.skip("query_meetings 未注册")
    ctx = ToolContext(db=None, user_id=None)
    t0 = time.monotonic()
    for _ in range(100):
        await dispatch_tool("query_meetings", {}, ctx)
    avg_ms = (time.monotonic() - t0) * 1000 / 100
    assert avg_ms < 5, f"工具 dispatch 平均 {avg_ms:.2f}ms (期望 < 5ms)"


@pytest.mark.asyncio
async def test_schema_export_latency():
    """get_all_tool_schemas() 性能：< 50ms（avg）"""
    from app.agent.tool_registry import get_all_tool_schemas
    t0 = time.monotonic()
    for _ in range(100):
        schemas = get_all_tool_schemas()
    avg_ms = (time.monotonic() - t0) * 1000 / 100
    assert avg_ms < 50, f"schema 导出平均 {avg_ms:.2f}ms (期望 < 50ms)"
    assert len(schemas) >= 30, f"应有 ≥ 30 工具，实际 {len(schemas)}"


@pytest.mark.asyncio
async def test_tool_registry_size():
    """TOOL_REGISTRY 应有 ≥ 30 工具（v4 目标 ≥ 33）"""
    assert len(TOOL_REGISTRY) >= 30, f"工具数 {len(TOOL_REGISTRY)} < 30（v4 目标 33）"
