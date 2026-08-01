"""RAG 索引一键重建 CLI (W101 P1 派工)

用法:
    python scripts/reindex_all.py --table knowledge
    python scripts/reindex_all.py --table all
    python scripts/reindex_all.py --table knowledge --batch-size 50 --dry-run

功能:
    1. embedding 重建 — 复用 app.services.embedding_recalc.recalc_all_embeddings (Celery)
    2. BM25 重建 — 复用 app.services.bm25_service.get_bm25_service().build_index
    3. tsvector — alembic 089 GENERATED ALWAYS AS, 入库自动重算, **无需单独重建**

边界:
    - 不动 alembic schema
    - 不动前端
    - 仅 orchestrator, 复用现有库 (4a 老核心 unchanged)

Redis 进度键:
    embedding_recompute:progress:{table} — 与 embedding_recalc.py 命名一致 (避免 E10 命名冲突)
"""
import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("reindex_all")


# 支持的表 — 与 embedding_recalc.py TABLE_TO_MODEL 对齐
SUPPORTED_TABLES = ["knowledge", "memories", "meetings", "knowledge_entities", "knowledge_chunks"]


def parse_args() -> argparse.Namespace:
    """CLI 参数解析 (E18 防御: argparse 严格校验)"""
    parser = argparse.ArgumentParser(
        description="RAG 索引一键重建 (embedding + BM25 + tsvector)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--table",
        type=str,
        required=True,
        help=f"目标表, 逗号分隔多表, 或 'all' 表示全部 (可选: {', '.join(SUPPORTED_TABLES)})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="embedding 重建的批大小 (默认 50, 与 embedding_recalc 一致)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印计划, 不实际执行 (E11 防御: dry-run 必须真实现)",
    )
    parser.add_argument(
        "--skip-bm25",
        action="store_true",
        help="跳过 BM25 重建 (默认重建)",
    )
    return parser.parse_args()


def resolve_tables(table_arg: str) -> List[str]:
    """解析 --table 参数

    Returns:
        列表, 至少 1 个表; 不在 SUPPORTED_TABLES 的表报错
    """
    raw = table_arg.strip().lower()
    if raw == "all":
        return list(SUPPORTED_TABLES)
    tables = [t.strip() for t in raw.split(",") if t.strip()]
    for t in tables:
        if t not in SUPPORTED_TABLES:
            raise ValueError(
                f"未知表 '{t}'. 支持: {', '.join(SUPPORTED_TABLES)}"
            )
    return tables


def plan_embedding_recalc(tables: List[str], batch_size: int) -> List[Dict]:
    """规划 embedding 重建 (E11 dry-run 守恒: dry-run 时只 plan 不执行)"""
    plan = []
    for t in tables:
        plan.append({
            "step": "embedding_recalc",
            "table": t,
            "batch_size": batch_size,
            "endpoint": "app.services.embedding_recalc.recalc_all_embeddings",
            "redis_key": f"embedding_recompute:progress:{t}",
        })
    return plan


def plan_bm25_rebuild(tables: List[str]) -> List[Dict]:
    """规划 BM25 重建

    仅 knowledge / knowledge_chunks 参与 BM25 索引 (符合 bm25_service 实际使用场景)
    """
    bm25_tables = [t for t in tables if t in ("knowledge", "knowledge_chunks")]
    plan = []
    for t in bm25_tables:
        plan.append({
            "step": "bm25_rebuild",
            "table": t,
            "endpoint": "app.services.bm25_service.get_bm25_service().build_index",
        })
    return plan


def plan_tsvector_note(tables: List[str]) -> List[Dict]:
    """tsvector 规划说明 (alembic 089 GENERATED 列, 入库自动重算, 无需操作)"""
    if "knowledge" in tables:
        return [{
            "step": "tsvector",
            "table": "knowledge",
            "note": "alembic 089 GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED — 入库自动重算, 无需手动重建",
            "action": "noop",
        }]
    return []


def execute_embedding_recalc(table: str, batch_size: int) -> Dict:
    """执行 Celery 任务派发 (E08 防御: 真派任务, 不假实现)

    Returns:
        Celery 派发结果 dict (dispatched/total/pending)
    """
    try:
        from app.services.embedding_recalc import recalc_all_embeddings
    except ImportError as e:
        logger.warning(f"无法导入 embedding_recalc (可能不在 docker 环境): {e}")
        return {"table": table, "error": "import_failed", "note": "需在 docker 容器内执行"}

    logger.info(f"派发 embedding 重建: table={table}, batch_size={batch_size}")
    result = recalc_all_embeddings.delay(table, batch_size=batch_size)
    # Celery AsyncResult; 不阻塞等待 (用户可另起 reindex_monitor.py 跟踪)
    return {
        "table": table,
        "task_id": str(result.id) if hasattr(result, "id") else None,
        "batch_size": batch_size,
    }


def execute_bm25_rebuild(table: str) -> Dict:
    """执行 BM25 索引重建 (E09 防御: bm25_service 真重建)"""
    try:
        from app.services.bm25_service import get_bm25_service
        from app.core.database import async_session
        from sqlalchemy import select
    except ImportError as e:
        logger.warning(f"无法导入 bm25_service: {e}")
        return {"table": table, "error": "import_failed"}

    async def _build():
        # 仅 knowledge 表重建 BM25 (knowledge_chunks 暂未接入 BM25)
        if table != "knowledge":
            return {"table": table, "skipped": "BM25 仅支持 knowledge 表"}
        from app.models.knowledge import Knowledge
        async with async_session() as db:
            result = await db.execute(select(Knowledge.id, Knowledge.title, Knowledge.content))
            rows = result.fetchall()
            docs = [{"id": r[0], "title": r[1] or "", "content": r[2] or ""} for r in rows]
        bm25 = get_bm25_service()
        bm25.build_index(docs)
        return {"table": table, "bm25_docs": len(docs)}

    return asyncio.run(_build())


def main() -> int:
    args = parse_args()
    try:
        tables = resolve_tables(args.table)
    except ValueError as e:
        logger.error(str(e))
        return 2

    logger.info(f"=== RAG 索引重建 ===")
    logger.info(f"目标表: {tables}")
    logger.info(f"batch_size: {args.batch_size}")
    logger.info(f"dry_run: {args.dry_run}")
    logger.info(f"skip_bm25: {args.skip_bm25}")

    # 规划三步
    embed_plan = plan_embedding_recalc(tables, args.batch_size)
    bm25_plan = [] if args.skip_bm25 else plan_bm25_rebuild(tables)
    tsvec_plan = plan_tsvector_note(tables)

    # 打印计划
    logger.info(f"--- 计划 ---")
    for p in embed_plan + bm25_plan + tsvec_plan:
        logger.info(f"  {p}")

    if args.dry_run:
        logger.info("=== DRY-RUN 结束 (无实际操作) ===")
        return 0

    # 执行
    t0 = time.time()
    summary = {"embedding": [], "bm25": [], "tsvector": tsvec_plan}

    for p in embed_plan:
        result = execute_embedding_recalc(p["table"], p["batch_size"])
        summary["embedding"].append(result)
        logger.info(f"  embedding 派发: {result}")

    for p in bm25_plan:
        result = execute_bm25_rebuild(p["table"])
        summary["bm25"].append(result)
        logger.info(f"  bm25 重建: {result}")

    elapsed = round(time.time() - t0, 1)
    logger.info(f"=== 重建完成: 耗时 {elapsed}s ===")
    logger.info(f"summary: {json.dumps(summary, ensure_ascii=False, default=str)}")
    logger.info(f"监控进度: python scripts/reindex_monitor.py --table {args.table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
