"""agent43 — PPT 整页视觉转写管线 (一次性, 只落 /tmp)。

设计要点 (与派工要求对齐):
  1. `native_chars` **现场重解析**得出 (agent38 修了 grpSp 递归但没重跑生产索引,
     所以绝不读 `knowledge_chunks` 的旧文本做筛选)。
  2. **必须先过 `filter_page_transcript`** 再判分类。
  3. `blocked=True` 的页 -> **正文不入池**, 只记 metadata。
  4. A/B/C/D 四分类沿用 agent35 口径, D = 4-gram >= 70% 覆盖。

渲染刻意**不写生产缓存目录** (`/app/data/pptx_pages`): 自用 `/tmp/a43/render` +
独立 soffice profile, 避免与生产 `_LIBREOFFICE_GATE` (全局 Semaphore(1)) 抢锁、
不改动生产状态。已缓存的页只**只读**复用。

不写生产库、不写 MinIO。
"""
from __future__ import annotations

import argparse, asyncio, base64, hashlib, json, os, re, shutil, subprocess, sys, time
from collections import Counter, defaultdict

sys.path.insert(0, "/app")

from app.core.llm import get_anthropic_client
from app.config import settings
from app.services.page_transcript_filter import filter_page_transcript

OUT = "/tmp/a43"
RENDER_ROOT = f"{OUT}/render"
PROD_CACHE = "/app/data/pptx_pages"
PROMPT = "提取这张幻灯片上的所有文字内容，按阅读顺序原样输出。不要总结、不要解释、不要添加图中没有的内容。"
COST_CAP = 2400          # 硬红线: 视觉调用上限
CONCURRENCY = 8

# ══════════════════════════════════════════════════════════════════════
# A/B/C/D 四分类 (agent35 口径的确定性实现)
# ══════════════════════════════════════════════════════════════════════

# A-1 实测数值: 数字 + 物理/生化单位
_UNIT = (r"%|min|h|hr|s|秒|分钟|小时|天|℃|°C|K\b|MPa|kPa|Pa|bar|rpm|mL|L|µL|μL|"
         r"ng|µg|μg|mg|g|kg|nm|µm|μm|mm|cm|m\b|km|log|CFU|mS|cm-1|N·m|kJ|kcal|"
         r"V\b|mV|A\b|mA|W\b|mW|Hz|kHz|dB|Ω|ohm|L·min|mg/L|g/L|mol|wt%|at%")
_MEASURE_RE = re.compile(rf"\d[\d.,]*\s*(?:{_UNIT})\b", re.I)
# 纯实测数值行 (无单位但明显是数据), 要求 >=2 个数字且不含中文散文
_PURE_NUM_RE = re.compile(r"^[\s\d.,%+\-eE()]+$")

# A-2 装置/材料/表征标签: 常见缩写 (含数字或化学式)
_APPARATUS_RE = re.compile(
    r"\b(?:N2|O2|O3|MNO|MnO2|TiO2|Fe3\+|Fe2\+|CuO|ZnO|Al2O3|SiO2|CeO2|H2O2|"
    r"DO|ORP|EC|TSS|COD|BOD|TOC|DOC|SMK|UV|IR|XRD|XRF|SEM|TEM|FTIR|HPLC|GC|"
    r"LC-MS|GC-MS|ICP|XPS|AFM|SEM|EDS|NMR|PCR|RT-qPCR|CFU|OD600|ROS\s*·|"
    r"·OH|O2·-|O2-|NO3-|SO4{2,}|Cl-|MBR|EPR|PDMS|PVDF|Pt|Ag|Cu|Ni|Co|Fe)\b"
)

# A-3 图注 / 表注
_CAPTION_RE = re.compile(
    r"^\s*(?:图|表|附图|附表|Fig\.?|Figure|Table|Scheme|Chart|Graph|Plot)\s*[0-9一二三四五六七八九十\-]*"
    r"[\s:：.、,]", re.I)

# A-4 泳道 / 分层标记 (材料相、流层、区域)
_LANE_RE = re.compile(
    r"(泳道|流层|底层|表层|中间层|上层|下层|污泥层|生物膜|附着层|"
    r"水相|油相|气相|固相|反应区|进水区|出水区|曝气区|缺氧区|好氧区|"
    r"对照组|实验组|处理组|投加组|空白组)")

