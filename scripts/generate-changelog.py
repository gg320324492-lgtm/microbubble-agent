#!/usr/bin/env python3
"""
generate-changelog.py — 从 git log 自动生成 changelog.json (W86 mini-11 A fix)
=============================================================================
替代手维护: 每次 deploy 自动跑, 从 git log 实时抽取最近 W 批次 commit
聚合到 web/src/data/changelog.json 头部, 与 pain_points/todos 字段合并保留.

铁律:
  1. 部署时自动跑 (scripts/deploy-auto.sh 调用) — 不依赖人手维护
  2. 保留现有 pain_points / todos 字段 — 只追加 changelog 段
  3. W batch 分类按 commit message 关键字扫描 (W82-W86)
  4. 失败 WARN 不阻断部署 (与 deploy-auto.sh:295-344 update-stats 行为一致)

用法:
  python scripts/generate-changelog.py           # 默认写到 web/src/data/changelog.json
  python scripts/generate-changelog.py --limit 100  # 看最近 100 commits (默认 500)
  python scripts/generate-changelog.py --dry-run    # 只 print 不写文件
"""
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT = PROJECT_ROOT / 'web/src/data/changelog.json'

# W batch 关键字 (commit message 含则归入对应 batch)
W_BATCH_KEYWORDS = {
    'W86': 'W86 mini batch (Tab 1 项目历程滞后 + UX 优化)',
    'W85': 'W85 第 1 批 grand closure (据实上报派工 + drive_upload 数据回填)',
    'W84': 'W84 第 1 批 (P1 latent bug batch 3 + 冗余重构 batch 2 + dead service batch 2)',
    'W83': 'W83 第 1 批 (据实上报派工 + P1 latent bug + 冗余重构)',
    'W82': 'W82 第 1 批 (24人月Q1商业化 + 主拍决策 + Phase 8 收官)',
    'W81': 'W81 第 1 批 (商业化运营收官 + Phase 8 收官)',
    'W80': 'W80 第 1 批 (PWA 资产缺失 hot-fix + 锚点范式)',
    'W79': 'W79 第 1 批 (商业化 Phase 8 商业化运营)',
    'W78': 'W78 第 1 批 (R10 灰度 + 商业化 Phase 8)',
    'W77': 'W77 第 1 批 (Edge-TTS Android mainplay)',
    'W76': 'W76 第 1 批 grand closure',
}


