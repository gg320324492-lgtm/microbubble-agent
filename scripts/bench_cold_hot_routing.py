"""W-N-E +2 PoC: 冷热分层路由层性能实测

> **范畴**: scripts/bench_cold_hot_routing.py
> **目的**: 实测 hot/cold query 平均延迟, 验证 PoC 决策门禁
> **决策门禁** (派工 brief 严禁跳过):
>   1. hot < 50ms? → 继续 / 暂停
>   2. cold < 500ms? → 继续 / 暂停
>   3. cold 占总查询比例 > 10%? → 启动 E.1 / 整段归档

实测策略 (W-N-E 据实上报):
- 由于当前 knowledge 库 530 行 100% hot (oldest 2026-05-17, NOW()-6m=2026-02-05), 真实 cold = 0 行
- 派工 brief 第 3 门禁 "cold > 10%" 在当前数据下必然 FAIL (0/530 = 0%)
- bench 仍忠实跑 3 类 query:
  - HOT query: knowledge 全表 (模拟 hot partition, HNSW 走)
  - COLD query: 强制 WHERE created_at < '2020-01-01' (空集, latency 极低但无意义)
  - ALL query: 知识全表无过滤 (baseline)
- 决策报告据实标注: PoC 代码完整跑通, 但 cold 数据缺失 → 第 3 门禁 FAIL → 归档
"""
from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import List, Tuple

import asyncpg

# 派工 brief 决策门禁常量
HOT_P50_LIMIT_MS = 50.0
COLD_P95_LIMIT_MS = 500.0
COLD_PROPORTION_THRESHOLD = 0.10  # 10%

# 默认配置
DEFAULT_N_QUERIES = 100
DEFAULT_LIMIT = 100
DEFAULT_THRESHOLD_MONTHS = 6

# 结果输出路径
RESULTS_DIR = Path(__file__).parent.parent / "results"
OUTPUT_FILE = RESULTS_DIR / "cold_hot_routing_bench_2026-08.json"


def get_dsn() -> str:
    """从 env 拿 DATABASE_URL, 默认 localhost:5432 (host 跑 bench)."""
    url = os.getenv("DATABASE_URL_BENCH")
    if url:
        return url
    # 容器内 db:5432 vs host localhost:5432
    if os.path.exists("/.dockerenv"):
        return "postgresql://postgres:microbubble2026@db:5432/microbubble"
    return "postgresql://postgres:microbubble2026@localhost:5432/microbubble"


# SQL 模板 (派工 brief 范畴: 0 schema 改动, 仅查询路径)
HOT_SQL = """
SELECT id, title, content, category
FROM knowledge
WHERE deleted_at IS NULL
  AND created_at > NOW() - INTERVAL '6 months'
ORDER BY created_at DESC
LIMIT 100
"""

COLD_SQL = """
SELECT id, title, content, category
FROM knowledge
WHERE deleted_at IS NULL
  AND created_at <= NOW() - INTERVAL '6 months'
ORDER BY created_at DESC
LIMIT 100
"""

# 模拟 cold query: 在 hot partition 上跑 (因为真实 cold = 0, 测 seq scan 性能)
# 用 ILIKE 强制全表扫, 模拟 cold partition seq scan 行为
COLD_SEQ_SCAN_SQL = """
SELECT id, title, content, category
FROM knowledge
WHERE deleted_at IS NULL
  AND content ILIKE '%气泡%'
ORDER BY created_at DESC
LIMIT 100
"""

ALL_SQL = """
SELECT id, title, content, category
FROM knowledge
WHERE deleted_at IS NULL
ORDER BY created_at DESC
LIMIT 100
"""


async def bench_query(
    pool: asyncpg.Pool,
    sql: str,
    n_queries: int,
    label: str,
) -> Tuple[List[float], int]:
    """跑 n_queries 次 query, 返回 (latencies_ms, n_returned)."""
    latencies: List[float] = []
    n_returned = 0
    for i in range(n_queries):
        t0 = time.perf_counter()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)
        n_returned = len(rows)
    return latencies, n_returned


def percentiles(latencies: List[float]) -> dict:
    """计算 P50 / P95 / P99 / avg / min / max / stdev."""
    if not latencies:
        return {"n": 0}
    s = sorted(latencies)
    n = len(s)
    return {
        "n": n,
        "min_ms": min(s),
        "max_ms": max(s),
        "avg_ms": statistics.mean(s),
        "median_ms": statistics.median(s),
        "p50_ms": s[int(n * 0.50)],
        "p95_ms": s[int(n * 0.95)],
        "p99_ms": s[int(n * 0.99)],
        "stdev_ms": statistics.stdev(s) if n > 1 else 0.0,
    }


