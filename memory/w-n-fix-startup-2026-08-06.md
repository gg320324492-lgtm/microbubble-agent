# W-N-FIX +0 起步记忆（2026-08-06）

W-N-FIX 针对 W-N-FILL-REAL-N Bug 2 修复后的测试回归断言失配启动。基线通过 `git log --oneline -3` 确认为 `6d8f0226f`；既有 commit 已把 apply-path 测试从宽泛的 `vector[]` 更新为 `vector(1024)[]` 并增加 `CAST` 断言。

起步守恒：
1. 只核对测试与 service 现状，不改测试或 production code。
2. 禁止回滚 `late_embedding_backfill.py` 的 CAST SQL 修复。
3. 禁止修改 alembic、app、web/src 及既有 W-N 阶段 commits。
4. 决策交付物限定为 1 个 decision doc 与 2 个 memory 文件。
5. 必须从仓库根目录执行回归测试，避免 worktree 相对路径误判。
6. 收口以 12/12 PASS、0 production code 改动、service SQL 修复保留为三重门禁。

派工锚点：W-N-FIX +0 起步；后续为 +1 决策、+2 收口。
