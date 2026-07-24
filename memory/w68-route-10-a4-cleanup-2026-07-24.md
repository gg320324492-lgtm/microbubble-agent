# W68 第 10 批 A-4 Cleanup 真跑 SOP 文档化 (锚点范式第 123 守恒)

> **本任务**: W68 第 10 批 A-4 主指挥 SSH 代理 — merge C-2 + dry-run + run 文档化 + memory 沉淀
>
> **任务 ID**: `chore/w68-10th-batch-a4-cleanup-2026-07-24` (anchor #123)
>
> **完成时间**: 2026-07-24
>
> **关联**: W68 第 8 批 C-2 (`cf03425a0` 锚点 #98) + W68 第 9 批 A-3 (锚点 #117) + 本任务 (#123)

## 背景

W68 第 7 批 15 worktree + 15 分支全部 merge 进 main (`f14cb43c1` → `e2d99511e`). C-2 agent 已建 cleanup 脚本 (`scripts/w68_7th_batch_cleanup_plan.sh`, 346 行) + runbook + memory. W68 第 9 批 A-3 agent 已 dry-run 验证语法 + 行为 OK. 本任务 (A-4) 把 C-2 merge 到 main, 再做一次 dry-run 捕获, 然后文档化主指挥 SSH 执行 SOP, **不真删** (主指挥拍板才 `--apply`).

## 任务清单 (完成情况)

| # | 任务 | 状态 | 验证 |
|---|------|------|------|
| 1 | merge C-2 分支 (`chore/w68-8th-batch-c2-cleanup-2026-07-24`) | ✅ | `e2d99511e` |
| 2 | `bash -n` syntax check | ✅ | syntax OK |
| 3 | 默认 dry-run (不传 --apply) | ✅ | `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt` |
| 4 | 15 分支 merge-base 验证 (本任务再 verify) | ✅ | 15/15 MERGED |
| 5 | 文档化主指挥 SSH 执行 SOP | ✅ | `docs/w68-7th-batch-cleanup-run-execution-v2-2026-07-24.md` (8 节, ~250 行) |
| 6 | memory 沉淀 (5 新铁律) | ✅ | 本文件 |

**0 production code 改动铁律维持** ✅ — 仅 merge + dry-run + docs + memory

## Merge commit 详情

- **Merge commit**: `e2d99511e` (锚点范式第 123 守恒)
- **Merge 方式**: `--no-ff` (保留分支拓扑)
- **父 1**: `f14cb43c1` (main HEAD)
- **父 2**: `cf03425a0` (C-2 branch HEAD, 锚点 #98)
- **Merge 文件**: 3 文件 / 857 行
  - `docs/w68-7th-batch-cleanup-runbook.md` (260 行)
  - `memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md` (251 行)
  - `scripts/w68_7th_batch_cleanup_plan.sh` (346 行)

## Dry-run 捕获

- **输出文件**: `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt`
- **15 项分支**: 全部 `branch-local:YES, branch-remote:YES`
- **15 项 worktree**: 全部 `WT:NO` (W68 第 9 批 cascade 已清目录, 不影响分支删除)
- **保护清单**: priceless-grothendieck-6a2998 + claude/priceless-grothendieck-6a2998 永不动

## Run 文档化 (主指挥 SOP)

- **路径**: `docs/w68-7th-batch-cleanup-run-execution-v2-2026-07-24.md`
- **结构** (8 节, ~250 行):
  - 第 0 节: 上下文
  - 第 1 节: C-2 merge 验证 (commit hash + syntax + merge-base 15/15)
  - 第 2 节: dry-run 输出捕获
  - 第 3 节: 主指挥 SSH 执行 SOP (4 步)
  - 第 4 节: 回滚方式 (backup 在 /tmp 30 天保留)
  - 第 5 节: 验证 (git worktree list / branch -r --merged / baseline 71 PASS + 7 SKIP)
  - 第 6 节: 边界与已知问题
  - 第 7 节: 时间线 + commit 链
  - 第 8 节: 关联资源

## 5 新铁律

### 铁律 1: cleanup 必须先 merge 再执行

- **场景**: W68 第 10 批 A-4 + W68 第 8 批 C-2 cleanup 双 agent 派工
- **纪律**: cleanup 脚本必须在分支 merge 进 main 之后才能执行 (避免删未 merge 分支 = 丢代码)
- **执行**: C-2 merge → A-4 merge → A-4 dry-run → 主指挥 SSH 真删
- **验证**: 本任务 15/15 分支 `git merge-base --is-ancestor <branch> HEAD` 全 MERGED
- **教训**: 派工顺序很重要, 不能并行 merge + cleanup (会丢代码)

### 铁律 2: cleanup 脚本默认 dry-run (双模铁律)

- **场景**: 任何 cleanup / destructive 操作脚本
- **纪律**: 默认 `dry-run` 模式 (不传 `--apply` 永远不真删), `--apply` 才真执行
- **执行**: C-2 脚本 `DRY_RUN=true` 默认值 + `case "--apply": DRY_RUN=false`
- **验证**: 本任务 `bash scripts/w68_7th_batch_cleanup_plan.sh` 不带参数 → 全 print, 0 副作用
- **教训**: "默认 dry-run" 是 destructive 脚本的标准纪律 (CLAUDE.md 752 行铁律精神 — 不破坏既有 baseline)

### 铁律 3: 保护清单必须硬编码 (永不依赖外部配置)

- **场景**: priceless-grothendieck-6a2998 (主指挥本地 hot-fix #18 仍跑)
- **纪律**: 保护项硬编码进脚本 (`PROTECTED_WORKTREE` + `PROTECTED_BRANCH` 常量), 不依赖外部配置或 `.env`
- **执行**: C-2 脚本 line 86-88:
  ```bash
  PROTECTED_WORKTREE="priceless-grothendieck-6a2998"
  PROTECTED_BRANCH="claude/priceless-grothendieck-6a2998"
  ```
  阶段 1/2/3 全用 `if [ "$WORKTREE_NAME" = "$PROTECTED_WORKTREE" ]; then SKIP; fi` 显式跳
- **验证**: dry-run 第 [2/4] 保护清单 print 包含 hot-fix #18, 不在 CLEANUP_LIST
- **教训**: 硬编码保护 = 任何环境 (CI / 主指挥 / dev) 都不会误删 hot-fix 资产 (CLAUDE.md 2026-07-24 派工硬编码保护模式)

### 铁律 4: 删前 backup 分支清单 (回滚锚点)

- **场景**: 任何批量删分支 / 删 worktree 操作
- **纪律**: 删前必须 backup 分支 SHA 列表到 `/tmp/<batch>-branches-backup-<ts>.txt` (30 天保留)
- **执行**: C-2 脚本 `[3/4]` 备份:
  ```bash
  BACKUP_FILE="/tmp/w68-7th-batch-branches-backup-$(date +%Y%m%d-%H%M%S).txt"
  # 格式: <worktree_path>\t<branch>\t<branch-sha>
  ```
- **验证**: backup 15 行 + 2 行注释 (`wc -l < $BACKUP_FILE` 期望 17)
- **教训**: "删前必备份" 是 destructive 操作的安全网 (CLAUDE.md 2026-07-22 W61 502 三层修复精神 — 任何 "删" 操作都有回滚路径)

### 铁律 5: 删后 verify baseline 守恒 (回归检测)

- **场景**: cleanup 完成后必须 verify 不破坏既有 baseline
- **纪律**: 删后跑 `bash scripts/check-baseline.sh` 期望 `71 PASS + 7 SKIP` + `git worktree list` 期望 ~10 项 + `git branch -r` 期望 ~5 项 + hot-fix #18 仍存在
- **执行**: 文档第 5 节 5 步验证 (worktree list / branch --merged / branch -r count / baseline / hot-fix 仍在)
- **验证**: W68 第 5 批 baseline 31+ 守恒, W68 第 7 批 32+, W68 第 8 批 ~33, W68 第 9 批 ~34, W68 第 10 批 (本任务) 期望 ~35
- **教训**: "删后必验证" 是 regression 防御 (CLAUDE.md 2026-06-13 PWA manifest 410 教训 — 删东西要立刻 verify 不破坏 baseline)

## 与 CLAUDE.md 铁律的呼应

| 本任务铁律 | CLAUDE.md 现有铁律 | 关系 |
|------------|-------------------|------|
| 铁律 1 (merge before cleanup) | CLAUDE.md 752 行铁律 (不破坏既有 baseline) | 强化: 派工顺序也算 baseline 守恒的一部分 |
| 铁律 2 (默认 dry-run) | CLAUDE.md 752 行铁律精神 | 强化: destructive 脚本必须 dry-run 默认 |
| 铁律 3 (硬编码保护) | CLAUDE.md 2026-07-24 派工硬编码保护模式 | 强化: cleanup 脚本沿用同一模式 |
| 铁律 4 (删前 backup) | CLAUDE.md 2026-07-22 W61 502 三层修复精神 | 强化: 任何删操作都有 backup 路径 |
| 铁律 5 (删后 verify) | CLAUDE.md 2026-06-13 PWA manifest 410 教训 | 强化: regression 防御必须立刻执行 |

## 锚点范式

- **本任务锚点**: 第 123 守恒
- **W68 第 8 批 C-2**: 第 98 守恒 (上游 merge 的 commit)
- **W68 第 9 批 A-3**: 第 117 守恒 (dry-run 已执行)
- **W68 第 10 批 A-1/A-2/A-3**: 第 120-122 守恒 (合并 C-2 前的 commits)

## 时间线

1. **W68 第 7 批 grand closure** (锚点 #85) — 15 agents 派工 + 全部 merge
2. **W68 第 8 批 A-1 merge** (锚点 #90, commit `62d4a59f7`) — 15 分支 merge 进 main
3. **W68 第 8 批 C-2 agent** (锚点 #98, commit `cf03425a0`) — cleanup 脚本 + runbook + memory
4. **W68 第 9 批 A-3 dry-run** (锚点 #117) — dry-run 验证脚本
5. **本任务 (A-4)** (锚点 #123, commit `e2d99511e`) — merge C-2 + run 文档化 + memory 沉淀
6. **主指挥 SSH 真删** (待执行, 不在本任务范围) — `--apply` 后 verify baseline 守恒

## commit 链 (本任务)

- **e2d99511e** (本任务 commit) — merge C-2 → main + 文档 + memory
- **f14cb43c1** (main HEAD, 上游) — W68 第 8 批 A-1 收尾
- **cf03425a0** (C-2 branch HEAD) — chore(w68-8th-batch-c2): W68 第 7 批 cleanup 脚本 + runbook

## 关联资源

- **Cleanup 脚本**: `scripts/w68_7th_batch_cleanup_plan.sh` (346 行, C-2 写, 本任务 merge 进 main)
- **Cleanup runbook**: `docs/w68-7th-batch-cleanup-runbook.md` (260 行, C-2 写)
- **C-2 memory**: `memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md` (251 行)
- **Run SOP (本任务)**: `docs/w68-7th-batch-cleanup-run-execution-v2-2026-07-24.md` (8 节, ~250 行)
- **Dry-run 捕获**: `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt`
- **W68 第 9 批 grand closure**: `memory/w68-grand-closure-9th-batch-2026-07-24.md`
- **W68 第 8 批 grand closure**: `memory/w68-grand-closure-8th-batch-2026-07-24.md`
- **W68 第 7 批 grand closure**: `memory/w68-grand-closure-7th-batch-2026-07-24.md`

## 完成定义检查 (CoD)

- [x] C-2 分支已 merge 到 main (`e2d99511e`)
- [x] dry-run 输出已捕获 (`logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt`)
- [x] 1 新建 run docs (`docs/w68-7th-batch-cleanup-run-execution-v2-2026-07-24.md`) + 1 新增 memory (本文件) = 2 文件
- [x] bash syntax 正确 (`bash -n` OK)
- [x] commit hash + push 成功 (待 push)
- [x] 0 production code 改动铁律维持 ✅
- [x] 不传 --apply ✅ (主指挥拍板才真删)
- [x] 不动 priceless-grothendieck ✅ (硬编码保护)
- [x] 分支 `chore/w68-10th-batch-a4-cleanup-2026-07-24` ✅