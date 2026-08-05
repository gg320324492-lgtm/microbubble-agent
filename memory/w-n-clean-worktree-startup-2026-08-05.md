# W-N-CLEAN worktree 清理起步（2026-08-05）

## W-N-CLEAN +0：6 项起步核验

1. **仓库与任务边界**：操作仓库为 `E:/microbubble-agent`；只允许处理 Git worktree、W-N 周期匹配分支，以及本任务 1 份 docs + 2 份 memory。
2. **派工基线核验**：派工指定基线 `97225717b` 存在且为当前 `HEAD` 祖先。开始执行时 `HEAD=347c38f43`（`W-N-MIN +3`）；执行期间并发推进到 `11a41509d`（`W-N-MIN +4`）。不 reset、不改写并发提交。
3. **工作区核验**：主仓开始时 `git status --short --branch` 为 `## main...origin/main`，无已跟踪文件修改。
4. **清理匹配规则**：仅匹配 `claude/w-n-*`、`claude/bold-mendeleev-*`、`claude/w-n-g-plus-*`；不把 `agent-fix-deploy`、`w100-p49` 等其他周期 worktree 纳入删除范围。
5. **保护规则**：禁止删除 `main`，禁止修改 plan、`alembic/versions/` 或 W-N 已有提交，禁止删除无法确认属于 W-N 周期的 worktree/branch。
6. **验证计划**：记录清理前 worktree/branch，删除确认命中项（若有），执行 `git worktree prune`，再核验 W-N 匹配项为 0，并记录其他受保护 worktree 原样保留。
