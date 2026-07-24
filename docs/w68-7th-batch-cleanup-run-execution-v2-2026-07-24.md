# W68 第 7 批 Cleanup 真跑执行 v2 — 主指挥 SSH 代理 (2026-07-24)

> **本任务**: W68 第 10 批 A-4 主指挥 SSH 代理 — 文档化 cleanup 真跑 SOP, 准备主指挥 SSH 上手
>
> **触发**: W68 第 7 批 15 worktree + 16 分支待清理 (C-2 脚本 + runbook 已 merge), W68 第 8 批 C-2 锚点范式第 98 守恒, W68 第 9 批 A-3 dry-run 已完成, 本任务仅做 run 文档化 + memory 沉淀

## 第 0 节: 上下文

- **背景**: W68 第 7 批 grand closure 15 agents + 15 worktree + 15 分支 (不含 hot-fix #18 永保) 全部 merge 进 main (f14cb43c1)
- **C-2 分支**: `chore/w68-8th-batch-c2-cleanup-2026-07-24` (commit `cf03425a0`, 锚点范式第 98 守恒) — 含 cleanup 脚本 + runbook + memory
- **A-3 dry-run**: W68 第 9 批 A-3 agent 已 dry-run 验证脚本语法 + 行为 OK
- **本任务 (A-4)**: 文档化主指挥 SSH 执行 SOP, **不真删** (主指挥拍板才 `--apply`)

## 第 1 节: C-2 脚本 merge 验证

### 1.1 Merge commit hash

| 项 | 值 |
|----|----|
| Merge commit | `e2d99511e` |
| Merge message | `merge: W68 第 7 批 cleanup 脚本 (W68 第 10 批)` |
| Merge 方式 | `--no-ff` (保留分支拓扑) |
| 父 1 | `f14cb43c1` (main HEAD) |
| 父 2 | `cf03425a0` (C-2 branch HEAD, 锚点范式第 98 守恒) |
| 文件 | `docs/w68-7th-batch-cleanup-runbook.md` (260 行) + `memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md` (251 行) + `scripts/w68_7th_batch_cleanup_plan.sh` (346 行) |
| 0 production code 改动 | ✅ 维持 (仅 scripts + docs + memory 三件套) |

### 1.2 脚本 syntax check

```bash
$ bash -n scripts/w68_7th_batch_cleanup_plan.sh && echo "syntax OK"
syntax OK
```

### 1.3 双模确认

| 模式 | 行为 |
|------|------|
| 默认 (无参数) | **dry-run**, 只打印待清理清单, 不真删 |
| `--apply` | 真执行 3 阶段清理 (主指挥拍板才用) |
| `--apply --force` | 真执行 + 跳过 `read -p yes` verify |
| `--help` | 打印用法 |

### 1.4 15 分支 merge-base 验证 (本任务执行)

```
$ git merge-base --is-ancestor <branch> HEAD
a1 (chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24)        MERGED
a2 (chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24)            MERGED
a3 (chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24)                MERGED
a4 (feat/qa-bench-d5-kb-monitor-2026-07-24)                              MERGED
a5 (feat/silly-gliding-dahl-impl-2026-07-24)                             MERGED
b1 (feat/drive-v2-pr10-collab-ws-2026-07-24)                             MERGED
b2 (test/qa-bench-phase2-dry-2026-07-24)                                 MERGED
b3 (feat/mobile-v3.2-push-backend-2026-07-24)                            MERGED
c1 (chore/w68-7th-batch-c1-plans-status-fix-2026-07-24)                  MERGED
c2 (chore/w68-7th-batch-c2-plans-archive-2026-07-24)                     MERGED
c3 (chore/w68-7th-batch-c3-verified-plans-doc-sync-2026-07-24)           MERGED
d1 (chore/w68-7th-batch-d1-5th-batch-deploy-2026-07-24)                  MERGED
d3 (chore/w68-7th-batch-d3-claude-code-voice-alert-2026-07-24)           MERGED
gc (chore/w68-7th-batch-grand-closure-2026-07-24)                        MERGED
runbook (docs/drive-pr10-deploy-runbook-2026-07-24)                       MERGED
```

**结论**: 15/15 分支均已 merge 进 main HEAD (`e2d99511e`), 可安全删.

## 第 2 节: dry-run 输出 (本任务捕获)

> **捕获位置**: `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt`
> **捕获时间**: 2026-07-24 (W68 第 10 批 A-4)
> **捕获命令**: `bash scripts/w68_7th_batch_cleanup_plan.sh`

```
================================================================
[DRY-RUN] W68 第 7 批 worktree + 分支清理预览 (默认模式)
================================================================

执行 w68_7th_batch_cleanup_plan.sh --apply 才会真删 (主指挥拍板)

[1/4] 待清理 worktree + 分支清单 (15 项):

  [ 1] agent-a00103ef46303806c          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 2] agent-a83d1f096269a7455          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 3] agent-a785756f198d623ee          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 4] agent-a862622ec21e4f37b          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 5] agent-a15b80d0cf50a32ec          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 6] agent-a68b44365140e9956          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 7] agent-a9ab41846632dd8cc          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 8] agent-a8e0f5a43fed97bbe          | WT:NO  | branch-local:YES | branch-remote:YES
  [ 9] agent-a2fa62d9143ea67e4          | WT:NO  | branch-local:YES | branch-remote:YES
  [10] agent-af1bda3114821c1f7          | WT:NO  | branch-local:YES | branch-remote:YES
  [11] agent-a4ef176d4f5c8a3c0          | WT:NO  | branch-local:YES | branch-remote:YES
  [12] agent-a5b02d4327953632f          | WT:NO  | branch-local:YES | branch-remote:YES
  [13] agent-ab788b1ac3a6db3da          | WT:NO  | branch-local:YES | branch-remote:YES
  [14] agent-af25e11b3f78258cc          | WT:NO  | branch-local:YES | branch-remote:YES
  [15] agent-ac0caaff1a01d57bb          | WT:NO  | branch-local:YES | branch-remote:YES

统计: 总计 15 项 | 存在 worktree 0 | 缺失 15
      存在 local branch 15

[2/4] 保护清单 (不动):
  - worktree: priceless-grothendieck-6a2998 (DO NOT TOUCH)
  - branch:   claude/priceless-grothendieck-6a2998 (主指挥本地 hot-fix #18 仍跑)

================================================================
[DRY-RUN COMPLETE] 不真删. 主指挥拍板后跑: w68_7th_batch_cleanup_plan.sh --apply
================================================================
```

**关键观察**:
- ✅ 15/15 分支 local + remote 均存在 (待清)
- ✅ 0/15 worktree 存在 (W68 第 9 批 cascade 清理已完成, 仍可执行删除分支)
- ✅ 保护清单: priceless-grothendieck-6a2998 + claude/priceless-grothendieck-6a2998 不在 CLEANUP_LIST 中

## 第 3 节: 主指挥 SSH 执行必做 (SOP)

### 3.1 SSH 上手 + pull 最新 main

```bash
# 在主指挥的本地 PC 上 (主仓库, 不是 worktree)
cd /path/to/microbubble-agent   # 主仓库路径, 例如 E:/microbubble-agent
git pull origin main            # 拉到 e2d99511e (含 C-2 merge)
git log --oneline -1            # 期望 e2d99511e merge: W68 第 7 批 cleanup 脚本 (W68 第 10 批)
```

### 3.2 预览 dry-run (确认状态)

```bash
# 默认 dry-run, 不传 --apply 永远不真删
bash scripts/w68_7th_batch_cleanup_plan.sh

# 期望输出与第 2 节一致:
#   - 15 项分支清单 (branch-local:YES, branch-remote:YES)
#   - 0 项 worktree (WT:NO, 已 cascade 清)
#   - 保护清单 priceless-grothendieck-6a2998 (DO NOT TOUCH)
```

### 3.3 真删 (主指挥拍板)

```bash
# 主指挥决定后才跑这条!
bash scripts/w68_7th_batch_cleanup_plan.sh --apply
```

**脚本会做**:
1. `[3/4] 主指挥拍板 verify` — `read -p "主指挥确认? 输入 'yes' 继续, 其他取消: "`
   - 必须输 `yes` 才继续, 否则 abort (exit 1, 无任何副作用)
2. `[3/4] 备份分支清单` — 写到 `/tmp/w68-7th-batch-branches-backup-<YYYYMMDD-HHMMSS>.txt` (15 行 + 注释)
3. `[4/4] 执行清理 (3 阶段)`:
   - 阶段 1: `git worktree remove --force` × 15 (全 SKIP, 因 WT 不存在)
   - 阶段 2: `git branch -D` × 15 (删 15 local 分支)
   - 阶段 3: `git push origin --delete` × 15 (删 15 remote 分支)
4. `[CLEANUP COMPLETE]` — 输出统计 (成功/失败计数)

**跳过 verify 步骤** (主指挥拍板 + 不想交互):
```bash
bash scripts/w68_7th_batch_cleanup_plan.sh --apply --force
```

### 3.4 推荐执行模式

```bash
# Step 1: dry-run 复核
bash scripts/w68_7th_batch_cleanup_plan.sh | tee logs/w68-7th-batch-cleanup-final-dryrun-2026-07-24.txt

# Step 2: 真删 (交互 verify)
bash scripts/w68_7th_batch_cleanup_plan.sh --apply
# 主指挥在 read -p 输 yes

# Step 3: 立即 verify (见第 5 节)
git worktree list
git branch -r | grep -E "w68-7th-batch|qa-bench-d5|silly-gliding|drive-v2-pr10|qa-bench-phase2|mobile-v3.2-push-backend|drive-pr10-deploy-runbook"
# 期望: 0 输出 (全删了)
```

## 第 4 节: 回滚方式 (P1)

### 4.1 Backup 路径

- **备份文件**: `/tmp/w68-7th-batch-branches-backup-<YYYYMMDD-HHMMSS>.txt` (脚本自动生成, 30 天保留)
- **格式**: `<worktree_path>\t<branch>\t<branch-sha>` (15 行)
- **示例**:
  ```
  # W68 第 7 批 分支清理备份 (2026-07-24 14:30:00)
  # 格式: <worktree_path>\t<branch>\t<branch-sha>

  .claude/worktrees/agent-a00103ef46303806c	chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24	a1b2c3d4
  .claude/worktrees/agent-a83d1f096269a7455	chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24	e5f6g7h8
  ...
  ```

### 4.2 回滚单条 (示例: a1 分支)

```bash
# 1. 从备份取 branch + SHA
BACKUP=/tmp/w68-7th-batch-branches-backup-20260724-143000.txt
grep "a1-cached-giggling" "$BACKUP"
# 输出: .claude/worktrees/agent-a00103ef46303806c  chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24  a1b2c3d4

# 2. 本地重建分支 (从 SHA)
git branch chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24 a1b2c3d4

# 3. 推到 remote (可选, 主指挥通常不需要)
git push origin chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24

# 4. 重建 worktree (如果需要)
git worktree add .claude/worktrees/agent-a00103ef46303806c chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
```

### 4.3 全量回滚 (主指挥拍板)

```bash
# 不推荐: 一旦 main HEAD 已推进, 重建分支会引发新冲突
# 推荐: 只回滚必要单条 (4.2), 不全量恢复
```

### 4.4 不动 hot-fix #18

- priceless-grothendieck-6a2998 worktree 永不被脚本触及 (硬编码保护)
- claude/priceless-grothendieck-6a2998 分支永不被脚本触及 (硬编码保护)
- 主指挥本地 hot-fix #18 持续运转, 不受影响

## 第 5 节: 验证 (删后必做)

### 5.1 git worktree list

```bash
$ git worktree list

# 期望: ~10 项, 不含 W68 第 7 批 15 项
# (W68 第 9 批 cascade 已删, 本次再清仍然 NO, 不报错)
```

### 5.2 git branch --merged main

```bash
$ git branch -r --merged main | grep -E "w68-7th-batch|qa-bench-d5-kb-monitor|silly-gliding|drive-v2-pr10-collab|qa-bench-phase2|mobile-v3.2-push-backend|drive-pr10-deploy-runbook"

# 期望: 0 输出 (全删了, 因为已 merge, 不再 --merged)
```

### 5.3 git branch -r (期望清理后)

```bash
$ git branch -r | wc -l

# 期望: ~5 项 remote (W68 第 7 批外其他 remote)
```

### 5.4 Baseline 守恒 (71 PASS + 7 SKIP)

```bash
# 在主仓库跑 (不在 worktree)
bash scripts/check-baseline.sh

# 期望: 71 PASS + 7 SKIP (W68 第 5 批 baseline 31+ 守恒)
```

### 5.5 保护项仍存在

```bash
$ git worktree list | grep priceless-grothendieck
.claude/worktrees/priceless-grothendieck-6a2998  <sha>  [claude/priceless-grothendieck-6a2998]

$ git branch -a | grep priceless-grothendieck
+ claude/priceless-grothendieck-6a2998

# 期望: hot-fix #18 仍在
```

## 第 6 节: 边界与已知问题

### 6.1 边界

- ✅ 不会动 main 分支
- ✅ 不会动 hot-fix #18
- ✅ 不会动 W68 第 8/9 批分支 (虽然有些已 merge)
- ✅ 不会动其他 worktree (例如本 A-4 worktree `agent-a1d02f90eee22c59a`)
- ✅ 默认 dry-run, 必须 `--apply` 才真删
- ⚠️ 删分支前会备份到 /tmp (仅 30 天保留, 跨服务器无保障)
- ⚠️ remote 分支删除需 push 权限 (主指挥确认)

### 6.2 已知问题

- ✅ W68 第 9 批 cascade 已清 15 个 worktree 目录, dry-run 显示 WT:NO 是预期的
- ⚠️ main HEAD 在 cleanup 后会推进 (`e2d99511e` 是 C-2 merge 后的当前), 备份里的 SHA 仍指向 e2d99511e 之前的历史, 不影响 branch 重建
- ⚠️ 若主指挥想保 1-2 个 W68 第 7 批分支 (例如 grand closure commit 历史价值), 可手动 `git branch <branch> <sha>` 重建

## 第 7 节: 时间线 + commit 链

1. **W68 第 7 批 grand closure** (2026-07-24, 锚点范式第 85 守恒) — 15 agents 派工 + 15 worktree + 15 分支全部 merge
2. **W68 第 8 批 A-1 merge** (`62d4a59f7`, 锚点范式第 90 守恒) — 15 分支 merge 到 main
3. **W68 第 8 批 C-2 agent** (`cf03425a0`, 锚点范式第 98 守恒) — 建 cleanup 脚本 + runbook + memory
4. **W68 第 9 批 A-3 dry-run** (2026-07-24, 锚点范式第 117 守恒) — dry-run 验证
5. **本任务 (A-4 merge C-2)** (`e2d99511e`, 锚点范式第 123 守恒) — merge C-2 到 main + 文档化 SOP
6. **主指挥 SSH 真删** (待执行, 不在本任务范围) — `--apply` 后验证 baseline 守恒

## 第 8 节: 关联资源

- **Cleanup 脚本**: `scripts/w68_7th_batch_cleanup_plan.sh` (346 行)
- **Cleanup runbook**: `docs/w68-7th-batch-cleanup-runbook.md` (260 行, C-2 写)
- **C-2 memory**: `memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md` (251 行)
- **A-3 memory**: `memory/w68-route-9-a3-cleanup-run-2026-07-24.md` (A-3 dry-run 沉淀)
- **本任务 memory**: `memory/w68-route-10-a4-cleanup-2026-07-24.md` (5 新铁律)
- **Dry-run 捕获**: `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt` (本任务生成)