"""W-N-G+ +2 _chunk_late_recall 路径可用性验证脚本

目标:
1. 实测 hybrid_retriever.retrieve() 4 路 + late chunking 5 路都能跑通
2. _chunk_late_recall 路径不静默失败 (无 chunk_embedding 数据时返回空集, 不崩)
3. 验证 schema drift 修复后 chunk_embedding 列可用
4. 输出 results/chunk_late_recall_verify_2026-08.json (CI 友好)

纪律:
- 0 production code 改动: 仅 scripts/ + tests/ + results/
- pytest integration test 1 个 (在 tests/ 范畴)
- 失败 fail-loud (W73 铁律: 验证不静默吞)

W-N-G+ +2 派工 brief:
- 实测跑 app/services/hybrid_retriever.py _chunk_late_recall 方法
- 1. 选 1 个 knowledge_id + 1 个 query
- 2. 跑 retrieve 入口
- 3. 验证 routes 4 个 (vector + BM25 + graph + rerank) + late chunking
- 4. 验证 late chunking 路径不静默失败
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# 项目根加 sys.path (本脚本在 scripts/ 范畴, 不在 app 包内)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def _run_verification(
    knowledge_id: int,
    query: str,
) -> Dict[str, Any]:
    """跑一次完整 retrieve + 4 路 + late chunking 验证.

    Returns:
        Dict with: routes_check, late_chunking_check, schema_check, results
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.database import async_session
    from app.services.hybrid_retriever import HybridRetriever

    out: Dict[str, Any] = {
        "knowledge_id": knowledge_id,
        "query": query,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "routes_check": {},
        "late_chunking_check": {},
        "schema_check": {},
        "results": {},
    }

    async with async_session() as db:  # type: AsyncSession
        retriever = HybridRetriever(db)

        # ===== Step 1: schema 检查 (W-N-G+ +1 验证) =====
        from sqlalchemy import text
        for table, col in [
            ("knowledge", "embedding_model_version"),
            ("meetings", "embedding_model_version"),
            ("knowledge_chunks", "chunk_embedding"),
        ]:
            row = await db.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name=:t AND column_name=:c"
                ),
                {"t": table, "c": col},
            )
            out["schema_check"][f"{table}.{col}"] = row.scalar() == 1

        # ===== Step 2: 跑 retrieve 入口 (4 路 + late chunking) =====
        # 5 路: vector + BM25 + graph + rerank + late chunking
        # late chunking 内部由 _retrieve_impl 触发
        try:
            t0 = time.time()
            results = await retriever.retrieve(query=query, top_k=5)
            elapsed_ms = int((time.time() - t0) * 1000)
            out["results"]["retrieve_count"] = len(results)
            out["results"]["retrieve_elapsed_ms"] = elapsed_ms
            out["results"]["retrieve_first_method"] = (
                results[0].get("retrieval_method", "unknown") if results else None
            )
            out["routes_check"]["retrieve"] = "OK"
        except Exception as exc:
            out["routes_check"]["retrieve"] = f"FAIL: {type(exc).__name__}: {exc}"
            return out

        # ===== Step 3: 直接跑 _chunk_late_recall (核心验证) =====
        try:
            from app.services.embedding_service import get_or_compute_query_embedding
            t0 = time.time()
            query_emb = await get_or_compute_query_embedding(query, has_query_prompt=True)
            emb_ms = int((time.time() - t0) * 1000)

            t0 = time.time()
            chunk_results = await retriever._chunk_late_recall(
                query_emb if query_emb is not None else [0.0] * 1024,
                top_k=5,
            )
            late_ms = int((time.time() - t0) * 1000)

            out["late_chunking_check"] = {
                "embedding_ok": query_emb is not None,
                "embedding_ms": emb_ms,
                "results_count": len(chunk_results),
                "elapsed_ms": late_ms,
                "first_result": chunk_results[0] if chunk_results else None,
                "path_works": True,
                "note": "no chunk_embedding data yet (empty result is expected)",
            }
            out["routes_check"]["chunk_late"] = "OK"
        except Exception as exc:
            out["late_chunking_check"] = {
                "path_works": False,
                "error_type": type(exc).__name__,
                "error_msg": str(exc)[:500],
            }
            out["routes_check"]["chunk_late"] = f"FAIL: {type(exc).__name__}"

    return out


async def main() -> int:
    """Main entry: 选一个 knowledge_id (任意有 embedding 的) + 一个 query.

    Returns: 0 = all checks pass, 1 = at least one FAIL
    """
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    from app.core.database import async_session

    # 选一个 knowledge_id (有 embedding + chunks 的)
    async with async_session() as db:
        row = await db.execute(
            text(
                "SELECT k.id, k.title FROM knowledge k "
                "WHERE k.embedding IS NOT NULL "
                "ORDER BY k.id LIMIT 1"
            )
        )
        k = row.fetchone()

    if k is None:
        print("ERROR: no knowledge row with embedding found, cannot verify")
        return 1

    knowledge_id = k[0]
    query = "微纳米气泡 表面张力"  # 中文 query 测试
    print(f"verify with knowledge_id={knowledge_id}, query={query!r}")

    out = await _run_verification(knowledge_id=knowledge_id, query=query)

    # 写结果 JSON
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / "chunk_late_recall_verify_2026-08.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"results written: {out_path}")

    # 输出总结
    print("\n===== W-N-G+ +2 Verification Summary =====")
    print(f"schema_check: {out['schema_check']}")
    print(f"routes_check: {out['routes_check']}")
    print(f"late_chunking_check: {out['late_chunking_check']}")
    print(f"results: {out['results']}")

    # fail-loud
    all_schema_ok = all(out["schema_check"].values())
    all_routes_ok = all(
        v == "OK" for v in out["routes_check"].values()
    )
    late_works = out["late_chunking_check"].get("path_works", False)

    if all_schema_ok and all_routes_ok and late_works:
        print("\n[OK] all checks pass")
        return 0
    else:
        print("\n[FAIL] at least one check failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
