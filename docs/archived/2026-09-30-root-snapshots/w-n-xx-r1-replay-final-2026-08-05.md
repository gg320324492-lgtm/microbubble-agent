# W-N-XX 留口 1 复盘 (2026-08-06)

> **派工**: W-N-XX-RC +0 (起步 memory) / W-N-XX-RC +1 (复盘 docs, 本文件)
> **基线 HEAD**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **派工 brief 严守**: 仅复盘 + 验证, **不再生成新 commit** (派工 brief 严禁擅自扩). 闭环验证的物证已存在
> (`e68412de4` 修复 + `8a3ae748b` 决策 + 本次重跑 8/8 PASS).

---

## 1. 复盘范围 (派工 brief 严守)

| 物证 | 提交 / 路径 | 状态 |
|------|-------------|------|
| 4 FAIL 修复 cherry-pick | `e68412de4` | 已是 `cde003abc` 的祖先 (`git merge-base --is-ancestor` 确认) |
| 闭环决策 + 8/8 PASS 报告 | `8a3ae748b` (`docs/w-n-xx-r1-replay-2026-08-05.md` + 2 memory) | 已是 `cde003abc` 的祖先 |
| 本次重跑 8/8 PASS | `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` → **8 passed in 42.15s** (本次实测, 7 warnings) | PASS |
| alembic 1 head | `python -m alembic heads` → `105_fix_drift (head)` | 守恒 |
| DB `version_num` | `SELECT version_num FROM alembic_version;` → `105_fix_drift` | 守恒 |

**派工 brief 严禁的事本任务全部未做**:
- 未改 `tests/test_w_n_g_plus_chunk_late_recall.py` (e68412de4 修好的 6475 字节版本保持原样)
- 未改 `app/` `web/src/` `alembic/versions/` 任何文件
- 未改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 任何 commit 内容
- 未开新 commit (`git log origin/main..HEAD` 预期空, 派工 brief 仅复盘)

---

## 2. W-N-G+ 4 FAIL 修复兑现 (`e68412de4`)

**根因** (来自 commit body 沉淀 `memory/w-n-g-plus-4fail-fix-closure-2026-08-05.md`):
- 派工 brief 估 4 FAIL 是 schema drift 列缺失, 实测是 **db 容器未发布 Windows 主机 5432**, 主机 pytest 调 `async_session` 走 `localhost:5432` → `ConnectionRefusedError [WinError 1225]`.
- 路径 A: 修测试运行方式, 不动 105 迁移 / 不动生产 DB / 不动 `app/services/hybrid_retriever.py` 4 路逻辑 / 不动方案 C 6 铁律.

**修复实现**:
- `tests/test_w_n_g_plus_chunk_late_recall.py` 新增 `_query_schema_scalar` helper
- `INTEGRATION=1` 走应用 `async_session` (覆盖 Compose `db` 主机名解析)
- 默认 Windows 路径走 `docker exec microbubble-agent-db-1 psql` 只读 fallback, 容器名可由 `W_N_G_PLUS_DB_CONTAINER` 覆盖
- 4 个 schema drift 测试改用 helper, 断言不变; 后 4 个 retrieve 行为测试保持原貌

**0 production code 守恒实测** (e68412de4 范围内):
```
$ git show --stat e68412de4
 memory/w-n-g-plus-4fail-fix-closure-2026-08-05.md |  77 ++++++++++++++++
 memory/w-n-g-plus-4fail-fix-startup-2026-08-05.md |  60 +++++++++++++
 tests/test_w_n_g_plus_chunk_late_recall.py        | 104 +++++++++++++++-------
 3 files changed, 207 insertions(+), 34 deletions(-)
```
1 测试文件 + 2 memory, `app/` `web/src/` `alembic/versions/` 0 diff ✓

---

## 3. W-N-VERIFY 决策文档兑现 (`8a3ae748b` 关联的 `docs/w-n-xx-r1-replay-2026-08-05.md`)

派工 brief 提到的 "W-N-VERIFY 决策文档" 对应 W-N-XX +R1 闭环验证报告 (`docs/w-n-xx-r1-replay-2026-08-05.md`, 200 行). 该文档已于 `8a3ae748b` 落 main, 内容:

1. **Step 1 留口文档 §1 定位** — 引用 `docs/w-n-future-leftover-2026-08-05.md` §1 W-N-G+ 4 FAIL 4 个漂移测试清单
2. **Step 2 8/8 PASS 验证** — 引用 W-N-XX +R1 当时实测的 8/8 PASS (43.65s), **本次派工再跑 42.15s PASS, 数值一致**
3. **Step 3 触发再启条件满足** — DB 容器可达 + schema drift 实际列名 + 16GB+ RAM, 3/3 满足
4. **决策** — W-N-XX 留口 1 完全闭环
5. **触发再启条件更新** — 旧 3 个基础设施条件 (DB 容器 / 列名 / RAM) 替换为 "W-N-G+ 修复回归" 单条件
6. **5 件套守恒** + **类 20.157** — 闭环验证 = 跑测试 + 验证触发条件 + 写决策文档; 测试 PASS 不代表闭环, 必须显式标注触发条件变化

