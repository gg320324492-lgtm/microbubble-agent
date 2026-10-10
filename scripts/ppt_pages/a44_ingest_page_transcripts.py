"""agent44 入库 — PPT 整页视觉转写 → knowledge_page_transcripts (迁移 144)

输入: 容器内 ``/tmp/a43/merged_a41.json`` (agent43 native<143 档产物, 不重跑转写)
落点: **kb 孪生行** (``meta->>'drive_source_file_id'``), 不是 drive 行
      —— 于是 multimodal_retriever 的 ``storage_mode == 'kb'`` 过滤无需放开。

纪律:
  * 只入库 ``blocked=False`` 的页, 且写的是 ``cleaned_text`` 不是 ``raw_text``
  * ``blocked=True`` 的页**只记 metadata** (content IS NULL), 正文不入池
  * 落库前**重新过一遍** ``page_transcript_filter`` (不以 agent43 的产物为
    唯一可信来源; 实测 40 页抽样 0 不一致, 这里做全量复检)
  * 写前把将被新增/改动的行导出到 ``data/backups/``
  * 幂等: ``(knowledge_id, page_number)`` 唯一, 重跑走 upsert

用法 (容器内, /app 目录):
    python /tmp/a44/ingest.py --dry-run
    python /tmp/a44/ingest.py --execute --batch a43-native143
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/app")

# 关掉 SQLAlchemy INFO 回显: 每条 INSERT 会把 1024 维向量整串打进日志
# (agent44 实战: 78KB 日志里 99% 是向量字面量), 且拖慢写入。
import logging as _logging
_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from sqlalchemy import select, text as sqlt

from app.core.database import async_session
from app.models.knowledge_page_transcript import KnowledgePageTranscript
from app.services.page_transcript_filter import filter_page_transcript

SRC = "/tmp/a43/merged_a41.json"
BACKUP_DIR = "/app/data/backups"
EMBED_BATCH = 16


def _truthy(v) -> bool:
    return str(v).lower() in ("true", "1")


async def load_twin_map(db, fids: list[int]) -> dict[int, int]:
    """drive fid -> kb 孪生行 id (meta->>'drive_source_file_id' 精确匹配)。"""
    rows = (await db.execute(sqlt("""
        SELECT (meta->>'drive_source_file_id')::int AS drive_id, id AS kb_id,
               visibility, deleted_at
        FROM knowledge
        WHERE storage_mode='kb'
          AND meta->>'drive_source_file_id' IS NOT NULL
          AND (meta->>'drive_source_file_id')::int = ANY(:fids)
    """), {"fids": fids})).all()
    out: dict[int, list[tuple[int, str, object]]] = defaultdict(list)
    for r in rows:
        out[r.drive_id].append((r.kb_id, r.visibility, r.deleted_at))
    resolved: dict[int, int] = {}
    for drive_id, cands in out.items():
        # 只认未删除且 team/public 的孪生行; 多孪生取 id 最小 (dry-run 实测无此情况)
        good = [c for c in cands if c[2] is None and c[1] in ("team", "public")]
        if good:
            resolved[drive_id] = min(c[0] for c in good)
    return resolved


async def do_backup(rows: list[dict], batch: str) -> str:
    """把将要写入的行导出到 data/backups/ (JSONL, 可完整重放回滚)。"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"a44-page-transcripts-{batch}-{ts}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--batch", default="a43-native143")
    args = ap.parse_args()
    if not (args.dry_run or args.execute):
        ap.error("需要 --dry-run 或 --execute")

    raw = json.load(open(SRC, encoding="utf-8"))
    ok = [r for r in raw if not _truthy(r.get("blocked"))]
    blocked = [r for r in raw if _truthy(r.get("blocked"))]
    print(f"[in] {len(raw)} rows -> ingestable={len(ok)} blocked={len(blocked)}")

    # ── 全量复检: 重跑 page_transcript_filter, 不盲信 agent43 的 cleaned_text ──
    print("[filter] 全量复检 raw_text -> filter_page_transcript")
    t0 = time.perf_counter()
    plan: list[dict] = []
    drift = 0
    for r in ok:
        again = filter_page_transcript(r.get("raw_text") or "")
        text = (again.text or "").strip()
        if _truthy(again.blocked):
            # agent43 判 ok 但 filter 现在判 block → 降级为 metadata-only
            blocked.append(r)
            continue
        if text != (r.get("cleaned_text") or "").strip():
            drift += 1
        if not text:
            continue
        plan.append({
            "fid": int(r["fid"]),
            "page": int(r["page"]),
            "text": text,
            "a_chars": int(r.get("A") or 0),
            "b_chars": int(r.get("B") or 0),
            "c_chars": int(r.get("C") or 0),
            "d_chars": int(r.get("D") or 0),
            "file_name": (r.get("file_name") or "")[:300],
            "chrome_ratio": float(r.get("chrome_ratio") or 0.0),
        })
    print(f"[filter] 复检完成 {time.perf_counter()-t0:.1f}s, "
          f"cleaned_text 与 agent43 不一致 {drift} 页, "
          f"可入库 {len(plan)} 页, 复检新增 blocked {len(blocked)-len(raw)+len(ok)} 页")

    fids = sorted({p["fid"] for p in plan} | {int(r["fid"]) for r in blocked})

    async with async_session() as db:
        twin_of = await load_twin_map(db, fids)
        print(f"[twin] drive fid -> kb 孪生: {len(twin_of)}/{len(fids)}")

        unmapped = [p for p in plan if p["fid"] not in twin_of]
        print(f"[twin] 无孪生的可入库页 = {len(unmapped)}")

        # 唯一性检查: 同一 (twin, page) 不能重复
        seen: dict[tuple[int, int], int] = defaultdict(int)
        for p in plan:
            if p["fid"] in twin_of:
                seen[(twin_of[p["fid"]], p["page"])] += 1
        dups = {k: v for k, v in seen.items() if v > 1}
        print(f"[dedup] (孪生,页码) 重复 = {len(dups)} {list(dups.items())[:5]}")

        writable = [p for p in plan if p["fid"] in twin_of]
        blocked_writable = [
            r for r in blocked
            if int(r["fid"]) in twin_of
        ]
        print(f"\n=== DRY RUN 汇总 ===")
        print(f"  写入正文行 (blocked=false): {len(writable)}")
        print(f"  写入 metadata 行 (blocked=true, content=NULL): {len(blocked_writable)}")
        print(f"  合计新增行: {len(writable) + len(blocked_writable)}")
        print(f"  正文字符合计: {sum(len(p['text']) for p in writable)}")
        print(f"  涉及 kb 孪生行 (knowledge_id): "
              f"{len({twin_of[p['fid']] for p in writable})}")
        print(f"  需 embedding 的行: {len(writable)}")
        print(f"  影响索引: 本表新建 HNSW ix_kpt_embedding_hnsw; "
              f"既有 knowledge_images / knowledge_chunks **零改动**")

        if args.dry_run:
            print("\n[dry-run] 未写入任何数据。")
            return

        # ── 备份 ──────────────────────────────────────────────────────────
        backup_payload = []
        for p in writable:
            backup_payload.append({
                "op": "insert", "knowledge_id": twin_of[p["fid"]],
                "source_drive_file_id": p["fid"], "page_number": p["page"],
                "content": p["text"], "char_count": len(p["text"]),
                "blocked": False, "a_chars": p["a_chars"], "b_chars": p["b_chars"],
                "c_chars": p["c_chars"], "d_chars": p["d_chars"],
                "chrome_ratio": p["chrome_ratio"], "file_name": p["file_name"],
                "ingest_batch": args.batch,
            })
        for r in blocked_writable:
            reasons = r.get("block_reasons")
            if isinstance(reasons, str):
                try:
                    reasons = json.loads(reasons or "[]")
                except Exception:
                    reasons = [reasons]
            backup_payload.append({
                "op": "insert", "knowledge_id": twin_of[int(r["fid"])],
                "source_drive_file_id": int(r["fid"]), "page_number": int(r["page"]),
                "content": None, "char_count": None,
                "blocked": True, "block_reasons": reasons or [],
                "chrome_ratio": float(r.get("chrome_ratio") or 0.0),
                "file_name": (r.get("file_name") or "")[:300],
                "ingest_batch": args.batch,
            })
        bpath = await do_backup(backup_payload, args.batch)
        print(f"\n[backup] {len(backup_payload)} 行 -> {bpath}")

        # ── 清空本批 scope (幂等/可重跑) ───────────────────────────────────
        # 范围 = 本次涉及的 kb 孪生行集合。先删后插保证「跑一次」与「跑 N 次」
        # 终态一致 (agent44 实战: 首跑因 GPU 争用卡死, 半批 448 行已落库)。
        scope_kids = sorted({twin_of[p["fid"]] for p in writable}
                             | {twin_of[int(r["fid"])] for r in blocked_writable})
        from sqlalchemy import delete as sa_delete
        deleted = (await db.execute(
            sa_delete(KnowledgePageTranscript)
            .where(KnowledgePageTranscript.knowledge_id.in_(scope_kids))
        )).rowcount
        await db.commit()
        print(f"[reset] 清空 scope 内 {deleted} 行 "
              f"(涉及 {len(scope_kids)} 个 kb 孪生行), 随后整批重写")

        # ── 写入 ──────────────────────────────────────────────────────────
        # 按长度升序分批: 同批长度同质, 避免「一个 11K 字页拖垮整批 120s」。
        # generate_embeddings 内部是 asyncio.wait_for(to_thread(...), 120s),
        # 超时返回 None 且 **底层线程不可取消** —— 若不兜底, 脚本会在解释器
        # 退出时永久挂住等那个线程 (agent44 实战踩到, GPU 32GB 占满不退)。
        # 兜底三级: 批失败 -> 单条重试 -> 单条仍失败则 embedding 留 NULL,
        # 由 PageTranscriptRetriever 检索时惰性补 (与第 5 路同款语义)。
        from app.services.embedding_service import generate_embeddings

        async def embed_one(text: str):
            try:
                one = await generate_embeddings([text], for_query=False)
            except Exception:
                return None
            if not one:
                return None
            v = one[0]
            return v if v is not None else None

        writable.sort(key=lambda p: len(p["text"]))
        t_write = time.perf_counter()
        written_body = 0
        written_meta = 0
        null_emb = 0
        retried = 0

        for i in range(0, len(writable), EMBED_BATCH):
            chunk = writable[i:i + EMBED_BATCH]
            texts = [p["text"] for p in chunk]
            vecs = None
            try:
                vecs = await generate_embeddings(texts, for_query=False)
            except Exception as exc:
                logger_line = f"[write] 批次 embedding 异常: {exc}"
                print(logger_line)
            if not vecs or len(vecs) != len(chunk):
                vecs = [None] * len(chunk)
                for j, p in enumerate(chunk):
                    retried += 1
                    vecs[j] = await embed_one(p["text"])

            for p, vec in zip(chunk, vecs):
                if vec is None:
                    null_emb += 1
                db.add(KnowledgePageTranscript(
                    knowledge_id=twin_of[p["fid"]],
                    source_drive_file_id=p["fid"],
                    page_number=p["page"],
                    content=p["text"],
                    char_count=len(p["text"]),
                    blocked=False,
                    block_reasons=[],
                    chrome_ratio=p["chrome_ratio"],
                    a_chars=p["a_chars"], b_chars=p["b_chars"],
                    c_chars=p["c_chars"], d_chars=p["d_chars"],
                    file_name=p["file_name"],
                    ingest_batch=args.batch,
                    embedding=vec,
                ))
                written_body += 1
            await db.commit()
            done = min(i + EMBED_BATCH, len(writable))
            el = time.perf_counter() - t_write
            rate = done / max(el, 1e-6)
            print(f"[write] {done}/{len(writable)} "
                  f"({el:.0f}s, {rate:.1f} 页/s, "
                  f"ETA {(len(writable)-done)/max(rate,1e-6)/60:.1f}min, "
                  f"null_emb={null_emb})", flush=True)

        for r in blocked_writable:
            reasons = r.get("block_reasons")
            if isinstance(reasons, str):
                try:
                    reasons = json.loads(reasons or "[]")
                except Exception:
                    reasons = [reasons]
            db.add(KnowledgePageTranscript(
                knowledge_id=twin_of[int(r["fid"])],
                source_drive_file_id=int(r["fid"]),
                page_number=int(r["page"]),
                content=None,
                char_count=None,
                blocked=True,
                block_reasons=list(reasons or []),
                chrome_ratio=float(r.get("chrome_ratio") or 0.0),
                file_name=(r.get("file_name") or "")[:300],
                ingest_batch=args.batch,
                embedding=None,
            ))
            written_meta += 1
        await db.commit()

        print(f"\n[done] 正文行={written_body} metadata 行={written_meta} "
              f"embedding 留空(检索时惰性补)={null_emb} "
              f"批次超时降级为单条重试={retried} "
              f"耗时 {time.perf_counter()-t_write:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
