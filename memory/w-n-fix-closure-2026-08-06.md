# W-N-FIX +2 收口记忆（2026-08-06）

W-N-FIX 已完成测试断言同步决策并收口。W-N-FILL-REAL-N Bug 2 的 service SQL 保持 `CAST(:chunk_emb AS text)::vector(1024)[]`，测试契约同步验证 `vector(1024)[]` 与 `CAST`，没有回滚生产修复。

## 5 件套守恒实测

- `SKIP_DB_SETUP=1 pytest tests/test_w_n_fill_impl_backfill.py -q`：**12 passed**。
- 本阶段不改 `app/`、`web/src/`、`alembic/versions/`，不新增数据库迁移。
- 未注册 Celery、未执行真实数据库回填，dry-run 默认行为保持。
- 前端/PWA 无改动，沿用既有基线。
- 交付物仅为 `docs/decisions/2026-08-06-test-fix-decision.md` 与本阶段 memory 文件；锚点守恒为 W-N-FIX +0..+2。

## 收口结论

(a) 12/12 测试 PASS；(b) 0 production code 改动；(c) service SQL 修复未回滚。W-N-FILL 真派工仍受 recall 硬门禁、qa-bench 门禁和主拍书面批准约束，当前不触发真实回填。
