"""生成「簇起名试听包」—— 人工试做材料 (Phase 1f 的「1/12 是代理下界」需要真人定真值)。

产物 (默认输出到桌面):
    簇起名试听_m259/
        清单.md              簇号/段数/候选名/文本摘要/音频文件名/**真值(留空待填)**
        清单.csv              同上, 便于填表
        音频/簇{cid}_{候选名}.wav   每簇一段 10–20s 的 16k 单声道 WAV
        转录/簇{cid}_转录.txt         簇内转录文本 (前 12 条, 带**系统当前**的说话人标记)
        说明.md               给主指挥的说明 (怎么用/要回答什么/注意事项)

⚠️ **不泄漏台账真值**
   - 清单的「真值」列**留空**, 由主指挥自己填
   - 转录里的说话人标记用**系统当前**的标签 (不是台账), 否则等于把答案给了
   - 「系统命名正确/错误」**不告诉主指挥** ⇒ 否则会高估难度
     ⇒ 但**对照簇必须包含在包里** (主会话要求) ⇒ 做法: **全部 6 个簇都放进包**,
       清单里不标注哪些是「要改的」⇒ 主指挥看到的是完整集合, 不会只盯着难的那几个。

口径: KMeans(k=6, n_init=3, 固定种子) on **生产 ASR 段** (与 Phase 1f 同参数)
⇒ 候选名 = 簇质心 ↔ **现役成员质心** 的最近者 (用户实际会看到的那个名字)。
"""
import argparse
import asyncio
import collections
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SR = 16000
K_FIXED = 6
SEED = 20261031
MIN_WAV_SEC = 10.0
MAX_WAV_SEC = 20.0
N_TEXT = 12


def log(m):
    print("[pack] " + m, flush=True)


def fetch_audio(key):
    local = os.path.join("/tmp/vp", "src_" + key.replace("/", "__"))
    if os.path.exists(local) and os.path.getsize(local) > 1024:
        return local
    from minio import Minio
    c = Minio("minio:9000", access_key=os.environ["MINIO_ACCESS_KEY"],
              secret_key=os.environ["MINIO_SECRET_KEY"], secure=False)
    resp = c.get_object("microbubble", key)
    try:
        data = resp.read()
    finally:
        resp.close()
        resp.release_conn()
    with open(local, "wb") as fh:
        fh.write(data)
    log("下载音频 %s (%.1f MB)" % (key, len(data) / 1048576))
    return local


def decode_audio(path):
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def write_wav(path, pcm):
    import soundfile as sf
    sf.write(path, pcm, SR, subtype="PCM_16")


