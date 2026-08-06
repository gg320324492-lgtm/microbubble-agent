# W-N-FIX +1 决策：测试断言与回填 SQL 同步

日期：2026-08-06  
锚点：W-N-FIX +1  旧基线：`6d8f0226f`

## §1 背景

W-N-FILL-REAL-N Bug 2 修复了 `test_backfill_one_chunk_apply_path` 所覆盖的真实写入路径：service SQL 使用 `CAST(:chunk_emb AS text)::vector(1024)[]`，避免 pgvector 数组参数在 SQLAlchemy/asyncpg 路径中的类型解析歧义。旧测试只断言 `vector[]`，既不能表达实际维度，也无法验证 CAST 修复，因此在 service 修复后失配。

## §2 决策

保持 `app/services/late_embedding_backfill.py` 的 service 修复不回滚；仅同步测试断言，使其验证实际 SQL 契约：

- SQL 必须包含 `chunk_embedding` 更新目标；
- SQL 必须包含 `vector(1024)[]`，与列类型和迁移定义一致；
- SQL 必须包含 `CAST`，锁定 Bug 2 的修复路径。

本决策不扩展生产路径，不改变回填默认 dry-run 行为，也不启用 Celery 或真实数据库回填。

## §3 类 20.166

**测试断言必须跟 service SQL 修复同步。** 当 service 修复了 SQL 类型、CAST 或参数绑定语义时，测试不能继续断言旧的宽泛片段（例如 `vector[]`）。应断言修复后的可观察契约（本例为 `vector(1024)[]` 与 `CAST`），避免测试假绿并防止未来回归。测试同步不等于回滚 service，也不允许借机修改 production code。

## §4 5 件套守恒实测

- **测试**：`cd E:\microbubble-agent && SKIP_DB_SETUP=1 pytest tests/test_w_n_fill_impl_backfill.py -q` → **12 passed**。
- **Production code**：本决策阶段未修改 `app/`、`web/src/`、`alembic/versions/` 或 service SQL。
- **数据库迁移**：未新增、未修改 migration；alembic 链保持不变。
- **前端/PWA**：本任务无 frontend 改动，沿用既有基线。
- **文档与锚点**：仅记录 W-N-FIX +1 决策；不改既有 W-N 阶段 commits。

## §5 决策门禁

以下门禁全部通过后，W-N-FIX 可收口：

- (a) **12/12 测试 PASS**：已通过。
- (b) **0 改 production code**：已通过；只同步了测试断言（既已由 `6d8f0226f` 完成）。
- (c) **service SQL 修复未回滚**：已通过；`late_embedding_backfill.py` 仍保留 `CAST(:chunk_emb AS text)::vector(1024)[]`。

## §6 触发再启条件

只有在主拍书面批准并重新确认 W-N-FILL 的业务门禁后，才可启动真实回填：

1. W-N-D++ 的 recall 决策不再是 `+0.00%` 硬失败；
2. qa-bench 门禁达到当前要求（至少 96.5%）；
3. `chunk_embedding` schema、service SQL 与测试契约再次完成三方核验；
4. 明确批准 `dry_run=False` 的部署窗口与回滚方案。

在这些条件满足前，继续保持默认 dry-run，不注册调度、不执行生产回填。