# B 图表通用配件: 坐标轴 / 刻度 / 图例通用项
_AXIS_RE = re.compile(
    r"(?:^|\b)(?:x\s*轴|y\s*轴|横轴|纵轴|坐标轴|axis|axes|X-axis|Y-axis|"
    r"time\s*\(|Time\b|浓度|温度|压力|流速|尺寸|直径|长度|高度|重量|质量|"
    r"吸光度|荧光强度|电流|电压)", re.I)
_LEGEND_GENERIC_RE = re.compile(
    r"^\s*(?:control|ctrl|test|sample|blank|实验组|对照组|样品|空白|"
    r"before|after|t\s*0|t\s*0h|0\s*h|\d+\s*(?:min|h|s|天|小时|分钟))\s*$", re.I)

# C 噪声: 残留 chrome / 纯符号 / URL / 文件系统路径
_C_NOISE_RE = re.compile(
    r"(?:https?://|www\.|C:/Users|[A-Za-z]:\\|file://|©|\u00a9|"
    r"点击|单击|双击|右键|快捷键|功能区|菜单栏|任务栏|窗口|对话框)")

_CJK_RE = re.compile(r"[\u3000-\u303f\uff00-\uffef\u4e00-\u9fff]")


def ngrams(s: str, n: int = 4) -> set:
    s = _WS.sub("", s)
    return {s[i:i + n] for i in range(len(s) - n + 1)} if len(s) >= n else ({s} if s else set())


_WS = re.compile(r"\s+")


def coverage(line: str, native_ngrams: set, n: int = 4) -> float:
    """该行 4-gram 被现有索引文本覆盖的比例。>= 0.70 判 D (重复)。"""
    g = ngrams(line, n)
    if not g:
        return 1.0
    if not native_ngrams:
        return 0.0
    return len(g & native_ngrams) / len(g)


def classify_line(line: str) -> str:
    """A / B / C / E —— 只对**已判定非重复**的行调用。

    A 是 agent35 定义的**窄**高价值集合（装置标签 / 实测数值 / 图注 / 泳道标记）,
    **不是**「一切新增文本」。⚠️ 初版这里 default-return "A", 实测把 30 页样本的
    A 率吹到 73.3%（远高于 agent41 抽样隐含的 3.2~22.9x 产出率）—— 新增散文
    确实不属这四类任何一类。故默认落到 E（一般新增文本, 不计 A）。
    判定优先级 A > B > C > E。
    """
    s = _WS.sub(" ", line).strip()
    if not s:
        return "C"
    # A —— 装置标签 / 实测数值 / 图注 / 泳道标记
    if _CAPTION_RE.match(s):
        return "A"
    if _LANE_RE.search(s):
        return "A"
    if _MEASURE_RE.search(s):
        return "A"
    if _APPARATUS_RE.search(s):
        return "A"
    if _PURE_NUM_RE.match(s) and len(re.findall(r"\d+(?:\.\d+)?", s)) >= 2:
        return "A"
    # C (噪声优先于 B: 图例项/坐标轴若同时像 chrome, 按 C)
    if _C_NOISE_RE.search(s):
        return "C"
    # B
    if _AXIS_RE.search(s) or _LEGEND_GENERIC_RE.match(s):
        return "B"
    # 纯符号 / 单字符 / 无实义
    if len(s) <= 2 or not re.search(r"[A-Za-z\u4e00-\u9fff0-9]", s):
        return "C"
    return "E"          # 一般新增文本 (标题句/结论句/术语) —— **不计 A**


def classify_page(transcript: str, native_text: str):
    """返回 (page_class, stats)。page_class 取**新增字符占比最高**的类 (平局 A 优先)。"""
    nn = ngrams(native_text or "")
    counts = Counter()
    novel_chars = Counter()
    for ln in (transcript or "").splitlines():
        if not ln.strip():
            continue
        cov = coverage(ln, nn)
        if cov >= 0.70:
            counts["D"] += 1
            continue
        c = classify_line(ln)
        counts[c] += 1
        novel_chars[c] += len(ln.strip())
    if not counts:
        return "D", {"D": 0}, {}
    if not novel_chars:
        return "D", dict(counts), {}
    # 平局优先级: A > E > B > C (A 是唯一的高价值类, 必须优先)
    _PRI = {"A": 3, "E": 2, "B": 1, "C": 0}
    best = max(novel_chars.items(), key=lambda kv: (kv[1], _PRI.get(kv[0], -1)))[0]
    return best, dict(counts), dict(novel_chars)


