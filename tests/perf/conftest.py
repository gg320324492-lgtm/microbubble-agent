"""tests/perf/conftest.py — 性能测试 fixtures

2026-06-14 方案 C Stage 3：基线修正

Stage 0 预算（被 Plan agent 6 修正后）：
- synthesis_first_byte_max_s: 1.5s → 2.5s（实际包含 Haiku intent ~400ms + 第一轮工具决策 ~500ms + 网络 overhead ~400ms + 第一段 text_delta）
- synthesis_p95_max_s: 8.0s → 10.0s（不含 retry 慢路径）
- synthesis_p95_with_retry_max_s: 16.0s（独立慢路径基线）

2026-06-29 收官：chat_engine_legacy.py 已删除（30 天回滚承诺提前收官, commit 817f1ffa），
新代码已无 brief/detail 双层事件路径，仅保留 synthesis P95 / first-byte 基线。
"""

import pytest


@pytest.fixture
def perf_config():
    """性能基线阈值配置（方案 C Stage 3 修正后）

    阈值首次跑取实测 P95 + 30% buffer；CI 接受 ±30% 浮动。
    实测在 2026-06-14 commit 9862546 部署后 24h 跑 20 次取 P95。
    """
    return {
        # === 2026-06-14 方案 C 新基线 ===
        "synthesis_first_byte_max_s": 2.5,  # 含 Haiku intent + 工具决策
        "synthesis_p95_max_s": 10.0,  # 不含 retry
        "synthesis_p95_with_retry_max_s": 16.0,  # 独立慢路径（retry 1 次）
        # === Stage 0 旧基线（保留为参考，不再断言） ===
        "brief_p95_max_s": 3.0,  # 仅 legacy 路径有效
        "detail_p95_max_s": 30.0,  # 仅 legacy 路径有效
        "sse_first_byte_max_s": 1.0,  # 仅 legacy 路径有效
        # === 工具调度（与方案 C 无关，保留） ===
        "tool_round_trip_max_s": 5.0,  # 单工具调用 < 5s
        "intent_classify_max_s": 0.5,  # Haiku 意图分类
        "compression_max_s": 1.5,  # Haiku 结果压缩
        "critique_max_s": 3.0,  # Sonnet 自评
    }