**派工 brief 期望的"W-N-XX-RC +0 起步 memory" 物证**: `memory/w-n-xx-r1-replay-startup-2026-08-05.md` (W73 铁律 6 项起步) 已存在.

**派工 brief 期望的"W-N-XX-RC +1 复盘验证" 物证**: 即本文件. 派工 brief 严禁再开 commit, 故本文件作为本地复盘 + 类 20 沉淀使用, 不通过 commit 进入 git 历史.

---

## 4. 8/8 PASS 验证 (本次复跑)

```
$ SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v
=================== 8 passed, 7 warnings in 42.15s ====================
```

4 个 schema drift 测试 (W-N-G+ +1 修复对象) + 4 个 retrieve 行为测试全部通过.

| # | 测试名 | 类别 | 本次 |
|---|--------|------|------|
| 1 | `test_schema_drift_knowledge_embedding_model_version` | schema drift (W-N-G+ +1 修复 1) | PASS |
| 2 | `test_schema_drift_meetings_embedding_model_version` | schema drift (W-N-G+ +1 修复 2) | PASS |
| 3 | `test_schema_drift_knowledge_chunks_chunk_embedding` | schema drift (W-N-G+ +1 修复 3) | PASS |
| 4 | `test_schema_drift_chunk_embedding_type_is_vector_array` | schema drift 类型 | PASS |
| 5 | `test_chunk_late_recall_path_no_silent_fail` | 行为 (16GB+ RAM) | PASS |
| 6 | `test_chunk_late_recall_handles_null_embedding_gracefully` | 行为 | PASS |
| 7 | `test_retrieve_runs_all_5_paths` | 行为 (4 路 + late chunking) | PASS |
| 8 | `test_retrieve_with_category_filter` | 行为 | PASS |

**本次复跑 8/8 PASS** ✓ (与 `8a3ae748b` 记录的 8/8 PASS 数值一致, 与 e68412de4 修复时的 56.29s / 69.56s 同档).

---

## 5. 触发再启条件更新 (本任务复盘)

派工 brief 期望 "触发再启条件更新 (仅当 W-N-G+ 修复回归)". 此更新已在 `8a3ae748b` 落 main, 本次复盘仅做引用 + 留口, 不再修订:

| 旧触发条件 (`c2acc536d` 留口) | 新触发条件 (本次闭环后) |
|------------------------------|----------------------|
| DB 容器可达 | **W-N-G+ 修复回归** — 新 commit 引入 drift (删列 / 改列名 / 改列类型) |
| schema drift 实际列名存在 | (隐含 — 触发后实测) |
| 16GB+ RAM | (隐含 — 触发后实测, 8 case 12GB 53s 已够) |

**何时不触发**:
- 8/8 PASS 现状保持 → 不触发, 沿用闭环结论
- 测试文件内容稳定 → 不触发
- schema drift 列名无变化 → 不触发

**新触发路径**:
- 跑 `SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v` 出现任意 1 个 FAIL
- 修复路径沿用 W-N-G+ +1 commit `7cb6bf0d1` 4 步 stamp+upgrade (见 `docs/w-n-future-leftover-2026-08-05.md` §1.4)
- 派工 brief 必含 4 项 checklist: DB 可达 / 列名类型 DSN version_num / RAM ≥ 16GB / 引用本决策文档

---

## 6. 决策

### W-N-XX 留口 1 完全闭环

W-N-G+ 4 FAIL 修复 `e68412de4` 已 cherry-pick 推 main, 闭环决策文档 `8a3ae748b` 已落 main, 本次复跑 8/8 PASS (42.15s) 与历史报告数值一致, 5 件套 (alembic 1 head / DB version_num / pytest / 0 production code / 锚点范式) 全部守恒.

**W-N-XX 留口 1 (W-N-G+ 4 FAIL) 完全闭环** ✓

### 派工 brief 严禁

派工 brief 明确要求 **0 改任何已有 W-N-* commit / 测试文件 / alembic**. 本任务严守:
- 未做 `git add` / `git commit` / `git push`
- 复盘 docs (`docs/w-n-xx-r1-replay-final-2026-08-05.md` 备用) + 收口 memory (本目录) 仅作为本次 agent 留痕使用, 不入 git
- 不擅自扩 anchor 编号 (W-N-XX-RC +0..+2 仅作任务内部标识, 不进 `git log --grep`)

### 0 production code 守恒 (本任务)

| 文件 | 类别 | 落地形式 |
|------|------|---------|
| `docs/w-n-xx-r1-replay-final-2026-08-05.md` | 备用 | 仅本任务沉淀, 不 commit |
| `memory/w-n-xx-r1-replay-closure-closure-2026-08-05.md` | 收口 | 仅本任务沉淀, 不 commit |

**0 production code 改动铁律 守恒** ✓ (派工 brief 严禁新增 commit, 故严格在 1 docs + 1 memory 文件范畴内"留口", 不入 git 历史).

---

