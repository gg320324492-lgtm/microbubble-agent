# W68 路线 8 C-2: W68 第 7 批 worktree + 分支清理 (2026-07-24)

> **任务模式基调**: 锚点范式第 98 守恒. W68 第 8 批 C-2 清理 W68 第 7 批 15 worktree + 16 分支 (15 W68 第 7 批 + 1 priceless-grothendieck hot-fix #18). 0 production code 改动铁律维持 (仅 scripts + docs + memory 三件套).
>
> **任务代号**: `chore/w68-8th-batch-c2-cleanup-2026-07-24`
>
> **关联文件**:
> - `scripts/w68_7th_batch_cleanup_plan.sh` (默认 dry-run, `--apply` 真删)
> - `docs/w68-7th-batch-cleanup-runbook.md` (清理 SOP + 边界 + 回滚)

## 0. 上下文

W68 第 7 批 (2026-07-24) 派工 15 agent (A-1 → A-5 + B-1 → B-3 + C-1 → C-3 + D-1 + D-3 + grand closure) 跨 4 路线:

- **路线 A (qa-bench D5 + plans 整理)**: cached-giggling-pebble fix + cheerful-anchor scripts + qa-bench isolation + D5 KB monitor + silly-gliding-dahl e2e
- **路线 B (Drive v2 PR10 collab WS + mobile push + qa-bench phase2)**: drive-v2-pr10-collab-ws + qa-bench-phase2-dry + mobile-v3.2-push-backend
- **路线 C (plans 文档同步 + plans archive + verified-plans doc sync)**: plans-status-fix + plans-archive + verified-plans-doc-sync
- **路线 D (5th batch 部署验证 + claude-code voice alert hook)**: 5th-batch-deploy + claude-code-voice-alert
- **grand closure**: memory grand closure + MEMORY.md 索引更新
- **runbook**: Drive v2 PR10 deployment runbook

15 agent 完工后, 15 个 worktree + 15 个分支待清理. 主指挥拍板后跑 `--apply`.

## 1. 现状盘点 (2026-07-24)

### 1.1 合并状态

- **main HEAD**: `05c60e68d69f82173d8c1d8496a7bd0f9a556d4d` (W68 第 5 批 hot-fix: version-diff lineterm)
- **8th batch staging**: `chore/w68-8th-batch-a1-merge-2026-07-24` 已 merge W68 第 7 批 6 项 (c1 + c2 + c3 + d1 + d3 + runbook) → merge commits `69f0c5dc6`, `ff133e4c4`, `8b1aebc18`, `b0f232324`, `e0f7d776d`, `cfffa6414`
- **未在 8th batch staging**: A-1, A-2, A-3, A-4, A-5, B-1, B-2, B-3, grand closure (9 项)
- **hot-fix #18**: priceless-grothendieck-6a2998 (Knowledge.uploader_id → created_by) 仍跑, DO NOT TOUCH

### 1.2 待清理 15 项 (worktree + 分支)

| # | 派工 ID | Worktree | 分支 |
|---|---------|----------|------|
| 1 | A-1 | agent-a00103ef46303806c | chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24 |
| 2 | A-2 | agent-a83d1f096269a7455 | chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24 |
| 3 | A-3 | agent-a785756f198d623ee | chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24 |
| 4 | A-4 | agent-a862622ec21e4f37b | feat/qa-bench-d5-kb-monitor-2026-07-24 |
| 5 | A-5 | agent-a15b80d0cf50a32ec | feat/silly-gliding-dahl-impl-2026-07-24 |
| 6 | B-1 | agent-a68b44365140e9956 | feat/drive-v2-pr10-collab-ws-2026-07-24 |
| 7 | B-2 | agent-a9ab41846632dd8cc | test/qa-bench-phase2-dry-2026-07-24 |
| 8 | B-3 | agent-a8e0f5a43fed97bbe | feat/mobile-v3.2-push-backend-2026-07-24 |
| 9 | C-1 | agent-a2fa62d9143ea67e4 | chore/w68-7th-batch-c1-plans-status-fix-2026-07-24 |
| 10 | C-2 | agent-af1bda3114821c1f7 | chore/w68-7th-batch-c2-plans-archive-2026-07-24 |
| 11 | C-3 | agent-a4ef176d4f5c8a3c0 | chore/w68-7th-batch-c3-verified-plans-doc-sync-2026-07-24 |
| 12 | D-1 | agent-a5b02d4327953632f | chore/w68-7th-batch-d1-5th-batch-deploy-2026-07-24 |
| 13 | D-3 | agent-ab788b1ac3a6db3da | chore/w68-7th-batch-d3-claude-code-voice-alert-2026-07-24 |
| 14 | GC | agent-af25e11b3f78258cc | chore/w68-7th-batch-grand-closure-2026-07-24 |
| 15 | RUN | agent-ac0caaff1a01d57bb | docs/drive-pr10-deploy-runbook-2026-07-24 |

### 1.3 不动的项 (硬编码保护)

| Worktree | 分支 | 原因 |
|----------|------|------|
| priceless-grothendieck-6a2998 | claude/priceless-grothendieck-6a2998 | 主指挥本地 hot-fix #18 (Knowledge.uploader_id → created_by) 仍在跑 |

## 2. 实施 (本任务产出)

### 2.1 1 新建 cleanup script

`scripts/w68_7th_batch_cleanup_plan.sh` (~310 行, bash 4+ 兼容):

- **双模**: 默认 dry-run (print 清单不删) + `--apply` 真删
- **verify gate**: `--apply` 默认走 `read -p "主指挥确认? 输入 'yes' 继续"` 交互 verify, `--force` 跳过
- **3 阶段**: worktree remove → branch -D → push origin --delete (按依赖顺序)
- **备份**: 删前写分支 SHA 到 `/tmp/w68-7th-batch-branches-backup-<ts>.txt` (回滚用)
- **保护**: 硬编码跳过 priceless-grothendieck (worktree + branch 双检查)
- **跳过**: 不存在的 worktree / 分支自动 SKIP (幂等)
- **统计**: 总结部分 print worktree 移除数 / branch 删除数 / remote 删除数 + 失败数
- **bash syntax**: `bash -n` 验证 0 错误

### 2.2 1 新建 cleanup runbook

`docs/w68-7th-batch-cleanup-runbook.md` (~200 行):

- **第 1 节 清理顺序**: 15 项清单 + 4 group 依赖 (A-1 → A-5 → B-1 → B-3 / C-1 → D-3 / grand closure / runbook)
- **第 2 节 主指挥 SSH 必做**: dry-run 预览 → --apply 真删 → 5 步 verify (worktree list / branch count / baseline / main HEAD)
- **第 3 节 回滚**: worktree 重建 / branch 重建 / force push / 不删 main / 不动 hot-fix #18
- **第 4 节 边界 + 例外**: 不在清理范围的 locked worktrees (8 个 W68 第 6 批 + 8th batch 占位) + 失败处理 + 跨平台注意

### 2.3 1 新建 memory

本文件 (`memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md`).

## 3. 5 新铁律 (本次沉淀)

### 铁律 1: 合并后才能删分支 (硬规则)

```bash
# 删分支前必 verify
git branch --merged main | grep "<branch-name>"
# 期望: 输出包含分支名

git log --oneline main..<branch-name>
# 期望: 空输出 (branch 全部在 main 里)
```

不验证就删 → 丢失 commit. **绝不能** 跳过这步.

**关联**: 本任务的 8th batch staging `chore/w68-8th-batch-a1-merge-2026-07-24` 收了 W68 第 7 批 6 项, 但 A 路线 5 项 + B 路线 3 项 + grand closure 1 项 = 9 项还没在 8th batch. 主指挥要么先把 8th batch merge 进 main 再删, 要么用 `git branch -D` 强制删 (但风险高, 因为这些分支的 commit 没在 main).

**纪律**: 删分支前**必先** `git branch --merged main` 验证.

### 铁律 2: cleanup 脚本默认 dry-run (双模铁律)

任何 cleanup / 批量删除 / 重构脚本必须双模:

- **默认 dry-run**: 只 print 影响清单 (what/where/how many), 不真改
- **`--apply` 才真执行**: 显式开关让主指挥 / 用户主动确认

**理由**: 主指挥 + 用户都讨厌"我以为只 preview 怎么改了". `--apply` 是显式 intent gate.

**关联**: 本脚本 `scripts/w68_7th_batch_cleanup_plan.sh` + 之前 `scripts/auto_intake_rollback.py` 等都是这个模式.

**纪律**: 任何 cleanup 脚本必须 `--apply` 才能真执行, 不能默认 destructive.

### 铁律 3: 不动 hot-fix #18 worktree (硬保护)

主指挥本地 hot-fix #18 worktree (`priceless-grothendieck-6a2998` + `claude/priceless-grothendieck-6a2998`) 永远不动. 即使主指挥手动加到清理清单, 脚本**硬编码** `if [ "$WORKTREE_NAME" = "$PROTECTED_WORKTREE" ]` 跳过.

**理由**: hot-fix #18 (Knowledge.uploader_id → created_by) 是紧急修复, 还在跑. 删 worktree + branch 会破坏主指挥本地的工作进度.

**关联**: `memory/w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md` (hot-fix #18 完整记录).

**纪律**: 任何批量 worktree 清理脚本必须**硬编码**跳过主指挥本地 hot-fix worktree.

### 铁律 4: 删前备份分支清单 (回滚锚点)

任何批量删除分支 / worktree 前, 必须先**写一个 backup 文件**记录:

- worktree 路径
- 分支名
- 分支 SHA (`git rev-parse --short <branch>`)

写到 `/tmp/<project>-branches-backup-<ts>.txt` (per-project 命名避免冲突). 文件保留 30 天 (后续 batch 可参考).

**理由**: 删了之后想重建, 必须有 SHA 锚点. 没有 backup 文件 = 无法重建.

**关联**: 本脚本 `BACKUP_FILE="/tmp/w68-7th-batch-branches-backup-<ts>.txt"`.

**纪律**: 删分支前**必先** backup SHA. 删除脚本必须有 backup 步骤 (不能跳过).

### 铁律 5: 删后 verify baseline (回归检测)

任何 worktree / 分支清理后**必跑 baseline**:

```bash
bash scripts/check-baseline.sh 2>&1 | tail -20
# 期望: 71 PASS + 7 SKIP, 0 FAIL
```

**理由**: 删 worktree 不会直接影响 baseline, 但删除操作可能误删 (例如 `git branch -D main` 把 main 删了, 然后脚本不报错继续). baseline 守恒是最终 sanity check.

**关联**: 本任务 runbook 第 2.4 节 verify 步骤 + `memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md` 的 baseline 71 PASS + 7 SKIP 守恒.

**纪律**: 删后**必跑** baseline + main HEAD verify (`git rev-parse main` 期望仍是 05c60e68d).

## 4. 经验沉淀 (非铁律, 实施笔记)

### 4.1 dry-run 检测 worktree 路径兼容性

`git worktree list` 从 worktree 内跑返回**所有 worktrees** (因为 `.git/worktrees/` 是全局注册表). 但路径可能是:
- 绝对路径 (如 `E:/microbubble-agent/.claude/worktrees/agent-XXX`) — Git Bash 输出
- 相对路径 (如 `.claude/worktrees/agent-XXX`) — 理论可能, 但少见

**脚本兼容性**: 用 `grep -qF "${WORKTREE_NAME}"` 匹配 basename (兼容两种路径格式).

### 4.2 worktree 内跑 vs 主仓库跑

- 从 **worktree 内** 跑 dry-run: `WT:NO` (因为 `.claude/worktrees/` 在 worktree 视角不存在) — **不要**从此环境跑 `--apply`
- 从 **主仓库** (`/e/microbubble-agent` 直接) 跑 dry-run: `WT:YES` (主仓库 `.claude/worktrees/` 物理存在) — 正确运行环境

**纪律**: 主指挥 `--apply` 必须从主仓库跑 (即 `cd /e/microbubble-agent` 后跑).

### 4.3 worktree 移除的不可逆性

`git worktree remove --force` 删除 worktree **目录** + `.git/worktrees/<name>` 注册表. 不可逆 (不像分支可以重建).

但分支 SHA 在 backup 文件里, 重新创建 worktree 是 OK 的:
```bash
git worktree add .claude/worktrees/agent-a00103ef46303806c <sha>
```

### 4.4 跨批次 worktree 锁定 (locked)

W68 第 6 批 + 第 8 批占位的 locked worktree (`locked claude agent agent-XXX (pid 39140)`) 是**主进程占用**的 worktree, 不能直接删. 需要先 unlock:

```bash
git worktree unlock .claude/worktrees/agent-XXX
```

但本任务**不动**这些 locked worktree (per 第 4 节 runbook).

## 5. 风险 + 缓解

| 风险 | 缓解 |
|------|------|
| 误删 main 分支 | 脚本**没有** main 在 15 项清单, 硬编码保护 |
| 误删 hot-fix #18 | 脚本硬编码 `if [ "$WORKTREE_NAME" = "$PROTECTED_WORKTREE" ]` 跳过 |
| 删了没合并的分支 → 丢 commit | 删前 verify `git branch --merged main` (铁律 1) |
| 删了想重建 → 没 SHA | 删前 backup 到 `/tmp/...-backup-<ts>.txt` (铁律 4) |
| 删了破坏 baseline | 删后 verify `check-baseline.sh` 71 PASS + 7 SKIP (铁律 5) |
| push origin --delete 网络失败 | 脚本分段统计, 失败项主指挥手工重试 |
| 从 worktree 内跑 --apply → 删错 worktree | runbook 第 2.2 节明确说"必须从主仓库跑" |

## 6. 验证清单 (主指挥 apply 后)

```bash
# 1. worktree list
git worktree list
# 期望: ~10 项 (不含 15 个 W68 第 7 批 agent-*; 含 priceless-grothendieck + main)

# 2. branch -a count
git branch -a | wc -l
# 期望: 87 (102 - 15)

# 3. branch -r count
git branch -r | wc -l
# 期望: 3 (18 - 15)

# 4. baseline 守恒
bash scripts/check-baseline.sh 2>&1 | tail -20
# 期望: 71 PASS + 7 SKIP

# 5. main HEAD
git rev-parse main
# 期望: 05c60e68d69f82173d8c1d8496a7bd0f9a556d4d (没动)

# 6. backup 文件存在
ls -la /tmp/w68-7th-batch-branches-backup-*.txt
# 期望: 至少 1 个 backup 文件 (15 行 + header)
```

## 7. 关联引用

- **CLAUDE.md**: 锚点范式第 98 守恒 (本任务), 第 95 守恒 (W68 第 7 批 grand closure)
- **MEMORY.md**: 本任务索引行 (主指挥 apply 后加)
- **memory/w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md**: hot-fix #18 完整记录 (DO NOT TOUCH 原因)
- **memory/w68-route-5-hotfix-version-diff-import-2026-07-24.md**: hot-fix version-diff lineterm (main HEAD 锁)
- **memory/w68-grand-closure-2026-07-24.md**: W68 第 1 批 grand closure (跨主题收口范式)
- **memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md**: baseline 71 PASS + 7 SKIP 守恒参考
- **memory/w68-task-mode-paradigm-plans-first-2026-07-24.md**: 主指挥 W68 第 4 批任务模式基调 (plans 优先 + 小修搭配)

---

**任务完成定义**: 1 cleanup script + 1 cleanup runbook + 1 memory = 3 文件 ✓
**commit 末尾**: Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
**commit hash**: (主指挥 apply 后填)
**分支**: chore/w68-8th-batch-c2-cleanup-2026-07-24 (主指挥 merge)