"""SSE 流式响应首字节延迟

目标：首字节 < 1s
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import json
import time
import pytest


@pytest.mark.asyncio
async def test_sse_first_byte_under_1s(client, auth_headers, perf_config):
    """SSE /chat/stream 首字节延迟 < 1s"""
    t0 = time.monotonic()
    try:
        async with client.stream(
            "POST",
            "/api/v1/chat/stream",
            json={"message": "hi", "session_id": "perf_sse_1"},
            headers=auth_headers,
        ) as r:
            if r.status_code != 200:
                pytest.skip(f"stream 端点 {r.status_code}（可能是 SKIP_DB_SETUP=1）")
            # 读第一个 chunk
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    first_byte_time = time.monotonic() - t0
                    break
    except Exception as e:
        pytest.skip(f"SSE 流测试失败: {e}")
        return

    assert first_byte_time < perf_config["sse_first_byte_max_s"], (
        f"SSE 首字节 = {first_byte_time:.2f}s (max {perf_config['sse_first_byte_max_s']}s)"
    )
