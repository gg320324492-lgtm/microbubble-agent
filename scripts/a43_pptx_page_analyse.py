"""agent43 分析 (a41 口径忠实移植版)。

**为什么重写**: agent41 的 `/tmp/a41_analyze.py` 在容器里还在, 读出来后发现
本任务 brief 里的 "3.2~22.9x / 0.37x / 72% 重复" 全部是 **a41 的口径**:

  * 指标是**字符级**的 (A/B/C/D = 跨页累加的字符数), 不是页级
  * A = **非 FURNITURE 且非 NOISE 且未被现有索引覆盖** 的新增字符
    —— 即我第一版的 "A + E", 不是什么都不算就默认 A
  * 4-gram 前先 `norm()` (只留小写字母数字 + 汉字), 再算 4-gram 覆盖率
  * 分母 "现有索引" = `knowledge.source_type='drive_extracted'` 的**生产现状**
    正文 (agent38 修复**前**), 按 [PAGE:N] 切页并剥掉 `--- 第N页 ---`

保持可比 = 逐条照抄 a41 的 FURNITURE / NOISE 正则与 norm()。若自创一套,
"与历史可比" 就失去意义 (这正是类 20.220 的反面: 指标口径必须能对拍)。
本脚本同时保留我第一版的**窄 A** 作为次要视角。
"""
import json, re, sys, os
from collections import Counter, defaultdict

sys.path.insert(0, "/app")
from app.services.page_transcript_filter import filter_page_transcript

sys.stdout.reconfigure(encoding="utf-8")

# ══════════════ a41_analyze.py 原样照抄 (勿改) ══════════════
FURNITURE = re.compile(
    r'^(Time \(s\)|Pressure \(MPa\)|Pressure \(×10⁵ MPa\)|Pressure \(.*MPa\)|'
    r'Bubble radius( \(μm\)|\(nm\))?|Bubble interface area( \(μm²\)|\(nm²\))?|'
    r'Inside|Interfacial line|Velocity \(m/s\)|Particle \(μm\)|'
    r'天津大学|Tianjin University|天津大学环境科学与工程学院|'
    r'SCHOOL OF ENVIRONMENTAL SCIENCE&ENGINEERING,TIANJIN UNIVERSITY|'
    r'哈尔滨工业大学|HARBIN INSTITUTE OF TECHNOLOGY|'
    r'南京大学（gr）|NANJING UNIVERSITY|Nanjing University|'
    r'天津大学 环境学院|环境科学与工程学院|'
    r'研究进展|课题进展|实验系统：|第一次|第二次|'
    r'文件|开始|插入|设计|视图|帮助|公式|图例|颜色|字体|段落|页面|表格|图片|形状|'
    r'图表|视频|音频|超链接|批注|文本框|对象|幻灯片|放映|切换|动画|审阅|修订|保护|'
    r'设置|格式|排列|对齐|组合|旋转|效果|背景样式|调色板|语言|拼写检查|校对|朗读|'
    r'查找和替换|全局替换|更改文本|说明|撤销|重做|剪切|复制|粘贴|打印|另存为|'
    r'天津大学｜|汇报人：|单 位：|时 间：|阶跃$|谢谢[！!]?)$', re.I)
NOISE = re.compile(r'^(激活\s*Windows|转到[“"\'\s]*设置[”"\'\s]*以激活\s*Windows\.?)$')


def norm(s):
    return ''.join(ch.lower() for ch in s if ch.isalnum() or '一' <= ch <= '鿿')


def grams(s, n=4):
    return [s[i:i + n] for i in range(len(s) - n + 1)]


def presenter(fname):
    m = re.search(r"([一-鿿]{2,4})\.pptx$", fname or "")
    return m.group(1) if m else "(unknown)"


