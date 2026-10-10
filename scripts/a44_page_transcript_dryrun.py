"""agent44 dry-run — PPT 整页视觉转写入库前的影响面测量（只读，零写入）。

回答三个问题：
  Q1 落点   — 每个 drive fid 的 kb 孪生行是否存在/唯一/可见（meta->>'drive_source_file_id'）
  Q3 爆炸半径 — 实际会写多少行、影响哪些索引、embedding 耗时
  净化幂等  — agent43 的 cleaned_text 再过一遍 page_transcript_filter 是否稳定

用法（容器内）：python /tmp/a44/dryrun.py
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, "/app")

from sqlalchemy import text as sqlt

from app.core.database import async_session
from app.services.page_transcript_filter import filter_page_transcript

SRC = "/tmp/a43/merged_a41.json"

_NORM_RE = re.compile(r"[^0-9a-z一-鿿]+")


def norm(s: str) -> str:
    return _NORM_RE.sub("", (s or "").lower())


def ngrams(s: str, n: int = 4):
    return {s[i:i + n] for i in range(len(s) - n + 1)}


async def main() -> None:
    raw = json.load(open(SRC, encoding="utf-8"))
    print(f"[src] {SRC}: {len(raw)} rows")

    ok = [r for r in raw if str(r.get("blocked")).lower() not in ("true", "1")]
    blocked = [r for r in raw if str(r.get("blocked")).lower() in ("true", "1")]
    print(f"[split] ingestable={len(ok)} blocked={len(blocked)}")
    print(f"[chars] cleaned_chars(ingestable)={sum(int(r['cleaned_chars'] or 0) for r in ok)}")
    print(f"[chars] cleaned_chars(blocked)   ={sum(int(r['cleaned_chars'] or 0) for r in blocked)}")

    # ── Q1 落点：drive fid -> kb 孪生 ────────────────────────────────────
    fids = sorted({int(r["fid"]) for r in ok})
    print(f"[q1] distinct drive fids (ingestable) = {len(fids)}")

    async with async_session() as db:
        rows = (await db.execute(sqlt("""
            SELECT d.id AS drive_id,
                   d.file_name,
                   d.visibility AS drive_vis,
                   d.deleted_at AS drive_del,
                   kb.id AS kb_id,
                   kb.visibility AS kb_vis,
                   kb.deleted_at AS kb_del,
                   length(kb.content) AS kb_content_len,
                   kb.content AS kb_content
            FROM knowledge d
            LEFT JOIN knowledge kb
                   ON (kb.meta->>'drive_source_file_id')::int = d.id
                  AND kb.storage_mode = 'kb'
            WHERE d.id = ANY(:fids) AND d.storage_mode = 'drive'
        """), {"fids": fids})).all()

    twin_by_drive: dict[int, list] = defaultdict(list)
    drive_meta: dict[int, dict] = {}
    for r in rows:
        twin_by_drive[r.drive_id].append(r)
        drive_meta[r.drive_id] = {
            "file_name": r.file_name,
            "drive_vis": r.drive_vis,
            "drive_del": r.drive_del,
            "kb_id": r.kb_id,
            "kb_vis": r.kb_vis,
            "kb_del": r.kb_del,
            "kb_len": r.kb_content_len,
            "kb_content": r.kb_content or "",
        }

    no_row = [f for f in fids if f not in drive_meta]
    no_twin = [f for f in fids if f in drive_meta and not twin_by_drive[f]]
    multi_twin = {f: len(twin_by_drive[f]) for f in fids if len(twin_by_drive[f]) > 1}
    vis_bad = [f for f in fids
               if f in drive_meta and twin_by_drive[f]
               and (drive_meta[f]["kb_vis"] not in ("team", "public")
                    or drive_meta[f]["kb_del"] is not None)]
    print(f"[q1] fids with no drive row   = {len(no_row)}")
    print(f"[q1] fids with NO kb twin     = {len(no_twin)} {no_twin[:10]}")
    print(f"[q1] fids with >1 kb twin     = {len(multi_twin)} {dict(list(multi_twin.items())[:5])}")
    print(f"[q1] fids w/ twin not team/public or deleted = {len(vis_bad)} {vis_bad[:10]}")

    # 唯一孪生映射（多孪生的取 id 最小者并记账）
    twin_of: dict[int, int] = {}
    for f in fids:
        cands = twin_by_drive.get(f) or []
        if cands:
            twin_of[f] = min(c.kb_id for c in cands if c.kb_id)
    usable = [f for f in fids if twin_of.get(f)]
    print(f"[q1] usable fid->twin mappings = {len(usable)} / {len(fids)}")

    # ── 新颖性抽查：A 类字符确实不在孪生正文里 ───────────────────────────
    print("\n[novelty] 抽查 8 个 A 字符最多的页，验证其转写正文不在孪生 knowledge.content 中")
    by_fid: dict[int, list] = defaultdict(list)
    for r in ok:
        by_fid[int(r["fid"])].append(r)
    top = sorted(ok, key=lambda r: -int(r.get("A") or 0))[:8]
    for r in top:
        f = int(r["fid"])
        twin_content = drive_meta.get(f, {}).get("kb_content", "")
        tn = ngrams(norm(twin_content))
        g = ngrams(norm(r.get("cleaned_text") or ""))
        novel = g - tn
        ratio = (len(novel) / len(g)) if g else 0.0
        print(f"   fid={f:<5} p{r['page']:<3} A={r.get('A'):<5} "
              f"cleaned={r.get('cleaned_chars'):<5} "
              f"twin_len={len(twin_content):<6} 4gram_novel={ratio:.1%} "
              f"| {r.get('file_name','')[:34]}")

    # ── 净化幂等：cleaned_text 再过一次 filter ───────────────────────────
    print("\n[filter] 对 40 页随机抽样重跑 filter_page_transcript，检查 cleaned_text 稳定性")
    import random
    random.seed(44)
    sample = random.sample(ok, min(40, len(ok)))
    unstable = []
    for r in sample:
        src = r.get("raw_text") or ""
        again = filter_page_transcript(src)
        if (again.text or "") != (r.get("cleaned_text") or ""):
            unstable.append(r["fid"] + "/p" + r["page"])
    print(f"[filter] 抽样 {len(sample)} 页，cleaned_text 不一致 = {len(unstable)} {unstable[:5]}")

    # 额外：blocked 页的 metadata-only 形态
    print("\n[blocked-metadata] blocked 页仅记 metadata 的字段可用性")
    print(f"[blocked-metadata] blocked 页数={len(blocked)}  "
          f"涉及 fid={len({int(r['fid']) for r in blocked})}")
    br = Counter()
    for r in blocked:
        v = r.get("block_reasons")
        for x in (v if isinstance(v, list) else json.loads(v or "[]")):
            br[str(x)] += 1
    print(f"[blocked-metadata] reasons = {br.most_common()}")

    # ── Q3 embedding 耗时 ────────────────────────────────────────────────
    print("\n[emb] 采样测 embedding 吞吐（本地 Qwen3-Embedding-0.6B）")
    from app.services.embedding_service import generate_embeddings
    texts = [(r.get("cleaned_text") or "") for r in ok[:32]]
    t0 = time.perf_counter()
    vecs = await generate_embeddings(texts, for_query=False)
    dt = time.perf_counter() - t0
    good = [v for v in vecs if v is not None]
    avg_chars = sum(len(t) for t in texts) / max(1, len(texts))
    print(f"[emb] 32 页 / {dt:.1f}s -> {dt/len(texts)*1000:.0f} ms/页, "
          f"成功 {len(good)}/{len(texts)}, 平均 {avg_chars:.0f} 字符/页")
    print(f"[emb] 全量 {len(ok)} 页线性外推 ≈ {dt/len(texts)*len(ok)/60:.1f} 分钟")
    print(f"[emb] 总待 embed 字符 = {sum(len(r.get('cleaned_text') or '') for r in ok)}")

    json.dump({
        "ingestable_pages": len(ok),
        "blocked_pages": len(blocked),
        "chars_ingestable": sum(int(r["cleaned_chars"] or 0) for r in ok),
        "distinct_fids": len(fids),
        "usable_mappings": len(usable),
        "mappings": {str(k): v for k, v in twin_of.items()},
    }, open("/tmp/a44/_dryrun_summary.json", "w"), ensure_ascii=False, indent=1)
    print("\n[done] /tmp/a44/_dryrun_summary.json")


if __name__ == "__main__":
    asyncio.run(main())