def pick_wav_span(segs):
    """从簇内挑一段 10–20 秒: 取**时间相邻**的若干段, 累计时长落在 [10,20] 且文本量最大。

    ⚠️ 原版是 while 双指针, 当 span < MIN 时不推进 i/j ⇒ **死循环**
    ⇒ 改成固定的双重循环 + 前缀和 (簇内段数不大, O(n^2) 可接受)。
    """
    segs = sorted(segs, key=lambda s: s["start"])
    n = len(segs)
    if n == 0:
        return None
    pre = [0]
    for s in segs:
        pre.append(pre[-1] + len(s.get("text") or ""))
    best = None
    for i in range(n):
        for j in range(i, n):
            span = segs[j]["end"] - segs[i]["start"]
            if span > MAX_WAV_SEC:
                break
            if span < MIN_WAV_SEC:
                continue
            chars = pre[j + 1] - pre[i]
            if best is None or chars > best[0]:
                best = (chars, i, j)
    if best is None:
        # 兜底: 取簇内最长的一段(可能不足 10s)
        k = max(range(n), key=lambda x: segs[x]["end"] - segs[x]["start"])
        return (segs[k]["start"], segs[k]["end"])
    _, i, j = best
    return (segs[i]["start"], segs[j]["end"])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/pack_m259")
    ap.add_argument("--meeting", type=int, default=259)
    ap.add_argument("--audio-url", default="")
    args = ap.parse_args()

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.models.member import Member

    engine, Session = create_celery_engine_and_session()
    mt, db_cent = {}, {}
    async with Session() as db:
        m = (await db.execute(
            select(Meeting).where(Meeting.id == args.meeting))).scalar_one()
        mt[args.meeting] = {"audio_url": m.audio_url,
                            "segs": sorted(m.transcript or [],
                                           key=lambda s: float(s.get("start") or 0))}
        for mm in (await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            v = np.asarray(mm.voice_embedding, dtype=np.float32)
            if np.linalg.norm(v) > 0:
                db_cent[mm.name] = v / np.linalg.norm(v)
    await engine.dispose()
    POOL = sorted(db_cent)
    log("会议 %d: %d 段; 现役质心 %d 人" % (
        args.meeting, len(mt[args.meeting]["segs"]), len(POOL)))

    # ---- 该场在 Phase 1 素材里的行 ----
    rows = [i for i, mm in enumerate(META)
             if mm["kind"] == "seg" and mm["meeting"] == args.meeting]
    if not rows:
        raise RuntimeError("Phase 1 素材里没有会议 %d 的段" % args.meeting)
    Ek = E[rows]
    from sklearn.cluster import KMeans
    lab = KMeans(n_clusters=min(K_FIXED, len(rows)), n_init=3,
                 random_state=SEED).fit_predict(Ek)
    cents = np.stack([norm for norm in [Ek[lab == c].mean(0) / max(
        1e-9, np.linalg.norm(Ek[lab == c].mean(0))) for c in sorted(set(lab.tolist()))]])

    # 簇 → 段 (用 Phase 1 素材里的 start/end) 与 簇 → 系统转录段
    mat = {}
    for r, i in enumerate(rows):
        mat.setdefault(int(lab[r]), []).append({
            "start": META[i]["start"], "end": META[i]["end"],
            "text": (mt[args.meeting]["segs"][0] or {}).get("text", "") or ""})
    # 用 DB 的转录补文本 (按 start/end 对齐)
    db_segs = [s for s in mt[args.meeting]["segs"]
               if float(s.get("end") or 0) - float(s.get("start") or 0) >= 0.5]
    for ci, lst in mat.items():
        for item in lst:
            mid_t = (item["start"] + item["end"]) / 2.0
            for s in db_segs:
                if float(s.get("start") or 0) <= mid_t <= float(s.get("end") or 0):
                    item["text"] = (s.get("text") or "")
                    item["speaker"] = (s.get("speaker") or "")
                    break
            item.setdefault("speaker", "")

    # ---- 候选名 (现役成员质心最近者 = 用户实际看到的名字) ----
    names = []
    for c in cents:
        names.append(min(POOL, key=lambda q: float(1.0 - np.dot(c, db_cent[q]))))

    # ---- 输出目录 ----
    out = args.out
    os.makedirs(os.path.join(out, "音频"), exist_ok=True)
    os.makedirs(os.path.join(out, "转录"), exist_ok=True)
    audio_path = fetch_audio(args.audio_url or mt[args.meeting]["audio_url"])
    pcm = decode_audio(audio_path)
    log("音频解码 %.1fs" % (len(pcm) / SR))

    rows_out = []
    for ci in sorted(mat):
        segs = mat[ci]
        cand = names[ci]
        span = pick_wav_span(segs)
        wav_name = ""
        if span:
            a, b = span
            lo, hi = int(a * SR), min(int(b * SR), len(pcm))
            if hi > lo:
                wav_name = "簇%d_%s.wav" % (ci, cand)
                write_wav(os.path.join(out, "音频", wav_name), pcm[lo:hi])
                log("  簇%d (%s) 段 %d ⇒ WAV %.1fs" % (ci, cand, len(segs), (hi - lo) / SR))
        # 转录文本 (前 N_TEXT 条)
        txt_lines = []
        for k, s in enumerate(sorted(segs, key=lambda x: x["start"])[:N_TEXT]):
            txt_lines.append("[%d] %s: %s" % (k + 1, s.get("speaker") or "?", s.get("text") or ""))
        with open(os.path.join(out, "转录", "簇%d_转录.txt" % ci), "w", encoding="utf-8") as fh:
            fh.write("簇 %d | 系统候选名: %s | 段数: %d\n\n" % (ci, cand, len(segs)))
            fh.write("\n".join(txt_lines) + "\n")
        summary = " ".join(s.get("text") or "" for s in
                           sorted(segs, key=lambda x: x["start"])[:6])[:60]
        # 簇内**现役**标签分布 (系统输出, 不是台账真值 ⇒ 不泄漏答案)
        lbl_hist = collections.Counter(s.get("speaker") or "?" for s in segs)
        lbl_dist = " / ".join("%s %d" % (k, v) for k, v in lbl_hist.most_common())
        rows_out.append({
            "簇号": "簇%d" % ci,
            "段数": len(segs),
            "系统候选名": cand,
            "簇内现役标签分布": lbl_dist,
            "文本摘要": summary,
            "音频文件": wav_name,
            "真值(请填)": "",
            "只凭文本能判?": "",
        })

    # ---- 清单 ----
    cols = ["簇号", "段数", "系统候选名", "簇内现役标签分布", "文本摘要", "音频文件",
            "真值(请填)", "只凭文本能判?"]
    with open(os.path.join(out, "清单.md"), "w", encoding="utf-8") as fh:
        fh.write("# 会议 %d 簇起名试听清单\n\n" % args.meeting)
        fh.write("| " + " | ".join(cols) + " |\n")
        fh.write("|" + "---|" * len(cols) + "\n")
        for r in rows_out:
            fh.write("| " + " | ".join(
                str(r[c]).replace("|", "／").replace("\n", " ") for c in cols) + " |\n")
        fh.write("\n> 「真值」列请填**这簇实际上是谁**（填成员的姓名，或「发言人?」）。\n")
        fh.write("> 「只凭文本能判?」列请填 **能 / 不能 / 不确定** —— "
                 "这是我们要的那个比例。\n")
    import csv
    with open(os.path.join(out, "清单.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    with open(os.path.join(out, "说明.md"), "w", encoding="utf-8") as fh:
        fh.write(
            "# 簇起名试听包 —— 说明\n\n"
            "## 这份材料要回答的问题\n\n"
            "**「光看转录文本，能不能判断一个簇是谁？」**\n\n"
            "背景: 自动聚类把同一说话人的段聚成一个「簇」, 但系统给簇起的名字只有约 **64%** 是对的\n"
            "(30% 左右的簇被安错了人)。有 5 种句式特征的自动代理只能纠正 **1/12** ——\n"
            "但那是**下界** (代理只认固定句式, 认不出「这是学生在向老师汇报」这种语义判断)。\n"
            "**这份材料就是用来定真值的。**\n\n"
            "## 怎么用\n\n"
            "1. 打开 `音频/` 下的 WAV (10–20 秒, 16k 单声道) —— 戴耳机逐个听。\n"
            "2. 对照 `转录/` 下的文本, 先**只看文本**判一次: 你能不能确定这个簇是谁?\n"
            "3. 再听音频确认。\n"
            "4. 把结论填进 `清单.md` / `清单.csv` 的「真值(请填)」列。\n\n"
            "## 需要你回答的两件事\n\n"
            "A. **真值**: 每个簇是谁 (填姓名或「发言人?」)。\n"
            "B. **只看文本能不能判**: 在清单上另加一列「只凭文本能判?」(能/不能/不确定)。\n"
            "   ⇒ 这就是我们要的那个比例。\n\n"
            "## 注意事项\n\n"
            "- 清单里**没有**标注哪些簇是系统命名错的 ⇒ 请**逐个**判断, 不要只挑看着可疑的。\n"
            "- 转录里的说话人标记是**系统当前的输出**, 不是人工确认结果 ⇒ 它可能就是错的。\n"
            "- WAV 是从簇内**连续**的一段里挑的, 尽量说话清楚。\n"
            "- ⭐ **「系统候选名」这一列可能出现重名** —— 这是系统当前的真实行为:\n"
            "  聚类把音频分成若干簇, 每个簇再按「簇质心 ↔ 成员声纹质心最近」取一个名字,\n"
            "  **不同簇可以拿到同一个名字**。所以看到几行同名, 不是说它们是同一个人。\n"
            "- 「簇内现役标签分布」列是**系统当前**给这些段打的标签, 用来对照参考, 同样不是答案。\n")

    log("已写出 %s (%d 个簇)" % (out, len(rows_out)))


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


if __name__ == "__main__":
    asyncio.run(main())
