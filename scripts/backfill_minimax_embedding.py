"""存量向量全量重建: 旧 1024 列文本 → MiniMax embo-01 → embedding_mm (1536d).

2026-11-17 Embedding 切云端主拍配套脚本。按表逐行读旧列对应的**源文本**,
调云端 embo-01 批量生成, 写入 embedding_mm。失败行跳过并记录, 可重复跑 (幂等:
已写 embedding_mm 的行跳过)。

⚠️ 检索读写两侧必须同时切换: 检索侧 query embedding 也是 embo-01 (embedding_service
EMBEDDING_BACKEND=minimax 已生效), 否则维度不匹配。

用法 (app 容器内):
    python /tmp/backfill_minimax_embedding.py --dry-run    # 只统计
    python /tmp/backfill_minimax_embedding.py --apply      # 回写
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("SKIP_DB_SETUP", "1")

from sqlalchemy import text

from app.core.database import async_session
from app.services.minimax_embedding_service import embed_texts

# (表, 主键列, 旧 embedding 列, 源文本 SQL) — 源文本必须与当初生成旧向量的输入一致语义
# knowledge_chunks: content 是 chunk 原文
# knowledge: title + content 前 2000 字 (与 generate_embedding 调用点同语义)
# meetings: summary (写入点 meeting_analysis_service 用 summary 生成)
# meeting_chunks: content
# 其余按各自写入点源字段
BATCH = 32


async def rows_needing(db, table, pk, src_sql, limit=None):
    sql = f"""
        SELECT {pk} AS pk, ({src_sql}) AS src
        FROM {table}
        WHERE embedding IS NOT NULL AND embedding_mm IS NULL
          AND ({src_sql}) IS NOT NULL AND ({src_sql}) <> ''
        ORDER BY {pk}
    """
    if limit:
        sql += f" LIMIT {limit}"
    r = await db.execute(text(sql))
    return [(row[0], row[1]) for row in r.fetchall()]


async def write_back(db, table, pk_col, ids, vecs):
    for pk, vec in zip(ids, vecs):
        await db.execute(text(
            f"UPDATE {table} SET embedding_mm = CAST(:v AS vector) WHERE {pk_col} = :pk"),
            {"v": "[" + ",".join(f"{x:.8f}" for x in vec) + "]", "pk": pk})
    await db.commit()


TABLES = [
    ("knowledge_chunks", "id", "content"),
    ("knowledge", "id", "left(content, 2000)"),
    ("meetings", "id", "COALESCE(summary, title)"),
    ("meeting_chunks", "id", "content"),
    ("kg_entities", "id", "entity_name"),
    ("knowledge_entities", "id", "COALESCE(object, subject)"),
    ("knowledge_images", "id", "COALESCE(visual_summary, ocr_text)"),
    ("knowledge_page_transcripts", "id", "content"),
    ("memories", "id", "content"),
]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    async with async_session() as db:
        grand_total = 0
        for table, pk, src in TABLES:
            rows = await rows_needing(db, table, pk, src)
            print(f"[{table}] 待重建 {len(rows)} 行", flush=True)
            grand_total += len(rows)
            if not args.apply:
                continue
            done = 0
            for i in range(0, len(rows), BATCH):
                batch = rows[i:i + BATCH]
                texts = [r[1] for r in batch]
                vecs = await embed_texts(texts, text_type="db")
                if not vecs or len(vecs) != len(batch):
                    print(f"  批 {i // BATCH + 1} 失败, 跳过 {len(batch)} 行 (可重跑)", flush=True)
                    continue
                await write_back(db, table, pk, [r[0] for r in batch], vecs)
                done += len(batch)
                if done % (BATCH * 10) == 0:
                    print(f"  进度 {done}/{len(rows)}", flush=True)
            print(f"[{table}] 完成 {done}/{len(rows)}", flush=True)
        print(f"=== 总计 {grand_total} 行 ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
