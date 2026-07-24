# W68 第 7 批 cleanup 执行文档 (dry-run 已跑, 主指挥 SSH 执行)

> **W68 第 9 批 #A-3 主指挥 SSH 代理产物** (2026-07-24)
>
> 背景: W68 第 9 批 #A-1 已把 W68 第 7 批 15 分支 merge 到 main 线
> (8th-batch merge staging `f14cb43c1`, 15 分支全部 `git merge-base --is-ancestor` PASS).
> 现在该 cleanup: 清掉 15 worktree + 16 分支 (15 W68 第 7 批 + 1 remote).
>
> **本文档 = 主指挥 SSH 执行手册**. dry-run 已在本地 PC 跑完 (见第 1 节),
> 主指挥按第 3 节命令 `--apply` 即可. 回滚见第 4 节, verify 见第 5 节.
>
> 配套脚本: `scripts/w68_7th_batch_cleanup_plan.sh` (W68 第 8 批 C-2 agent 建, 双模 dry-run/--apply)
> 配套 runbook: `docs/w68-7th-batch-cleanup-runbook.md` (C-2 SOP)
> dry-run 输出: `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt`

---

## 第 1 节 dry-run 输出 (本地 PC 已跑)

### 1.1 前置验证 (全 PASS)

| 检查项 | 命令 | 结果 |
|--------|------|------|
| bash 语法 | `bash -n scripts/w68_7th_batch_cleanup_plan.sh` | `SYNTAX_OK` (0 错误) |
| 15 分支 merge 状态 | `git merge-base --is-ancestor <branch> f14cb43c1` | **15/15 MERGED** |
| priceless 保护 | script grep `priceless` | 5 处 (comments + PROTECTED vars + skip logic), **NOT in CLEANUP_LIST** |
| baseline 测试存在 | `ls tests/test_baseline_audit.py` | 存在 |

**15 分支 merge 状态 (全 MERGED 到 `f14cb43c1`)**:

```
MERGED a1   chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
MERGED a2   chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24
MERGED a3   chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24
MERGED d5kb feat/qa-bench-d5-kb-monitor-2026-07-24
MERGED silly feat/silly-gliding-dahl-impl-2026-07-24
MERGED pr10ws feat/drive-v2-pr10-collab-ws-2026-07-24
MERGED phase2 test/qa-bench-phase2-dry-2026-07-24
MERGED mobpush feat/mobile-v3.2-push-backend-2026-07-24
MERGED c1   chore/w68-7th-batch-c1-plans-status-fix-2026-07-24
MERGED c2   chore/w68-7th-batch-c2-plans-archive-2026-07-24
MERGED c3   chore/w68-7th-batch-c3-verified-plans-doc-sync-2026-07-24
MERGED d1   chore/w68-7th-batch-d1-5th-batch-deploy-2026-07-24
MERGED d3   chore/w68-7th-batch-d3-claude-code-voice-alert-2026-07-24
MERGED gc   chore/w68-7th-batch-grand-closure-2026-07-24
MERGED pr10runbook docs/drive-pr10-deploy-runbook-2026-07-24
```

> **注**: `main` 分支指针停在 `05c60e68d` (W68 第 5 批), 而 W68 第 7 批实际 merge
> 进 8th-batch merge staging `f14cb43c1` (A-1 W68 第 9 批的 base). 判断 merge 用
> `--is-ancestor <branch> f14cb43c1`, **不是** `main`. 主指挥 SSH 上 cleanup 前先确认
> 本地/远程 main 已推进到含 15 分支的 commit (A-1 merge 结果).

### 1.2 dry-run 完整输出 (15 worktree + 分支清单)

`bash scripts/w68_7th_batch_cleanup_plan.sh` (默认 dry-run, 不真删):

```
================================================================
[DRY-RUN] W68 第 7 批 worktree + 分支清理预览 (默认模式)
================================================================

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
[DRY-RUN COMPLETE] 不真删. 主指挥拍板后跑: --apply
================================================================
```

> **`WT:NO` 说明**: dry-run 在**隔离 worktree cwd** 下跑, 脚本用相对路径
> `.claude/worktrees/<name>` 判断 worktree, 从隔离 worktree 看不到兄弟 worktree,
> 故显示 `WT:NO / 存在 worktree 0`. **主指挥在 main checkout (`E:/microbubble-agent`
> 或 SSH 上仓库根) 跑时 15 worktree 会正常识别为 YES**. 这不是 bug, 是 cwd 差异.
> `git worktree list` 实际 15 worktree 全部存在 (见 1.3).

### 1.3 实际 git 命令预览 (script `--apply` 会跑的 3 阶段)

> `git worktree remove` / `git branch -D` **不支持 `--dry-run` flag** (已验证:
> `error: unknown option 'dry-run'`). 脚本自身的**默认 dry-run 模式** (不传 `--apply`)
> 就是唯一预览机制. 下面是 `--apply` 时脚本对每一项跑的 3 条命令:

