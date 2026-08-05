# W-N-CLEAN-FINAL worktree 清理起步（2026-08-06）

## 1. 任务背景

W-N 周期第 15 stages 收口后（W-N-FILL + W-N-P3-A + W-N-W72 + W-N-XX 联合 commit `b170a8ff3` 已推 main），重新执行 worktree/branch 元数据集中确认 + 清理。派工锚点 `W-N-CLEAN-F +0/+1/+2`，仅限 git worktree / git branch 元数据 + 1 docs + 2 memory，禁止触碰业务代码、alembic、plans。

与昨日 `W-N-CLEAN`（commit `1579b457a`）的区别：本次为最终态确认（在 W-N 周期 15 stages 全收口 + W-N-FILL-IMPL 沉淀之后），属于「最终巡检 + 守恒」模式。

## 2. 派工 brief 锁定状态

- W-N-A worktree `claude/bold-mendeleev-fdc0e8` 已删（W-N-ARC 归档）
- W-N-G+ worktree `claude/w-n-g-plus-4fail-fix` 已删（W-N-G+ 4 FAIL 归档）
- W-N-CLEAN 之前已清理 0 命中 W-N 周期（commit `1579b457a` 实测 0 stale + 0 匹配 branch）

## 3. base head 验证

`git log --oneline -1` → `b170a8ff3 feat(rag): W-N-FILL + W-N-P3-A + W-N-W72 + W-N-XX 4 agent 联合 commit 推 main (W-N 周期第 15 stages)` ✓

`git status` clean，main 与 origin/main 无 divergence（待 push 完成后守恒）。

## 4. Step 1 — git worktree list 实测

当前 worktree 注册项 15 个：

| 序号 | 路径 | HEAD | branch |
|------|------|------|--------|
| 1 | E:/microbubble-agent | b170a8ff3 | main |
| 2 | E:/agent-fix-deploy | 0000000000 | chore/fix-deploy |
| 3 | .claude/worktrees/busy-satoshi-abd395 | 0000000000 | claude/busy-satoshi-abd395 |
| 4 | .claude/worktrees/sharp-varahamihira-2c7a28 | 2e15eb45c | claude/sharp-varahamihira-2c7a28 |
| 5 | .claude/worktrees/w100-multi-fix | ba9661886 | claude/w100-multi-fix |
| 6 | .claude/worktrees/w100-p49-contentbrief-unfold | 0000000000 | claude/w100-p49-contentbrief-unfold |
| 7 | .claude/worktrees/w100-p50-phase-debug | 0000000000 | claude/w100-p50-phase-debug |
| 8 | .claude/worktrees/w100-p51-ui-buttons | 0000000000 | claude/w100-p51-ui-buttons |
| 9 | .claude/worktrees/w100-p52-plan-autoclose | 0000000000 | claude/w100-p52-plan-autoclose |
| 10 | .claude/worktrees/w100-p53-plan-done | 0000000000 | claude/w100-p53-plan-done |
| 11 | .claude/worktrees/w100-p54-plan-compat | 0000000000 | claude/w100-p54-plan-compat |
| 12 | .claude/worktrees/w100-p55-bubble-upgrade | 0000000000 | claude/w100-p55-bubble-upgrade |
| 13 | .claude/worktrees/w100-p57-blank-fix | 0000000000 | claude/w100-p57-blank-fix |
| 14 | .claude/worktrees/w100-p75-cleanup | 5a98fb25f | claude/w100-p75-cleanup |
| 15 | .claude/worktrees/w100-rag-final | f872d73fb | claude/w100-rag-final |
| 16 | .worktrees/perf-pgvector-hnsw-tuning | 0e1331bc4 | perf/pgvector-hnsw-tuning |

总计 16 个（含主仓），与昨日 W-N-CLEAN（15 个）相比多了 `sharp-varahamihira-2c7a28`，属于其他批次（非 W-N 周期）落地。

## 5. Step 2 — W-N 周期匹配排查

- `git branch -a 2>&1 | grep -iE "w-n|W_N|w_n"` → 0 命中 ✓
- worktree 列表全文检索 `claude/w-n-*` / `claude/bold-mendeleev-*` / `claude/w-n-g-plus-*` → 0 命中 ✓

派工 brief 描述完全一致：W-N 周期在 worktree/branch 元数据层面已无残留 anchor。

## 6. 派工约束

- 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 任何已有 commit
- 0 改 main HEAD（base `b170a8ff3` 守恒）
- 0 删其他 agent 的 worktree（W-N-CLEAN 之前已清理 0 命中；本任务延续「0 触发写删除」原则）
- 锚点范式守恒：`W-N-CLEAN-F +0/+1/+2`
- 严格只在 git worktree + git branch + 1 docs + 2 memory 文件范畴

## 7. 计划路径

- W-N-CLEAN-F +0：本起步 memory
- W-N-CLEAN-F +1：git worktree prune + git branch 匹配 + docs 报告 + 1 commit
- W-N-CLEAN-F +2：收口 memory 5 件套守恒实测 + commit