def abcd(raw, existing):
    """a41 口径: 返回 (A,B,C,D) 字符数。"""
    fr = filter_page_transcript(raw)
    eg = set(grams(norm(existing))) if len(norm(existing)) >= 4 else set()
    A = B = C = D = 0
    for ln in fr.text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if NOISE.match(s):
            C += len(s); continue
        if FURNITURE.match(s):
            B += len(s); continue
        g = grams(norm(s), 4)
        cov = (sum(1 for x in g if x in eg) / len(g)) if g else 0.0
        if cov >= 0.70:
            D += len(s)
        else:
            A += len(s)
    return A, B, C, D, fr
# ══════════════════════════════════════════════════


async def load_existing():
    """a41 口径的「现有索引」正文: drive_extracted 按 [PAGE:N] 切页。"""
    from app.core.database import get_db
    from sqlalchemy import text as sqlt
    db = await anext(get_db())
    PG = re.compile(r"\[PAGE:(\d+)\]")
    out = defaultdict(dict)
    fname = {}
    for fid, content, fn in (await db.execute(sqlt("""
        SELECT k.id, e.content, k.file_name
        FROM knowledge k JOIN knowledge e ON e.file_path = k.file_path
              AND e.source_type='drive_extracted' AND e.file_type='.pptx'
        WHERE k.storage_mode='drive' AND k.file_type='.pptx' AND k.deleted_at IS NULL
    """))).fetchall():
        content = content or ""
        marks = [(m.start(), int(m.group(1))) for m in PG.finditer(content)]
        for i, (pos, num) in enumerate(marks):
            end = marks[i + 1][0] if i + 1 < len(marks) else len(content)
            seg = content[pos + len(f"[PAGE:{num}]"):end]
            seg = re.sub(r"--- 第\d+页 ---\s*", "", seg)
            out[fid][num] = seg.strip()
        fname[fid] = fn
    return out, fname


def build(res_path, existing, fname):
    recs = [json.loads(l) for l in open(res_path, encoding="utf-8")]
    pages = []
    for r in recs:
        if r.get("error"):
            continue
        fid, pg = r["file_id"], r["page"]
        ex = existing.get(fid, {}).get(pg, "")
        A, B, C, D, fr = abcd(r["raw"], ex)
        pages.append({
            "fid": fid, "page": pg, "presenter": presenter(fname.get(fid)),
            "file_name": fname.get(fid),
            "native_chars": r["native_chars"], "old_char_count": r["old_char_count"],
            "existing_chars": len(ex), "raw_chars": len(r["raw"]),
            "transcript_chars": A + B + C + D,
            "A": A, "B": B, "C": C, "D": D,
            "blocked": fr.blocked, "block_reasons": list(fr.block_reasons),
            "third_party_paper": fr.third_party_paper, "template_page": fr.template_page,
            "template_kind": fr.template_kind, "paper_families": list(fr.paper_families),
            "paper_foreign_chars": fr.paper_foreign_chars,
            "chrome_ratio": round(fr.chrome_ratio, 4), "removed_chars": fr.removed_chars,
            "cleaned_chars": len(fr.text), "raw_text": r["raw"], "cleaned_text": fr.text,
        })
    pages.sort(key=lambda p: (p["fid"], p["page"]))
    return pages