def run_git_log(limit: int):
    """返回 [(sha, msg, date), ...] 倒序"""
    result = subprocess.run(
        ['git', 'log', f'--pretty=format:%H|%s|%ci', f'-n{limit}'],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding='utf-8',
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")
    out = []
    for line in result.stdout.strip().split('\n'):
        if '|' in line and line.count('|') >= 2:
            parts = line.split('|', 2)
            out.append((parts[0], parts[1], parts[2]))
    return out


def classify_batch(msg: str):
    """按 commit message 关键字返回 (W_batch_keyword, label)"""
    for w in W_BATCH_KEYWORDS:
        # 用词边界匹配, 避免 W86 命中 W860
        if re.search(rf'\b{w}\b', msg):
            return w
    return None


def aggregate_batches(commits):
    """按 W batch 聚合 commits, 返回 {W86: [commits...], ...}"""
    batches = defaultdict(list)
    for sha, msg, date in commits:
        w = classify_batch(msg)
        if w:
            # 跳过 pure build / merge commit (避免噪声)
            if msg.startswith('build:') or msg.startswith('merge:'):
                # build 仍然保留作时间锚点, 但不计入"实质改动"
                batches[w + '_builds'].append({'sha': sha[:7], 'msg': msg, 'date': date})
                continue
            batches[w].append({'sha': sha[:7], 'msg': msg, 'date': date})
    return batches


def synthesize_changelog_entry(w_keyword, commits, builds):
    """根据 W batch + commits 生成一个 changelog 条目 (模仿现有格式)"""
    if not commits:
        return None
    # 取最新 commit date
    latest_date = commits[0]['date'][:10] if commits else builds[0]['date'][:10]
    # 关键字分类标签: 看 commits 里出现最频繁的 type
    type_counts = defaultdict(int)
    for c in commits:
        m = re.match(r'^([a-z]+)\(', c['msg'])
        if m:
            type_counts[m.group(1)] += 1
    top_type = max(type_counts, key=type_counts.get) if type_counts else 'fix'
    tag_map = {
        'fix': '修复', 'feat': '功能', 'chore': '优化',
        'perf': '优化', 'refactor': '重构', 'docs': '数据',
        'build': '数据', 'merge': '数据',
    }
    tag = tag_map.get(top_type, '功能')

    # title = {W_label} ({commits 数} commits, +builds builds)
    label = W_BATCH_KEYWORDS[w_keyword]
    n_commits = len(commits)
    n_builds = len(builds)
    title = f'{w_keyword} {label.split(" ", 1)[1] if " " in label else label}'
    if n_builds:
        title += f' ({n_commits} commits + {n_builds} builds)'
    else:
        title += f' ({n_commits} commits)'

    # pain_point = 取前 5 个 commit msg 拼成简短描述
    pain_lines = [f"{c['sha']}: {c['msg'][:120]}" for c in commits[:5]]
    pain_point = '\n'.join(pain_lines)
    if n_commits > 5:
        pain_point += f'\n... +{n_commits - 5} more commits'

    return {
        'date': latest_date,
        'tag': tag,
        'title': title,
        'pain_point': pain_point,
    }


def main():
    parser = argparse.ArgumentParser(description='从 git log 自动生成 changelog.json')
    parser.add_argument('--limit', type=int, default=500, help='最近 N 条 commit (默认 500)')
    parser.add_argument('--dry-run', action='store_true', help='只 print 不写文件')
    parser.add_argument('--output', type=str, default=str(OUTPUT), help='输出文件路径')
    args = parser.parse_args()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    print(f'[generate-changelog] Scanning last {args.limit} commits...')
    commits = run_git_log(args.limit)
    batches = aggregate_batches(commits)
    print(f'[generate-changelog] Found {len(batches)} batches')

    # 读现有 changelog.json (保留 pain_points / todos)
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f'[generate-changelog] WARN: parse existing failed ({e}), starting fresh')
            data = {'pain_points': [], 'todos': [], 'changelog': []}
    else:
        data = {'pain_points': [], 'todos': [], 'changelog': []}

    # 取现有 changelog 中已存在的 W batch title 集合 (避免重复追加)
    existing_w_titles = set()
    for entry in data.get('changelog', []):
        m = re.match(r'^(W\d+) ', entry.get('title', ''))
        if m:
            existing_w_titles.add(m.group(1))

    # 生成新 entries (W82 ~ W86 顺序, 最新在前)
    new_entries = []
    for w_keyword in ['W86', 'W85', 'W84', 'W83', 'W82', 'W81', 'W80', 'W79', 'W78', 'W77', 'W76']:
        if w_keyword in existing_w_titles:
            print(f'[generate-changelog] Skip {w_keyword} (already in changelog)')
            continue
        commits_for_w = batches.get(w_keyword, [])
        builds_for_w = batches.get(w_keyword + '_builds', [])
        if not commits_for_w and not builds_for_w:
            continue
        entry = synthesize_changelog_entry(w_keyword, commits_for_w, builds_for_w)
        if entry:
            new_entries.append(entry)
            print(f"[generate-changelog] + {w_keyword}: {entry['title']}")

    if not new_entries:
        print('[generate-changelog] No new W batches found, no changes')
        return 0

    # 头部插入 (保留原有倒序)
    data['changelog'] = new_entries + data.get('changelog', [])

    if args.dry_run:
        print(f"[generate-changelog] DRY-RUN: would append {len(new_entries)} entries")
        print(json.dumps(new_entries[:2], ensure_ascii=False, indent=2))
        return 0

    # 写回
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'[generate-changelog] Updated {output_path} (+{len(new_entries)} entries)')
    return 0


if __name__ == '__main__':
    sys.exit(main())