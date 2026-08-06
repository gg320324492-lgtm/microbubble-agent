# W-N-CLEAN-F2 Startup - 2026-08-06

## 任务锚点
- 派工 brief: W-N-CLEAN-F2 worktree 清理 agent
- 当前 commit (main HEAD): `6d8f0226f` (W-N-FILL-REAL-N 测试 FAIL 修复)
- 工作目录: `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8\`
- W-N 锚点范式: W-N-CLEAN-F2 +0 / +1 / +2

## 6 项起步 (W73 铁律)

### 1. base head 验证
```
git log --oneline -5
6d8f0226f fix(test): W-N-FILL-REAL-N 测试回归断言修正 (12/12 PASS)
8c50c777a perf(rag): bge-m3 1000 题真测 encoder-only 数据 (W-N-BGE-A 收尾)
c34e6739f docs(memory): W-N-FILL-REAL-N +2 收口沉淀 (5 件套守恒实测 + ...)
b99f300b7 feat(rag): W-N-FILL-REAL-N 修 Bug 2 + 真派工 37/37 chunks 写入
2329d0b44 feat(dft): 容器 bind mount workflows + g16w + SCISOFTWARE_BASE env
```
✅ base head = `6d8f0226f` 与派工 brief 一致

### 2. git worktree list 全量调研 (15 worktrees)
```
E:/microbubble-agent                                                6d8f0226f [main]
E:/agent-fix-deploy                                                 000000000 [chore/fix-deploy]
E:/microbubble-agent/.claude/worktrees/busy-satoshi-abd395          000000000 [claude/busy-satoshi-abd395]
E:/microbubble-agent/.claude/worktrees/sharp-varahamihira-2c7a28    2e15eb45c [claude/sharp-varahamihira-2c7a28]
E:/microbubble-agent/.claude/worktrees/w100-multi-fix               ba9661886 [claude/w100-multi-fix]
E:/microbubble-agent/.claude/worktrees/w100-p49-contentbrief-unfold 000000000 [claude/w100-p49-contentbrief-unfold]
E:/microbubble-agent/.claude/worktrees/w100-p50-phase-debug         000000000 [claude/w100-p50-phase-debug]
E:/microbubble-agent/.claude/worktrees/w100-p51-ui-buttons          000000000 [claude/w100-p51-ui-buttons]
E:/microbubble-agent/.claude/worktrees/w100-p52-plan-autoclose      000000000 [claude/w100-p52-plan-autoclose]
E:/microbubble-agent/.claude/worktrees/w100-p53-plan-done           000000000 [claude/w100-p53-plan-done]
E:/microbubble-agent/.claude/worktrees/w100-p54-plan-compat         000000000 [claude/w100-p54-plan-compat]
E:/microbubble-agent/.claude/worktrees/w100-p55-bubble-upgrade      000000000 [claude/w100-p55-bubble-upgrade]
E:/microbubble-agent/.claude/worktrees/w100-p57-blank-fix           000000000 [claude/w100-p57-blank-fix]
E:/microbubble-agent/.claude/worktrees/w100-p75-cleanup             5a98fb25f [claude/w100-p75-cleanup]
E:/microbubble-agent/.claude/worktrees/w100-rag-final               f872d73fb [claude/w100-rag-final]
E:/microbubble-agent/.worktrees/perf-pgvector-hnsw-tuning           0e1331bc4 [perf/pgvector-hnsw-tuning]
```

### 3. W-N 周期相关残留识别
**派工 brief 关注三类残留**:
- `claude/w-n-*` (派工 brief 严禁其他 W-N agent 残留)
- `claude/bold-mendeleev-*` (W-N-A 派工 anchor)
- `claude/w-n-g-plus-*` (W-N-G+ 4 FAIL 派工 anchor)

**实测 (2026-08-06)**:
- `claude/w-n-*` 模式: 0 个本地 worktree / 0 个本地 branch ✅ (W-N-ARC + W-N-G+ 已清理)
- `claude/bold-mendeleev-*` 模式: 0 个本地 worktree / 0 个本地 branch ✅
  - 但 `E:/microbubble-agent/.claude/worktrees/bold-mendeleev-fdc0e8/` **目录残留** (orphan dir, 无 `.git` link, 不在 git worktree list)
- `claude/w-n-g-plus-*` 模式: 0 个本地 worktree / 0 个本地 branch ✅

**结论**: W-N 周期相关 worktree 全部 0 命中, **0 删除对象**.

### 4. 派工 brief vs 实测
- 派工 brief: "W-N-CLEAN 之前已清理 0 命中 W-N 周期" ✅ 验证通过
- 派工 brief: "W-N-A worktree `claude/bold-mendeleev-fdc0e8` 已删 (W-N-ARC 归档)" ✅ 验证通过 (branch 已删, 仅 orphan dir 残留)
- 派工 brief: "W-N-G+ worktree `claude/w-n-g-plus-4fail-fix` 已删 (W-N-G+ 4 FAIL 归档)" ✅ 验证通过

### 5. 守恒铁律
- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/FILL-REAL/FILL-REAL-N 既有 commits
- ✅ 0 改 main HEAD (`6d8f0226f`)
- ✅ 0 删其他 agent 的 worktree (派工 brief 严禁删 w100-*/sharp-*/busy-*/perf-* 等其他 agent 的 worktree)
- ✅ 0 改 tests/ 任何文件
- ✅ 0 改 alembic/versions/
- ✅ 锚点范式: W-N-CLEAN-F2 +0..+2 据实累计
- ✅ base head 守恒: `6d8f0226f`

### 6. 清理范围判定
**Step 1**: `git worktree prune` (清理 stale 引用) — 已执行, 无 stale 引用可清理 (prune 返回空)
**Step 2**: `git branch -a` 全量调研 — 列出所有本地 + remote branches
**Step 3**: W-N 周期相关 worktree/branch 识别 — **0 命中**
**Step 4**: W-N 周期相关 worktree 清理 — **0 删除对象** (前次 W-N-CLEAN 已清干净)
**Step 5**: 验证 — `git worktree list` 输出符合派工 brief 期望
**Step 6**: 写 `docs/w-n-clean-final-2026-08-06-f2.md` 报告
**Step 7**: commit 1 docs + 1 memory 范畴
**Step 8**: 写收口 memory

## 下一步
执行 Step 1-7, 然后写 `memory/w-n-clean-f2-closure-2026-08-06.md`.