## 7. 类 20 沉淀 (W-N-XX-RC 据实)

### 类 20.183 (新, W-N-XX-RC 据实)

**复盘 agent 不开 commit, 仅物证 + 触发条件更新**

W-N-XX 留口 1 闭环后, 复盘 agent 派工的本质是 "物证核对 + 触发条件复验 + 类 20 沉淀", 不是 "新增 commit 推翻原决策". 派工 brief 若以"复盘 + 验证"为名, 必须**严禁**复盘 agent 自行:
- 重写 `docs/w-n-xx-r1-replay-2026-08-05.md` (W-N-XX +R1 已落 main 的闭环报告)
- 修改 `tests/test_w_n_g_plus_chunk_late_recall.py` (e68412de4 修好的版本)
- 改 W-N-* 系列已有 commit
- 改 alembic / app / web 任何文件

**纪律**:
- 复盘 agent 跑测试 + 写备用复盘 docs + 写收口 memory, 全部留口不入 git
- 锚点编号 W-N-XX-RC +0/+1/+2 仅在任务内部使用, 不进 `git log --grep`
- 闭环物证 (e68412de4 + 8a3ae748b) 必须先于复盘 agent 派工存在, 否则不算"复盘"而是"重新闭环"

### 类 20.184 (新, W-N-XX-RC 据实)

**闭环决策文档必含触发条件 "替代" 而非 "附加"**

W-N-XX +R1 闭环报告 (`docs/w-n-xx-r1-replay-2026-08-05.md` §触发再启条件更新) 的关键操作是 **替代** 旧 3 个基础设施条件 (DB 容器可达 / schema drift 列名 / 16GB+ RAM), 不是 **附加** 新条件. 旧条件在 8/8 PASS 后已隐含满足, 写成"附加新触发条件"会误把已闭环的留口再次重启.

**纪律**:
- 闭环报告必含 "旧条件 → 新条件" 替代表
- 新触发条件必须能从旧条件 + 8/8 PASS 现状推断 (本次: W-N-G+ 修复回归 = 列变化)
- 不许 "附加" 含糊条件 (例如 "再派一次"), 必须明确可观测的回归信号

---

## 8. 5 件套守恒实测 (本任务复盘 + 历史)

| # | 件 | 实测 | 状态 |
|---|----|------|------|
| 1 | alembic 1 head | `105_fix_drift (head)` | ✓ 守恒 |
| 2 | DB version | `SELECT version_num` → `105_fix_drift` | ✓ 守恒 |
| 3 | pytest | 本次复跑 8/8 PASS (42.15s) + 历史 43.65s + e68412de4 修复时 56.29s / 69.56s | ✓ 守恒 |
| 4 | 0 production code | 本任务 0 commit + e68412de4 1 test + 2 memory + 8a3ae748b 1 doc + 2 memory | ✓ 守恒 |
| 5 | 锚点范式 | W-N-G+ +4..+6 (e87cc9a51 / 54ac813c3 / 7d1292c0b) + W-N-XX +R0..+R2 (8a3ae748b) | ✓ 守恒 |

**5 件套 5/5 守恒** ✓

---

## 9. 关联沉淀

- `docs/w-n-xx-r1-replay-2026-08-05.md` (W-N-XX +R1 闭环报告, 落 main at `8a3ae748b`)
- `memory/w-n-xx-r1-replay-startup-2026-08-05.md` (W-N-XX +R0 起步, 落 main at `8a3ae748b`)
- `memory/w-n-xx-r1-replay-closure-2026-08-05.md` (W-N-XX +R2 收口, 落 main at `8a3ae748b`)
- `memory/w-n-g-plus-4fail-fix-startup-2026-08-05.md` (W-N-G+ +4 startup, 落 main at `e68412de4`)
- `memory/w-n-g-plus-4fail-fix-closure-2026-08-05.md` (W-N-G+ +6 收口, 落 main at `e68412de4`)
- `memory/w-n-verify-4fail-archive-2026-08-05.md` (W-N-VERIFY +1 决策留口, 派工 brief 严禁擅自扩)
- `docs/w-n-future-leftover-2026-08-05.md` §1 W-N-G+ 4 FAIL (W-N-XX +1 留口 runbook, commit `c2acc536d`)
- `tests/test_w_n_g_plus_chunk_late_recall.py` (e68412de4 修复版, 6475 字节, 8/8 PASS 复跑 42.15s)
- commit `e68412de4` (W-N-G+ +4..+6 cherry-pick 推 main)
- commit `8a3ae748b` (W-N-XX +R0/+R1/+R2 闭环推 main)
- commit `7cb6bf0d1` (W-N-G+ +0/+1 schema drift 修复迁移)

---

**W-N-XX-RC 复盘结论**: 闭环物证 `e68412de4` (修复) + `8a3ae748b` (决策) + 本次 8/8 PASS 复跑 全部守恒, W-N-XX 留口 1 完全闭环. 派工 brief 严禁新增 commit, 本任务严守, 复盘文档 + 收口 memory 仅作 agent 留痕.
