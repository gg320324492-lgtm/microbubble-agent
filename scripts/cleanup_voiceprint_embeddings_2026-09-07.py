# -*- coding: utf-8 -*-
"""声纹库数据清洗 — 2026-09-07 (配合 docs/vibevoice-evaluation-2026-09-07.md §6.3)

清洗目标（基于实测发现的两类污染向量）:
  A. 非归一化向量: |norm - 1| > 0.05 （ERes2Net 原始输出 norm 488~859，
     2026-06-28 的归一化修复只覆盖"多次录入取均值"分支，单次录入未归一化）
  B. 重复坏向量: 多名成员存有完全相同的向量（耿嘉栋/关小未/宋洋/刘莫菲
     norm 全等 13.2603，两两余弦距离 = 0）

处理方式: voice_embedding = NULL, voice_sample_count = 0（相当于未录入，
等成员重新录入；voiceprint_service.py 现已强制归一化，新录入不会再坏）。
绝不触碰: anchor 成员（voice_confirmed_at 非空）与 norm 正常的向量。

用法:
  python scripts/cleanup_voiceprint_embeddings_2026-09-07.py            # dry-run
  python scripts/cleanup_voiceprint_embeddings_2026-09-07.py --execute  # 真正执行
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

BACKUP_TSV = Path(r"E:\microbubble-agent\backups\voiceprint"
                  r"\members_voice_embedding_backup_2026-09-07.tsv")
CONTAINER = "microbubble-agent-db-1"
NORM_TOL = 0.05


def load_backup():
    rows = []
    with open(BACKUP_TSV, encoding="utf-8") as f:
        for line in f:
            mid, name, count, anchor, vec = line.rstrip("\n").split("\t")
            emb = np.array([float(x) for x in vec.strip("[]").split(",")],
                           dtype=np.float32)
            rows.append({"id": int(mid), "name": name, "count": int(count),
                         "anchor": anchor == "t", "emb": emb})
    return rows


def main(execute: bool):
    rows = load_backup()
    print(f"DB 内已有声纹成员: {len(rows)}")

    for r in rows:
        r["norm"] = float(np.linalg.norm(r["emb"]))

    # A. 非归一化
    bad_norm = [r for r in rows if abs(r["norm"] - 1.0) > NORM_TOL]
    # B. 重复向量组（两两 max|diff| < 1e-5）
    dup_groups = []
    used = set()
    for i in range(len(rows)):
        if i in used:
            continue
        group = [i]
        for j in range(i + 1, len(rows)):
            if j in used:
                continue
            if float(np.max(np.abs(rows[i]["emb"] - rows[j]["emb"]))) < 1e-5:
                group.append(j)
                used.add(j)
        if len(group) > 1:
            dup_groups.append(group)

    dup_ids = {rows[k]["id"] for g in dup_groups for k in g}

    to_clean, kept = [], []
    for r in rows:
        reason = None
        if abs(r["norm"] - 1.0) > NORM_TOL:
            reason = f"非归一化 (norm={r['norm']:.2f})"
        if r["id"] in dup_ids:
            reason = (reason + " + " if reason else "") + "重复坏向量组"
        if reason:
            if r["anchor"]:
                print(f"!! 警告: anchor 成员 {r['name']} 命中清洗条件({reason})，"
                      f"按规则跳过绝不触碰")
                kept.append(r)
            else:
                to_clean.append((r, reason))
        else:
            kept.append(r)

    print("\n=== 将被清空（等待重新录入）===")
    for r, reason in to_clean:
        print(f"  id={r['id']:>3} {r['name']:<6} 采样{r['count']}次  原因: {reason}")
    print("\n=== 保留不动 ===")
    for r in kept:
        print(f"  id={r['id']:>3} {r['name']:<6} 采样{r['count']}次  "
              f"anchor={r['anchor']} norm={r['norm']:.4f}")

    if not to_clean:
        print("\n无需清洗。")
        return

    ids = sorted(r["id"] for r, _ in to_clean)
    sql = (f"UPDATE members SET voice_embedding = NULL, voice_sample_count = 0, "
           f"voice_enrolled_at = NULL WHERE id IN ({','.join(map(str, ids))}) "
           f"AND voice_confirmed_at IS NULL;")
    print(f"\n计划 SQL:\n  {sql}")

    if not execute:
        print("\n[dry-run] 未执行。确认无误后加 --execute 运行。")
        return

    r = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d",
         "microbubble", "-c", sql],
        capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print("执行失败:", r.stderr)
        sys.exit(1)
    print(f"已清洗 {len(to_clean)} 名成员的声纹，等待重新录入。"
          f"完整备份: {BACKUP_TSV}")


if __name__ == "__main__":
    main(execute="--execute" in sys.argv)
