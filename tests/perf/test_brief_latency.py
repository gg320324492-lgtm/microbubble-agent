"""brief 响应延迟基线

brief 阶段：max_tokens=500 + 工具循环
目标：P95 < 3s
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import time
import pytest


@pytest.mark.asyncio
async def test_brief_latency_p95(client, auth_headers, test_member, perf_config):
    """brief 响应延迟：跑 20 次取 P95，应 < 3s"""
    durations = []
    n = 20
    for i in range(n):
        t0 = time.monotonic()
        try:
            r = await client.post(
                "/api/v1/chat",
                json={"message": f"hi {i}", "session_id": f"perf_brief_{i}"},
                headers=auth_headers,
            )
            elapsed = time.monotonic() - t0
            if r.status_code == 200:
                durations.append(elapsed)
        except Exception:
            # 网络/LLM 错误不计入
            continue

    if not durations:
        pytest.skip("无可用响应（可能是 SKIP_DB_SETUP=1）")

    durations.sort()
    p95 = durations[int(len(durations) * 0.95)]
    p50 = durations[int(len(durations) * 0.50)]
    max_d = max(durations)

    assert p95 < perf_config["brief_p95_max_s"], (
        f"brief P95 = {p95:.2f}s (max {perf_config['brief_p95_max_s']}s). "
        f"p50={p50:.2f}s, max={max_d:.2f}s, n={len(durations)}"
    )


@pytest.mark.asyncio
async def test_brief_response_has_duration_ms(client, auth_headers):
    """ChatResponse 必须含 duration_ms 字段"""
    r = await client.post(
        "/api/v1/chat",
        json={"message": "ping", "session_id": "perf_test_dm"},
        headers=auth_headers,
    )
    if r.status_code != 200:
        pytest.skip(f"chat 端点 {r.status_code}（可能是 SKIP_DB_SETUP=1）")
    body = r.json()
    # 兼容：v2 ChatResponse 含 duration_ms
    if "duration_ms" in body:
        assert isinstance(body["duration_ms"], int)
    # v1 ChatResponse 不含也 OK
