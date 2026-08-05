# W-N-E 冷热分层路由 PoC - 收口 (2026-08-05)

> **派工 anchor**: W-N-E +3 (本文件, 收口)
> **Plan**: `docs/superpowers/plans/2026-08-05-pgvector-optimization.md` §2 阶段 E.0 修订版
> **Base head**: `fb4343f29` (W-N-D late chunking 收口)
> **Final main head**: `aac562075` (W-N-E +2 决策 commit)
> **Alembic head**: `104_add_knowledge_chunk_late_embedding` 守恒

---

## §1 完整交付 (W-N-E +0 / +1 / +2 / +3)

| 锚点 | 内容 | 文件 / commit |
|---|---|---|
| +0 | 起步 memory (6 项实测) | `memory/w-n-e-cold-hot-poc-startup-2026-08-05.md` |
| +1 | 路由层 PoC (新 service + 新方法 + tests) | `app/services/cold_hot_router.py` + `app/services/knowledge_service.py:list_knowledge_partition` + `tests/integration/test_cold_hot_routing.py` (18/18 PASS) |
| +2 | bench 100q × 4 types + 3 决策门禁 | commit `aac562075` (3 files: bench script + JSON + decision doc) |
| +3 | 收口 memory (本文件) | `memory/w-n-e-cold-hot-poc-closure-2026-08-05.md` |

**类 20.156 实战 (W-N-E 据实上报)**: W-N-E +1 commit `a530fedc1` (cold_hot_router.py + knowledge_service.py + test + startup memory) 在其他 agent 跨分支 rebase/merge 时被合并进 W-N-GC +2 commit `91fa4b450`, 我自己 commit hash 不在 main history. 但 **4 个文件 100% 在 main**, 且 W-N-E +2 单独 commit `aac562075` 守恒派工 brief +2 anchor. **0 production code 守恒不变**.

---

## §2 3 决策门禁实测 (派工 brief 严禁跳过)

| 门禁 | 实测 | 派工 brief 门禁值 | 结果 |
|---|---|---|---|
| 1. hot P50 < 50ms | 0.59ms | < 50ms | ✅ PASS |
| 2. cold P95 < 500ms | 16.26ms (seq scan 模拟) | < 500ms | ✅ PASS |
| 3. cold 比例 > 10% | **0%** (530 全 hot, 0 cold) | > 10% | ❌ **FAIL** |

**整体决策**: 2/3 PASS → 派工 brief "❌ 整段价值不大, 归档" → ✅ 归档阶段 E

详见: `docs/decisions/2026-08-05-cold-hot-routing-poc.md` (本任务决策报告)

---

## §3 5 件套守恒实测 (W-N-E 收口)

1. **alembic 1 head**: `104_add_knowledge_chunk_late_embedding` 守恒 ✓ (W-N-E 不动 schema, plan 派工 brief 严禁改)
2. **pytest tests/integration/test_cold_hot_routing.py**: **18/18 PASS** ✓ (SKIP_DB_SETUP=1 mock 跑过, 派工 brief 严禁改)
3. **0 production code 改动**: 仅新 `app/services/cold_hot_router.py` (109 行全新) + `list_knowledge_partition` 新方法 (29 行, 0 改既有) ✓
4. **0 schema 改动**: `git diff fb4343f29..main -- alembic/versions/ | wc -l` = 0 ✓
5. **锚点守恒**: W-N-E +0 (memory) + W-N-E +1 (4 文件落地, 跨 commit 合并进 W-N-GC +2) + W-N-E +2 (commit `aac562075` 单独) + W-N-E +3 (本文件) ✓

---

## §4 派工 brief 严禁事项 100% 守恒

- ❌ 0 schema 改动 (alembic/versions/ 0 diff)
- ❌ 0 改 `app/services/hybrid_retriever.py` (W-N-D 范畴)
- ❌ 0 改 `app/agent/chat_engine.py` (方案 C 6 铁律)
- ❌ 0 改 `alembic/versions/`
- ❌ 0 改 DFT 集成 dirty 文件 (已 commit)
- ❌ 0 改 W-N-A/B/C/D commits
- ❌ 0 改 plan 文件
- ✅ 仅新文件 + 1 个新方法 + tests + bench + decision

---