# ══════════════════════════════════════════════════════════════════════
# 渲染 (自用目录 + 独立 profile, 不碰生产缓存)
# ══════════════════════════════════════════════════════════════════════

_render_gate = asyncio.Semaphore(1)     # soffice 自身对并发敏感, 串行
PROFILE = "file:///tmp/a43/lo_profile"


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
    pages = sorted(__import__("glob").glob(f"{tmp}/page-*.png"))
    for i, png in enumerate(pages, 1):
        shutil.move(png, f"{out_dir}/page-{i}.png")
    shutil.rmtree(tmp, ignore_errors=True)
    return len(pages)


# ══════════════════════════════════════════════════════════════════════
# 视觉调用
# ══════════════════════════════════════════════════════════════════════

class Budget:
    def __init__(self, cap): self.cap, self.used = cap, 0
    def take(self):
        if self.used >= self.cap:
            raise RuntimeError(f"COST CAP REACHED: {self.used}/{self.cap}")
        self.used += 1
        return self.used


async def vision_one(client, budget: Budget, png_path: str, retries: int = 3):
    raw = open(png_path, "rb").read()
    b64 = base64.standard_b64encode(raw).decode()
    last = None
    for attempt in range(retries):
        try:
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
            return "\n".join(texts).strip(), thinks, r.usage.output_tokens, None
        except RuntimeError:
            raise
        except Exception as e:                      # noqa: BLE001
            last = e
            await asyncio.sleep(1.5 * (attempt + 1))
    return None, 0, 0, f"{type(last).__name__}: {str(last)[:180]}"


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 个目标页 (验证用)")
    ap.add_argument("--sample", action="store_true",
                    help="--limit 时用固定 seed 无偏随机抽样 (agent41 口径)")
    ap.add_argument("--seed", type=int, default=4301)
    ap.add_argument("--only-cached", action="store_true", help="只用已缓存的页 (跳过渲染)")
    ap.add_argument("--file", type=int, default=0, help="只跑指定 file_id")
    ap.add_argument("--out", default=f"{OUT}/results.jsonl")
    ap.add_argument("--resume-from", default="",
                    help="逗号分隔的已有 jsonl; 其中的 (file_id,page) 直接跳过, 不重复计费")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RENDER_ROOT, exist_ok=True)

    # ── resume: 已转写过的页不再调模型 (成本红线 2400, 复用前序验证批) ──
    done_keys = set()
    for seed in [s for s in args.resume_from.split(",") if s.strip()]:
        if not os.path.exists(seed):
            continue
        for ln in open(seed, encoding="utf-8"):
            try:
                r = json.loads(ln)
            except Exception:                        # noqa: BLE001
                continue
            if r.get("error"):
                continue
            done_keys.add((r["file_id"], r["page"]))
    if done_keys:
        print(f"[pipeline] resume: 复用 {len(done_keys)} 页已转写结果", flush=True)

    # ── 载入侦察结果 (= 现场重解析, 不用旧 chunk) ──
    pages = json.load(open(f"{OUT}/pages_recon.json", encoding="utf-8"))
    targets = [p for p in pages if p["native_chars"] < 143]
    if args.file:
        targets = [p for p in targets if p["file_id"] == args.file]
    if args.only_cached:
        targets = [p for p in targets if p["cache_hit"]]
    if args.limit:
        if args.sample:
            import random
            rnd = random.Random(args.seed)
            targets = rnd.sample(targets, min(args.limit, len(targets)))
        else:
            targets = targets[:args.limit]
    before_skip = len(targets)
    targets = [p for p in targets if (p["file_id"], p["page"]) not in done_keys]
    if before_skip != len(targets):
        print(f"[pipeline] 跳过已转写 {before_skip - len(targets)} 页", flush=True)
    print(f"[pipeline] 目标页 {len(targets)}", flush=True)

    # 现有索引正文 (现场解析的 native text) —— 用于 D 判定
    from app.core.database import get_db
    from app.services.file_service import FileService
    from app.services.file_parser_service import file_parser_service
    db = await anext(get_db())
    from sqlalchemy import text as sqlt
    fs = FileService()

    # 重建 native_text (与 native_chars 同源, 保证口径一致)
    nat_cache = {}
    need_files = sorted(set(p["file_id"] for p in targets))
    raw = (await db.execute(sqlt(
        "SELECT id, file_path FROM knowledge WHERE id = ANY(:ids)"
    ).bindparams(ids=need_files))).fetchall()
    fpath = {r.id: r.file_path for r in raw}
    print(f"[pipeline] 实时重解析 {len(need_files)} 个文件取 native_text ...", flush=True)
    import re as _re
    for fid in need_files:
        try:
            data = await fs.download_file(fpath[fid])
            text = await file_parser_service._parse_pptx(data)
            m = {}
            parts = _re.split(r"\[PAGE:(\d+)\]", text)
            # parts = [pre, '1', body1, '2', body2, ...]
            for i in range(1, len(parts), 2):
                m[int(parts[i])] = parts[i + 1] if i + 1 < len(parts) else ""
            nat_cache[fid] = m
        except Exception as e:                       # noqa: BLE001
            print(f"  [warn] {fid} native_text 失败: {str(e)[:120]}")
            nat_cache[fid] = {}
    print(f"[pipeline] native_text 就绪 ({len(nat_cache)} 文件)", flush=True)

    # ── 渲染缺失的文件 ──
    budget = Budget(COST_CAP)
    client = get_anthropic_client()

    need_render = sorted(set(p["file_id"] for p in targets if not p["cache_hit"]))
    render_stats = {"rendered": 0, "failed": 0, "cached_files": 0, "secs": 0.0}
    if need_render:
        print(f"[pipeline] 需渲染 {len(need_render)} 个文件 ...", flush=True)
        t0 = time.time()
        for n, fid in enumerate(need_render, 1):
            out_dir = f"{RENDER_ROOT}/{fid}"
            if os.path.exists(f"{out_dir}/page-1.png"):
                render_stats["cached_files"] += 1
                continue
            async with _render_gate:
                try:
                    data = await fs.download_file(fpath[fid])
                    total = render_pptx(data, out_dir)
                    render_stats["rendered"] += 1
                    print(f"  [{n}/{len(need_render)}] {fid}: {total} 页 "
                          f"({time.time()-t0:.0f}s)", flush=True)
                except Exception as e:                # noqa: BLE001
                    render_stats["failed"] += 1
                    print(f"  [{n}/{len(need_render)}] {fid}: 渲染失败 {str(e)[:120]}", flush=True)
        render_stats["secs"] = time.time() - t0

    # ── 视觉转写 ──
    sem = asyncio.Semaphore(CONCURRENCY)
    out_f = open(args.out, "a", encoding="utf-8")
    t0 = time.time()
    done = {"ok": 0, "err": 0}

    async def handle(p):
        async with sem:
            if p["cache_hit"]:
                png = f"{p['cache_dir']}/page-{p['page']}.png"
            else:
                png = f"{RENDER_ROOT}/{p['file_id']}/page-{p['page']}.png"
            if not os.path.exists(png):
                rec = {**p, "error": "png_missing"}
                done["err"] += 1
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return
            try:
                text, thinks, outtok, err = await vision_one(client, budget, png)
            except RuntimeError as e:
                rec = {**p, "error": str(e)}
                done["err"] += 1
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return
            if err:
                rec = {**p, "error": err}
                done["err"] += 1
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                return
            done["ok"] += 1
            rec = {
                "file_id": p["file_id"], "page": p["page"],
                "native_chars": p["native_chars"], "old_char_count": p["old_char_count"],
                "cache_hit": p["cache_hit"], "file_name": p["file_name"],
                "created_by": p["created_by"],
                "raw": text, "thinking_blocks": thinks, "out_tokens": outtok,
            }
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if done["ok"] % 50 == 0:
                out_f.flush()
                el = time.time() - t0
                print(f"  [{done['ok']}/{len(targets)}] {el:.0f}s "
                      f"{done['ok']/max(el,1):.2f}/s eta {(len(targets)-done['ok'])/max(done['ok']/max(el,1),1e-9):.0f}s "
                      f"cost={budget.used}", flush=True)

    await asyncio.gather(*[handle(p) for p in targets])
    out_f.close()
    json.dump({"render": render_stats, "vision_calls": budget.used,
               "ok": done["ok"], "err": done["err"],
               "wall_secs": time.time() - t0},
              open(f"{OUT}/run_stats_{os.path.basename(args.out)}.json", "w"),
              indent=1, ensure_ascii=False)
    print(f"[pipeline] 完成 ok={done['ok']} err={done['err']} "
          f"vision_calls={budget.used} wall={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())