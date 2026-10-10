"""agent46 入库 — 补齐的 179 页 → knowledge_page_transcripts (迁移 144)。

**范围严格限定**: 只处理 agent46 补齐的 179 页 (156 口径差 + 23 曾 429)。
**不触碰** agent44 已入库的 2316 行 (即不整批清空 scope —— agent44 的 ingest
脚本按 kb 孪生行 scope 先删后插, 会把既有行一并删掉重写; 本脚本改用
**逐页 upsert**, 只影响这 179 个 (knowledge_id, page_number) 键)。

纪律 (与 agent44 ingest 一致):
  * 只入库 ``blocked=False`` 的页, 写 ``filter_page_transcript().text``
  * ``blocked=True`` 页只记 metadata (content IS NULL), 正文不入池
  * 落库前**重新过一遍** ``page_transcript_filter``
  * 按长度升序分批 + 三级降级 (批失败 -> 单条 -> 留 NULL), 避免 agent44
    踩到的 ``generate_embeddings`` 120s 超时后底层线程不可取消 + 解释器退出挂死
  * 幂等: ``(knowledge_id, page_number)`` 唯一, 走 upsert

用法 (容器内):
    python /tmp/a46/ingest.py --dry-run
    python /tmp/a46/ingest.py --execute --batch a46-native143-gap
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

import logging as _logging
_logging.getLogger("sqlalchemy.engine").setLevel(_logging.WARNING)

from sqlalchemy import select, text as sqlt
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import async_session
from app.models.knowledge_page_transcript import KnowledgePageTranscript
from app.services.page_transcript_filter import filter_page_transcript

OUT = "/tmp/a46"
BACKUP_DIR = "/app/data/backups"
EMBED_BATCH = 16
RESULTS = f"{OUT}/results.jsonl"


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
        good = [c for c in cands if c[2] is None and c[1] in ("team", "public")]
        if good:
            resolved[drive_id] = min(c[0] for c in good)
    return resolved


async def do_backup(rows: list[dict], batch: str) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(BACKUP_DIR, f"a46-page-transcripts-{batch}-{ts}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def _reasons(r) -> list:
    reasons = r.get("block_reasons")
    if isinstance(reasons, str):
        try:
            reasons = json.loads(reasons or "[]")
        except Exception:
            reasons = [reasons]
    return list(reasons or [])


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--batch", default="a46-native143-gap")
    ap.add_argument("--results", default=RESULTS)
    args = ap.parse_args()
    if not (args.dry_run or args.execute):
        ap.error("需要 --dry-run 或 --execute")

    recs = [json.loads(l) for l in open(args.results, encoding="utf-8")]
    ok_recs = [r for r in recs if not r.get("error")]
    err_recs = [r for r in recs if r.get("error")]
    print(f"[in] {len(recs)} 行 -> 转写成功 {len(ok_recs)}, 仍失败 {len(err_recs)}")
    if err_recs:
        print(f"[in] 仍失败样例: {err_recs[0].get('error','')[:120]}")

    # ── 全量复检 filter (不盲信转写产物) ──
    print("[filter] raw -> filter_page_transcript 复检")
    t0 = time.perf_counter()
    plan: list[dict] = []
    blocked: list[dict] = []
    for r in ok_recs:
        again = filter_page_transcript(r.get("raw") or "")
        text = (again.text or "").strip()
        if _truthy(again.blocked):
            blocked.append({**r, "block_reasons": list(again.block_reasons),
                            "chrome_ratio": again.chrome_ratio})
            continue
        if not text:
            blocked.append({**r, "block_reasons": list(again.block_reasons) + ["empty_after_filter"],
                            "chrome_ratio": again.chrome_ratio})
            continue
        plan.append({
            "fid": int(r["file_id"]),
            "page": int(r["page"]),
            "text": text,
            "chrome_ratio": float(again.chrome_ratio or 0.0),
            "file_name": (r.get("file_name") or "")[:300],
        })
    print(f"[filter] {time.perf_counter()-t0:.1f}s, 可入库 {len(plan)}, blocked {len(blocked)}")

    fids = sorted({p["fid"] for p in plan} | {int(b["file_id"]) for b in blocked})

    async with async_session() as db:
        twin_of = await load_twin_map(db, fids)
        print(f"[twin] drive fid -> kb 孪生: {len(twin_of)}/{len(fids)}")
        unmapped = [p for p in plan if p["fid"] not in twin_of]
        if unmapped:
            print(f"[twin] 无孪生的可入库页 = {len(unmapped)}")

        writable = [p for p in plan if p["fid"] in twin_of]
        blocked_w = [b for b in blocked if int(b["file_id"]) in twin_of]

        # 现有表中已有这些键吗 (判断是 insert 还是覆盖)
        keys = [(twin_of[p["fid"]], p["page"]) for p in writable]
        existing = set()
        if keys:
            krows = (await db.execute(sqlt("""
                SELECT knowledge_id, page_number FROM knowledge_page_transcripts
                WHERE (knowledge_id, page_number) IN (
                    SELECT k, p FROM unnest(CAST(:ks AS int[]), CAST(:ps AS int[]))
                    AS t(k, p))
            """), {"ks": [k for k, _ in keys], "ps": [p for _, p in keys]})).all()
            existing = {(r.knowledge_id, r.page_number) for r in krows}

        print("\n=== DRY RUN 汇总 ===")
        print(f"  可入库正文行: {len(writable)} (其中已存在需覆盖 {len(existing)})")
        print(f"  metadata 行 (blocked): {len(blocked_w)}")
        print(f"  正文字符合计: {sum(len(p['text']) for p in writable)}")
        print(f"  涉及 kb 孪生行: {len({twin_of[p['fid']] for p in writable})}")
        print(f"  需 embedding 的行: {len(writable)}")

        if args.dry_run:
            print("\n[dry-run] 未写入任何数据。")
            return

        # ── 备份 (仅将要写入的行) ──
        payload = []
        for p in writable:
            payload.append({
                "op": "upsert", "knowledge_id": twin_of[p["fid"]],
                "source_drive_file_id": p["fid"], "page_number": p["page"],
                "content": p["text"], "char_count": len(p["text"]),
                "blocked": False, "chrome_ratio": p["chrome_ratio"],
                "file_name": p["file_name"], "ingest_batch": args.batch,
            })
        for b in blocked_w:
            payload.append({
                "op": "upsert", "knowledge_id": twin_of[int(b["file_id"])],
                "source_drive_file_id": int(b["file_id"]), "page_number": int(b["page"]),
                "content": None, "blocked": True,
                "block_reasons": _reasons(b),
                "chrome_ratio": float(b.get("chrome_ratio") or 0.0),
                "file_name": (b.get("file_name") or "")[:300],
                "ingest_batch": args.batch,
            })
        bpath = await do_backup(payload, args.batch)
        print(f"\n[backup] {len(payload)} 行 -> {bpath}")

        # ── embedding: 长度升序分批 + 三级降级 ──
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
        null_emb = 0
        retried = 0

        for i in range(0, len(writable), EMBED_BATCH):
            chunk = writable[i:i + EMBED_BATCH]
            texts = [p["text"] for p in chunk]
            vecs = None
            try:
                vecs = await generate_embeddings(texts, for_query=False)
            except Exception as exc:
                print(f"[write] 批次 embedding 异常: {str(exc)[:120]}")
            if not vecs or len(vecs) != len(chunk):
                vecs = [None] * len(chunk)
                for j, p in enumerate(chunk):
                    retried += 1
                    vecs[j] = await embed_one(p["text"])

            for p, vec in zip(chunk, vecs):
                if vec is None:
                    null_emb += 1
                stmt = pg_insert(KnowledgePageTranscript).values(
                    knowledge_id=twin_of[p["fid"]],
                    source_drive_file_id=p["fid"],
                    page_number=p["page"],
                    content=p["text"],
                    char_count=len(p["text"]),
                    blocked=False,
                    block_reasons=[],
                    chrome_ratio=p["chrome_ratio"],
                    file_name=p["file_name"],
                    ingest_batch=args.batch,
                    embedding=vec,
                ).on_conflict_do_update(
                    constraint="uq_kpt_knowledge_page",
                    set_=dict(
                        content=p["text"], char_count=len(p["text"]),
                        blocked=False, block_reasons=[],
                        chrome_ratio=p["chrome_ratio"],
                        file_name=p["file_name"], ingest_batch=args.batch,
                        embedding=vec,
                        updated_at=sqlt("now()"),
                    ),
                )
                await db.execute(stmt)
                written_body += 1
            await db.commit()
            done = min(i + EMBED_BATCH, len(writable))
            el = time.perf_counter() - t_write
            rate = done / max(el, 1e-6)
            print(f"[write] {done}/{len(writable)} ({el:.0f}s, {rate:.1f} 页/s, "
                  f"ETA {(len(writable)-done)/max(rate,1e-6)/60:.1f}min, null_emb={null_emb})",
                  flush=True)

        for b in blocked_w:
            stmt = pg_insert(KnowledgePageTranscript).values(
                knowledge_id=twin_of[int(b["file_id"])],
                source_drive_file_id=int(b["file_id"]),
                page_number=int(b["page"]),
                content=None, char_count=None,
                blocked=True, block_reasons=_reasons(b),
                chrome_ratio=float(b.get("chrome_ratio") or 0.0),
                file_name=(b.get("file_name") or "")[:300],
                ingest_batch=args.batch, embedding=None,
            ).on_conflict_do_update(
                constraint="uq_kpt_knowledge_page",
                set_=dict(content=None, char_count=None, blocked=True,
                          block_reasons=_reasons(b),
                          chrome_ratio=float(b.get("chrome_ratio") or 0.0),
                          file_name=(b.get("file_name") or "")[:300],
                          ingest_batch=args.batch, embedding=None,
                          updated_at=sqlt("now()")),
            )
            await db.execute(stmt)
        await db.commit()

        print(f"\n[done] 正文行={written_body} metadata 行={len(blocked_w)} "
              f"embedding 留空={null_emb} 单条降级={retried} "
              f"耗时 {time.perf_counter()-t_write:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
