# W-N-A HNSW 调优 起步 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N 周期 A 阶段 (HNSW 调优)
> **Task**: pgvector HNSW m / ef_construction / ef_search 扫参, 找甜点参数
> **Plan**: `E:\microbubble-agent\docs\superpowers\plans\2026-08-05-pgvector-optimization.md` §2 阶段 A 全文
> **基线 HEAD**: `0e1331bc4` (W100 +75 收尾) — 守恒 ✓
> **alembic head**: `098_meetings_status_varchar_32` (单链, 1 head) — 守恒 ✓
> **Worktree**: `claude/bold-mendeleev-fdc0e8`

---

## 起点 6 项 (W73 铁律)

### 1. base head 守恒
- 派工 brief 期望: `0e1331bc4` (W100 +75 收尾)
- 实测: `0e1331bc4` ✅ 守恒

### 2. test baseline 实测
- `tests/perf/conftest.py` 已存在 (`perf_config` fixture, 沿用不加改)
- `tests/perf/test_recall_perf_baseline.py` 已存在 (沿用)
- `tests/integration/__init__.py` 已存在
- 新建 `tests/perf/test_hnsw_recall_at_k.py` + `test_hnsw_recall_calc.py` 不冲突

### 3. 文件清单 (新增, 不动老路径)
| 文件 | 类型 | 阶段 |
|---|---|---|
| `scripts/bench_hnsw_params.py` | 新建 | A.1+A.2+A.3 |
| `tests/perf/test_hnsw_recall_at_k.py` | 新建 | A.1 |
| `tests/perf/test_hnsw_recall_calc.py` | 新建 | A.2 |
| `tests/integration/test_hnsw_bench_real.py` | 新建 | A.3 |
| `alembic/versions/099_hnsw_param_tune.py` | 新建 (新迁移) | A.4 (实测后才写) |
| `results/hnsw_*_2026-08.json` | bench 输出 (gitignore 不拦) | A.4 |

### 4. 风险表
| 风险 | 缓解 |
|---|---|
| `ALTER INDEX ... SET (m=24)` 在 pgvector 是 no-op (§0.4 P1-3) | **改 DROP + CREATE 全重写** |
| 1k+ rows 表 REINDEX 锁表 | 选低峰期 / n_queries 控制在 100 (≈ 5s) |
| Postgres 离线时 code 写得能跑但跑不通 | 标 SKIPPED + memory 标 DEFERRED |
| bench JSON 文件不 commit | 加 `results/` 到 .gitignore 检查 (本次 fix) |
| `pytest tests/integration/` 漏 env 控 | 必须 `INTEGRATION=1` 才跑 (pytestmark skipif) |

### 5. 验证策略
- 步骤级 TDD: 写失败测试 → 跑确认 fail → 写最小实现 → 跑 PASS → commit
- 5 件套守恒: alembic 1 head + pytest PASS + no main HEAD drift + 0 prod code 守恒 + 锚点范式
- 收尾: `python -m alembic heads` 必须 1 head `099_hnsw_param_tune` (如果写 migration)

### 6. 失败回滚
- bench JSON 不入仓 → 重跑即可
- migration 写错 → `alembic downgrade -1` 回退 (downgrade 函数里有 DROP INDEX + CREATE 默认索引)
- 整体撤回干净 → `git reset --hard 0e1331bc4` (本分支独享, 不影响 main)

---

## 派工预期 vs 实测 (据实上报)

| 任务 | 派工 brief | 实测 | 偏差 |
|---|---|---|---|
| A.1 bench 骨架 | `tests/perf/__init__.py` + `conftest.py` 新建 | 都已存在, 不创建 (plan 已注解) | **+0 commits** (plan 修订版) |
| Postgres 可用性 | 假设本地有 | 实测 `microbubble-agent-db-1` UP, 530 knowledge / 19 meetings / 37 members | ✅ |
| 基线 HEAD | `0e1331bc4` | `0e1331bc4` | ✅ |
| Alembic head | `098_meetings_status_varchar_32` | `098_meetings_status_varchar_32` (1 head) | ✅ |

---

## 类 20 沉淀 (起步)

- **类 20.153 (新, W-N-A 实战)**:
  `set -euo pipefail` 严格模式下 `bench_hnsw_params.py --help` 子进程调用必须
  `result.returncode == 0` 严格断言, 不能容忍 "stderr 有 warning 但 exit 0"
  (e.g. asyncpg 旧版 deprecation warning 不会 fail exit code).

- **类 20.154 (新, W-N-A 实战)**:
  pgvector HNSW 在 PG 16 + pgvector 0.7+ **DROP + CREATE 唯一改 m / ef_construction 的方法**,
  `ALTER INDEX ... SET (m=N)` 是 no-op (plan §0.4 P1-3 修订版来源).

---

**派工 brief 锚点**: W-N-A +0 ~ +5 (6 commits 预期). 据实上报后写到 closure memory.
**主拍**: 派工 v6 §13 仓库实情真查 ✓ (实测 HEAD/alembic/postgres/脚本/测试目录)
