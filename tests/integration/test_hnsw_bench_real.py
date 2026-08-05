"""tests/integration/test_hnsw_bench_real.py — run_bench 真实 DB 集成测试

阶段 A.3 集成测试 (硬门禁 + INTEGRATION=1 gate):

- test_run_bench_returns_results_dict: 跑单 combo (m=16, ef_c=64, ef_s=40), 必须返回 dict
  且含正确 key 形式 "m=16,ef_c=64,ef_s=40", recall_at_10 字段存在 + 数值合法
- test_run_bench_multiple_combos: 多 combo 跑通, 每个都返回 recall_at_k

依赖: 真 PostgreSQL + pgvector 0.7+, 通过 docker compose 起 microbubble-agent-db-1.

启动方式: INTEGRATION=1 pytest tests/integration/test_hnsw_bench_real.py -v
SKIP_DB_SETUP=1 也允许 (本测试不依赖 conftest fixtures, 自己创 engine).

测试用 settings.DATABASE_URL 真连 production-like DB. 若 DB 不可用则
pytest.skip 跳过, 不报错 (本测试属于 PoC, Postgres 离线不算 regression).
"""
import os
import socket

import pytest


def _postgres_reachable() -> bool:
    """快速 TCP 探测 postgres:5432 是否可达. 避免 30s connection timeout.

    试多个候选地址 (docker 网络名 + localhost):
    - microbubble-agent-db-1:5432 (docker network, 跑在容器里时的可达性)
    - localhost:5432 (主机本地 port mapping, 一般没暴露)
    - host.docker.internal:5432 (Windows Docker Desktop)
    """
    candidates = [
        os.getenv("PG_PORT_FOR_TEST", "microbubble-agent-db-1:5432"),
        "localhost:5432",
        "host.docker.internal:5432",
    ]
    for cand in candidates:
        host, _, port = cand.partition(":")
        try:
            with socket.create_connection((host, int(port)), timeout=2):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError, ValueError):
            continue
    return False


pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="needs real DB (set INTEGRATION=1)",
)


@pytest.fixture
def hnsw_bench_setup():
    """检查 DB 可达性 + 引 run_bench.

    本测试在不依赖 conftest fixtures 前提下, 尝试连 localhost:5432.
    若失败 → skip, 不 fail.
    """
    if not _postgres_reachable():
        pytest.skip("postgres not reachable at localhost:5432")
    from scripts.bench_hnsw_params import run_bench  # noqa: WPS433
    return run_bench


def test_run_bench_returns_results_dict(hnsw_bench_setup):
    """跑单 combo, 必须返回 dict 且含正确 key 形式.

    用 knowledge_chunks 表 (W97 PR2 段落级表, 必有 HNSW 索引 ix_*_hnsw).
    实测: knowledge 表无 HNSW 索引 (只有 knowledge_chunks / kg_entities 有),
    沿用章节 §0.4 P1-3 修订版: 必须先验证索引存在, 否则 DROP 失败.
    """
    run_bench = hnsw_bench_setup
    result = run_bench(
        table="knowledge_chunks",  # 实际有 HNSW 索引的表
        m_values=[16],
        ef_construction_values=[64],
        ef_search_values=[40],
        k=10,
        n_queries=10,
    )
    assert isinstance(result, dict)
    assert "m=16,ef_c=64,ef_s=40" in result, f"key mismatch; got keys: {list(result)}"

    combo = result["m=16,ef_c=64,ef_s=40"]
    assert "recall_at_k" in combo
    assert 0.0 <= combo["recall_at_k"] <= 1.0, (
        f"recall_at_k out of range: {combo['recall_at_k']}"
    )
    assert "p50_ms" in combo
    assert "p95_ms" in combo
    assert "n_queries" in combo
    assert combo["n_queries"] >= 1


def test_run_bench_multiple_combos(hnsw_bench_setup):
    """多 combo 跑通 (m 不同), 每个 combo 都返回结构化结果."""
    run_bench = hnsw_bench_setup
    result = run_bench(
        table="knowledge_chunks",
        m_values=[16, 24],
        ef_construction_values=[64],
        ef_search_values=[40],
        k=10,
        n_queries=10,
    )
    assert "m=16,ef_c=64,ef_s=40" in result
    assert "m=24,ef_c=64,ef_s=40" in result

    for key, combo in result.items():
        assert 0.0 <= combo["recall_at_k"] <= 1.0, f"{key} recall invalid"
        assert combo["drop_create_ms"] >= 0, f"{key} drop_create_ms negative"


def test_run_bench_ef_search_only_no_reindex_needed(hnsw_bench_setup):
    """仅 ef_search 维度 (session-level) 时跑通, 不需要 DROP+CREATE 索引."""
    run_bench = hnsw_bench_setup
    result = run_bench(
        table="knowledge_chunks",
        m_values=[16],   # 固定
        ef_construction_values=[64],  # 固定
        ef_search_values=[40, 100],  # 多个 ef_search
        k=10,
        n_queries=5,
    )
    assert "m=16,ef_c=64,ef_s=40" in result
    assert "m=16,ef_c=64,ef_s=100" in result
