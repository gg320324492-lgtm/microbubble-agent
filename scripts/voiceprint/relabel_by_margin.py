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

import numpy as np

sys.path.insert(0, "/app")

SR = 16000
MIN_SEC = 0.5
WORK = "/tmp/vp"


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
        segs = sorted(raw, key=lambda s: float(s.get("start") or 0))

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
        for lp in os.environ.get("LEDGER_FILES", "/tmp/ledger_13.json,/tmp/ledger_30.json").split(","):
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
        if args.apply and truth_score["after_ok"] < truth_score["before_ok"]:
            print("[vp] ⚠ 安全闸A: 改后台账真值判对数(%d) < 改前(%d) ⇒ **不写库**" % (
                truth_score["after_ok"], truth_score["before_ok"]), flush=True)
            await engine.dispose()
            return

        # ---- 安全闸 B: 不得给「台账里该场会议没出现过」的成员安上大块段 ----
        # 背景: 会议 259 的重标会把 **75 段判给蒋芦笛** —— 而台账里蒋芦笛在这场
        #       **一句都没说**(2026-10-30 已确认) ⇒ 这正是刚修好的那个 bug 被重新引入。
        #       台账是人工逐块听辨建成的 ⇒ 若某个成员在台账里**完全没出现**,
        #       却拿到 >10% 的段, 说明模型在给一个"人耳从没听见过的人"安名字。
        ledger_people = {who for mm, s0, e0, who in lb}
        total_segs = len(segs)
        new_heavy = []
        for name, cnt in after.items():
            if name in ledger_people or name.startswith("发言人") or cnt <= 0:
                continue
            if cnt > total_segs * 0.10:
                new_heavy.append((name, cnt))
        if new_heavy:
            print("[vp] ⚠ 安全闸B: 台账里本场没出现过的成员被安上大块段 ⇒ **不写库**:" % ())
            for name, cnt in new_heavy:
                print("[vp]     %s 拿到 %d 段 (占 %d 段的 %.0f%%)" % (
                    name, cnt, total_segs, cnt / max(1, total_segs) * 100))
            print("[vp]     台账里本场出现的人: %s" % ", ".join(sorted(ledger_people)), flush=True)
            await engine.dispose()
            return
        print("[vp] 安全闸B: 无『台账外成员占大片段』⇒ 通过", flush=True)

        if args.apply:
            await db.execute(sqlt("DROP TABLE IF EXISTS meeting_%d_backup_pre_margin_relabel" % mid))
            await db.execute(sqlt("CREATE TABLE meeting_%d_backup_pre_margin_relabel AS "
                                   "SELECT * FROM meetings WITH NO DATA" % mid))
            await db.execute(sqlt("INSERT INTO meeting_%d_backup_pre_margin_relabel "
                                   "SELECT * FROM meetings WHERE id = :i" % mid), {"i": mid})
            await db.commit()
            applied = 0
            for i, s in enumerate(segs):
                new_spk = new_speaker.get(i)
                if not new_spk or cur_raw[i].get("speaker") == new_spk:
                    continue
                u = update_transcript_speaker(cur_raw, cur_pol, cur_map, i, new_spk)
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
            print("[vp] 已写回 %d 段 (备份表 meeting_%d_backup_pre_margin_relabel)" % (applied, mid), flush=True)
        else:
            print("[vp] dry-run, 未写库", flush=True)
    await engine.dispose()


if __name__ == "__main__":
    from collections import Counter
    asyncio.run(main())
