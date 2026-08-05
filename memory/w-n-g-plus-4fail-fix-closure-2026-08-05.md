# W-N-G+ 4 FAIL 修复收口 (2026-08-05)

## 1. 决策结果 (W-N-G+ +5)

- 路径: **Path A — 测试运行方式错误**。
- 失败并非 schema drift 真错误，也不是缺列/类型错。
- 失败原因: `db-1` 容器 Up/healthy 但**不发布 Windows 主机 5432**，`async_session` 拿 `.env` 的 `localhost:5432` → `ConnectionRefusedError [WinError 1225]`。
- 范围: 不动 105、不动生产 DB、不动既有 4 路逻辑、不动方案 C 6 铁律文件。

## 2. 5 件套守恒实测 (W-N-G+ +6)

| 件 | 项 | 实测 |
|----|----|----|
| 1 | alembic 1 head | `105_fix_drift (head)` 单 head 守恒 |
| 2 | DB alembic_version | `105_fix_drift` 守恒 |
| 3 | pytest 默认 Windows 主机 | `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` → **8/8 PASS** (56.29s) |
| 3b | pytest 容器内 INTEGRATION | `INTEGRATION=1 SKIP_DB_SETUP=0 ... pytest ...` → **8/8 PASS** (69.56s) |
| 4 | 0 production code 改动 | 仅 `tests/test_w_n_g_plus_chunk_late_recall.py` + 2 memory，`app/` `web/src/` `alembic/versions/` 0 diff |
| 5 | 锚点范式 W-N-G+ +4..+6 | +4 memory startup (e87cc9a51) + +5 test fix (54ac813c3) + +6 收口 memory (本文件, 待 commit) |

## 3. 修改边界

分支: `claude/w-n-g-plus-4fail-fix`，base = `fbc11908e`。
改动: 1 个测试 + 1 份 startup memory + 1 份 closure memory。
- `tests/test_w_n_g_plus_chunk_late_recall.py` 新增 `_query_schema_scalar` 异步 helper。
  - `INTEGRATION=1`: 走 `async_session`（覆盖 app 容器原集成路径）。
  - 默认主机: 走 `docker exec microbubble-agent-db-1 psql` 只读查询，绕过未发布端口。
  - 容器名可由 `W_N_G_PLUS_DB_CONTAINER` 覆盖。
- 4 个 schema 测试改用 helper，断言不变。
- 后 4 个 _chunk_late_recall / retrieve 行为测试保持原貌。
- 未改 `app/services/hybrid_retriever.py` 既有 4 路逻辑、未改 105 迁移。

## 4. 8/8 PASS 双路径验证

- Windows 主机默认: `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` → 8 passed。
- app 容器内集成: `INTEGRATION=1 SKIP_DB_SETUP=0 ... pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` → 8 passed。
- 默认路径耗时 56.29s；容器路径耗时 69.56s（包含 4 个真 DB 召回）。

## 5. 派工 v6 §13 仓库实情真查 (据实上报 1 项)

- 派工 brief 假设: 4 FAIL 为 schema 缺列/类型错。
- 实测真值: schema 已修，三列都存在且类型正确。失败根因是 db 容器未发布主机端口。
- 偏差处理: 据实改测试运行方式，迁移/生产 DB 不动。

## 6. 6 类 20 沉淀

- **类 20.157 (新, W-N-G+ +5)**: pytest 真 DB 集成测试的“默认”入口必须**实测可达**——db 容器 Up/healthy 不会自动发布到主机 5432，pytest 直接走 `localhost:5432` 必爆 `ConnectionRefusedError`；要么 `INTEGRATION=1` 走应用 session，要么用 `docker exec` 只读 fallback（`docker compose run` 不能直接 mount pytest 配置）。修测试默认路径优先于改迁移。
- **类 20.158 (新, W-N-G+ +5)**: 双路径 integration test 设计——`INTEGRATION=1` 用应用 session 覆盖 Compose `db` 主机名解析；非 INTEGRATION 走 `docker exec` 旁路 Windows 主机端口。容器名 env override 保证跨环境可移植。
- **类 20.159 (新, W-N-G+ +5)**: 派工 brief 假设与实测偏差——派工 brief 估 “schema drift 真实未修”，实测三列均已存在。沿用派工 v6 §13 假设禁令，不擅自扩也不擅自缩。
- **类 20.160 (新, W-N-G+ +5)**: Worktree 并发隔离纪律——主仓库 main HEAD 在派工期间被其他会话推进，**严格**从指定 base `fbc11908e` 建独立分支 `claude/w-n-g-plus-4fail-fix` 操作，不纳入其他会话提交。锚点 W-N-G+ +4..+6 守恒。
- **类 20.161 (新, W-N-G+ +5)**: 0 production code 守恒 5/5 — 不改 `app/` `web/src/` `alembic/versions/105_*.py`，本任务仅在 `tests/` + `memory/` 范畴。
- **类 20.162 (新, W-N-G+ +5)**: alembic 1 head 与 DB version_num 守恒 — `python -m alembic heads` = `['105_fix_drift']` + `SELECT version_num` = `105_fix_drift`，实测守恒。

## 7. W-N-G+ 6 commits 据实累计 (含 W-N-G+ +4..+6)

| 锚点 | commit | 改动 |
|------|--------|------|
| +0 | `7cb6bf0d1` | memory startup (派工 v6 §13 + drift 锁定) |
| +1 | `7cb6bf0d1` | alembic 105_fix_drift.py + 4 步 stamp/upgrade (合并到 +0 commit) |
| +2 | `322455f5d` | verify script + pytest + results JSON |
| +3 | `e8b517144` | 5 件套守恒 + 类 20.153/154 (合并到 +0/+1 收口) |
| +4 | `e87cc9a51` | memory startup 4 FAIL 修复 (本任务) |
| +5 | `54ac813c3` | test fix 双路径 helper (本任务) |
| +6 | 待 commit (本文件) | 收口 memory + 5 件套守恒实测 (本任务) |

派工 brief 估 W-N-G+ +4..+6 = 3 commits, 实测 +4..+6 = 3 commits (e87cc9a51 + 54ac813c3 + 待 +6), 守恒。

## 8. 风险与限制

- 默认主机命令的 schema fallback 依赖 `docker exec` 在 PATH 中可用且容器名匹配；若未来 compose 重命名 db 容器必须同步更新默认参数 `microbubble-agent-db-1`（或显式传 `W_N_G_PLUS_DB_CONTAINER`）。
- `_query_schema_scalar` 仅做只读查询，不写库；任何写入仍必须走 `INTEGRATION=1` 集成路径。
- `pytest.skip` 没有使用：默认 Windows 路径下若 db 不可达，调用 `pytest.fail` fail-loud，避免 W73 类“测试静默通过”陷阱。

## 9. 后续留口 (主拍决策)

- main 侧 worktree 物理路径是 `E:/microbubble-agent/.worktrees/w-n-g-plus-4fail-fix`，独立分支 `claude/w-n-g-plus-4fail-fix`（已含 +4 +5 +6 共 3 commit，HEAD 在 closure memory commit 上）。
- 是否合并入 main 由主拍决定，本任务不在授权范围。
