"""chunk 级多窗口向量回填：chunk 正文按句切窗 → embo-01 → chunk_embedding_mm (1536[]).

2026-11-17 链条收口的配套脚本。原 late-chunking 臂（`chunk_embedding vector(1024)[]`）
依赖本地 Qwen3 的 token 级前向；切云端 embo-01 后无法复现真正的 late chunking，
改为**多窗口向量**：每条 chunk 取 1–3 个 ~300 字窗口（带 60 字重叠），逐窗生成
一个 1536 维向量，存入 `knowledge_chunks.chunk_embedding_mm`。
检索臂语义不变（多向量取最小 cosine distance），向量空间与主检索一致。

幂等：只处理 `chunk_embedding_mm IS NULL` 且已有主向量 `embedding_mm` 的行，可重复跑。

用法（app 容器内）：
    python scripts/backfill_chunk_embedding_mm.py --dry-run
    python scripts/backfill_chunk_embedding_mm.py --apply [--limit N]
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

WINDOW_CHARS = 300
WINDOW_OVERLAP = 60
MAX_WINDOWS = 3
BATCH = 32
SENT_END = "。！？；\n"


def split_windows(content: str) -> list:
    """按句切窗：每窗 ≤300 字、窗间重叠 60 字，最多 3 窗（长文取头/中/尾）。"""
    text_ = (content or "").strip()
    if not text_:
        return []
    if len(text_) <= WINDOW_CHARS:
        return [text_]
    windows = []
    step = WINDOW_CHARS - WINDOW_OVERLAP
    start = 0
    while start < len(text_) and len(windows) < MAX_WINDOWS:
        end = min(start + WINDOW_CHARS, len(text_))
        # 尽量在句末截断，避免把一句话劈开
        if end < len(text_):
            cut = max((text_.rfind(ch, start, end) for ch in SENT_END), default=-1)
            if cut > start + WINDOW_CHARS // 2:
                end = cut + 1
        windows.append(text_[start:end])
        if end >= len(text_):
            break
        start = end - WINDOW_OVERLAP if end - WINDOW_OVERLAP > start else end
    return windows


def to_pg_array(vecs: list) -> list:
    """list[list[float]] → list[str], 每项是 pgvector 文本字面量。

    ⚠️ 不能返回 `{"[..]","[..]"}` 字符串: asyncpg 对 `CAST(:v AS vector[])`
    按数组类型编码参数, 传 str 会报 "a sized iterable container expected"。
    """
    return ["[" + ",".join(f"{x:.8f}" for x in v) + "]" for v in vecs]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    async with async_session() as db:
        sql = (
            "SELECT id, content FROM knowledge_chunks "
            "WHERE chunk_embedding_mm IS NULL AND embedding_mm IS NOT NULL "
            "AND content IS NOT NULL AND content <> '' ORDER BY id"
        )
        if args.limit:
            sql += f" LIMIT {args.limit}"
        rows = (await db.execute(text(sql))).fetchall()
        print(f"[chunk_mm] 待回填 {len(rows)} 行", flush=True)
        if not args.apply:
            for r in rows[:3]:
                ws = split_windows(r[1])
                print(f"  sample id={r[0]} windows={len(ws)} lens={[len(w) for w in ws]}", flush=True)
            return

        done = 0
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            flat, owners = [], []
            for cid, content in batch:
                for w in split_windows(content):
                    flat.append(w)
                    owners.append(cid)
            if not flat:
                continue
            vecs = await embed_texts(flat, text_type="db")
            if not vecs or len(vecs) != len(flat):
                print(f"  批 {i // BATCH + 1} embedding 失败, 跳过 {len(batch)} 行 (可重跑)", flush=True)
                continue
            # 按 chunk 归并
            grouped = {}
            for cid, vec in zip(owners, vecs):
                grouped.setdefault(cid, []).append(vec)
            for cid, vlist in grouped.items():
                await db.execute(text(
                    "UPDATE knowledge_chunks SET chunk_embedding_mm = "
                    "CAST(:v AS vector(1536)[]) WHERE id = :pk"),
                    {"v": to_pg_array(vlist), "pk": cid})
            await db.commit()
            done += len(batch)
            if done % (BATCH * 10) == 0:
                print(f"  进度 {done}/{len(rows)}", flush=True)
        print(f"[chunk_mm] 完成 {done}/{len(rows)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
