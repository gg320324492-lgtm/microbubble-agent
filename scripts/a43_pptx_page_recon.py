"""agent43 侦察阶段: 现场重解析 PPTX, 计算每页 native_chars, 统计目标档位规模。

**只用实时解析, 不读旧 chunk** —— agent38 今天修了 `_parse_pptx` 的 grpSp 递归
但没重跑生产索引, `knowledge_chunks.content` 是修复前的文本。

只读: 不写库、不写 MinIO。结果落 /tmp/a43/。
"""
import asyncio, io, json, os, sys, hashlib
from collections import defaultdict

sys.path.insert(0, "/app")

from sqlalchemy import text as sqlt
from app.core.database import get_db
from app.services.file_service import FileService
from app.services.file_parser_service import file_parser_service
from app.services.chunking_service import chunk_text, ChunkConfig
from app.config import settings

OUT = "/tmp/a43"
os.makedirs(OUT, exist_ok=True)
CACHE_ROOT = "/app/data/pptx_pages"


def preview_key(file_path: str) -> str:
    return hashlib.md5(("v2:" + str(file_path)).encode()).hexdigest()[:12]


async def main():
    fs = FileService()
    db = await anext(get_db())
    if True:
        rows = (await db.execute(sqlt("""
            SELECT id, file_path, file_name, title, created_by, content
            FROM knowledge
            WHERE storage_mode='drive' AND file_type='.pptx' AND deleted_at IS NULL
            ORDER BY id
        """))).fetchall()
        print(f"[recon] drive pptx files = {len(rows)}", flush=True)

        # 生产旧值 (修复前), 用于量化 agent38 修复的影响。
        # ⚠️ 仅用于**对比**, 不参与 native_chars 计算 (后者全部来自实时解析)。
        import re as _re
        old = defaultdict(dict)
        for kid, ccontent, cc in (await db.execute(sqlt("""
            SELECT c.knowledge_id, c.content, c.char_count
            FROM knowledge_chunks c
            WHERE c.strategy='page' AND c.knowledge_id = ANY(:ids)
        """).bindparams(ids=[r.id for r in rows]))).fetchall():
            m = _re.search(r"\[PAGE:(\d+)\]", ccontent or "")
            if m:
                old[kid][int(m.group(1))] = cc

        pages = []          # 每页一条记录
        cache_hit = 0
        cache_miss = 0
        files_with_cache = set()
        parse_errors = []

        for n, r in enumerate(rows, 1):
            try:
                data = await fs.download_file(r.file_path)
            except Exception as e:
                parse_errors.append({"id": r.id, "stage": "download", "err": str(e)[:200]})
                continue
            try:
                # 用**修复后**的解析器现场重解析
                text = await file_parser_service._parse_pptx(data)
                chunks = chunk_text(text, ChunkConfig(strategy="page"))
            except Exception as e:
                parse_errors.append({"id": r.id, "stage": "parse", "err": str(e)[:200]})
                continue

            cdir = os.path.join(CACHE_ROOT, f"{r.id}_{preview_key(r.file_path)}")
            ready = os.path.join(cdir, "ready.json")
            cached_total = 0
            if os.path.exists(ready):
                try:
                    cached_total = json.load(open(ready)).get("total", 0)
                    files_with_cache.add(r.id)
                except Exception:
                    pass

            oldmap = old.get(r.id, {})
            for c in chunks:
                # 从内容里的 [PAGE:N] 标记取页号 (chunk_index 可能不同, 用标记更可靠)
                import re
                m = re.search(r"\[PAGE:(\d+)\]", c.content)
                pg = int(m.group(1)) if m else None
                if pg is None:
                    continue
                hit = os.path.exists(os.path.join(cdir, f"page-{pg}.png"))
                if hit:
                    cache_hit += 1
                else:
                    cache_miss += 1
                pages.append({
                    "file_id": r.id,
                    "page": pg,
                    "native_chars": c.char_count,
                    "old_char_count": oldmap.get(pg),
                    "cache_dir": cdir if os.path.exists(ready) else None,
                    "cache_hit": hit,
                    "cached_total": cached_total,
                    "slide_total": cached_total,
                    "file_name": r.file_name,
                    "title": r.title,
                    "created_by": r.created_by,
                })
            if n % 25 == 0:
                print(f"[recon] {n}/{len(rows)} files, pages so far {len(pages)}, "
                      f"cache_hit={cache_hit} miss={cache_miss}", flush=True)

    json.dump(pages, open(f"{OUT}/pages_recon.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    json.dump(parse_errors, open(f"{OUT}/parse_errors.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # ── 汇总 ──
    lt143 = [p for p in pages if p["native_chars"] < 143]
    print("\n" + "=" * 64)
    print(f"总页数 (修复后实时解析) = {len(pages)}")
    print(f"  < 143                 = {len(lt143)}")
    print(f"  143-299               = {sum(1 for p in pages if 143 <= p['native_chars'] < 300)}")
    print(f"  >= 300                = {sum(1 for p in pages if p['native_chars'] >= 300)}")
    print(f"涉及文件数 (<143)      = {len(set(p['file_id'] for p in lt143))}")
    print(f"缓存命中 / 未命中      = {cache_hit} / {cache_miss} "
          f"({cache_hit / max(1, cache_hit + cache_miss):.1%})")
    print(f"有缓存的文件数         = {len(files_with_cache)} / {len(rows)}")
    print(f"解析错误               = {len(parse_errors)}")

    # 修复前后对比
    both = [(p["old_char_count"], p["native_chars"]) for p in pages
            if p["old_char_count"] is not None]
    if both:
        grew = sum(1 for o, n_ in both if n_ > o)
        print(f"\nagent38 修复影响 (可对齐 {len(both)} 页):")
        print(f"  页文本变长的页数 = {grew} ({grew/len(both):.1%})")
        print(f"  总增量 = {sum(n_-o for o, n_ in both)} 字符")
        o_lt = sum(1 for o, n_ in both if o < 143)
        n_lt = sum(1 for o, n_ in both if n_ < 143)
        print(f"  <143 页数: 修复前 {o_lt} -> 修复后 {n_lt} (移出 {o_lt-n_lt} 页)")
    # 页数 vs 缓存页数一致性
    mism = [(p["file_id"], p["slide_total"]) for p in pages
            if p["slide_total"] and p["page"] > p["slide_total"]]
    print(f"页号 > 渲染总页 的不一致页 = {len(mism)} (前5: {mism[:5]})")


asyncio.run(main())