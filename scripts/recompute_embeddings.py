"""Embedding 全量重算脚本 (v29 Qwen3-Embedding 切换)

背景:
  alembic 030 迁移加了 embedding_v2 列 (1024d). 本脚本覆盖所有 embedding_v2 IS NULL
  的行, 用当前 EMBEDDING_MODEL_NAME (默认 Qwen3-Embedding-0.6B) 重算并写入.

为什么用同步脚本不用 Celery:
  - 数据规模小 (~350 条), Qwen3 GPU 推理 ~63ms/条, 总耗时 < 30 秒
  - Qwen3 模型已在 app 容器加载 (1168 MB 显存), 直接复用
  - Celery 异步任务需要 NullPool 跨 loop + 独立 redis + retry, 实现复杂
  - Celery 适合 5000+ 条 + 需要断点续传的场景, 当前规模 overkill

用法:
  docker exec microbubble-agent-app-1 python /tmp/recompute_embeddings.py [table]
  不传 table 参数则重算全部 4 张表.
"""
import asyncio
import sys
import time
from typing import Optional

from app.core.database import async_session
from app.core.redis import get_redis
from app.services.embedding_service import generate_embedding
from app.services.embedding_recalc import _get_embedding_text


# 4 张表 + 文本提取函数
TABLES = ["knowledge", "memories", "meetings", "knowledge_entities"]


async def recompute_table(table: str) -> dict:
    """重算单表的 embedding_v2 (WHERE embedding_v2 IS NULL)"""
    from sqlalchemy import select, func

    model_name_map = {
        "knowledge": "Knowledge",
        "memories": "Memory",
        "meetings": "Meeting",
        "knowledge_entities": "KnowledgeEntity",
    }
    from app.models.knowledge import Knowledge
    from app.models.memory import Memory
    from app.models.meeting import Meeting
    from app.models.knowledge_entity import KnowledgeEntity
    Model = {"knowledge": Knowledge, "memories": Memory, "meetings": Meeting,
             "knowledge_entities": KnowledgeEntity}[table]

    redis = await get_redis()
    async with async_session() as db:
        total = await db.scalar(select(func.count(Model.id)))
        pending_q = await db.execute(
            select(Model.id).where(Model.embedding_v2.is_(None))
        )
        row_ids = [r[0] for r in pending_q.fetchall()]
        if not row_ids:
            return {"table": table, "total": total, "done": 0, "skipped": 0,
                    "failed": 0, "pending": 0}

        done = failed = skipped = 0
        for i, row_id in enumerate(row_ids, 1):
            row = await db.get(Model, row_id)
            if row is None:
                skipped += 1
                continue
            if row.embedding_v2 is not None:
                skipped += 1
                continue
            text = _get_embedding_text(table, row)
            if not text:
                skipped += 1
                continue
            text = text[:6000]  # 截断超长文本
            embedding = await generate_embedding(text)
            if embedding and len(embedding) == 1024:
                row.embedding_v2 = embedding
                await db.commit()
                done += 1
            else:
                failed += 1
                logger_msg = f"[{table}] {row_id}: dim={len(embedding) if embedding else 0} (期望 1024)"
                print(f"  ⚠️ 失败: {logger_msg}")
            if i % 20 == 0:
                print(f"  [{table}] 进度: {i}/{len(row_ids)}, done={done}, skipped={skipped}, failed={failed}")

        # 写最终进度到 Redis
        try:
            completed = total - len(row_ids) + done + skipped
            percent = round(completed / total * 100, 1) if total > 0 else 0
            import json
            await redis.set(
                f"embedding_recompute:progress:{table}",
                json.dumps({"table": table, "done": completed, "total": total, "percent": percent}),
                ex=86400,
            )
        except Exception as e:
            print(f"  ⚠️ 写 Redis 进度失败: {e}")

        return {"table": table, "total": total, "done": done,
                "skipped": skipped, "failed": failed}


async def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tables = [only] if only else TABLES

    print(f"=== 开始重算 (同步模式, Qwen3 已在 app 容器加载) ===")
    print(f"目标表: {tables}")
    print()
    t_total = time.time()
    summary = []
    for table in tables:
        print(f"--- {table} ---")
        t0 = time.time()
        result = await recompute_table(table)
        elapsed = time.time() - t0
        result["elapsed_sec"] = round(elapsed, 1)
        summary.append(result)
        print(f"  ✅ {table}: {result}")
        print()

    total_time = time.time() - t_total
    total_done = sum(r["done"] for r in summary)
    total_failed = sum(r["failed"] for r in summary)
    print(f"=== 重算完成: 总耗时 {total_time:.1f}s, 成功 {total_done}, 失败 {total_failed} ===")
    print()
    print("验证 (SELECT COUNT):")
    print("  SELECT 'knowledge', COUNT(*) AS total, COUNT(embedding_v2) AS done FROM knowledge")
    print("  -- 期望 done = total (100%)")


if __name__ == "__main__":
    asyncio.run(main())
