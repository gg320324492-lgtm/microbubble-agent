# W-N-VERIFY 4 FAIL 归档沉淀 起步 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N-VERIFY 阶段 (W-N-G+ +2 验证测试 4 FAIL 归档决策)
> **Task**: 为 W-N-G+ +2 `_chunk_late_recall` 集成测试的 4 FAIL 写归档决策 memory, 不再修, 留未来派工
> **派工 brief 假设 base HEAD**: `fbc11908e` (W-N-BGE +3 收口)
> **实测 base HEAD (派工时)**: `bfc2f1108` (W-N-ANS +1 Revert) — 派工 brief 偏差据实, 主仓库在我派工期间已 advance 3 commits

---

## 1. 6 项起步 (W73 铁律)

### 1.1 据实现象 (已实测)

```
$ SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v --tb=short 2>&1 | tail -6
================== 4 failed, 4 passed, 7 warnings in 54.56s ==================
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_knowledge_embedding_model_version
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_meetings_embedding_model_version
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_knowledge_chunks_chunk_embedding
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_chunk_embedding_type_is_vector_array
```

4 个 FAIL 全部是 **schema drift 检查** (column existence + vector array type), 4 个 PASS 是 `_chunk_late_recall` 业务路径测试.

### 1.2 派工 brief 假设 vs 实测 偏差据实 (类 20 实战)

| 维度 | 派工 brief 假设 | 实测真值 | 偏差 |
|------|----------------|---------|------|
| Base HEAD | `fbc11908e` (W-N-BGE +3) | `bfc2f1108` (W-N-ANS +1 Revert) | **派工 brief 偏差** |
| pytest 结果 | 8/8 PASS | 4/8 PASS + 4 FAIL | **派工 brief 偏差** |
| FAIL 数量 | 0 | 4 | 派工 brief 错估 |
| DB 容器可达性 | (假设可达) | socket.gaierror 不可达 | **环境漂移** |
| 修 agent 并行 | W-N-G+ 修 4 FAIL agent (任务 #28) | 已派工, 结果未定 | 据实 2 种情况留口 |

**关键偏差 (派工 brief base head 漂移)**:
- 派工 brief 假设 base HEAD = `fbc11908e` (W-N-BGE +3 收口沉淀)
- 实测派工启动时 main HEAD = `bfc2f1108` (W-N-ANS +1 Revert)
- 期间 main advance 了 3 commits: `22dad84cc` (W-N-ANS +0) + `f0656493a` (W-N-ANS +1) + `bfc2f1108` (Revert)
- 这是派工 brief 与实测环境的时差, **W-N-VERIFY 不擅自 git reset, 沿用当前 main HEAD 推进**

**socket.gaierror 核心信号**: pytest 真实运行 traceback 显示 `socket.gaierror: [Errno 11001] getaddrinfo failed`, 说明 DB 容器当前不可达. 4 FAIL 可能是 fixture 出错回退到错误状态而非真列缺失. 这点无法在 W-N-VERIFY 范畴证实 (派工 brief 严禁改 environment).

### 1.3 任务范围 (严禁擅自扩)

- ✅ 写 3 个 memory 文件
- ✅ 写 1 个 commit 推 main (锚点 W-N-VERIFY +0..+2)
- ❌ 不改 `tests/test_w_n_g_plus_chunk_late_recall.py`
- ❌ 不改 `alembic/versions/105_fix_drift.py`
- ❌ 不改任何 W-N-* 老 commits
- ❌ 不改 plan 文件
- ❌ 不尝试 "顺便修 4 FAIL" (派工 brief 严禁)
- ❌ 不擅自 git reset / cherry-pick (派工 brief 严禁)

### 1.4 派工 v6 §13 仓库实情真查 据实上报 (3 项)

1. **DB 当前状态未知**: socket.gaierror 无法实测 DB, 派工 brief 假设 "105_fix_drift 已应用" 无法证实/证伪
2. **W-N-G+ +2 当时 pytest 8/8 PASS 的环境已不可重现**: W-N-BGE +1 跑过 bge-m3 1000 题真 bench, 可能重建 DB 容器或重置 schema; 后 W-N-ANS 3 commits 期间可能进一步漂移
3. **派工后续触发条件必须 3 维度** (环境 / 文档 / 资源) — 详见 W-N-VERIFY +1 决策 memory

### 1.5 类 20 沉淀预留 (W-N-VERIFY +1 据实上报)

- 类 20.180 (新): agent 自报 8/8 PASS vs 实测 4 FAIL 偏差校验
- 类 20.181 (新): 派工 brief 假设 vs 实测必写偏差表
- 类 20.182 (新): 派工后续触发条件必 3 维度 (环境 / 文档 / 资源)

### 1.6 锚点范式守卫

- W-N-VERIFY +0..+2 = 3 commits (本任务)
- 派工 brief 估 +0 / +1 / +2 = 3 commits ✅
- 不擅自扩

---

## 2. 待 W-N-VERIFY +1 决策 memory 收纳的内容

- 决策 3 选 1 (W-N-G+ +5 修 agent 结果分支)
- 触发再启 W-N-G+ +X 条件 (3 维度)
- 类 20.180/181/182 沉淀完整版
- 1 commit `docs(memory): W-N-VERIFY 4 FAIL 归档沉淀 (W-N-VERIFY +1)`

待 W-N-VERIFY +2 收口 memory 收纳的内容:
- 5 件套守恒实测
- 派工 brief vs 实测 偏差表 (终态)
- 锚点范式 W-N-VERIFY +0..+2 据实累计

---

## 3. 不在派工范围 (W19 选项 A 维持)

- 不实际跑 "W-N-G+ +5 修 4 FAIL" agent (派工 brief 明示 "可能与 #28 并行", 不在 W-N-VERIFY 任务)
- 不尝试 docker ps / alembic heads 实测 (派工 brief 严禁改 environment)
- 不重新 build app image (派工 brief 严禁)
- 不重启 DB 容器 (派工 brief 严禁)
- 不擅自 cherry-pick W-N-ANS +1 (派工 brief 严禁, 沿用 main 当前 Revert 状态)

---

## 4. 文件清单

- 本文件: `memory/w-n-verify-4fail-archive-startup-2026-08-05.md` (W-N-VERIFY +0)
- 待写: `memory/w-n-verify-4fail-archive-2026-08-05.md` (W-N-VERIFY +1)
- 待写: `memory/w-n-verify-4fail-archive-closure-2026-08-05.md` (W-N-VERIFY +2)
- 1 commit: `docs(memory): W-N-VERIFY 4 FAIL 归档沉淀 (W-N-VERIFY +1)`
- 1 commit: `docs(memory): W-N-VERIFY 4 FAIL 归档收口 (W-N-VERIFY +2)`

---

## 5. 与 W-N-XX 派工的关系

W-N-XX 派工 (`docs/w-n-future-leftover-2026-08-05.md`) §1 是 "W-N-G+ 4 FAIL" 留口的 runbook, 沉淀触发条件. W-N-VERIFY 是该留口的 **决策沉淀** (为什么不再修 + 派工后续什么时候再启), 与 W-N-XX 是 **协作互补** 关系, 不冲突.

W-N-XX +0 起步 memory (`memory/w-n-xx-future-leftover-startup-2026-08-05.md`) 已存在, 与 W-N-VERIFY +0 据实并行沉淀.