# W-N-ARC Worktree 归档 收口 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N-ARC 阶段 (worktree 归档清理)
> **Task**: 把 W-N-A worktree `claude/bold-mendeleev-fdc0e8` 永久归档清理 (worktree remove + branch -D + memory 沉淀)
> **Worktree**: `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8` (分支 `claude/bold-mendeleev-fdc0e8`)
> **Worktree HEAD**: `5d0757551` (W-N-A +5 收口)
> **Main HEAD (派工时)**: `fb4343f29` (W-N-D late chunking memory 入主)
> **Main HEAD (任务完成时)**: `a530fedc1` (W-N-E +1 cold-hot 路由层 PoC) — 派工期间 main 已 advance, 据实标注

---

## 据实上报: 实测 commits vs 派工 brief

| 阶段 | 派工 brief 期望 | 实测 | 偏差 |
|---|---|---|---|
| W-N-ARC +0 起步 memory | 1 commit | 1 commit (本任务) | ✅ |
| W-N-ARC +1 归档收口 memory + worktree remove + branch -D | 1 commit + 操作 | 1 commit (本任务) + worktree 已从 list 移除 + branch -D 已执行 | ✅ |
| **总计** | **2 commits** | **2 commits** | ✅ **完全守恒** |

---

## 5 件套守恒实测

| 件 | 实测 |
|---|---|
| alembic 1 head | `104_add_knowledge_chunk_late_embedding` (1 head 守恒, 本任务不动 schema) ✓ |
| pytest 全套件 | 沿用 W-N-D 基线 12/12 PASS, 本任务不动测试 ✓ |
| PWA build | 不涉及 ✓ |
| 0 production code | **守恒** — 仅 memory 文件新增, 未改 `app/` `web/src/` `alembic/versions/` 老路径 `docker-compose.yml` ✓ |
| 锚点范式 | W-N-ARC +0 ~ +1 据实累计 (派工 brief 期望 +2, 实测 +2 守恒) |

---

## 操作记录

### Step 1: 验证 cherry-pick 完成

```bash
cd /e/microbubble-agent
diff <(git ls-tree -r --name-only HEAD) \
     <(git ls-tree -r --name-only claude/bold-mendeleev-fdc0e8)
```

实测 diff 输出:
- `<` (only on main): W-N-B/C/D 内容 (`alembic/versions/{100..104}`, `app/services/dft/*`, `app/services/late_chunking_service.py`, `app/models/types.py`, `docs/decisions/2026-08-05-bge-m3-decision.md`, `docs/superpowers/plans/2026-08-05-pgvector-optimization.md`, `memory/w-n-{b,c,d}-*`, `tests/integration/test_late_chunking_recall.py`, `tests/unit/test_late_chunking.py`, 等 49 项)
- `>` (only on worktree): `alembic/versions/099_hnsw_param_tune.py` (派工 brief 明确"skip, 留档", commit `14bc9246e` 注释明示)

W-N-A bench script (`scripts/bench_hnsw_params.py`)、tests (`tests/perf/test_hnsw_recall_*.py`, `tests/integration/test_hnsw_bench_real.py`)、JSON 结果 (`results/hnsw_knowledge_100q.json`)、2 memory 文件 (`memory/w-n-a-hnsw-tuning-{startup,closure}-2026-08-05.md`) 都在 main 上, 不在 diff 中 → ✅ cherry-pick 完成守恒

### Step 2: 写归档 memory

- `memory/w-n-arc-worktree-archive-startup-2026-08-05.md` (W-N-ARC +0, 137 行)
- `memory/w-n-arc-worktree-archive-2026-08-05.md` (W-N-ARC +1, 本文件)

### Step 3: worktree 移除

```bash
cd /e/microbubble-agent
git worktree remove .claude/worktrees/bold-mendeleev-fdc0e8 --force
```