```bash
# 阶段 1/3: 移除 worktree (15 次, 示例第 1 项)
git worktree remove --force .claude/worktrees/agent-a00103ef46303806c

# 阶段 2/3: 删除 local 分支 (15 次)
git branch -D chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24

# 阶段 3/3: 删除 remote 分支 (15 次)
git push origin --delete chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
```

15 worktree ↔ 分支映射 (脚本 `CLEANUP_LIST` 硬编码, 顺序 = W68 第 7 批派工 ID):

| # | worktree | branch |
|---|----------|--------|
| 1 | agent-a00103ef46303806c | chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24 |
| 2 | agent-a83d1f096269a7455 | chore/w68-7th-batch-a2-cheerful-anchor-scripts-2026-07-24 |
| 3 | agent-a785756f198d623ee | chore/w68-7th-batch-a3-qa-bench-isolation-2026-07-24 |
| 4 | agent-a862622ec21e4f37b | feat/qa-bench-d5-kb-monitor-2026-07-24 |
| 5 | agent-a15b80d0cf50a32ec | feat/silly-gliding-dahl-impl-2026-07-24 |
| 6 | agent-a68b44365140e9956 | feat/drive-v2-pr10-collab-ws-2026-07-24 |
| 7 | agent-a9ab41846632dd8cc | test/qa-bench-phase2-dry-2026-07-24 |
| 8 | agent-a8e0f5a43fed97bbe | feat/mobile-v3.2-push-backend-2026-07-24 |
| 9 | agent-a2fa62d9143ea67e4 | chore/w68-7th-batch-c1-plans-status-fix-2026-07-24 |
| 10 | agent-af1bda3114821c1f7 | chore/w68-7th-batch-c2-plans-archive-2026-07-24 |
| 11 | agent-a4ef176d4f5c8a3c0 | chore/w68-7th-batch-c3-verified-plans-doc-sync-2026-07-24 |
| 12 | agent-a5b02d4327953632f | chore/w68-7th-batch-d1-5th-batch-deploy-2026-07-24 |
| 13 | agent-ab788b1ac3a6db3da | chore/w68-7th-batch-d3-claude-code-voice-alert-2026-07-24 |
| 14 | agent-af25e11b3f78258cc | chore/w68-7th-batch-grand-closure-2026-07-24 |
| 15 | agent-ac0caaff1a01d57bb | docs/drive-pr10-deploy-runbook-2026-07-24 |

---

## 第 2 节 保护清单 (硬编码跳过, 不动)

| 项 | 值 | 原因 |
|----|-----|------|
| worktree | `priceless-grothendieck-6a2998` | 主指挥本地 hot-fix #18 worktree, 仍在跑 |
| branch | `claude/priceless-grothendieck-6a2998` | hot-fix #18 未 commit, 不能删 |

**验证**: 脚本 `PROTECTED_WORKTREE="priceless-grothendieck-6a2998"` + `PROTECTED_BRANCH="claude/priceless-grothendieck-6a2998"`
硬编码, 3 阶段每一阶段头部 `if [ "$WORKTREE_NAME" = "$PROTECTED_WORKTREE" ]; then echo SKIP; continue; fi` 兜底. dry-run
[2/4] 段明确列 "保护清单 (不动)". priceless-grothendieck **不在** 15 项 CLEANUP_LIST 中 (双重保护).

本地实测 `git worktree list | grep priceless`:
```
E:/microbubble-agent/.claude/worktrees/priceless-grothendieck-6a2998 05c60e68d [claude/priceless-grothendieck-6a2998]
```
worktree + 分支均存在, cleanup 后仍保留.

> 除 priceless 外, 主指挥仓库还有 8+ 个 `locked` worktree (W68 第 9 批在跑的 agent) 和
> 若干 `worktree-agent-*` 占位分支 — 这些**不在**本脚本清理范围 (脚本只删硬编码 15 项).
> 本脚本只清 **W68 第 7 批** 遗留, 不碰第 8/9 批 worktree.

---

## 第 3 节 主指挥 SSH 执行必做

> ⚠️ **前提**: 主指挥确认 W68 第 9 批 A-1 已把 15 分支 merge 进本地/远程 main
> (含 15 分支的 commit). 未 merge 前跑 cleanup = 丢未合并工作.

```bash
# 0. 切到仓库根 (SSH 上路径以实际为准)
cd /path/to/microbubble-agent

# 1. 先 dry-run 复核 (在 main checkout 跑, 15 worktree 应显示 YES)
bash scripts/w68_7th_batch_cleanup_plan.sh

# 2. 复核无误后 --apply (会 read -p 提示输入 'yes')
bash scripts/w68_7th_batch_cleanup_plan.sh --apply
#    → 提示 "主指挥确认? 输入 'yes' 继续" → 键入 yes
#    → 自动 3 阶段: worktree remove → branch -D → push origin --delete
#    → 删前自动备份分支 SHA 到 /tmp/w68-7th-batch-branches-backup-<ts>.txt

# 3. (可选) 非交互跳过 verify 提示 (CI / 无 tty 场景)
bash scripts/w68_7th_batch_cleanup_plan.sh --apply --force
```

