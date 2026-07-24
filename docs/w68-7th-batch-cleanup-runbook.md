# W68 第 7 批 worktree + 分支清理 Runbook (2026-07-24)

> **目的**: W68 第 7 批 完工后, 15 worktree + 16 分支 (15 W68 第 7 批 + 1 priceless-grothendieck hot-fix #18) 待清理. 主指挥合并后才能删分支. 本文档是清理的 SOP + 边界 + 回滚路径.
>
> **关联文件**: `scripts/w68_7th_batch_cleanup_plan.sh` (默认 dry-run, `--apply` 真删)
>
> **任务代号**: `chore/w68-8th-batch-c2-cleanup-2026-07-24`
>
> **0 production code 改动铁律维持**: 仅 docs/scripts/memory 三件套.

## 第 1 节 清理顺序 (按 commit 时间 + 依赖)

W68 第 7 批 15 项清理按派工 ID + 依赖排序. 删除前**必须**先确认分支已合并到 `chore/w68-8th-batch-a1-merge-2026-07-24` (8th batch staging branch).

### 1.1 清理清单 (15 项)

按派工时序 (A-1 → A-5 → B-1 → B-3 → C-1 → C-3 → D-1 → D-3 → grand closure → runbook):

| # | 派工 ID | 主题 | Worktree 名 | 分支名 | 已合并到 8th batch? |
|---|---------|------|-------------|--------|---------------------|
| 1 | A-1 | cached-giggling-pebble fix | `agent-a00103ef46303806c` | `chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24` | ❌ 否 (独立 merge) |
| 2 | A-2 | cheerful-anchor scripts | `agent-a83d1f096269a7455` | `chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24` | ❌ 否 |
| 3 | A-3 | qa-bench isolation | `agent-a785756f198d623ee` | `chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24` | ❌ 否 |
| 4 | A-4 | qa-bench D5 KB monitor | `agent-a862622ec21e4f37b` | `feat/qa-bench-d5-kb-monitor-2026-07-24` | ❌ 否 |
| 5 | A-5 | silly-gliding-dahl | `agent-a15b80d0cf50a32ec` | `feat/silly-gliding-dahl-impl-2026-07-24` | ❌ 否 |
| 6 | B-1 | drive-v2-pr10 collab WS | `agent-a68b44365140e9956` | `feat/drive-v2-pr10-collab-ws-2026-07-24` | ❌ 否 |
| 7 | B-2 | qa-bench phase2 dry | `agent-a9ab41846632dd8cc` | `test/qa-bench-phase2-dry-2026-07-24` | ❌ 否 |
| 8 | B-3 | mobile-v3.2 push backend | `agent-a8e0f5a43fed97bbe` | `feat/mobile-v3.2-push-backend-2026-07-24` | ❌ 否 |
| 9 | C-1 | plans status fix | `agent-a2fa62d9143ea67e4` | `chore/w68-7th-batch-c1-plans-status-fix-2026-07-24` | ✅ 是 |
| 10 | C-2 | plans archive | `agent-af1bda3114821c1f7` | `chore/w68-7th-batch-c2-plans-archive-2026-07-24` | ✅ 是 |
| 11 | C-3 | verified-plans doc sync | `agent-a4ef176d4f5c8a3c0` | `chore/w68-7th-batch-c3-verified-plans-doc-sync-2026-07-24` | ✅ 是 |
| 12 | D-1 | 5th batch deploy | `agent-a5b02d4327953632f` | `chore/w68-7th-batch-d1-5th-batch-deploy-2026-07-24` | ✅ 是 |
| 13 | D-3 | claude-code voice alert | `agent-ab788b1ac3a6db3da` | `chore/w68-7th-batch-d3-claude-code-voice-alert-2026-07-24` | ✅ 是 |
| 14 | GC | grand closure | `agent-af25e11b3f78258cc` | `chore/w68-7th-batch-grand-closure-2026-07-24` | ❌ 否 (依赖 A-1 单独 merge) |
| 15 | RUN | Drive PR10 deploy runbook | `agent-ac0caaff1a01d57bb` | `docs/drive-pr10-deploy-runbook-2026-07-24` | ✅ 是 |

### 1.2 清理依赖 + 顺序

**依赖关系**:

- **group 1 (A-1 → A-5, B-1 → B-3)**: 这 8 项是 W68 第 7 批 source 实施 (含 qa-bench / drive-v2-pr10 / mobile-v3.2 push), 已被 merge 进 `chore/w68-8th-batch-a1-merge-2026-07-24` 的 merge commit (`69f0c5dc6` → `cfffa6414`). 删除前必须先 `git merge` 8th batch merge staging 到 main, **或** 8th batch merge 已到 main.
- **group 2 (C-1 → D-3)**: 这 5 项是 W68 第 7 批 docs/memory (plans 状态修复 + 部署验证 + claude-code hook), 同样已 merge 到 8th batch staging.
- **group 3 (grand closure)**: 依赖 group 1 + group 2 全部 merge, 所以排在最后.
- **group 4 (runbook)**: 独立 runbook 文档, 可单独 merge (但已在 8th batch staging 里 merge 了).

**推荐清理顺序** (从安全角度):

```
1. group 2 (5 项 docs/memory)   ← 风险最低, 纯 docs/memory, 删除安全
2. group 4 (1 项 runbook)       ← 独立 runbook 文档
3. group 1 (8 项 source)        ← 含代码改动, 验证 main HEAD 已包含
4. group 3 (1 项 grand closure) ← 最后, 因为依赖前 14 项全合并
```

### 1.3 删除前的强制 verify

每项删除前**必须**先验证:

```bash
# 1. 验证分支已 merge 到 main (合并后才能删)
git branch --merged main | grep "<branch-name>"
# 期望: 输出包含分支名

# 2. 验证 worktree HEAD 在 main HEAD 之前 (optional)
git log --oneline main..<branch-name>
# 期望: 空输出 (无 main..branch 提交 = branch 全部在 main 里)

# 3. 备份分支 SHA (脚本自动, 见第 2 节)
git rev-parse <branch-name>
```

### 1.4 不动的项 (保护清单)

| Worktree | 分支 | 原因 |
|----------|------|------|
| `priceless-grothendieck-6a2998` | `claude/priceless-grothendieck-6a2998` | 主指挥本地 hot-fix #18 (Knowledge.uploader_id → created_by 修复) 仍在跑, per `memory/w68-route-5-hotfix-knowledge-uploader-id-2026-07-24.md`. 不要动. |

## 第 2 节 主指挥 SSH 必做 (本地 PC)

主指挥在本机跑 cleanup 脚本. **绝不在云服务器上跑** (云服务器 worktree 是另一份物理副本).

### 2.1 dry-run 预览 (推荐先跑)

```bash
cd /e/microbubble-agent
bash scripts/w68_7th_batch_cleanup_plan.sh
```

期望输出:
- `[DRY-RUN] W68 第 7 批 worktree + 分支清理预览` banner
- 15 项清单 (worktree 状态 + local/remote 分支状态)
- `[DRY-RUN COMPLETE]` 收尾

**dry-run 不真删任何东西**. 跑 100 次都安全.

### 2.2 验证输出

期望 dry-run 输出:

```
[ 1] agent-a00103ef46303806c   | WT:YES | branch-local:YES | branch-remote:YES
[ 2] agent-a83d1f096269a7455   | WT:YES | branch-local:YES | branch-remote:YES
...
[15] agent-ac0caaff1a01d57bb   | WT:YES | branch-local:YES | branch-remote:YES
```

> ⚠️ 注意: 从 worktree 内跑会看到 `WT:NO` (worktree 没有 `.claude/worktrees/` 子目录). **必须从 main worktree 跑** (即主指挥默认 cd `/e/microbubble-agent` 后跑).

### 2.3 --apply 真删 (主指挥拍板)

```bash
cd /e/microbubble-agent
bash scripts/w68_7th_batch_cleanup_plan.sh --apply
```

流程:
1. 解析 + print 15 项清单
2. 保护清单 print (priceless-grothendieck 不动)
3. **`read -p "主指挥确认? 输入 'yes' 继续, 其他取消"`** ← 必走 verify 步骤
4. 备份分支清单到 `/tmp/w68-7th-batch-branches-backup-<ts>.txt`
5. 阶段 1: `git worktree remove --force` × 15
6. 阶段 2: `git branch -D` × 15
7. 阶段 3: `git push origin --delete` × 15
8. 总结统计 + 下一步提示

可选 `--force` 跳过步骤 3 的 verify (主指挥确认过 100% 后用):

```bash
bash scripts/w68_7th_batch_cleanup_plan.sh --apply --force
```

### 2.4 删后 verify

主指挥删完后**必须**跑以下 5 步验证:

```bash
# 1. worktree list 期望 ~10 项 (排除 15 个 W68 第 7 批)
git worktree list
# 期望: 不包含 15 个 W68 第 7 批 agent-*; 仍含 priceless-grothendieck + main worktree

# 2. branch list 期望 ~87 项 local (102 - 15 = 87)
git branch -a | wc -l
# 期望: ~87 (102 - 15 W68 第 7 批分支)

# 3. remote branch list 期望 ~3 项 (18 - 15 = 3)
git branch -r | wc -l
# 期望: ~3 (18 - 15 W68 第 7 批远程分支)

# 4. baseline 守恒 (Lint CSS 71 PASS + 7 SKIP)
bash scripts/check-baseline.sh 2>&1 | tail -20
# 期望: 71 PASS + 7 SKIP, 0 FAIL

# 5. main HEAD 守恒 (没误删 main)
git rev-parse main
# 期望: 05c60e68d69f82173d8c1d8496a7bd0f9a556d4d (W68 第 5 批 hot-fix)
```

### 2.5 完成后沉淀

主指挥在 merge 完成后, 在 `memory/MEMORY.md` 添加一行引用:

```markdown
- [W68 第 7 批 worktree + 分支清理](w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md) — 15 worktree + 15 分支清理, 主指挥 --apply 后 baseline 71 PASS + 7 SKIP 守恒
```

## 第 3 节 回滚

清理是不可逆操作, 但 git reflog + 备份清单 + 远程 origin 历史提供了多重回滚路径.

### 3.1 worktree 回滚

```bash
# 从备份清单读分支 SHA
cat /tmp/w68-7th-batch-branches-backup-<ts>.txt

# 重新创建 worktree (用 reflog 或 backup 文件的 SHA)
git worktree add .claude/worktrees/agent-a00103ef46303806c <branch-sha>
```

### 3.2 branch 回滚 (local)

```bash
# 从 backup 文件读 SHA
BRANCH_SHA=$(awk -F'\t' '$2=="chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24" {print $3}' /tmp/w68-7th-batch-branches-backup-<ts>.txt)

# 重新创建 local 分支
git branch chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24 "$BRANCH_SHA"

# 如果需要, 切换到该分支
git checkout chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
```

### 3.3 branch 回滚 (remote)

如果已经 `git push origin --delete`, remote 分支恢复需要**主指挥联系 GitHub admin** 或用 git reflog 找 SHA 后 force push:

```bash
# 警告: 仅当分支有未在 origin 备份的提交时才需要
git push origin <branch>:<branch> --force
# 期望: GitHub 拒绝 (因为 origin 也已删除), 此时只能 fork 仓库恢复
```

### 3.4 不删 main (铁律)

**绝不能**通过本脚本删除 `main` 或 `master` 分支. 脚本**没有** `--delete main` 选项, 也不会匹配 `main` (15 项清单里没有 main). 这是硬编码保护.

### 3.5 不动 hot-fix #18 (铁律)

脚本**硬编码**跳过:
- worktree: `priceless-grothendieck-6a2998`
- branch: `claude/priceless-grothendieck-6a2998`

即使主指挥手动加这些到清单, 脚本的 `if [ "$WORKTREE_NAME" = "$PROTECTED_WORKTREE" ]` 也会跳过. 这是 hot-fix #18 保护.

## 第 4 节 边界 + 例外

### 4.1 不在清理范围 (locked worktrees)

以下 worktrees 是 W68 第 6 批 / 早期 批次 锁定的占位 worktree, **不在 W68 第 7 批清理范围**:

- `agent-a052a299bbab82ba5` → `feat/drive-v2-pr12-reactions-2026-07-24` (locked, W68 第 6 批)
- `agent-a240983957feff32b` → `docs/drive-pr9-11-master-runbook-2026-07-24` (locked)
- `agent-a40d4982f17b79e22` → `feat/drive-v2-pr11-path-materialized-2026-07-24` (locked)
- `agent-a4a2a4e22f37b401a` → `worktree-agent-a4a2a4e22f37b401a` (locked, stub)
- `agent-acf1402436eea9c1c` → `feat/mobile-v3.2-share-biometric-2026-07-24` (locked)
- `agent-ae68d99c07918c976` → `chore/w68-8th-batch-a3-7th-batch-deploy-2026-07-24` (locked, 8th batch)
- `agent-af01b551c21b2e90f` → `test/qa-bench-phase3-matrix-2026-07-24` (locked)
- `agent-ad38ef07a864d94c6` → `worktree-agent-ad38ef07a864d94c6` (本 worktree, locked, 即 `w68-8th-batch-c2-cleanup` 实施者)

这些 locked worktrees 由后续 batch 处理 (W68 第 8 批 C-2 后续 / 第 9 批), **不要手动删**.

### 4.2 失败处理

如果 `--apply` 中途失败 (例如 push origin 失败), 脚本会:
1. 继续后续步骤 (set +e 默认会让脚本继续)
2. 在总结部分 print 失败计数
3. 主指挥看总结手工处理失败项

**不要**中途 Ctrl-C, 因为已经执行的 `git worktree remove` 不可逆 (worktree 文件没了). 但分支 SHA 在 backup 文件里, 可以重建.

### 4.3 跨平台注意

脚本用 `date +%Y%m%d-%H%M%S` (Linux/Git Bash 兼容). 在 Windows cmd.exe 不能直接跑, 必须用 Git Bash 或 WSL.

---

## 附录: 完整时间线 (W68 第 7 批 → 第 8 批 C-2)

- **2026-07-24**: W68 第 7 批 派工 15 + 1 (hot-fix #18), 跨 A 路线 (qa-bench D5) + B 路线 (drive-v2-pr10 collab WS) + C 路线 (plans 文档同步) + D 路线 (claude-code hook wire)
- **2026-07-24 (晚)**: W68 第 7 批 全部 15 agent merge 到 `chore/w68-8th-batch-a1-merge-2026-07-24` (8th batch staging)
- **2026-07-24 (当晚)**: W68 第 8 批 C-2 cleanup 派工 (本任务)
- **2026-07-24 (主指挥拍板)**: 跑 `bash scripts/w68_7th_batch_cleanup_plan.sh --apply`
- **2026-07-24 (verify)**: baseline 71 PASS + 7 SKIP 守恒 + worktree list ~10 项 + branch -r ~3 项
- **W68 第 8 批**: 8th batch merge staging 进 main, 触发下一轮 worktree 清理

---

**维护者**: 主指挥 (per task `chore/w68-8th-batch-c2-cleanup-2026-07-24`).
**关联 memory**: `memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md` (本次任务沉淀).
**最后更新**: 2026-07-24 W68 第 8 批 C-2 派工.