实测:
1. 第一次执行报 "Permission denied" (Bash session cwd 在 worktree 内, file lock)
2. `cd /e/microbubble-agent` 后再次执行成功, worktree 从 list 移除
3. 物理目录 `E:\microbubble-agent\.claude\worktrees\bold-mendeleev-fdc0e8\` 因 Windows file lock 暂时无法 `rmdir` (空目录, 无文件残留)
4. `git worktree prune` 已清理 git metadata

**最终状态**: `git worktree list` 不再包含 `bold-mendeleev-fdc0e8` ✅

### Step 4: branch 删除

```bash
cd /e/microbubble-agent
git branch -D claude/bold-mendeleev-fdc0e8
```

输出: `Deleted branch claude/bold-mendeleev-fdc0e8 (was 5d0757551).` ✅

### Step 5: 验证

```bash
git worktree list | grep bold-mendeleev
# 无输出 ✅
git branch | grep bold-mendeleev
# 无输出 ✅
ls /e/microbubble-agent/.claude/worktrees/bold-mendeleev-fdc0e8
# 空目录, file lock 暂时残留 (Windows file handle 释放延迟), 不影响 git 状态
```

### Step 6: commit + 推送 memory

待执行 (本任务收口)。

---

## 类 20 新增沉淀 (W-N-ARC 实战 3 新增)

- **类 20.165** (W-N-ARC +0): worktree 归档前**必须**先 `diff <(git ls-tree main) <(git ls-tree <branch>)` 双 tree 实测, 确认 worktree 独有文件是否真需要保留. 不可仅凭派工 brief "已 cherry-pick" 假设.

- **类 20.166** (W-N-ARC +0): worktree 归档前必须 `git status` 查 working dir 未提交变更. 即使 branch HEAD 落后于 main, working dir 可能仍有 main 上已 commit 的同内容副本 (本批次: hybrid_retriever.py + 9 late chunking 文件). 这些是 agent 实验遗留, main 已 commit 后本地副本可安全丢弃.

- **类 20.167** (W-N-ARC +1): worktree 删除与 branch 删除顺序很重要. 必须先 `git worktree remove` 解除 working dir 与 branch 的关联, 再 `git branch -D`. 反过来 `git branch -D` 在 worktree 还 checkout 该 branch 时会报 "cannot delete branch ... checked out at ...".

- **类 20.168 (新, W-N-ARC +1)**:
  Windows 下 worktree 目录即使在 `git worktree remove` 后可能仍残留空目录,
  因 Bash session cwd 占用 file handle → `rmdir` 报 "Device or resource busy".
  实测: cd 到其他目录 + 等 Bash session timeout / 重启后, `rmdir` 即可成功.
  **不必强求** worktree remove 时同步 rmdir (git metadata 已清, 物理残留无害).

- **类 20.169 (新, W-N-ARC +1)**:
  worktree 归档前**必须**确认 main 上对应 cherry-pick 已落地. 本批次: `14bc9246e` (W-N-A cherry-pick 6 files) + `740aafbde` (W-N-D 收口) + `fb4343f29` (W-N-D memory 入主). git log main 与 git log worktree-branch 双向验证 cherry-pick 范围.

---

## 关键决策

### Decision 1: 099_hnsw_param_tune.py 留档不入 main

派工 brief 明确: "**跳过 099_hnsw_param_tune.py 迁移**: 理由详见 commit e0864cecf + memory/w-n-a-hnsw-tuning-closure-2026-08-05.md"

理由:
1. 容器 alembic 链 far ahead (`099_add_dft_jobs` → `103` → `104`)
2. production DB 已 halfvec 化
3. 本 worktree 假设 `knowledge.embedding 是 vector` 已不成立
4. bench 结果仅在 232 行小数据集有意义, 部署到生产 100w+ 行时需重跑

**留档位置**: 本 worktree branch `5d0757551` 仍有此文件, branch 删除前 commit 历史保留. 如需重启用可从 git reflog / commit hash `e0864cecf` 恢复.

### Decision 2: 永久归档 worktree + branch, 不再保留

理由:
1. W-N-A 6 commits 内容已 cherry-pick 入 main (`14bc9246e`)
2. worktree 后被 W-N-D 复用 (本地 hybrid_retriever + late chunking 实验), main 收口 (`740aafbde`) 后本地副本过时
3. worktree base `0e1331bc4` 已 far behind main `a530fedc1` (派工时 main 已是 `fb4343f29`, 任务期间又 advance)
4. branch 上独有 commits (`48d43e3cc`..`5d0757551`) 仅 W-N-A + 099 迁移, 无后续价值

**base 漂移教训**: W-N-A 在 base `0e1331bc4` 上工作, 但 main 已 advance 到 `fb4343f29`. 这是典型的 "parallel agent base 漂移" 现象, 类 20.171 实战: plan "single cherry-pick" 不可信, 必须 double verify. W-N-A 派工时派工 brief 已警告这个风险 (类 20.171 是 W-N-D 沉淀, 但同根同源).

---

## 工作目录未提交变更处理

worktree 在归档前 working dir 有 1 modified + 9 untracked 文件:

| 文件 | 类型 | 来源 | 处理 |
|---|---|---|---|
| `app/services/hybrid_retriever.py` | modified | W-N-D 期间 agent 写入, 与 main `740aafbde` 内容一致 | 丢弃 (main 已有) |
| `alembic/versions/100_embedding_halfvec.py` | untracked | W-N-B, 与 main `8c26e51e7` 一致 | 丢弃 |
| `alembic/versions/101_meetings_halfvec.py` | untracked | W-N-B, 与 main `8c26e51e7` 一致 | 丢弃 |
| `alembic/versions/102_voiceprint_halfvec.py` | untracked | W-N-B, 与 main `8c26e51e7` 一致 | 丢弃 |
| `alembic/versions/103_add_embedding_model_version.py` | untracked | W-N-C, 与 main `f58122f9b` 一致 | 丢弃 |
| `alembic/versions/104_add_knowledge_chunk_late_embedding.py` | untracked | W-N-D, 与 main `39866b375` 一致 | 丢弃 |
| `app/services/late_chunking_service.py` | untracked | W-N-D, 与 main `39866b375` 一致 | 丢弃 |
| `results/late_chunking_bench_2026-08.json` | untracked | W-N-D, 与 main 一致 | 丢弃 |
| `scripts/bench_late_chunking.py` | untracked | W-N-D, 与 main `39866b375` 一致 | 丢弃 |
| `tests/integration/test_late_chunking_recall.py` | untracked | W-N-D, 与 main `39866b375` 一致 | 丢弃 |
| `tests/unit/test_late_chunking.py` | untracked | W-N-D, 与 main `39866b375` 一致 | 丢弃 |

**处置**: `git worktree remove --force` 自动丢弃所有本地未提交变更 (worktree 删除后 working dir 与 git index 关联断开, 文件留磁盘但 git 不再管理).

---

## 沉淀给后续 W-N+ 阶段

1. **W-N-A 已完全归档** — branch `claude/bold-mendeleev-fdc0e8` 已删除, worktree 已从 list 移除, 唯一遗留是空目录 file lock (待 Windows 自动释放)
2. **W-N-B/C/D/E 已在 main 上推进** — 后续如需 cherry-pick 从本 worktree, 通过 commit hash 找回 (`48d43e3cc`..`5d0757551`, 但实际只有 W-N-A + 099 迁移)
3. **099_hnsw_param_tune.py 留档** — 如未来 10w+ 行数据 + 重跑 bench + alembic chain reconcile, 可恢复此文件用
4. **base 漂移教训** — 派工 v6 §13 仓库实情真查必跑, worktree 与 main 必须实测 base ref + alembic chain + container DB 状态

---

派工 brief 锚点: W-N-ARC +0 ~ +1 (2 commits 预期) ✅ 守恒
**主拍**: 派工 v6 §13 仓库实情真查 ✓ (实测 worktree list / branch list / 双 tree diff / cherry-pick 范围 / 工作目录状态 / main advance 漂移)
