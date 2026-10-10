"""agent46 — 补齐 native<143 档的 179 页缺口 (156 顶部口径差 + 23 429 失败)。

**与 agent43 的差别 (派工要求)**:
  1. 并发 8 → **4** (agent43 并发 8 对云端太猛, 产生 119 次重试 + 23 页 429 失败)
  2. 退避 1.5*(attempt+1) 线性 → **指数退避 1s→2s→4s, 最多 3 次, 带 jitter**
  3. 新增**请求间隔节流** (每次调用前 sleep THROTTLE 秒, 全局)
  4. 429 单独识别并做**更长退避** (区分"服务端限流"与"一般错误")

目标页来源 (确定性的, 不重算):
  * 156 页 = `pages_a41def.json` 里 `native_chars < 143` 但 `a43_chars_with_marker >= 143`
    (a41 纯 shape 文本口径 vs a43 含 [PAGE:N]/页头口径的差, 实测差 22-24 字符)
  * 23 页  = `merged.jsonl` 里 `error` 非空的页

渲染: 复用生产缓存 `/app/data/pptx_pages/{file_id}_{key}/page-N.png` (只读),
缺的渲染到 `/tmp/a46/render/` (独立 soffice profile, 不碰生产)。
不写生产库、不写 MinIO; 结果落 `/tmp/a46/`.
"""
from __future__ import annotations

import argparse, asyncio, base64, hashlib, json, os, random, re, shutil, subprocess, sys, time
from collections import defaultdict

sys.path.insert(0, "/app")

from app.core.llm import get_anthropic_client
from app.config import settings

OUT = "/tmp/a46"
RENDER_ROOT = f"{OUT}/render"
PROD_CACHE = "/app/data/pptx_pages"
PROMPT = "提取这张幻灯片上的所有文字内容，按阅读顺序原样输出。不要总结、不要解释、不要添加图中没有的内容。"

# ── 修正后的并发/退避参数 (派工要求) ──
CONCURRENCY = 4            # 8 → 4
MAX_ATTEMPTS = 3           # 最多 3 次
BACKOFF_BASE = 1.0         # 1s -> 2s -> 4s
BACKOFF_JITTER = 0.4       # ±40% jitter
THROTTLE = 0.35            # 每次调用前全局节流间隔 (秒)
RATE_LIMIT_BACKOFF = 8.0   # 429 专用更长基线退避 (秒)
COST_CAP = 260             # 179 页 + 10 页验证, 重试计入; 硬上限

PROFILE = "file:///tmp/a46/lo_profile"


def pkey(file_path: str) -> str:
    """与生产/agent43 一致的预览缓存 key (v2 前缀)。"""
    return hashlib.md5(("v2:" + str(file_path)).encode()).hexdigest()[:12]


# ══════════════════════════════════════════════════════════════════════
# 目标页 (确定性, 从 agent43 产物算出, 不重跑 recon)
# ══════════════════════════════════════════════════════════════════════

def build_targets() -> list[dict]:
    p = json.load(open("/tmp/a43/pages_a41def.json", encoding="utf-8"))
    by_key = {(x["file_id"], x["page"]): x for x in p}

    # 156: a41 口径 <143 但 a43 口径 >=143
    missed = []
    for x in p:
        if x["native_chars"] < 143 <= x["a43_chars_with_marker"]:
            missed.append({
                "file_id": x["file_id"], "page": x["page"],
                "file_name": x["file_name"], "created_by": x.get("created_by"),
                "native_chars": x["native_chars"],
                "a43_chars_with_marker": x["a43_chars_with_marker"],
                "gap_kind": "caliber",
            })

    # 23: merged.jsonl 里 error 非空
    failed = []
    for ln in open("/tmp/a43/merged.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        if not r.get("error"):
            continue
        k = (r["file_id"], r["page"])
        base = by_key.get(k, {})
        failed.append({
            "file_id": r["file_id"], "page": r["page"],
            "file_name": r.get("file_name") or base.get("file_name"),
            "created_by": r.get("created_by") or base.get("created_by"),
            "native_chars": base.get("native_chars", r.get("native_chars")),
            "a43_chars_with_marker": base.get("a43_chars_with_marker"),
            "prev_error": r.get("error"),
            "gap_kind": "retry_429",
        })
    return missed, failed


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
# 视觉调用 (修正版: 指数退避 + jitter + 节流 + 429 专用)
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
    """全局请求间隔节流 (所有并发共享一个 last_call 时间戳)。"""
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
    """返回 (text, thinking_blocks, out_tokens, error, attempts_used, rate_limited)。"""
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
            # 指数退避: base * 2^attempt, 带 ±jitter
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
    ap.add_argument("--seed", type=int, default=4601)
    ap.add_argument("--only-cached", action="store_true")
    ap.add_argument("--out", default=f"{OUT}/results.jsonl")
    ap.add_argument("--resume-from", default="",
                    help="逗号分隔 jsonl; 其中无 error 的 (file_id,page) 直接跳过不重复计费")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RENDER_ROOT, exist_ok=True)

    missed, failed = build_targets()
    print(f"[targets] caliber-missed 156 = {len(missed)}, retry-429 = {len(failed)}",
          flush=True)
    targets = missed + failed

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

    # 定位 png (生产缓存优先, 否则 /tmp/a46/render)
    for t in targets:
        fid = t["file_id"]
        cdir = os.path.join(PROD_CACHE, f"{fid}_{pkey(fpath.get(fid, ''))}")
        pp = os.path.join(cdir, f"page-{t['page']}.png")
        rp = os.path.join(RENDER_ROOT, str(fid), f"page-{t['page']}.png")
        t["png"] = pp if os.path.exists(pp) else (rp if os.path.exists(rp) else None)
        t["png_from"] = "prod" if os.path.exists(pp) else (
            "a46" if os.path.exists(rp) else None)

    need_render = sorted({t["file_id"] for t in targets
                          if t["png"] is None and t["file_id"] in fpath})
    print(f"[cache] prod-hit={sum(1 for t in targets if t['png_from']=='prod')} "
          f"a46-hit={sum(1 for t in targets if t['png_from']=='a46')} "
          f"need-render-files={len(need_render)}", flush=True)

    if args.sample:
        rnd = random.Random(args.seed)
        # 验证批: 优先固定抽样, 混入已知曾 429 的页以验证退避
        sample = rnd.sample(targets, min(args.sample, len(targets)))
        targets = sample
        print(f"[sample] 验证批 {len(targets)} 页 "
              f"(其中曾 429 = {sum(1 for t in targets if t['gap_kind']=='retry_429')})",
              flush=True)

    if args.only_cached:
        targets = [t for t in targets if t["png"]]

    # resume: 跳过已有成功转写的页 (不重复计费)
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
        # 重新定位 newly rendered
        for t in targets:
            if t["png"] is None:
                rp = os.path.join(RENDER_ROOT, str(t["file_id"]), f"page-{t['page']}.png")
                if os.path.exists(rp):
                    t["png"] = rp
                    t["png_from"] = "a46"

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
    summary = {"render": render_stats, "vision_calls": budget.used,
               "ok": done["ok"], "err": done["err"], "retried": stats["retried"],
               "rate_limited": stats["rate_limited"], "wall_secs": time.time() - t0}
    json.dump(summary, open(f"{OUT}/run_stats_{os.path.basename(args.out)}.json", "w"),
              indent=1, ensure_ascii=False)
    print(f"[done] ok={done['ok']} err={done['err']} vision_calls={budget.used} "
          f"retried={stats['retried']} rate_limited={stats['rate_limited']} "
          f"wall={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
