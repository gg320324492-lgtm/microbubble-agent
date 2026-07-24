# W68 第 9 批 #A-3 — W68 第 7 批 cleanup 真跑 (主指挥 SSH 代理, dry-run 就绪)

> 2026-07-24 · 锚点范式第 107 守恒 · 0 production code 改动铁律维持
> 分支 `chore/w68-9th-batch-a3-cleanup-run-2026-07-24` (不 merge, 主指挥来 merge)

## 背景

W68 第 9 批 #A-1 已把 W68 第 7 批 15 分支 merge 进 8th-batch merge staging `f14cb43c1`
(= 本 agent base). 该 cleanup 把 15 worktree + 16 分支 (15 local + 15 remote + 保护 1) 清掉.

配套三件套 (W68 第 8 批 C-2 agent commit `cf03425a0` 建):
- `scripts/w68_7th_batch_cleanup_plan.sh` — 双模 bash (默认 dry-run, `--apply` 真删)
- `docs/w68-7th-batch-cleanup-runbook.md` — cleanup SOP
- `memory/w68-route-8-c2-w68-7th-batch-cleanup-2026-07-24.md` — C-2 沉淀 (锚点第 98)

C-2 脚本此时**仅在** `chore/w68-8th-batch-c2-cleanup-2026-07-24` 分支, 未 merge 进 main.
本 agent 从该分支 `git show cf03425a0:scripts/...` 提取到 `/tmp` 跑 dry-run (不把脚本 copy
进自己分支, 避免与 C-2 merge 冲突).

## 本 agent 产物 (scripts + docs + logs + memory 四件套)

1. `logs/w68-7th-batch-cleanup-dryrun-2026-07-24.txt` — dry-run 输出捕获 (15 项 + 保护清单)
2. `docs/w68-7th-batch-cleanup-run-execution-2026-07-24.md` — 主指挥 SSH 执行手册 (5 节)
3. `memory/w68-route-9-a3-cleanup-2026-07-24.md` — 本文件

## dry-run 验证结果

- `bash -n` 语法 → `SYNTAX_OK` (0 错误)
- 15 分支 `git merge-base --is-ancestor <branch> f14cb43c1` → **15/15 MERGED** (合并后才能删铁律 PASS)
- dry-run 输出: 15 项 local branch YES + remote YES, 保护清单 priceless 明确列出
- priceless-grothendieck-6a2998 (branch `claude/priceless-grothendieck-6a2998`) worktree + 分支存在,
  **NOT in 15-item CLEANUP_LIST** (双重保护: 不在删列表 + 3 阶段 SKIP 兜底)

## 关键坑

1. **`main` 指针 vs merge staging 分歧**: `main` 停在 `05c60e68d` (W68 第 5 批), W68 第 7 批实际
   merge 进 `f14cb43c1` (8th-batch staging = A-1 base). 判 merge 用 `--is-ancestor <b> f14cb43c1`
   **不是** `main`. 主指挥 SSH cleanup 前须确认本地/远程 main 已推进到含 15 分支的 commit.
2. **`git worktree remove` / `git branch -D` 无 `--dry-run` flag** (`error: unknown option 'dry-run'`).
   脚本自身默认 dry-run 模式是唯一预览机制, 不能用 git 原生 dry-run.
3. **隔离 worktree cwd 致 `WT:NO`**: dry-run 在隔离 worktree 里跑, 脚本用相对路径
   `.claude/worktrees/<name>` 判 worktree, 从隔离 worktree 看不到兄弟 worktree → `WT:NO / 存在 0`.
   主指挥在 main checkout 跑时 15 worktree 正常显示 YES. 非 bug, cwd 差异.
4. **不把 C-2 脚本 copy 进自己分支**: 从 `git show cf03425a0:...` 提取到 `/tmp` 跑, 避免与 C-2
   merge 时冲突 (同一路径两 agent 各带一份 = merge 冲突).

## 5 新铁律 (锚点范式第 107 守恒)

1. **cleanup 默认 dry-run** — 双模脚本不传 `--apply` 永不真删; `--apply` 无 `--force` 时
   `read -p yes` 主指挥拍板才执行. dry-run 输出必须捕获到 logs/ 供审计.
2. **保护清单硬编码** — hot-fix worktree (priceless-grothendieck-6a2998) 硬编码
   `PROTECTED_WORKTREE`/`PROTECTED_BRANCH` + 不在 CLEANUP_LIST + 3 阶段 SKIP 三重保护.
   任何仍未 commit 的 worktree 都要硬编码保护, 不靠 merge 状态判断.
3. **backup branch list 回滚锚点** — `--apply` 删前写 `/tmp/w68-7th-batch-branches-backup-<ts>.txt`
   (worktree_path\tbranch\tsha), 30 天保留. `/tmp` 易清 → 建议 apply 后 `cp` 到 logs/ 长期留存.
4. **apply 后 baseline audit 守恒** — cleanup 只删 git 引用不动源码, 但 apply 后必跑
   `pytest tests/test_baseline_audit.py -v` (71 PASS + 7 SKIP) 确认无回归.
5. **回滚锚点 = 分支已 merge 则内容不丢** — 15 分支全 merge 进 main, 删分支只删引用,
   commit 留在 main 历史. 回滚 = `git branch <b> <sha>` + `git push origin <b>` 恢复引用,
   而非恢复内容. 未 merge 分支删除才是真丢工作 (故 cleanup 前 merge verify 是硬门禁).

## 主指挥 SSH 执行 (第 3 节摘要)

```bash
cd /path/to/microbubble-agent
bash scripts/w68_7th_batch_cleanup_plan.sh          # dry-run 复核
bash scripts/w68_7th_batch_cleanup_plan.sh --apply  # read -p yes → 3 阶段真删
```

verify: `git worktree list` (15 项消失, priceless 留) + `git branch -r | grep 7th-batch` (0) +
`pytest tests/test_baseline_audit.py` (71 PASS + 7 SKIP).

## 锚点范式链

W68 30 (第 1 批) → 42 (第 3 批) → 57 (第 4 批) → 72 (第 5 批) → 90 (第 8 批 A-1) →
98 (第 8 批 C-2 建脚本) → **107 (第 9 批 A-3 dry-run 就绪)**. 单调上升维持.
