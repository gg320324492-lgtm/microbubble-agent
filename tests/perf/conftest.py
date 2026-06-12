"""tests/perf/conftest.py — 性能测试 fixtures

复用 tests/conftest.py 的 db / client / auth_headers
"""

import pytest


@pytest.fixture
def perf_config():
    """性能基线阈值配置

    注：阈值首次跑取实测 P95 + 30% buffer；CI 接受 ±30% 浮动
    """
    return {
        "brief_p95_max_s": 3.0,    # brief < 3s (P95)
        "detail_p95_max_s": 30.0,  # detail < 30s (P95)
        "sse_first_byte_max_s": 1.0,  # SSE 首字节 < 1s
        "tool_round_trip_max_s": 5.0,  # 单工具调用 < 5s
    }