async def main() -> dict:
    dsn = get_dsn()
    n_queries = int(os.getenv("BENCH_N_QUERIES", DEFAULT_N_QUERIES))

    print(f"[W-N-E bench] DSN: {dsn}")
    print(f"[W-N-E bench] N_QUERIES: {n_queries}")

    # 1. 验证 DB 可达
    pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
    try:
        n_total = await pool.fetchval("SELECT COUNT(*) FROM knowledge")
        n_hot = await pool.fetchval(
            "SELECT COUNT(*) FROM knowledge WHERE created_at > NOW() - INTERVAL '6 months'"
        )
        n_cold = await pool.fetchval(
            "SELECT COUNT(*) FROM knowledge WHERE created_at <= NOW() - INTERVAL '6 months'"
        )
        print(f"[W-N-E bench] knowledge table: total={n_total} hot={n_hot} cold={n_cold}")
    except Exception as e:
        print(f"[W-N-E bench] ERROR: cannot reach DB: {e}")
        await pool.close()
        raise

    # 2. 跑 4 类 query
    results = {}
    for label, sql in [
        ("hot_partition", HOT_SQL),
        ("cold_partition", COLD_SQL),
        ("cold_seq_scan_simulation", COLD_SEQ_SCAN_SQL),
        ("all_no_filter", ALL_SQL),
    ]:
        print(f"[W-N-E bench] running {label} ...")
        latencies, n_returned = await bench_query(pool, sql, n_queries, label)
        stats = percentiles(latencies)
        stats["n_rows_returned"] = n_returned
        results[label] = stats
        print(
            f"  -> p50={stats.get('p50_ms', 0):.3f}ms "
            f"p95={stats.get('p95_ms', 0):.3f}ms "
            f"p99={stats.get('p99_ms', 0):.3f}ms "
            f"n_returned={n_returned}"
        )

    await pool.close()

    # 3. 决策门禁
    hot_p50 = results["hot_partition"].get("p50_ms", float("inf"))
    cold_p95 = results["cold_seq_scan_simulation"].get("p95_ms", float("inf"))
    cold_real_count = n_cold  # 真实 cold 行数 (派工 brief 严禁跳过)
    cold_proportion = (cold_real_count / n_total) if n_total > 0 else 0.0

    decisions = {
        "gate_1_hot_p50_under_50ms": {
            "value_ms": hot_p50,
            "limit_ms": HOT_P50_LIMIT_MS,
            "pass": hot_p50 < HOT_P50_LIMIT_MS,
        },
        "gate_2_cold_p95_under_500ms": {
            "value_ms": cold_p95,
            "limit_ms": COLD_P95_LIMIT_MS,
            "pass": cold_p95 < COLD_P95_LIMIT_MS,
        },
        "gate_3_cold_proportion_above_10pct": {
            "value_pct": cold_proportion * 100,
            "threshold_pct": COLD_PROPORTION_THRESHOLD * 100,
            "n_cold": cold_real_count,
            "n_total": n_total,
            "pass": cold_proportion > COLD_PROPORTION_THRESHOLD,
        },
    }

    # 总体决策
    all_pass = all(d["pass"] for d in decisions.values())
    decisions["overall"] = {
        "all_pass": all_pass,
        "recommendation": (
            "E.1 物理分区可启动" if all_pass
            else "PoC 价值不大, 据实归档阶段 E (cold 数据缺失, 路由层代码保留)"
        ),
    }

    output = {
        "metadata": {
            "table": "knowledge",
            "n_queries": n_queries,
            "n_total_rows": n_total,
            "n_hot_rows": n_hot,
            "n_cold_rows": n_cold,
            "threshold_months": DEFAULT_THRESHOLD_MONTHS,
            "decision_gates": {
                "hot_p50_ms_limit": HOT_P50_LIMIT_MS,
                "cold_p95_ms_limit": COLD_P95_LIMIT_MS,
                "cold_proportion_threshold": COLD_PROPORTION_THRESHOLD,
            },
        },
        "results": results,
        "decisions": decisions,
    }

    # 4. 写 JSON
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[W-N-E bench] WROTE: {OUTPUT_FILE}")
    print(f"[W-N-E bench] DECISIONS:")
    for k, v in decisions.items():
        if k == "overall":
            print(f"  overall: {v}")
        else:
            print(f"  {k}: pass={v['pass']} value={v}")

    return output


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