def agg(pages, title):
    TA = sum(p["A"] for p in pages); TB = sum(p["B"] for p in pages)
    TC = sum(p["C"] for p in pages); TD = sum(p["D"] for p in pages)
    TT = TA + TB + TC + TD
    TE = sum(p["existing_chars"] for p in pages)
    print("\n" + "=" * 78)
    print(f"【{title}】{len(pages)} 页 / {len(set(p['fid'] for p in pages))} 文件 / "
          f"{len(set(p['presenter'] for p in pages))} 位汇报人")
    print("=" * 78)
    print(f"现有索引 (抽样页合计) : {TE:>9} 字符")
    print(f"视觉转写 (净化后)     : {TT:>9} 字符  (原始 {sum(p['raw_chars'] for p in pages)}, "
          f"过滤器剔除 {sum(p['removed_chars'] for p in pages)})")
    print(f"  ├ A 高价值新增      : {TA:>9}  ({TA/max(1,TT)*100:.1f}%)")
    print(f"  ├ B 图表通用配件    : {TB:>9}  ({TB/max(1,TT)*100:.1f}%)")
    print(f"  ├ C 噪声            : {TC:>9}  ({TC/max(1,TT)*100:.1f}%)")
    print(f"  └ D 重复(已在索引)  : {TD:>9}  ({TD/max(1,TT)*100:.1f}%)")
    print(f"\n★ 产出率 A/转写总量 = {TA}/{TT} = {TA/max(1,TT)*100:.1f}%")
    print(f"★ A/现有索引        = {TA}/{TE} = {TA/max(1,TE):.2f}x")
    print(f"  (转写总量/现有索引 = {TT/max(1,TE):.2f}x)")
    bl = [p for p in pages if p["blocked"]]
    print(f"\nblocked 页 = {len(bl)}/{len(pages)} = {len(bl)/max(1,len(pages)):.1f}%  "
          f"(third_party_paper={sum(1 for p in bl if p['third_party_paper'])}, "
          f"template={sum(1 for p in bl if p['template_page'])})")
    # blocked 排除后
    ub = [p for p in pages if not p["blocked"]]
    A2 = sum(p["A"] for p in ub); T2 = sum(p["transcript_chars"] for p in ub)
    E2 = sum(p["existing_chars"] for p in ub)
    print(f"★ blocked 排除后: A率={A2/max(1,T2)*100:.1f}%  "
          f"A/索引={A2/max(1,E2):.2f}x  (转写/索引={T2/max(1,E2):.2f}x)  "
          f"入库页 {len(ub)}/{len(pages)}")
    return {"TA": TA, "TT": TT, "TE": TE, "A_existing": TA / max(1, TE),
            "A_rate": TA / max(1, TT), "blocked": len(bl), "n": len(pages)}


def bands(pages):
    BANDS = [(0, 20), (20, 60), (60, 143)]
    LAB = ["0-19 (纯图)", "20-59 (极少字)", "60-142 (<中位)"]
    print("\n" + "=" * 78)
    print("【按 native_chars 分档 — 产出率】(只跑 <143 档)")
    print("=" * 78)
    print(f"{'档':<16}{'页数':>6}{'现有索引':>10}{'转写':>9}{'A':>9}{'A率':>9}{'A/索引':>9}{'D率':>8}")
    for (lo, hi), lab in zip(BANDS, LAB):
        sub = [p for p in pages if lo <= p["native_chars"] < hi]
        if not sub:
            continue
        a = sum(x["A"] for x in sub); t = sum(x["transcript_chars"] for x in sub)
        e = sum(x["existing_chars"] for x in sub); d = sum(x["D"] for x in sub)
        print(f"{lab:<16}{len(sub):>6}{e:>10}{t:>9}{a:>9}"
              f"{(a/t*100 if t else 0):>8.1f}%{(a/e if e else 0):>8.2f}x{(d/t*100 if t else 0):>7.1f}%")


def presenters(pages):
    print("\n" + "=" * 78)
    print("【按汇报人 — 是否被单一课题组主导】")
    print("=" * 78)
    by = defaultdict(lambda: [0, 0, 0, 0])
    for p in pages:
        b = by[p["presenter"]]
        b[0] += 1; b[1] += p["A"]; b[2] += p["transcript_chars"]; b[3] += p["existing_chars"]
    rows = sorted(by.items(), key=lambda kv: -kv[1][0])
    TA = sum(p["A"] for p in pages)
    print(f"{'汇报人':<12}{'页数':>6}{'占样本':>8}{'转写':>9}{'A':>9}{'A率':>9}{'A/索引':>9}")
    for name, (n, a, t, e) in rows:
        print(f"{name:<12}{n:>6}{n/len(pages)*100:>7.1f}%{t:>9}{a:>9}"
              f"{(a/t*100 if t else 0):>8.1f}%{(a/e if e else 0):>8.2f}x")
    top = max(rows, key=lambda kv: kv[1][0])
    print(f"\n最大单一汇报人 {top[0]}: {top[1][0]}/{len(pages)} 页 "
          f"({top[1][0]/len(pages)*100:.1f}%), 占 A 字符 {top[1][1]/max(1,TA)*100:.1f}%")


