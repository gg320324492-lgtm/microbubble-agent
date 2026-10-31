"""把 m259 簇起名试听包的主指挥裁决写进段级裁决表 (真值更正, 默认 dry-run)。

主指挥 2026-10-31 亲耳听完 ``C:\\Users\\pc\\Desktop\\簇起名试听_m259\\`` 后的判定 (由
主会话转交): **簇4 (38 段) = 肖佐林** —— 现标签混杂 (王天志16/发言人?17/肖佐林2/
耿嘉栋1/刘子煜1/杜同贺1) 全部改判。按类 20.244 的段级裁决机制写进
``meeting_speaker_adjudications``, source=``listening-pack-m259`` (可审计可清空)。
簇0/2/3/5 现标签正确不改; 簇1 需段级拆分, 等主指挥后续指示, **不写**。

⚠️ 这是**真值数据**, 不是重标实验 —— 写的是裁决表 (重跑优先应用), **不碰 transcript**。

防错断言 (全部 fail-loud):
  ① 复现试听包的聚类 (同一份数据 + 同一 KMeans 参数) ⇒ 簇大小必须逐簇相等
     {0:55, 1:28, 2:154, 3:32, 4:38, 5:64}; 不等 ⇒ 环境漂移, 拒绝写。
  ② 38 段必须能在**当前 DB 转录**里按中点唯一匹配到段; 匹配数 != 38 ⇒ 拒绝写
     (转录在试听包生成后变过 ⇒ 簇↔段映射不可信)。
  ③ 已存在 source='listening-pack-m259' 的行 ⇒ 拒绝重写 (除非 --replace)。
  ④ 与既有裁决 (台账播种等) 的时间重叠 ⇒ dry-run 里列出, --apply 时也只报告不强判
     (重叠=两个来源对同一段各执一词, 属主指挥裁决范围)。

用法 (容器内):
    python /tmp/vp/apply_listening_pack_m259.py            # dry-run, 只打印
    python /tmp/vp/apply_listening_pack_m259.py --apply    # 真写 (须主指挥确认后执行)
    python /tmp/vp/apply_listening_pack_m259.py --apply --prune-superseded
        # 写完顺带清掉"被新裁决完全取代"的旧行 (见下方坑)

## ⛔ 坑: 只写不清 ⇒ 「写了但没生效」(类 20.220, 2026-10-31 m259 实测)

裁决命中按**段中点**找区间; 与新行重叠的旧行 (台账播种等) 不会自动失效 ⇒
apply 后端到端实测只有 30/38 命中新裁决 —— 与旧行重叠的段胜负取决于
resolver 对同/近区间的命中顺序 (旧行区间更宽时 seg_start 更小, 新行赢;
区间几乎重合时是掷硬币)。

⇒ **apply 后必须清理被取代的旧行**, 判据 (保守, 宁漏勿错):
   旧行**可删** ⇔ 它覆盖的**全部**转录段中点都落在新裁决的 38 段之内
   (即删它不会让任何"新裁决没覆盖"的段失去既有裁决)。
   覆盖范围超出新段集合的旧行 ⇒ **保留**并在 dry-run 里列出, 由人裁决。
   ``--prune-superseded`` 自动执行: 先备份到
   ``meeting_<id>_adjud_backup_pre_listeningpack`` (已存在则跳过建表), 再删可删行。
   2026-10-31 实测: 91 条旧裁决中 31 条可删 (14 条精确同段 + 17 条只含新段),
   删后端到端 38/38 命中; 备份表留底可回溯。
"""
import argparse
import asyncio
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/app")

SR_MEETING = 259
SOURCE_TAG = "listening-pack-m259"
SPEAKER = "肖佐林"
#: 试听包生成时的簇大小 (KMeans k=6, n_init=3, seed=20261031, phase1 seg 嵌入)
EXPECTED_CLUSTER_SIZES = {0: 55, 1: 28, 2: 154, 3: 32, 4: 38, 5: 64}
NOTE = ("簇4 试听真值 (主指挥 2026-10-31 亲耳判定); 原标签混杂: "
        "王天志16/发言人?17/肖佐林2/耿嘉栋1/刘子煜1/杜同贺1")


