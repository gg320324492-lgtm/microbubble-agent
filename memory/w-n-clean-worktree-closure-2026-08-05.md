# W-N-CLEAN worktree 清理收口（2026-08-05）

## 5 件套守恒实测

1. **主仓 HEAD 守恒**：基线 `97225717b` 为 main 祖先（`git merge-base --is-ancestor 97225717b HEAD` 返回 0）；执行期间 HEAD 漂移由并发批次 `W-N-MIN +3/+4` 产生，本任务未对 main 做 reset/amend，仅在漂移之上追加 1 commit `1579b457a`（W-N-CLEAN +0/+1）。
2. **派工 brief 范畴守恒**：仅 1 份 docs（`docs/w-n-clean-worktree-report-2026-08-05.md`）+ 2 份 memory（`memory/w-n-clean-worktree-startup-2026-08-05.md` + 本收口文件）。`git diff --cached 11a41509d..1579b457a --stat` 仅 2 files changed, 58 insertions, 0 deletions。`app/`、`web/src/`、`alembic/versions/`、plan 文件均未被触碰。
3. **worktree/branch 元数据守恒**：
   - 清理前 worktree 注册项 15 个；W-N 周期 anchor（`claude/w-n-*`/`claude/bold-mendeleev-*`/`claude/w-n-g-plus-*`）命中数 = 0（与派工 brief「W-N-A / W-N-G+ 已归档」一致）。
   - `git worktree prune` 静默成功，无 stale 引用可清，未触发任何写删除逻辑。
   - 非 W-N 周期 worktree（`agent-fix-deploy`、`w100-multi-fix`、`w100-p49..p75`、`w100-rag-final`、`perf/pgvector-hnsw-tuning`、`busy-satoshi-abd395`）原样保留，0 误删。
4. **0 改 W-N 已有 commit**：W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 任何已有 commit 0 diff 守恒。本任务仅在 main 末位追加 1 commit，序号 `W-N-CLEAN +0/+1` 与并发 `W-N-MIN +3/+4` 不撞号。
5. **锚点范式守恒**：`git log origin/main --oneline -50 | grep -oE 'W-N[A-Z-]* ?\+[0-9.]+'` 中 W-N-CLEAN 仅出现 `+0/+1` 2 个匹配点（同一 commit 行内），符合派工 brief「`W-N-CLEAN +0..+2`」范围。

## 关键物证

- 提交 hash：`1579b457a`（`docs(memory): W-N-CLEAN worktree 清理报告 + 起步 (W-N-CLEAN +0/+1)`），已推 `origin/main`。
- 落地文件：
  - `docs/w-n-clean-worktree-report-2026-08-05.md`（80 行 5 段 + 守恒铁律）
  - `memory/w-n-clean-worktree-startup-2026-08-05.md`（6 项起步核验）
  - `memory/w-n-clean-worktree-closure-2026-08-05.md`（本文件，5 件套守恒实测）
- 并发批次共存：`W-N-MIN +3 (347c38f43)` + `W-N-MIN +4 (11a41509d)` + `W-N-CLEAN +0/+1 (1579b457a)`，均文档/memory 范畴，互不干扰。

## 留口

- W-N 周期后续若新增 `claude/w-n-*` worktree，应在任务结束阶段（`ARC` 或 `GC` 批次）显式 `git worktree remove --force` + `git branch -D`，避免 anchor 漂移。
- 跨批次并发（如 `W-N-MIN` 与 `W-N-CLEAN` 同时在途）应互不 commit `app/`、`web/src/`、`alembic/versions/` 等业务代码；本任务并发守住此铁律。
