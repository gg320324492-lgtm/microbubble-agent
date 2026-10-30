"""三态对比 (类 20.249 ⑥): 备份态 / 库内当前 / 新判据重算态。

为什么要比三态而不是「回滚到备份态」:
备份态里可能带着**已知错名** ⇒ 回滚会**引入**错名。
⇒ 必须逐场对比「台账真值分 + 未识别数 + 错名明细」。

三个状态:
  备份态      = 备份表里存的改前快照 (重标脚本每次写库前自动建)
  库内当前    = meetings.transcript 现值
  新判据重算态 = 用现在的判据 + 现在的候选池重跑一遍(可选, 需 --recompute)

用法 (容器内):
    python /tmp/vp/three_state_compare.py --meeting 256 --backup meeting_256_backup_pre_margin0p05_relabel

台账来源按顺序探测:
    1) --ledger 显式指定 (逗号分隔)
    2) 环境变量 VP_LEDGER_FILES
    3) 仓库内 docs/voiceprint-confirmed-blocks-*.json
    4) 容器内 /tmp/ledger_13.json,/tmp/ledger_30.json
不存在的文件**跳过并告警**(不静默当成空台账 —— 否则台账分会是 0/0 假通过)。
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/app")

# 「不是人声」的负样本 —— 不参与判分
NEG = {"环境声", "人群杂音", "视频"}


def _candidate_ledgers(explicit):
    if explicit:
        return [p.strip() for p in explicit.split(",") if p.strip()]
    env = os.environ.get("VP_LEDGER_FILES")
    if env:
        return [p.strip() for p in env.split(",") if p.strip()]
    out = []
    repo_root = Path(__file__).resolve().parents[2]
    for name in ("voiceprint-confirmed-blocks-2026-10-13.json",
                 "voiceprint-confirmed-blocks-2026-10-30.json"):
        p = repo_root / "docs" / name
        if p.exists():
            out.append(str(p))
    if out:
        return out
    return ["/tmp/ledger_13.json", "/tmp/ledger_30.json"]


def load_truth(ledger_spec):
    """返回 [(meeting, s, e, who|None)] —— None = 负样本(环境声/人群杂音), 跳过判分。"""
    out = []
    missing = []
    for lp in _candidate_ledgers(ledger_spec):
        if not os.path.exists(lp):
            missing.append(lp)
            continue
        ld = json.load(open(lp, encoding="utf-8"))
        for b in ld.get("blocks", []):
            if b.get("_可用") is False:
                continue
            who = b.get("who")
            out.append((int(b["meeting"]), float(b["s"]), float(b["e"]),
                        None if who in NEG else who))
    if missing:
        print("[3state] ⚠ 台账文件不存在(已跳过): %s" % ", ".join(missing), flush=True)
    if not out:
        print("[3state] ⚠ 没有可用台账 ⇒ 台账分会是 0/0(假通过), 请检查路径", flush=True)
    return out


def score(transcript, truth):
    """(命中, 总数, 错名明细) —— 逐段按 midpoint 落在台账块内判。"""
    hit = tot = 0
    bad = Counter()
    for s in transcript:
        st = float(s.get("start") or 0)
        en = float(s.get("end") or 0)
        midp = (st + en) / 2.0
        for _m, s0, e0, who in truth:
            if s0 <= midp <= e0:
                if who is None:
                    break
                tot += 1
                got = s.get("speaker")
                if got == who:
                    hit += 1
                else:
                    bad["%s->%s" % (who, got)] += 1
                break
    return hit, tot, bad


def describe(transcript):
    c = Counter(s.get("speaker") or "发言人?" for s in transcript)
    unk = c.get("发言人?", 0)
    return c, unk


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--backup", default="", help="备份表名, 如 meeting_256_backup_pre_margin0p05_relabel")
    ap.add_argument("--ledger", default="", help="台账 JSON 路径, 逗号分隔")
    ap.add_argument("--out", default="", help="额外写一份到该文件")
    args = ap.parse_args()
    mid = args.meeting
    truth = [t for t in load_truth(args.ledger) if t[0] == mid]

    from sqlalchemy import select, text as sqlt
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    engine, Session = create_celery_engine_and_session()
    lines = []
    async with Session() as db:
        cur = list((await db.execute(
            select(Meeting).where(Meeting.id == mid))).scalar_one().transcript or [])
        states = [("库内当前", cur)]
        if args.backup:
            r = await db.execute(sqlt(
                "SELECT transcript FROM %s WHERE id = :i" % args.backup), {"i": mid})
            row = r.first()
            if row and row[0]:
                states.insert(0, ("备份态", list(row[0])))
            else:
                print("[3state] ⚠ 备份表 %s 无此会议的行" % args.backup, flush=True)

        for name, tr in states:
            c, unk = describe(tr)
            hit, tot, bad = score(tr, truth)
            lines.append("--- %s: %d 段, 未识别 %d (%.1f%%), 台账 %d/%d (%.1f%%)" % (
                name, len(tr), unk, unk / max(1, len(tr)) * 100, hit, tot,
                hit / max(1, tot) * 100))
            lines.append("    分布: %s" % dict(c.most_common()))
            if bad:
                lines.append("    错名明细: %s" % dict(bad.most_common()))
        await engine.dispose()

    txt = "\n".join(lines)
    print(txt, flush=True)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(txt + "\n")


if __name__ == "__main__":
    asyncio.run(main())