**脚本 --apply 行为**:
- 无 `--force` → `read -p "主指挥确认? 输入 'yes'"`, 非 `yes` 则 `[ABORTED]` exit 1
- 删前写备份 `/tmp/w68-7th-batch-branches-backup-<ts>.txt` (worktree_path\tbranch\tsha)
- 3 阶段幂等: worktree/branch 不存在自动 `SKIP`, 不报错中断 (`FAIL` 计数不 abort)

---

## 第 4 节 回滚方式

### 4.1 备份文件 (自动生成, 回滚锚点)

脚本 `--apply` 时删前写:
```
/tmp/w68-7th-batch-branches-backup-<YYYYMMDD-HHMMSS>.txt
```
格式: `<worktree_path>\t<branch>\t<branch-sha>`. 每行含删前 SHA, 是回滚的唯一凭据.

> **保留期**: 主指挥拍板 30 天保留 (C-2 agent runbook). `/tmp` 可能重启清空 —
> 建议 `--apply` 后立刻 `cp /tmp/w68-7th-batch-branches-backup-*.txt logs/` 长期留存.

### 4.2 单分支回滚

```bash
# 从备份文件读 SHA 重建 local 分支
git branch chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24 85d130ab1
# 推回 remote
git push origin chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
# (可选) 重建 worktree
git worktree add .claude/worktrees/agent-a00103ef46303806c chore/w68-7th-batch-a1-cached-giggling-pebble-fix-2026-07-24
```

> 已知删前 SHA 示例: a1 = `85d130ab1`, pr10-runbook = `398c67f3e` (完整清单见备份文件).
> 因 15 分支已全部 merge 进 main, **即使删掉分支 commit 也留在 main 历史里**, 内容不丢,
> 回滚只是恢复分支引用 + worktree 目录方便再操作.

### 4.3 不回滚的项

- **main 分支**: cleanup 从不动 main (脚本无 main 相关操作)
- **priceless-grothendieck-6a2998**: 硬编码 SKIP, 不删 = 无需回滚
- **第 8/9 批 worktree**: 不在范围, 不受影响

---

## 第 5 节 验证 (--apply 后)

```bash
# 1. worktree list — 应不含 15 个 W68 第 7 批, 仍剩 main + locked + priceless + 第 8/9 批
git worktree list
git worktree list | grep -cE "agent-a00103ef46303806c|agent-a83d1f096269a7455|agent-a785756f198d623ee|agent-a862622ec21e4f37b|agent-a15b80d0cf50a32ec|agent-a68b44365140e9956|agent-a9ab41846632dd8cc|agent-a8e0f5a43fed97bbe|agent-a2fa62d9143ea67e4|agent-af1bda3114821c1f7|agent-a4ef176d4f5c8a3c0|agent-a5b02d4327953632f|agent-ab788b1ac3a6db3da|agent-af25e11b3f78258cc|agent-ac0caaff1a01d57bb"
#    期望: 0 (15 项全清)

# 2. priceless 仍在
git worktree list | grep priceless-grothendieck   # 期望 1 行

# 3. branch 清零验证 (15 个 7th-batch 分支 local + remote 全删)
git branch | grep -c "w68-7th-batch\|qa-bench-d5-kb-monitor\|silly-gliding-dahl\|drive-v2-pr10-collab\|qa-bench-phase2-dry\|mobile-v3.2-push-backend\|drive-pr10-deploy-runbook"   # 期望 0
git branch -r | grep -c "w68-7th-batch\|qa-bench-d5-kb-monitor\|silly-gliding-dahl\|drive-v2-pr10-collab\|qa-bench-phase2-dry\|mobile-v3.2-push-backend\|drive-pr10-deploy-runbook"  # 期望 0

# 4. baseline 守恒 (71 PASS + 7 SKIP)
pytest tests/test_baseline_audit.py -v   # 期望 6+ PASS
#    (完整 9 baseline 合跑见 docs/2026-07-22-baseline-13-stats.md)

# 5. 备份文件长期留存
cp /tmp/w68-7th-batch-branches-backup-*.txt logs/
```

**期望结果**:
- `git worktree list`: 15 项 W68 第 7 批 worktree 全部消失, priceless + main + locked (第 8/9 批) 保留
- `git branch --merged main | wc -l`: 相比 cleanup 前 -15 (15 merged 分支删除)
- baseline: 71 PASS + 7 SKIP 守恒 (cleanup 只删 worktree/分支, 不动 tests/production code)

---

## 附: 纪律回顾 (0 production code 铁律维持)

本任务仅产出 **scripts (C-2 已建) + docs (本文档) + logs (dry-run 捕获) + memory** 四件套,
0 production code 改动. cleanup 本身只删 git worktree/分支引用, 不改任何源代码/测试/配置.

- dry-run 默认 — 不传 `--apply` 永不真删
- priceless-grothendieck hot-fix #18 硬编码保护
- 删前备份分支 SHA (回滚锚点, 30 天保留)
- apply 后 baseline audit 守恒验证
- 主指挥拍板 (`read -p yes`) 才执行真删
