"""HNSW 参数网格扫参工具 (阶段 A.1 + A.2 + A.3)

用法:
    python scripts/bench_hnsw_params.py --help
    python scripts/bench_hnsw_params.py --table knowledge --param-grid ef_search --k 10 --n-queries 50

设计目标: 通过 grid sweep 找出 recall >= 0.95 且 p95 最低的 HNSW 参数组合.
ground truth: 对每个 query 全表 cosine brute-force 当 oracle.

**重要**: pgvector HNSW 的 `m` 和 `ef_construction` 是**构建时参数**, 不可通过
`ALTER INDEX SET` 改 (实测是 no-op 或报错). 必须 DROP INDEX + CREATE INDEX.

见 plan §0.4 P1-3 + plan §2 阶段 A.4 步骤 3.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from itertools import product
from typing import Any, Dict, List, Sequence

import numpy as np
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# === 任务 A.2: recall@k 计算 (W-N-A +2) ===

def compute_recall_at_k(
    predicted: Sequence[Sequence[int]],
    ground_truth: Sequence[Sequence[int]],
    k: int,
) -> float:
    """单 query 集合的 mean recall@k.

    对每个 query, 截取 predicted[:k] 与 ground_truth 求交, recall = |交集| / |ground_truth|;
    返回所有 query recall 的算术平均.

    Args:
        predicted: 每个 query 的 top-k 命中 id 列表 (长度 == len(ground_truth))
        ground_truth: 每个 query 的真实相关 id 集合
        k: top-k 截断 (避免 predicted 包含额外 ID 干扰)

    Returns:
        0.0 ~ 1.0, 若 predicted/ground_truth 都为空则返回 0.0
    """
    assert k > 0, f"k must be positive, got {k}"
    assert len(predicted) == len(ground_truth), (
        f"predicted/ground_truth length mismatch: "
        f"{len(predicted)} vs {len(ground_truth)}"
    )
    recalls: List[float] = []
    for pred, truth in zip(predicted, ground_truth):
        pred_set = set(pred[:k])
        truth_set = set(truth)
        if not truth_set:
            continue
        recalls.append(len(pred_set & truth_set) / len(truth_set))
    return float(np.mean(recalls)) if recalls else 0.0


# === 任务 A.3: 真实 DB 召回评估 (W-N-A +3) ===

# 默认网格
DEFAULT_M_VALUES: List[int] = [16, 24, 32, 48]
DEFAULT_EF_CONSTRUCTION_VALUES: List[int] = [64, 128, 256]
DEFAULT_EF_SEARCH_VALUES: List[int] = [40, 100, 200]

# 表名 → embedding 列名映射
TABLE_EMB_COLUMN: Dict[str, str] = {
    "knowledge": "embedding",
    "knowledge_chunks": "embedding",
    "meetings": "embedding",
    "members": "voice_embedding",
    "memories": "embedding",  # 长期记忆, 实测 29 行有 embedding + HNSW 索引 idx_memories_embedding
}

# 已知的 HNSW 索引名 (实测 schema, plan §0.4 P1-3 修订版来源)
# 注意: 实测索引名前缀不一致 (knowledge/meetings/memories/members 用 idx_*,
# kg_entities/knowledge_chunks 用 ix_*_hnsw). bench 函数动态 fetch.
TABLE_HNSW_INDEX: Dict[str, str] = {
    "knowledge": "idx_knowledge_embedding",
    "knowledge_chunks": "ix_knowledge_chunks_embedding_hnsw",
    "meetings": "idx_meetings_embedding",
    "members": "idx_member_voice_embedding",
    "memories": "idx_memories_embedding",
}


async def run_bench(
    table: str,
    m_values: List[int],
    ef_construction_values: List[int],
    ef_search_values: List[int],
    k: int,
    n_queries: int,
    database_url: str | None = None,
) -> Dict[str, Dict[str, Any]]:
    """对一组 HNSW 参数组合跑真实召回/延迟评估.

    Ground truth: 对每个 query 跑全表 cosine 顺序扫描当 oracle.

    流程 (plan §0.4 P1-3 修订版):
    1. 抽 n_queries 个 sample rows (有 embedding) + 缓存 embedding
    2. 对每组合 (m, ef_c, ef_s):
       a. DROP + CREATE INDEX 应用新 m/ef_construction (锁表, 选低峰期)
       b. SET hnsw.ef_search = ef_s (session-level)
       c. 跑 HNSW top-k 查询, 收集 predicted[] + latencies[]
       d. 跑 brute-force ORDER BY embedding <=> :q LIMIT :k 收集 ground_truth[]
       e. compute_recall_at_k + np.percentile(p50/p95)

    Returns:
        {combo_key: {m, ef_construction, ef_search, recall_at_k, p50_ms, p95_ms, n_queries, drop_create_ms}}

    Args:
        database_url: 覆盖 settings.DATABASE_URL. 测试可注入, 主流程走 settings.
    """
    if database_url is None:
        from app.config import settings
        database_url = settings.DATABASE_URL

    db_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, pool_size=5)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    emb_col = TABLE_EMB_COLUMN.get(table)
    if emb_col is None:
        raise ValueError(f"unsupported table {table!r}; valid: {list(TABLE_EMB_COLUMN)}")
    index_name = TABLE_HNSW_INDEX.get(table)
    if index_name is None:
        raise ValueError(f"unknown HNSW index for table {table!r}")

    results: Dict[str, Dict[str, Any]] = {}
    try:
        async with Session() as db:
            # 0. 探测列类型 → 选 ops class (halfvec_cosine_ops vs vector_cosine_ops)
            col_type_row = await db.execute(sql_text(f"""
                SELECT udt_name FROM information_schema.columns
                WHERE table_name = :t AND column_name = :c
            """), {"t": table, "c": emb_col})
            udt = col_type_row.scalar()
            if udt == "halfvec":
                ops_class = "halfvec_cosine_ops"
            elif udt == "vector":
                ops_class = "vector_cosine_ops"
            else:
                raise ValueError(f"unsupported embedding type {udt!r} for {table}.{emb_col}")

            # 1. 抽 n_queries 个 sample rows (pgvector asyncpg 必须 string 传 embedding)
            sample_rows = await db.execute(sql_text(f"""
                SELECT id, {emb_col}::text AS emb_text
                FROM {table}
                WHERE {emb_col} IS NOT NULL
                ORDER BY random() LIMIT :n
            """), {"n": n_queries})
            rows = sample_rows.fetchall()
            samples: List[tuple] = []
            for r in rows:
                emb = r.emb_text
                if isinstance(emb, str):
                    samples.append((r.id, emb))
                else:
                    samples.append((r.id, list(emb)))

            if not samples:
                logger.warning("no samples found for table=%s, skipping bench", table)
                return results

            logger.info(
                "running bench table=%s index=%s ops=%s n_queries=%d",
                table, index_name, ops_class, len(samples),
            )

            for m, ef_c, ef_s in product(m_values, ef_construction_values, ef_search_values):
                key = f"m={m},ef_c={ef_c},ef_s={ef_s}"
                logger.info("benchmarking %s ...", key)
                t_drop = time.perf_counter()
                # 2a. DROP + CREATE (REQUIRED for m change — ALTER INDEX SET no-op)
                await db.execute(sql_text(f"DROP INDEX IF EXISTS {index_name};"))
                await db.execute(sql_text(f"""
                    CREATE INDEX {index_name}
                    ON {table}
                    USING hnsw ({emb_col} {ops_class})
                    WITH (m = {m}, ef_construction = {ef_c});
                """))
                # 2b. SET hnsw.ef_search (session-level)
                await db.execute(sql_text(f"SET hnsw.ef_search = {ef_s};"))

                # 2c. HNSW 检索 (embedding 传 str 让 pgvector asyncpg 接受)
                latencies: List[float] = []
                predicted: List[List[int]] = []
                for _, sample_emb in samples:
                    t0 = time.perf_counter()
                    res = await db.execute(sql_text(f"""
                        SELECT id FROM {table}
                        ORDER BY {emb_col} <=> :q LIMIT :k
                    """), {"q": sample_emb, "k": k})
                    latencies.append((time.perf_counter() - t0) * 1000)
                    predicted.append([r[0] for r in res.fetchall()])

                # 2d. brute-force ground truth
                ground_truth: List[List[int]] = []
                for _, sample_emb in samples:
                    gt_res = await db.execute(sql_text(f"""
                        SELECT id FROM {table}
                        WHERE {emb_col} IS NOT NULL
                        ORDER BY {emb_col} <=> :q LIMIT :k
                    """), {"q": sample_emb, "k": k})
                    ground_truth.append([r[0] for r in gt_res.fetchall()])

                drop_create_ms = (time.perf_counter() - t_drop) * 1000
                results[key] = {
                    "m": m,
                    "ef_construction": ef_c,
                    "ef_search": ef_s,
                    "recall_at_k": compute_recall_at_k(predicted, ground_truth, k),
                    "p50_ms": float(np.percentile(latencies, 50)),
                    "p95_ms": float(np.percentile(latencies, 95)),
                    "n_queries": len(samples),
                    "drop_create_ms": drop_create_ms,
                }
                logger.info(
                    "  recall@%d=%.3f p50=%.1fms p95=%.1fms drop+create=%.0fms",
                    k, results[key]["recall_at_k"],
                    results[key]["p50_ms"], results[key]["p95_ms"],
                    drop_create_ms,
                )
        return results
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HNSW 参数网格扫参 (阶段 A.1 + A.2 + A.3)"
    )
    parser.add_argument(
        "--table",
        required=True,
        choices=list(TABLE_EMB_COLUMN.keys()),
        help="待扫参表 (含 knowledge_chunks: W97 PR2 段落级表)",
    )
    parser.add_argument(
        "--param-grid",
        required=True,
        help="逗号分隔, 例 'm,ef_construction', 'ef_search', 'm,ef_construction,ef_search'",
    )
    parser.add_argument("--k", type=int, default=10, help="recall@k")
    parser.add_argument("--n-queries", type=int, default=100, help="采样 query 数")
    parser.add_argument(
        "--output",
        default="results/hnsw_bench.json",
        help="结果 JSON 路径",
    )
    parser.add_argument(
        "--m-values",
        default=",".join(str(x) for x in DEFAULT_M_VALUES),
        help="m 候选值 (逗号分隔)",
    )
    parser.add_argument(
        "--ef-construction-values",
        default=",".join(str(x) for x in DEFAULT_EF_CONSTRUCTION_VALUES),
        help="ef_construction 候选值",
    )
    parser.add_argument(
        "--ef-search-values",
        default=",".join(str(x) for x in DEFAULT_EF_SEARCH_VALUES),
        help="ef_search 候选值 (session-level)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    m_vals = [int(x) for x in args.m_values.split(",") if x.strip()]
    ef_c_vals = [int(x) for x in args.ef_construction_values.split(",") if x.strip()]
    ef_s_vals = [int(x) for x in args.ef_search_values.split(",") if x.strip()]

    logger.info(
        "Bench table=%s grid=[%s] k=%d n_queries=%d",
        args.table, args.param_grid, args.k, args.n_queries,
    )
    logger.info(
        "  m values=%s ef_c values=%s ef_s values=%s",
        m_vals, ef_c_vals, ef_s_vals,
    )

    # 仅当 axes 含 'm' 或 'ef_construction' 时需要 DROP+CREATE INDEX (锁表)
    needs_reindex = "m" in args.param_grid or "ef_construction" in args.param_grid

    # axes 含 m → 传 m_values; 含 ef_c → 传 ef_c; 否则传单个默认
    results = await run_bench(
        table=args.table,
        m_values=m_vals if "m" in args.param_grid else [DEFAULT_M_VALUES[1]],  # 24
        ef_construction_values=(
            ef_c_vals if "ef_construction" in args.param_grid
            else [DEFAULT_EF_CONSTRUCTION_VALUES[1]]
        ),  # 128
        ef_search_values=(
            ef_s_vals if "ef_search" in args.param_grid
            else [DEFAULT_EF_SEARCH_VALUES[0]]
        ),  # 40
        k=args.k,
        n_queries=args.n_queries,
    )

    payload = {
        "table": args.table,
        "param_grid": args.param_grid,
        "k": args.k,
        "n_queries": args.n_queries,
        "needs_reindex": needs_reindex,
        "results": results,
    }

    out_path = args.output
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"✅ wrote bench results to {out_path} ({len(results)} combos)")


if __name__ == "__main__":
    asyncio.run(main())
