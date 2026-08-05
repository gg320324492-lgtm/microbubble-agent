# W-N-G+ 4 FAIL 修复起步 (2026-08-05)

## 1. 派工 brief 锚定

- 任务: W-N-G+ 测试 4 FAIL 真实原因定位与修复
- 指定 base: `fbc11908e` (W-N-BGE +3)
- W-N-G+ 既有链: `7cb6bf0d1` (105_fix_drift) + `322455f5d` (verification/test)
- 锚点范围: W-N-G+ +4..+6
- 允许边界: 105 迁移（仅必要时）+ 1 个测试 + startup/closure memory

## 2. 仓库与分支实测

- 指定 base `fbc11908e` 已验证。
- 主仓库有其他会话并发推进 main，因此本任务从指定 base 创建独立分支 `claude/w-n-g-plus-4fail-fix`，避免纳入无关改动。
- 工作树: `E:/microbubble-agent/.worktrees/w-n-g-plus-4fail-fix`。

## 3. 失败基线实测

命令:

```bash
SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v
```

结果: **4 FAILED + 4 PASSED**。四个失败均在 `async_session()` 首次查询时抛出 `ConnectionRefusedError: [WinError 1225]`，不是断言发现列缺失或类型错误。

## 4. Docker 与 schema 实测

- `microbubble-agent-db-1`: Up/healthy。
- db 容器端口: 仅 `5432/tcp`，未发布 Windows 主机端口。
- `knowledge.embedding_model_version`: 存在，`varchar`。
- `meetings.embedding_model_version`: 存在，`varchar`。
- `knowledge_chunks.chunk_embedding`: 存在，`vector(1024)[]`；information_schema 为 `ARRAY/_vector`。
- DB `alembic_version`: `105_fix_drift`。
- app 容器内显式集成运行已实测 **8/8 PASS**。

## 5. Path A/B/C/D 决策

- **Path A 采用**: 测试运行环境错误。默认主机命令继承 `.env` 的 `localhost:5432`，但 db 未发布该端口；`SKIP_DB_SETUP=1` 只跳 root conftest DB 初始化，不会改 production `async_session` 的连接目标。
- Path B 否: db 容器已运行且 healthy。
- Path C 否: 105 schema drift 已真实修复，三个列均存在。
- Path D 否: `chunk_embedding` 类型确为 `_vector` 数组。

## 6. 修复策略与边界

- 不改 105，不改生产 DB。
- 只修改 `tests/test_w_n_g_plus_chunk_late_recall.py`。
- schema 测试统一调用只读 helper:
  - `INTEGRATION=1`: 使用应用 `async_session`，覆盖 app 容器真实连接路径；
  - 默认主机运行: 使用 `docker exec microbubble-agent-db-1 psql` 只读查询，绕过未发布的 Windows 主机端口。
- 后四个召回测试保持原逻辑不动。

## 7. 六项起步清单 (W73 铁律)

- [x] 指定 base/commit 锚定
- [x] 失败基线 4 FAIL 实测
- [x] Docker 容器状态实测
- [x] DB schema/type/version 实测
- [x] Path A/B/C/D 决策完成
- [x] 修改边界与 8/8 验证命令锁定