def crossval(pages):
    """与 a41 的 269 页抽样交叉验证: 重叠页上的分类一致率。"""
    p41 = json.load(open("/tmp/a41/pages.json", encoding="utf-8"))
    m41 = {(int(p["fid"]), int(p["page"])): p for p in p41}
    mine = {(p["fid"], p["page"]): p for p in pages}
    common = sorted(set(m41) & set(mine))
    print("\n" + "=" * 78)
    print(f"【与 agent41 抽样交叉验证】a41={len(m41)} 页, a43={len(mine)} 页, "
          f"重叠={len(common)} 页")
    print("=" * 78)
    if not common:
        print("无重叠页。")
        return
    # 页级主类 (按字符占比最大) 一致率
    agree = 0
    rows = []
    for k in common:
        a, b = m41[k], mine[k]
        def dom(x):
            c = {"A": x["A"], "B": x["B"], "C": x["C"], "D": x["D"]}
            m = max(c.values())
            return max((kk for kk, vv in c.items() if vv == m),
                       key=lambda kk: {"A": 3, "D": 2, "B": 1, "C": 0}[kk])
        d1, d2 = dom(a), dom(b)
        agree += (d1 == d2)
        rows.append((k, d1, d2, a["A"], b["A"], a["existing_chars"], b["existing_chars"]))
    print(f"页级主类一致率 = {agree}/{len(common)} = {agree/len(common)*100:.1f}%")
    # D 判定一致 (最关键的判据)
    dd = sum(1 for k in common
             if (m41[k]["D"] > 0.5 * max(1, m41[k]["transcript_chars"]))
             == (mine[k]["D"] > 0.5 * max(1, mine[k]["transcript_chars"])))
    print(f"D 为主类的一致率 = {dd}/{len(common)} = {dd/len(common)*100:.1f}%")
    # 分母一致性 (口径核对)
    de = sum(1 for k in common if m41[k]["existing_chars"] == mine[k]["existing_chars"])
    print(f"「现有索引」分母逐页一致 = {de}/{len(common)} = {de/len(common)*100:.1f}%  "
          f"(口径是否对齐的直接证据)")
    # A/索引 倍数对比
    mA = sum(mine[k]["A"] for k in common); mE = sum(mine[k]["existing_chars"] for k in common)
    pA = sum(m41[k]["A"] for k in common); pE = sum(m41[k]["existing_chars"] for k in common)
    print(f"重叠页 A/索引: a41={pA/max(1,pE):.2f}x   a43={mA/max(1,mE):.2f}x")
    diff = [(k, m41[k]["A"], mine[k]["A"]) for k in common
            if abs(m41[k]["A"] - mine[k]["A"]) > max(20, 0.3 * max(1, m41[k]["A"]))]
    print(f"A 字符差异 >30% 的重叠页 = {len(diff)}/{len(common)}")
    for k, x, y in diff[:8]:
        print(f"   fid={k[0]} p{k[1]}: a41 A={x}  a43 A={y}")


if __name__ == "__main__":
    import asyncio
    res = sys.argv[1] if len(sys.argv) > 1 else "/tmp/a43/results.jsonl"
    title = sys.argv[2] if len(sys.argv) > 2 else "agent43 <143 档全量"
    existing, fname = asyncio.run(load_existing())
    pages = build(res, existing, fname)
    json.dump(pages, open(res.replace(".jsonl", "_a41.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    agg(pages, title)
    bands(pages)
    presenters(pages)
    if os.path.exists("/tmp/a41/pages.json"):
        crossval(pages)