## §5 类 20 实战新增 (W-N-E 据实上报 4 实例)

- **类 20.153 (新)**: 冷热分层 PoC 起步必跑 hot/cold COUNT(*), 0 cold 数据 PoC 仍有意义(证明代码可工作),但 Gate 3 "cold > 10%" 必然 FAIL → 据实归档.
- **类 20.154 (新)**: PoC 不动 schema 铁律, 判断标准 = 派工 brief 是否要求 alembic 迁移,没要求就是 PoC.
- **类 20.155 (新)**: pgvector HNSW 是全表索引, `WHERE created_at > ...` 不会让 HNSW 更快;冷热分层真实价值 = 物理分区后每个分区独立 HNSW, 100w+ 行才显著.
- **类 20.156 (新, W-N-E +1 实战)**: 跨 agent commit 合并时, 文件可能从自己 commit 漂移到其他 commit, commit hash 不再属于自己,但文件 100% 在 main. 处理: 据实上报, 文件已落地即可, 不要重做 commit (force-push 污染 main). 检查方式: `git log --all --oneline -- <file>` 看引入该文件的实际 commit.

---

## §6 关键决策 (主拍后续参考)

**W-N-E 最终决策**: ❌ **阶段 E 整段归档**
- 路由层 PoC 代码 (`a530fedc1` 4 文件) 保留, 可作为未来 "cold 数据 > 10%" 时的快速启用 hook
- E.1 物理分区 (pg_partman) **不启动**, cold 0 行没数据可装
- 触发重启评估条件 (W-N-E 决策报告 §4):
  1. cold 数据 > 10% (月度复盘跑 COUNT(*) FILTER cold)
  2. knowledge 库 > 1w 行 (HNSW 索引内存压力)
  3. search_log cold query 比例 > 10% (业务触发)
- 下次复盘建议: **2026-11-05** (3 个月后)

---

## §7 W-N-E 沉淀文件清单 (本任务全产出)

| 文件 | 范畴 | 行数 | 备注 |
|---|---|---|---|
| `memory/w-n-e-cold-hot-poc-startup-2026-08-05.md` | memory 起步 | 128 | W-N-E +0 |
| `app/services/cold_hot_router.py` | 新 service | 109 | W-N-E +1 |
| `app/services/knowledge_service.py` | +1 新方法 (list_knowledge_partition) | +29 | W-N-E +1 (0 改既有) |
| `tests/integration/test_cold_hot_routing.py` | 18 test | 156 | W-N-E +1 (18/18 PASS) |
| `scripts/bench_cold_hot_routing.py` | bench 脚本 | 187 | W-N-E +2 |
| `results/cold_hot_routing_bench_2026-08.json` | bench 结果 | 89 | W-N-E +2 |
| `docs/decisions/2026-08-05-cold-hot-routing-poc.md` | 决策报告 | 138 | W-N-E +2 |
| `memory/w-n-e-cold-hot-poc-closure-2026-08-05.md` | memory 收口 | 170 | W-N-E +3 (本文件) |

**总产出**: 7 新文件 + 1 新方法 (29 行) + 1 commit `aac562075` (W-N-E +2)

---

## §8 派工 v6 §13.3 仓库实情真查 收口

派工 brief 4 commit (W-N-E +0/+1/+2/+3) 派工预期:
- +0 memory ✓
- +1 service + new method + tests ✓ (4 文件落地, 跨 commit 合并)
- +2 bench + JSON + decision ✓ (commit `aac562075`)
- +3 memory ✓ (本文件)

**实际**: 1 main commit (`aac562075`, W-N-E +2 范畴) + 3 memory 文件 + 4 个 main 文件来自其他 commit (`91fa4b450` W-N-GC +2 含 +1 文件). **派工 brief 偏差据实**: W-N-E +1 独立 commit 不存在 (合并进 W-N-GC +2), W-N-E +2 + +3 守恒.

---

## §9 总结

W-N-E 冷热分层 PoC 完整跑通, 3 决策门禁据实报告, 整体决策 "❌ 整段归档" 与派工 brief 完全对齐, 0 擅自扩缩. 路由层 PoC 代码保留供未来 cold 数据增长时快速启用, 决策报告 + 复盘建议沉淀完整. **W-N-E 任务圆满收口**.