def log(m):
    print("[pack-m259] " + m, flush=True)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--apply", action="store_true", help="真写 (默认 dry-run)")
    ap.add_argument("--replace", action="store_true",
                    help="先清掉本脚本此前写入的行 (按 source), 再写")
    ap.add_argument("--prune-superseded", action="store_true",
                    help="写完后清掉「覆盖范围完全落在新段集合内」的旧行"
                         "(先备份到 meeting_<id>_adjud_backup_pre_listeningpack; 详见 docstring)")
    args = ap.parse_args()

    # ---- ① 复现试听包的聚类 ----
    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    rows = [i for i, m in enumerate(META)
            if m["kind"] == "seg" and m["meeting"] == SR_MEETING]
    from sklearn.cluster import KMeans
    lab = KMeans(n_clusters=6, n_init=3, random_state=20261031).fit_predict(E[rows])
    sizes = collections.Counter(int(lab[r]) for r in range(len(rows)))
    sizes = {c: sizes.get(c, 0) for c in sorted(EXPECTED_CLUSTER_SIZES)}
    log("复现聚类簇大小: %s" % sizes)
    if sizes != EXPECTED_CLUSTER_SIZES:
        raise SystemExit("❌ 簇大小与试听包不一致 %s != %s ⇒ 环境漂移, 拒绝写"
                         % (sizes, EXPECTED_CLUSTER_SIZES))
    c4 = [rows[r] for r in range(len(rows)) if int(lab[r]) == 4]
    assert len(c4) == 38

    # ---- ② 读当前 DB 转录, 按中点匹配 ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.speaker_adjudication_service import (
        get_adjudications, record_adjudication)

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        m = (await db.execute(
            select(Meeting).where(Meeting.id == SR_MEETING))).scalar_one()
        segs = m.transcript or []
        idx_by_mid = {}
        for k, s in enumerate(segs):
            a, b = float(s.get("start") or 0), float(s.get("end") or 0)
            if b > a:
                idx_by_mid.setdefault(round((a + b) / 2.0, 3), k)
        matched, unmatched = [], []
        for i in c4:
            mid = round((META[i]["start"] + META[i]["end"]) / 2.0, 3)
            k = idx_by_mid.get(mid)
            if k is None:
                unmatched.append((META[i]["start"], META[i]["end"]))
            else:
                matched.append((k, float(segs[k].get("start")), float(segs[k].get("end"))))
        log("簇4 段匹配: %d/%d (未匹配 %d)" % (len(matched), len(c4), len(unmatched)))
        if unmatched:
            for a, b in unmatched[:10]:
                log("   未匹配: [%.2f, %.2f]" % (a, b))
            raise SystemExit("❌ %d 段无法在当前转录中按中点匹配 ⇒ 转录已变, 拒绝写"
                             % len(unmatched))

        # ---- ③ 幂等守卫 + ④ 重叠报告 ----
        existing = await get_adjudications(db, SR_MEETING)
        prior = [r for r in existing if r.source == SOURCE_TAG]
        log("既有裁决 %d 条 (本 source 已有 %d 条)" % (len(existing), len(prior)))
        if prior and not args.replace:
            raise SystemExit("❌ source=%s 已有 %d 行; 要重写请加 --replace"
                             % (SOURCE_TAG, len(prior)))
        overlaps = []
        new_mids = set()
        for k, a, b in matched:
            new_mids.add(round((a + b) / 2.0, 3))
            mid = (a + b) / 2.0
            for r in existing:
                if r.source != SOURCE_TAG and float(r.seg_start) <= mid <= float(r.seg_end):
                    overlaps.append((a, b, r.speaker, r.source))
        if overlaps:
            log("⚠️ 与既有裁决重叠 %d 段 (两个来源各执一词, 已列出供主指挥裁决):" % len(overlaps))
            by_sp = collections.Counter((o[2], o[3]) for o in overlaps)
            for (sp, src), n in by_sp.most_common():
                log("   %s (%s) × %d 段" % (sp, src, n))
        # ⛔ 坑: 只写不清 ⇒ 新裁决对重叠段不保证生效 (docstring「写了但没生效」节)
        # 无重叠时两个清单为空, 后续 --prune-superseded 分支是 no-op。
        prunable, keep = [], []
        for r in existing:
            if r.source == SOURCE_TAG:
                continue
            inside = [m for m in idx_by_mid
                      if float(r.seg_start) <= m <= float(r.seg_end)]
            if inside and set(inside) <= new_mids:
                prunable.append(r)
            elif inside:
                keep.append(r)
        if prunable or keep:
            log("被取代旧行清理清单 (判据: 覆盖的段中点全部落在新 38 段内):")
            log("   可删 %d 条; 覆盖超出新段集合、需人工裁决 %d 条"
                % (len(prunable), len(keep)))
            for r in keep[:10]:
                log("   保留: [%.1f,%.1f] %s (%s)" % (r.seg_start, r.seg_end,
                                                     r.speaker, r.source))
            if overlaps and not args.prune_superseded:
                log("   ⇒ apply 后必须清掉这 %d 条可删行, 否则新裁决对这些段不保证生效"
                    % len(prunable))

        cur_labels = collections.Counter(
            (segs[k].get("speaker") or "?") for k, _, _ in matched)
        log("将写 %d 条裁决: 全部 → %s | 现标签分布 %s"
            % (len(matched), SPEAKER, dict(cur_labels)))
        log("区间范围: [%.1f, %.1f]s" % (min(a for _, a, _ in matched),
                                        max(b for _, _, b in matched)))

        if not args.apply:
            log("DRY-RUN 结束 (未写库)。确认后加 --apply 执行。")
            return

        if args.replace and prior:
            from sqlalchemy import delete
            from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication
            await db.execute(delete(MeetingSpeakerAdjudication).where(
                MeetingSpeakerAdjudication.source == SOURCE_TAG,
                MeetingSpeakerAdjudication.meeting_id == SR_MEETING))
            await db.commit()
            log("已清旧 %d 行 (--replace)" % len(prior))
        written = 0
        for k, a, b in matched:
            await record_adjudication(
                db, SR_MEETING, a, b, SPEAKER,
                source=SOURCE_TAG, note=NOTE, seg_index=k)
            written += 1
        log("✅ 已写 %d 条段级裁决 (source=%s)" % (written, SOURCE_TAG))
        # 回读验证 (类 20.220: 验副作用)
        back = [r for r in await get_adjudications(db, SR_MEETING)
                if r.source == SOURCE_TAG]
        log("回读: %d 条在表, speaker 全为 %s ⇒ %s"
            % (len(back), SPEAKER, all(r.speaker == SPEAKER for r in back)))

        # ⛔ 写了不等于生效: 清掉被新裁决完全取代的旧行 (判据见 docstring)
        if args.prune_superseded:
            from sqlalchemy import text as sa_text
            bak = "meeting_%d_adjud_backup_pre_listeningpack" % SR_MEETING
            exists = (await db.execute(sa_text(
                "SELECT to_regclass(:t)"), {"t": bak})).scalar()
            if not exists:
                await db.execute(sa_text(
                    "CREATE TABLE %s AS SELECT * FROM meeting_speaker_adjudications "
                    "WHERE meeting_id = :mid" % bak), {"mid": SR_MEETING})
                await db.commit()
                log("已建备份表 %s" % bak)
            else:
                log("备份表 %s 已存在 ⇒ 跳过建表 (只备份一次, 保留最初 91 行原貌)" % bak)
            deleted = 0
            for r in prunable:
                await db.execute(sa_text(
                    "DELETE FROM meeting_speaker_adjudications WHERE id = :i"),
                    {"i": r.id})
                deleted += 1
            await db.commit()
            log("已清被取代旧行 %d 条 (备份在 %s)" % (deleted, bak))
            # 端到端回验: 现在每一新段的中点都应命中 listening-pack 行
            resolver_rows = await get_adjudications(db, SR_MEETING)
            from app.services.speaker_adjudication_service import AdjudicationResolver
            res = AdjudicationResolver(resolver_rows)
            hit = sum(1 for k, a, b in matched
                      if res.lookup(a, b) == SPEAKER)
            log("端到端回验: %d/%d 段命中 %s" % (hit, len(matched), SPEAKER))
            if hit != len(matched):
                log("⚠️ 未全命中 ⇒ 还有覆盖冲突, 见上方「保留」清单, 交人工裁决")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
