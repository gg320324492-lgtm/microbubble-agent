"""a47 — 把 PPT 整页视觉转写从 `native<143` 档扩到 `143-299` 档。

**背景**: `knowledge_page_transcripts` 已入库 2495 行 (native<143 档, agent44/46)。
本次扩展 `143 <= native_chars < 300` 档 —— 增量收益约 **1.5x A/索引**
(抽样定标, 见 CLAUDE.md 当前状态 §C), 属于"边际但为正"的最后一档主动投喂。
`>=300` 档 (0.37x, 72% 重复) **不做**。

**与 a46 的差别**:
  1. 目标页来源不同 —— a46 是"156 口径差 + 23 个 429 失败"的补漏;
     本脚本是**整档 143-299 的首页投喂** (从 pages_a41def.json 直接筛)
  2. 排除**已在库的键** —— 若某 (file_id, page) 已经进过 knowledge_page_transcripts
     (agent44/46 可能已覆盖个别页), 不再重复计费
  3. 单文件多页: 同一 file 的多个目标页共用一个渲染目录 (生产缓存优先)

**复用**: 渲染 (独立 soffice profile) / 视觉调用 (指数退避+节流+429 专用) /
并发 4 / Budget 硬上限 —— 全部沿用 a46 的成熟逻辑, 只换 build_targets。

**纪律 (与 a46 一致)**:
  * 渲染到 /tmp/a47/render/ (不碰生产 soffice profile, 但**读**生产 png 缓存)
  * 不写生产库、不写 MinIO; 结果落 /tmp/a47/results.jsonl
  * 支持 --resume-from <jsonl> 断点续跑
  * 支持 --sample N (验证批) / --only-cached (零渲染先跑缓存命中页)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/app")

from app.core.llm import get_anthropic_client
from app.config import settings

OUT = "/tmp/a47"
RENDER_ROOT = f"{OUT}/render"
PROD_CACHE = "/app/data/pptx_pages"
PAGES_DEF = "/tmp/a43/pages_a41def.json"
PROMPT = "提取这张幻灯片上的所有文字内容，按阅读顺序原样输出。不要总结、不要解释、不要添加图中没有的内容。"

# ── 沿用 a46 的修正后并发/退避参数 ──
CONCURRENCY = 4
MAX_ATTEMPTS = 3
BACKOFF_BASE = 1.0
BACKOFF_JITTER = 0.4
THROTTLE = 0.35
RATE_LIMIT_BACKOFF = 8.0
COST_CAP = 1400  # 1262 页 + 重试余量; 硬上限

PROFILE = f"file://{OUT}/lo_profile"
BAND_LO, BAND_HI = 143, 300


def pkey(file_path: str) -> str:
    """与生产/agent43/46 一致的预览缓存 key (v2 前缀)。"""
    return hashlib.md5(("v2:" + str(file_path)).encode()).hexdigest()[:12]


# ══════════════════════════════════════════════════════════════════════
# 目标页: 143 <= native_chars < 300 的整档
# ══════════════════════════════════════════════════════════════════════

def build_targets() -> list[dict]:
    p = json.load(open(PAGES_DEF, encoding="utf-8"))
    band = [x for x in p if BAND_LO <= x["native_chars"] < BAND_HI]
    return [{
        "file_id": x["file_id"], "page": x["page"],
        "file_name": x["file_name"], "created_by": x.get("created_by"),
        "native_chars": x["native_chars"],
        "gap_kind": "band_143_299",
    } for x in band]


async def already_ingested(pairs: list[tuple[int, int]]) -> set[tuple[int, int]]:
    """已在 knowledge_page_transcripts 的 (source_drive_file_id, page_number) 集合。

    注意: 表里存的是 **kb 孪生行 id 作为 knowledge_id**, 但另存了
    source_drive_file_id (原始 drive fid) —— 用后者与 pages_def 的 file_id 对齐。
    """
    if not pairs:
        return set()
    from sqlalchemy import text as sqlt
    from app.core.database import async_session
    fids = [f for f, _ in pairs]
    async with async_session() as db:
        rows = (await db.execute(sqlt("""
            SELECT source_drive_file_id, page_number
            FROM knowledge_page_transcripts
            WHERE source_drive_file_id = ANY(:fids)
        """), {"fids": fids})).all()
    return {(r.source_drive_file_id, r.page_number) for r in rows}


# ══════════════════════════════════════════════════════════════════════
# 渲染 (独立 profile, 不碰生产)
# ══════════════════════════════════════════════════════════════════════

_render_gate = asyncio.Semaphore(1)


def render_pptx(data: bytes, out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    tmp = f"{out_dir}/_conv"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    with open(f"{tmp}/in.pptx", "wb") as f:
        f.write(data)
    subprocess.run(
        ["soffice", f"-env:UserInstallation={PROFILE}", "--headless",
         "--convert-to", "pdf", "--outdir", tmp, f"{tmp}/in.pptx"],
        check=True, timeout=900, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(
        ["pdftoppm", "-png", "-r", "110", f"{tmp}/in.pdf", f"{tmp}/page"],
        check=True, timeout=900, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import glob
    pages = sorted(glob.glob(f"{tmp}/page-*.png"))
    for i, png in enumerate(pages, 1):
        shutil.move(png, f"{out_dir}/page-{i}.png")
    shutil.rmtree(tmp, ignore_errors=True)
    return len(pages)


# ══════════════════════════════════════════════════════════════════════
# 视觉调用 (沿用 a46)
# ══════════════════════════════════════════════════════════════════════

class Budget:
    def __init__(self, cap): self.cap, self.used = cap, 0
    def take(self):
        if self.used >= self.cap:
            raise RuntimeError(f"COST CAP REACHED: {self.used}/{self.cap}")
        self.used += 1
        return self.used


_throttle_lock = asyncio.Lock()
_last_call = [0.0]


async def _throttle() -> None:
    async with _throttle_lock:
        now = time.monotonic()
        wait = THROTTLE - (now - _last_call[0])
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[0] = time.monotonic()


def _is_rate_limit(exc: Exception) -> bool:
    s = f"{type(exc).__name__}: {exc}".lower()
    return ("429" in s or "rate" in s or "too many" in s
            or "overload" in s or "529" in s)


async def vision_one(client, budget: Budget, png_path: str):
    raw = open(png_path, "rb").read()
    b64 = base64.standard_b64encode(raw).decode()
    last = None
    rate_limited_hits = 0
    for attempt in range(MAX_ATTEMPTS):
        try:
            await _throttle()
            budget.take()
            r = await client.messages.create(
                model=settings.VISION_MODEL, max_tokens=4096,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64",
                                                 "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": PROMPT}]}])
            texts, thinks = [], 0
            for blk in r.content:
                t = blk.get("type") if isinstance(blk, dict) else getattr(blk, "type", "")
                if t == "text":
                    texts.append(blk.get("text", "") if isinstance(blk, dict)
                                 else getattr(blk, "text", ""))
                elif t == "thinking":
                    thinks += 1
            return ("\n".join(texts).strip(), thinks, r.usage.output_tokens,
                    None, attempt + 1, rate_limited_hits > 0)
        except RuntimeError:
            raise
        except Exception as e:  # noqa: BLE001
            last = e
            rl = _is_rate_limit(e)
            if rl:
                rate_limited_hits += 1
            base = RATE_LIMIT_BACKOFF if rl else BACKOFF_BASE
            delay = base * (2 ** attempt)
            delay = delay * (1 + random.uniform(-BACKOFF_JITTER, BACKOFF_JITTER))
            if attempt < MAX_ATTEMPTS - 1:
                print(f"    [retry] {os.path.basename(os.path.dirname(png_path))}"
                      f"/{os.path.basename(png_path)} attempt {attempt+1} "
                      f"{'RATE-LIMIT ' if rl else ''}sleep {delay:.1f}s: "
                      f"{type(last).__name__}: {str(last)[:90]}", flush=True)
                await asyncio.sleep(delay)
    return (None, 0, 0, f"{type(last).__name__}: {str(last)[:180]}",
            MAX_ATTEMPTS, rate_limited_hits > 0)


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="只跑前 N 页 (验证用)")
    ap.add_argument("--seed", type=int, default=4701)
    ap.add_argument("--only-cached", action="store_true")
    ap.add_argument("--recon", action="store_true",
                    help="纯勘察: 打印 target/cache 统计后直接退出, 零视觉调用")
    ap.add_argument("--no-skip-ingested", action="store_true",
                    help="不排除已在库的键 (默认排除, 省额度)")
    ap.add_argument("--out", default=f"{OUT}/results.jsonl")
    ap.add_argument("--resume-from", default="",
                    help="逗号分隔 jsonl; 其中无 error 的 (file_id,page) 跳过不重复计费")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RENDER_ROOT, exist_ok=True)

    targets = build_targets()
    print(f"[targets] band {BAND_LO}-{BAND_HI} = {len(targets)} 页, "
          f"{len({t['file_id'] for t in targets})} 文件", flush=True)

    # 排除已在库的键 (省额度, 默认开)
    if not args.no_skip_ingested:
        pairs = [(t["file_id"], t["page"]) for t in targets]
        try:
            done_ing = await already_ingested(pairs)
            before = len(targets)
            targets = [t for t in targets
                       if (t["file_id"], t["page"]) not in done_ing]
            print(f"[skip-ingested] 已在库 {before - len(targets)} 页, "
                  f"剩 {len(targets)}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[skip-ingested] 查库失败, 不排除: {str(e)[:120]}", flush=True)

    # 解析 file_path
    from sqlalchemy import text as sqlt
    from app.core.database import async_session
    from app.services.file_service import FileService
    fids = sorted({t["file_id"] for t in targets})
    async with async_session() as db:
        rows = (await db.execute(sqlt(
            "SELECT id, file_path FROM knowledge WHERE id = ANY(:ids)"
        ).bindparams(ids=fids))).fetchall()
    fpath = {r.id: r.file_path for r in rows}
    missing_fp = [f for f in fids if f not in fpath]
    if missing_fp:
        print(f"[warn] 无 file_path 的 fid = {missing_fp}", flush=True)

    # 定位 png (生产缓存优先, 否则 /tmp/a47/render)
    for t in targets:
        fid = t["file_id"]
        cdir = os.path.join(PROD_CACHE, f"{fid}_{pkey(fpath.get(fid, ''))}")
        pp = os.path.join(cdir, f"page-{t['page']}.png")
        rp = os.path.join(RENDER_ROOT, str(fid), f"page-{t['page']}.png")
        t["png"] = pp if os.path.exists(pp) else (rp if os.path.exists(rp) else None)
        t["png_from"] = "prod" if os.path.exists(pp) else (
            "a47" if os.path.exists(rp) else None)

    print(f"[cache] prod-hit={sum(1 for t in targets if t['png_from']=='prod')} "
          f"a47-hit={sum(1 for t in targets if t['png_from']=='a47')} "
          f"need-render-files={len({t['file_id'] for t in targets if t['png'] is None and t['file_id'] in fpath})}",
          flush=True)

    if args.recon:
        print(f"[recon] 纯勘察模式, 零视觉调用退出。"
              f"targets={len(targets)} "
              f"cache-hit={sum(1 for t in targets if t['png'])} "
              f"need-render-pages={sum(1 for t in targets if t['png'] is None)}",
              flush=True)
        return

    if args.sample:
        rnd = random.Random(args.seed)
        targets = rnd.sample(targets, min(args.sample, len(targets)))
        print(f"[sample] 验证批 {len(targets)} 页", flush=True)

    if args.only_cached:
        targets = [t for t in targets if t["png"]]

    if args.resume_from:
        done_keys = set()
        for seed in [s for s in args.resume_from.split(",") if s.strip()]:
            if not os.path.exists(seed):
                continue
            for ln in open(seed, encoding="utf-8"):
                try:
                    r = json.loads(ln)
                except Exception:  # noqa: BLE001
                    continue
                if r.get("error"):
                    continue
                done_keys.add((r["file_id"], r["page"]))
        before = len(targets)
        targets = [t for t in targets
                   if (t["file_id"], t["page"]) not in done_keys]
        print(f"[resume] 复用 {before - len(targets)} 页, 剩 {len(targets)}", flush=True)

    # ── 渲染缺失 ──
    fs = FileService()
    render_stats = {"rendered": 0, "failed": 0, "secs": 0.0}
    need_files = sorted({t["file_id"] for t in targets if t["png"] is None
                         and t["file_id"] in fpath})
    if need_files:
        print(f"[render] 需渲染 {len(need_files)} 文件 ...", flush=True)
        t0 = time.time()
        for n, fid in enumerate(need_files, 1):
            out_dir = f"{RENDER_ROOT}/{fid}"
            if os.path.exists(f"{out_dir}/page-1.png"):
                continue
            async with _render_gate:
                try:
                    data = await fs.download_file(fpath[fid])
                    total = render_pptx(data, out_dir)
                    render_stats["rendered"] += 1
                    print(f"  [{n}/{len(need_files)}] {fid}: {total} 页 "
                          f"({time.time()-t0:.0f}s)", flush=True)
                except Exception as e:  # noqa: BLE001
                    render_stats["failed"] += 1
                    print(f"  [{n}/{len(need_files)}] {fid}: 渲染失败 {str(e)[:120]}",
                          flush=True)
        render_stats["secs"] = time.time() - t0
        for t in targets:
            if t["png"] is None:
                rp = os.path.join(RENDER_ROOT, str(t["file_id"]), f"page-{t['page']}.png")
                if os.path.exists(rp):
                    t["png"] = rp
                    t["png_from"] = "a47"

    # ── 视觉转写 ──
    budget = Budget(COST_CAP)
    client = get_anthropic_client()
    sem = asyncio.Semaphore(CONCURRENCY)
    out_f = open(args.out, "a", encoding="utf-8")
    t0 = time.time()
    done = {"ok": 0, "err": 0}
    stats = defaultdict(int)

    async def handle(t):
        async with sem:
            png = t["png"]
            if not png or not os.path.exists(png):
                rec = {**t, "error": "png_missing"}
                done["err"] += 1
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return
            try:
                text, thinks, outtok, err, attempts, was_rl = await vision_one(
                    client, budget, png)
            except RuntimeError as e:
                rec = {**t, "error": str(e)}
                done["err"] += 1
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return
            if err:
                stats["errors"] += 1
                stats["rate_limited"] += int(was_rl)
                rec = {**t, "error": err, "attempts": attempts,
                       "rate_limited": was_rl}
                done["err"] += 1
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return
            done["ok"] += 1
            stats["retried"] += int(attempts > 1)
            stats["rate_limited"] += int(was_rl)
            rec = {**t, "raw": text, "thinking_blocks": thinks,
                   "out_tokens": outtok, "attempts": attempts,
                   "rate_limited": was_rl}
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if done["ok"] % 20 == 0:
                out_f.flush()
                el = time.time() - t0
                print(f"  [{done['ok']}/{len(targets)}] {el:.0f}s "
                      f"cost={budget.used} retried={stats['retried']} "
                      f"rl={stats['rate_limited']} err={done['err']}", flush=True)

    await asyncio.gather(*[handle(t) for t in targets])
    out_f.close()
    summary = {"band": [BAND_LO, BAND_HI], "render": render_stats,
               "vision_calls": budget.used,
               "ok": done["ok"], "err": done["err"], "retried": stats["retried"],
               "rate_limited": stats["rate_limited"], "wall_secs": time.time() - t0}
    json.dump(summary, open(f"{OUT}/run_stats_{os.path.basename(args.out)}.json", "w"),
              indent=1, ensure_ascii=False)
    print(f"[done] ok={done['ok']} err={done['err']} vision_calls={budget.used} "
          f"retried={stats['retried']} rate_limited={stats['rate_limited']} "
          f"wall={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
