"""按**生产判据**(含 margin)给存量会议重新标发言人, 人工裁决优先。

为什么需要这个脚本
------------------
`POST /meetings/{id}/reprocess` 的 `speaker_assignment` 阶段**只重算 speaker_stats**,
根本不重跑声纹识别 (meeting_reprocessing_service.py:287);
而 `scripts/reprocess_meeting.py` 用的是**旧算法**(`vote_names_by_cluster`),
没有 margin。⇒ 要让存量会议按新判据重算, 只能用本脚本。

本脚本**复刻生产路径**(类 20.243 ⑥: 判据必须复刻生产路径, 不能复刻"看起来像的那条"):
  1. 逐转录段切音频 → GPU 提取 3D-Speaker 嵌入 (VoiceprintService.batch_extract_embeddings)
  2. `smart_select_k` 聚类 (与 post_meeting_tasks 阶段 2.3 同参: n_expected=3, K∈[2,8])
  3. `vote_with_quality_gates` 投票 (生产函数, 带 margin 判据)
  4. 分配: **人工裁决(meeting_speaker_adjudications)逐段优先**, 其次聚类名, 最后「发言人?」
  5. 写回: `update_transcript_speaker` (保留 start/end/speaker_label/text) + speaker_mapping
     + speaker_stats, 写前建备份表

用法 (容器内):
    python scripts/voiceprint/relabel_by_margin.py --meeting 254 --dry-run
    python scripts/voiceprint/relabel_by_margin.py --meeting 254 --apply
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, "/app")

SR = 16000
MIN_SEC = 0.5
WORK = "/tmp/vp"

# 安全闸 C 的容差: 新增段到该成员 anchor 的中位距离, 不得超过「同场人耳确认段」
# 中位距离的该倍数。
# ⚠️ **这个数不是凭空设的**(类 20.226 ⑤): 6 场实测的比值分两组——
#   接受组 = {0.957, 0.976, 1.010}(256 张宏魁/王天志, 229 王天志)
#   拒绝组 = {1.242, 1.281}(250 蒋芦笛/王天志)
#   两组之间有**空档 [1.010, 1.242]** ⇒ 阈值取空档中部 1.15。
GATE_C_RATIO_MAX = 1.15


def decode_audio(path: str) -> np.ndarray:
    p = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
        capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError("ffmpeg 解码失败: " + p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def fetch_audio(key: str) -> str:
    """从 MinIO 取会议音频 (缓存键含**完整对象键**, 不用 basename — 类 20.242)。"""
    os.makedirs(WORK, exist_ok=True)
    local = os.path.join(WORK, "src_" + key.replace("/", "__"))
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
    print("[vp] 下载 %s (%.1f MB)" % (key, len(data) / 1048576), flush=True)
    return local


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ledger-files", default=os.environ.get(
        "LEDGER_FILES", "/tmp/ledger_13.json,/tmp/ledger_30.json"))
    args = ap.parse_args()
    mid = args.meeting

    from sqlalchemy import select, text as sqlt
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.transcript_editor import update_transcript_speaker
    from app.services.voiceprint_service import VoiceprintService
    from app.services.voiceprint_voting import (
        get_min_margin, smart_select_k, vote_with_quality_gates,
    )
    from app.services.speaker_adjudication_service import build_resolver

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        m = (await db.execute(select(Meeting).where(Meeting.id == mid))).scalar_one()
        raw = list(m.transcript or [])
        pol = list(m.transcript_polished or [])
        audio_url = m.audio_url
        # ⚠️ **下标必须显式映射, 不能靠「库里恰好是排好的」(类 20.248 ⑥ 的同型坑)**:
        #   `segs` 是**按 start 排序**的, 而 `raw`/`cur_raw` 是**库内原序**。
        #   若两者顺序不一致 ⇒ 用 `segs` 的下标去写 `cur_raw` ⇒ **段与标签张冠李戴**,
        #   而且**不会报错**(只是标错人)。
        #   实测 256/229/243 的库内顺序确实已按 start 排好 ⇒ 当时用下标对齐是对的;
        #   但那是**当时的事实**, 不是**不变量** ⇒ 这里用 `order` 显式映射, 与顺序无关。
        order = sorted(range(len(raw)), key=lambda i: float(raw[i].get("start") or 0))
        segs = [raw[i] for i in order]

        # ---- 1. 音频 + 逐段嵌入 ----
        pcm = decode_audio(fetch_audio(audio_url))
        need = max((float(s.get("end") or 0) for s in segs), default=0.0)
        if len(pcm) / SR < need * 0.95:
            raise RuntimeError("音频长度不足: %.1fs < 转录 %.1fs" % (len(pcm) / SR, need))
        idxs, clips = [], []
        for i, s in enumerate(segs):
            st, en = float(s.get("start") or 0), float(s.get("end") or 0)
            if en - st < MIN_SEC:
                continue
            a = pcm[int(st * SR):int(en * SR)]
            if len(a) < SR * MIN_SEC:
                continue
            idxs.append(i)
            clips.append(a)
        svc = VoiceprintService()
        embs = svc.batch_extract_embeddings(clips)
        seg_embs = [None] * len(segs)
        for i, e in zip(idxs, embs):
            if e is not None and not np.all(e == 0):
                seg_embs[i] = np.asarray(e, dtype=np.float32)
        valid = sum(1 for e in seg_embs if e is not None)
        print("[vp] 会议 %d: %d 段 (有效嵌入 %d), 音频 %.1fs" % (
            mid, len(segs), valid, len(pcm) / SR), flush=True)

        # ---- 2. 聚类 (与生产同参) ----
        labels, k, score, _ = smart_select_k(seg_embs=seg_embs, n_expected=3, min_k=2, max_k=8)
        clusters = list(labels)
        print("[vp] smart_select_k: K=%d composite=%.3f" % (k, score), flush=True)

        # ---- 3. enrolled 池 (+ context 过滤, 与生产一致) ----
        from app.models.member import Member
        rows = (await db.execute(
            select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all()
        enrolled = [(r.id, r.name, np.array(r.voice_embedding, dtype=np.float32),
                      r.voice_sample_count or 1) for r in rows]
        all_enrolled_names = {e[1] for e in enrolled}
        ctx_names = set()
        try:
            from app.services.voiceprint_voting import (
                extract_context_speakers, get_recent_meeting_speakers,
                resolve_context_to_names,
            )
            ctx_raw = extract_context_speakers(m)
            ctx_names = await resolve_context_to_names(ctx_raw, db) if ctx_raw else set()
            hist = await get_recent_meeting_speakers(mid, db, lookback_count=10, lookback_days=90)
            if hist:
                ctx_names = ctx_names | hist
        except Exception as e:
            print("[vp] context 解析失败(不启用过滤): %r" % (e,), flush=True)
        if ctx_names:
            filt = [e for e in enrolled if e[1] in ctx_names]
            if filt:
                enrolled = filt
            print("[vp] context 过滤后 enrolled 池 %d 人" % len(enrolled), flush=True)

        # ---- 4. 生产投票 (带 margin) ----
        margin = get_min_margin()
        cluster_names = vote_with_quality_gates(
            seg_embs, clusters, enrolled, context_names=None,
            center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
        )
        print("[vp] margin=%.2f 聚类命名: %s" % (
            margin, {k: (v[0], round(v[1], 3), v[2], v[3]) for k, v in cluster_names.items()}), flush=True)

        # ---- 5. 分配 (人工裁决逐段优先) ----
        resolver = await build_resolver(db, mid)
        print("[vp] 人工裁决 %d 条" % len(resolver), flush=True)
        cur_raw, cur_pol, cur_map = list(raw), list(pol), dict(m.speaker_mapping or {})
        before = Counter(s.get("speaker") for s in raw)
        new_speaker = {}
        adjudicated = 0
        for i, s in enumerate(segs):
            decided = resolver.lookup(s.get("start"), s.get("end"))
            if decided:
                new_speaker[i] = decided
                adjudicated += 1
                continue
            cid = clusters[i] if i < len(clusters) else -1
            name = None
            if cid is not None and cid >= 0:
                entry = cluster_names.get(cid)
                if entry and entry[0]:
                    name = entry[0]
            new_speaker[i] = name or "发言人?"
        after = Counter(new_speaker.values())
        print("[vp] 裁决覆盖 %d 段" % adjudicated, flush=True)
        print("[vp] before=%s" % dict(sorted(before.items())), flush=True)
        print("[vp] after =%s" % dict(sorted(after.items())), flush=True)
        changed = sum(1 for i, s in enumerate(segs)
                      if s.get("speaker") != new_speaker.get(i))
        print("[vp] 标签会变的段: %d / %d" % (changed, len(segs)), flush=True)

        # ---- 5b. 安全闸: 用台账真值给「改前/改后」打分, 不达标不写 ----
        ledger_blocks = []
        for lp in args.ledger_files.split(","):
            if not lp.strip() or not os.path.exists(lp.strip()):
                continue
            ld = json.load(open(lp.strip(), encoding="utf-8"))
            for b in ld.get("blocks", []):
                if b.get("_可用") is False:
                    continue
                ledger_blocks.append((int(b["meeting"]), float(b["s"]), float(b["e"]),
                                      {"环境声": "发言人?", "人群杂音": "发言人?",
                                       "视频": "发言人?"}.get(b["who"], b["who"])))
        lb = [x for x in ledger_blocks if x[0] == mid]
        truth_score = {"before_ok": 0, "before_n": 0, "after_ok": 0, "after_n": 0,
                       "before_wrong": {}, "after_wrong": {}}
        for i, sg in enumerate(segs):
            st, en = float(sg.get("start") or 0), float(sg.get("end") or 0)
            midp = (st + en) / 2.0
            truth = None
            for mm, s0, e0, who in lb:
                if s0 <= midp <= e0:
                    truth = who
                    break
            if truth is None:
                continue
            truth_score["before_n"] += 1
            truth_score["after_n"] += 1
            if sg.get("speaker") == truth:
                truth_score["before_ok"] += 1
            else:
                truth_score["before_wrong"].setdefault(
                    "%s->%s" % (sg.get("speaker"), truth), 0)
                truth_score["before_wrong"]["%s->%s" % (sg.get("speaker"), truth)] += 1
            ns = new_speaker.get(i)
            if ns == truth:
                truth_score["after_ok"] += 1
            else:
                truth_score["after_wrong"].setdefault("%s->%s" % (ns, truth), 0)
                truth_score["after_wrong"]["%s->%s" % (ns, truth)] += 1
        bn = max(1, truth_score["before_n"])
        an = max(1, truth_score["after_n"])
        print("[vp] 台账真值打分: 改前 %d/%d (%.1f%%)  改后 %d/%d (%.1f%%)" % (
            truth_score["before_ok"], truth_score["before_n"], truth_score["before_ok"] / bn * 100,
            truth_score["after_ok"], truth_score["after_n"], truth_score["after_ok"] / an * 100), flush=True)
        if truth_score["before_wrong"]:
            print("[vp]   改前错名明细: %s" % dict(sorted(
                truth_score["before_wrong"].items(), key=lambda kv: -kv[1])[:6]), flush=True)
        if truth_score["after_wrong"]:
            print("[vp]   改后错名明细: %s" % dict(sorted(
                truth_score["after_wrong"].items(), key=lambda kv: -kv[1])[:6]), flush=True)
        if truth_score["after_ok"] < truth_score["before_ok"]:
            print("[vp] ⚠ 安全闸A: 改后台账真值判对数(%d) < 改前(%d) ⇒ **不写库**" % (
                truth_score["after_ok"], truth_score["before_ok"]), flush=True)
            await engine.dispose()
            return

        # ---- 安全闸 B1: 候选池必须覆盖「台账真值里所有有声纹的人」 ----
        # 背景: 模型**只能**从候选池里挑名字。若某位真值人物虽然有声纹却被
        #       `context` 过滤踢出候选池, 重标必然把段**兜底**给池里最接近的别人
        #       (类 20.247 的「最大类兜底」)。
        # 实测: 会议 243 的池 = {宋洋,张宏魁,赵航佳,陈金薪,韩重阳}, 而台账真值
        #       25 段**全是王天志** ⇒ 王天志被踢出 ⇒ 613 段全部兜底给宋洋。
        # ⇒ 这是**纯逻辑判据, 不依赖任何阈值**。
        ledger_people = {who for mm, s0, e0, who in lb}
        pool_names = {e[1] for e in enrolled}
        lost = sorted(p for p in ledger_people
                      if p in all_enrolled_names and p not in pool_names)
        if lost:
            print("[vp] ⚠ 安全闸B1: 台账真值里的人被 context 过滤踢出候选池 ⇒ **不写库**: %s"
                  % ", ".join(lost), flush=True)
            print("[vp]     模型不可能认出一个不在候选集里的人; 重标只会把段兜底给最接近的别人。",
                  flush=True)
            await engine.dispose()
            return
        print("[vp] 安全闸B1: 台账真值里所有有声纹的人都在候选池内 ⇒ 通过 (池 %d 人: %s)"
              % (len(pool_names), ", ".join(sorted(pool_names))), flush=True)

        # ---- 公共: anchor 向量(用于 B2 / C 的距离计算) ----
        anchor_vec = {e[1]: e[2] / (np.linalg.norm(e[2]) + 1e-9) for e in enrolled}
        anchor_names = list(anchor_vec.keys())
        anchor_mat = np.stack([anchor_vec[n] for n in anchor_names]) if anchor_names else None

        def nearest_anchor(i):
            e = seg_embs[i]
            if e is None or anchor_mat is None:
                return None, None
            d = np.linalg.norm(anchor_mat - e, axis=1)
            j = int(np.argmin(d))
            return anchor_names[j], float(d[j])

        # ---- 迁移报表: 「原本有名字 → 换成另一个名字」是最危险的一类改动 ----
        # 台账只覆盖 2%–45% 的段 ⇒ 台账外的改动**无法用台账验证**(类 20.244)。
        # 闸 A / B / C 都看不到「把 A 的段改判成 B」这类**换名**(它们只看
        # 「未识别→有名字」的补名与总数)⇒ 必须单独报表 + 声学交叉验证。
        # 判据(相对量, 不设自造阈值): 逐段最近 anchor **支持新名字的比例**;
        # 若多数段的最近 anchor 仍是**原名字** ⇒ 这次换名没有声学依据 ⇒ 报警。
        trans = Counter()
        for i, s in enumerate(segs):
            cur = s.get("speaker") or "发言人?"
            new = new_speaker.get(i) or "发言人?"
            if cur != new:
                trans["%s -> %s" % (cur, new)] += 1
        if trans:
            print("[vp] 迁移明细: %s" % dict(trans.most_common()), flush=True)
        renames = {}
        for i, s in enumerate(segs):
            cur = s.get("speaker") or "发言人?"
            new = new_speaker.get(i) or "发言人?"
            if cur == new or cur == "发言人?" or new == "发言人?":
                continue
            renames.setdefault("%s -> %s" % (cur, new), []).append(i)
        for label, idxs in sorted(renames.items(), key=lambda kv: -len(kv[1])):
            pairs = [nearest_anchor(i) for i in idxs]
            valid_pairs = [(n, d) for n, d in pairs if n is not None]
            new_name = label.split(" -> ")[1]
            agree = sum(1 for n, _ in valid_pairs if n == new_name)
            ratio = agree / len(valid_pairs) if valid_pairs else 0.0
            med = (float(np.median([d for _, d in valid_pairs]))
                   if valid_pairs else float("nan"))
            print("[vp] 换名 %s: %d 段, 最近 anchor 支持新名字 %.0f%%(%d/%d), 中位距离 %.3f%s" % (
                label, len(idxs), ratio * 100, agree, len(valid_pairs), med,
                "" if ratio >= 0.5 else "  ⚠ 声学不支持这次换名 ⇒ 台账外的高风险改动"),
                flush=True)

        # ---- 安全闸 B2: 「台账外成员占大段」的告警, 必须用**最近 anchor**交叉验证 ----
        # 背景(类 20.249): 本项目台账覆盖率只有 4%–23%(229 = 8.5%, 243 = 4.1%),
        #       此时「台账里没出现」**≠**「没发言」⇒ 闸 B 会把真正发了言的人误报。
        # 实测: 229 的杜同贺(台账里没出现)拿到 31 段(10.9%)触发闸 B, 但
        #       **逐段最近 anchor 有 24/31 指向杜同贺** ⇒ 告警被证伪 ⇒ 他确实发言了。
        # 解药 = 逐段最近 anchor: 多数段最近就是他 ⇒ 命名可信, 告警作废。
        total_segs = len(segs)
        new_heavy = []
        for name, cnt in after.items():
            if name in ledger_people or name.startswith("发言人") or cnt <= 0:
                continue
            if cnt > total_segs * 0.10:
                new_heavy.append((name, cnt))
        for name, cnt in new_heavy:
            newly = [i for i in range(total_segs)
                     if new_speaker.get(i) == name and segs[i].get("speaker") != name]
            agree = n_valid = 0
            for i in newly:
                na, _d = nearest_anchor(i)
                if na is None:
                    continue
                n_valid += 1
                if na == name:
                    agree += 1
            ratio = (agree / n_valid) if n_valid else 0.0
            if ratio < 0.5:
                print("[vp] ⚠ 安全闸B2: %s 拿 %d 段(%.0f%%)但台账里本场没出现过, "
                      "且逐段最近 anchor 只有 %.0f%% 指向他 ⇒ **不写库**" % (
                          name, cnt, cnt / max(1, total_segs) * 100, ratio * 100), flush=True)
                await engine.dispose()
                return
            print("[vp] 安全闸B2: %s 拿 %d 段(%.0f%%)触发台账外告警, 但逐段最近 anchor "
                  "有 %.0f%%(%d/%d) 指向他 ⇒ 告警被交叉验证推翻, 放行" % (
                      name, cnt, cnt / max(1, total_segs) * 100,
                      ratio * 100, agree, n_valid), flush=True)
        if not new_heavy:
            print("[vp] 安全闸B2: 无『台账外成员占大片段』⇒ 通过", flush=True)

        # ---- 安全闸 C: 新增段的声学是否与该成员**同场人耳确认段**同源 ----
        # 对照组 = 同一场里该成员的台账确认段(同场同人 ⇒ 最贴近的对照)。
        #   C1: 新增段到该成员 anchor 的中位距离 ≤ 对照中位 × GATE_C_RATIO_MAX
        #   C2: 新增段到该成员 anchor 的中位距离 ≤ 「仍未识别段」到同一 anchor 的中位距离
        #       (符号判据: 若新命名的段比留空的段还远 ⇒ 这次命名是倒退)
        ledger_conf = defaultdict(list)
        for mm, s0, e0, who in lb:
            if who.startswith("发言人"):
                continue
            for i, s in enumerate(segs):
                st = float(s.get("start") or 0)
                en = float(s.get("end") or 0)
                if st >= s0 - 1e-6 and en <= e0 + 1e-6:
                    ledger_conf[who].append(i)
        unknown_idx = [i for i in range(total_segs) if new_speaker.get(i) == "发言人?"]
        for name in sorted(set(new_speaker.values())):
            if name.startswith("发言人"):
                continue
            newly = [i for i in range(total_segs)
                     if new_speaker.get(i) == name and segs[i].get("speaker") != name]
            if not newly:
                continue
            a = anchor_vec.get(name)
            if a is None:
                continue
            d_new = [float(np.linalg.norm(seg_embs[i] - a)) for i in newly
                     if seg_embs[i] is not None]
            if not d_new:
                continue
            m_new = float(np.median(d_new))
            conf = ledger_conf.get(name, [])
            d_con = [float(np.linalg.norm(seg_embs[i] - a)) for i in conf
                     if seg_embs[i] is not None]
            d_unk = [float(np.linalg.norm(seg_embs[i] - a)) for i in unknown_idx
                     if seg_embs[i] is not None]
            msg = ("[vp]   闸C %s: 新增 %d 段, 到 anchor 中位 %.4f" % (
                name, len(newly), m_new))
            if d_con:
                m_con = float(np.median(d_con))
                ratio = m_new / max(1e-9, m_con)
                msg += " / 同场人耳确认中位 %.4f (n=%d) 比值 %.3f" % (
                    m_con, len(d_con), ratio)
                if ratio > GATE_C_RATIO_MAX:
                    print(msg + " ⇒ ⚠ 超过 %.2f" % GATE_C_RATIO_MAX, flush=True)
                    print("[vp] ⚠ 安全闸C1: 新命名段比同场人耳确认段远 %.0f%% ⇒ **不写库**" % (
                        (ratio - 1) * 100), flush=True)
                    await engine.dispose()
                    return
            if d_unk:
                m_unk = float(np.median(d_unk))
                msg += " / 仍未识别段中位 %.4f (n=%d) 比值 %.3f" % (
                    m_unk, len(d_unk), m_new / max(1e-9, m_unk))
                if m_new > m_unk:
                    print(msg + " ⇒ ⚠ 新命名段比留空段还远", flush=True)
                    print("[vp] ⚠ 安全闸C2: 新命名段比『仍未识别』段离该成员更远 ⇒ "
                          "这次命名是倒退 ⇒ **不写库**", flush=True)
                    await engine.dispose()
                    return
            print(msg, flush=True)
        print("[vp] 安全闸C: 新增段的声学与同场人耳确认段同源 ⇒ 通过", flush=True)

        # ---- 安全闸 D: 全局未识别率不得上升 ----
        # 背景(类 20.249): 2026-10-30 的 margin=0.10 重标把 5 场会议的命名覆盖打崩
        #       (250: 34→572 未识别, 256: 263→2023, 243: 91→588, 247: 6→87,
        #        255: 308→413)。闸 A 只看台账覆盖的段 ⇒ 对**台账外**的崩塌完全失明。
        # ⇒ 必须有一条**全局**判据兜住。
        u_before = sum(1 for s in segs if (s.get("speaker") or "发言人?") == "发言人?")
        u_after = after.get("发言人?", 0)
        if u_after > u_before:
            print("[vp] ⚠ 安全闸D: 未识别段 %d → %d (变多) ⇒ **不写库**" % (
                u_before, u_after), flush=True)
            await engine.dispose()
            return
        print("[vp] 安全闸D: 未识别段 %d → %d (未变多) ⇒ 通过" % (u_before, u_after), flush=True)
        print("[vp] ✅ 五道安全闸全部通过 ⇒ %s" % ("可写库" if args.apply else "dry-run, 未写库"),
              flush=True)

        if args.apply:
            # ⚠️ 备份表名必须**自带判据版本** —— 否则「pre_margin_relabel」这种
            #   泛名在跑过多次不同 margin 的重标后**无法区分是哪一次的前态**
            #   (类 20.220: 名字在说谎)。这里用 `margin0p05` 这样的字面量。
            bk_suffix = "margin%s" % (("%.2f" % margin).replace(".", "p"))
            bk = "meeting_%d_backup_pre_%s_relabel" % (mid, bk_suffix)
            await db.execute(sqlt("DROP TABLE IF EXISTS %s" % bk))
            await db.execute(sqlt("CREATE TABLE %s AS SELECT * FROM meetings WITH NO DATA" % bk))
            await db.execute(sqlt("INSERT INTO %s SELECT * FROM meetings WHERE id = :i" % bk),
                             {"i": mid})
            await db.commit()
            applied = 0
            for i, s in enumerate(segs):
                new_spk = new_speaker.get(i)
                ri = order[i]          # segs 的下标 → cur_raw(库内原序)的下标
                if not new_spk or cur_raw[ri].get("speaker") == new_spk:
                    continue
                u = update_transcript_speaker(cur_raw, cur_pol, cur_map, ri, new_spk)
                cur_raw, cur_pol, cur_map = u.transcript, u.transcript_polished, u.speaker_mapping
                applied += 1
            from app.services.meeting_analysis_service import MeetingAnalysisService
            stats = None
            try:
                stats = MeetingAnalysisService().compute_speaker_stats(cur_raw)
            except Exception as e:
                print("[vp] speaker_stats 重算失败: %r" % (e,), flush=True)
            m.transcript = cur_raw
            m.transcript_polished = cur_pol
            m.speaker_mapping = cur_map
            if stats is not None:
                m.speaker_stats = stats
            await db.commit()
            print("[vp] 已写回 %d 段 (备份表 %s)" % (applied, bk), flush=True)
        else:
            print("[vp] dry-run, 未写库", flush=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
