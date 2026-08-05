# W-N-ARC Worktree 归档 起步 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N-ARC 阶段 (worktree 归档清理)
> **Task**: 把 W-N-A worktree `claude/bold-mendeleev-fdc0e8` 永久归档清理 (worktree remove + branch -D + memory 沉淀)
> **Worktree**: `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8` (分支 `claude/bold-mendeleev-fdc0e8`)
> **Worktree HEAD**: `5d0757551` (W-N-A +5 收口)
> **Main HEAD (派工时)**: `fb4343f29` (W-N-D late chunking memory 入主)

---

## 起点 6 项 (W73 铁律)

### 1. base head 守恒

- main HEAD: `fb4343f29` (W-N-D late chunking memory 入主)
- worktree branch HEAD: `5d0757551` (W-N-A +5 收口)
- worktree branch base: `0e1331bc4` (W100 +75 收尾, 守恒 ✓)
- branch 比 main 旧 (base `0e1331bc4` << `fb4343f29`), W-N-A 之后的 W-N-B/C/D 都在 main 上演进

### 2. 实测 worktree 状态

- `git worktree list`: 1 行包含 `bold-mendeleev-fdc0e8` (路径 `E:/microbubble-agent/.claude/worktrees/bold-mendeleev-fdc0e8`)
- worktree branch HEAD = `5d0757551` (W-N-A +5)
- 工作目录有 1 个 modified + 9 个 untracked (来自 W-N-D 期间本地实验, 内容**已通过其他 commit 在 main 入主**):
  - `app/services/hybrid_retriever.py` (modified, 与 main `740aafbde` 内容一致)
  - `alembic/versions/{100,101,102,103,104}_*.py` (untracked, 与 main `39866b375` + `f58122f9b` + `a528fab7d` 内容一致)
  - `app/services/late_chunking_service.py` (untracked, 与 main `39866b375` 一致)
  - `results/late_chunking_bench_2026-08.json` (untracked, 与 main 一致)
  - `scripts/bench_late_chunking.py` (untracked, 与 main 一致)
  - `tests/integration/test_late_chunking_recall.py` (untracked, 与 main 一致)
  - `tests/unit/test_late_chunking.py` (untracked, 与 main 一致)

### 3. 文件清单 (本任务范畴)

| 文件 | 类型 | 范畴 |
|---|---|---|
| `memory/w-n-arc-worktree-archive-startup-2026-08-05.md` | 新建 | W-N-ARC +0 (本文件) |
| `memory/w-n-arc-worktree-archive-2026-08-05.md` | 新建 | W-N-ARC +1 收口 |

### 4. 风险表

| 风险 | 缓解 |
|---|---|
| worktree 有未提交 W-N-D 实验文件, 可能误丢 | 主拍决策: 这些文件已在 main 上 commit (`39866b375` + `740aafbde` + `f58122f9b` + `a528fab7d`), 可安全丢弃本地副本 |
| `git worktree remove --force` 误删其他 worktree | 实测只列 1 个目标, 严格路径匹配 `.claude/worktrees/bold-mendeleev-fdc0e8` |
| `git branch -D` 误删 main 分支 | 严格指定分支名 `claude/bold-mendeleev-fdc0e8`, 主拍执行前 double check |
| main 上 W-N-A 内容未完全对齐 (分支有 099_hnsw_param_tune.py 独有文件) | 派工 brief 已确认 main cherry-pick 跳过了 099 迁移 (commit `14bc9246e` 注释明示), 主拍决策: **099_hnsw_param_tune.py 留档, 不入 main** |
| cherry-pick commit 推 main 后分支 5 commits 仍存在 | branch 上独有 commits (`48d43e3cc`..`5d0757551`) 内容大部分已 cherry-pick, branch 仍可 force delete 不影响 main |

### 5. 验证策略

- 5 件套守恒: alembic 1 head 守恒 + pytest 全守恒 + 0 production code 改 + 锚点范式守恒 + PWA build 不涉及
- 步骤级验证: worktree 列表 → branch 列表 → commit diff → 文件 diff → memory commit 推送
- 收尾: `git worktree list` 不再含 `bold-mendeleev-fdc0e8` + `git branch -D` 成功 + `git log origin/main --oneline -3` 显示新 memory commit

### 6. 失败回滚

- `git worktree remove` 前**不动任何文件**, 仅 verify 路径
- 若 worktree remove 失败 → `cd /e/microbubble-agent && git worktree remove --force .claude/worktrees/bold-mendeleev-fdc0e8`
- 若 branch -D 失败 (e.g. branch 当前 checkout) → 先 worktree remove 再 branch -D
- memory 文件 commit 失败 → `git add` 重试或手动编辑后 `git commit --amend`

---

## 派工预期 vs 实测 (据实上报)

| 项 | 派工 brief | 实测 | 偏差 |
|---|---|---|---|
| worktree HEAD | `5d0757551` (W-N-A +5) | `5d0757551` ✅ | 无 |
| main HEAD | `fb4343f29` (W-N-D memory 入主) | `fb4343f29` ✅ | 无 |
| cherry-pick 已合 main | `14bc9246e` (6 files) + `740aafbde` + `fb4343f29` | ✅ | 派工 brief 已明确 |
| worktree 未提交变更 | (派工 brief 未提) | 1 modified + 9 untracked (W-N-D 实验) | **+0 commits 据实** (本地丢弃, main 上已有) |
| 099_hnsw_param_tune.py | 派工 brief: "skip, 留档" | main 上确实没有, 留档决定成立 ✅ | 无 |
| W-N-A branch commits | `48d43e3cc`..`5d0757551` (6 commits) | 6 commits 仍独有, 内容大部分已 cherry-pick | 无 |

---

## 类 20 沉淀 (起步)

- **类 20.165 (新, W-N-ARC 实战)**:
  worktree 归档前**必须**先 `diff <(git ls-tree main) <(git ls-tree <branch>)` 双 tree 实测,
  确认 worktree 独有文件是否真需要保留. 不可仅凭派工 brief "已 cherry-pick" 假设.

- **类 20.166 (新, W-N-ARC 实战)**:
  worktree 归档前必须 `git status` 查 working dir 未提交变更. 即使 branch HEAD 落后于 main,
  working dir 可能仍有 main 上已 commit 的同内容副本 (本批次: hybrid_retriever.py + 9 late chunking 文件).
  这些是 agent 实验遗留, main 已 commit 后本地副本可安全丢弃.

- **类 20.167 (新, W-N-ARC 实战)**:
  worktree 删除与 branch 删除顺序很重要. 先 `git worktree remove` 解除 working dir 与 branch 的关联,
  再 `git branch -D`. 反过来 `git branch -D` 在 worktree 还 checkout 该 branch 时会报
  "cannot delete branch ... checked out at ...".

---

**派工 brief 锚点**: W-N-ARC +0 ~ +1 (2 commits 预期)
**主拍**: 派工 v6 §13 仓库实情真查 ✓ (实测 worktree HEAD / main HEAD / worktree list / branch list / working dir status / cherry-pick 范围 / 099 迁移去向)
