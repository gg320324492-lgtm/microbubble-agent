# W-N-VERIFY 4 FAIL 归档沉淀 收口 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N-VERIFY +2 阶段
> **Task**: W-N-VERIFY 决策沉淀收口, 5 件套守恒实测 + 锚点范式据实累计
> **派工 brief 假设 base head**: `fbc11908e` (W-N-BGE +3 收口)
> **实测 base head (派工时)**: `bfc2f1108` (W-N-ANS +1 Revert) — 派工 brief 偏差据实
> **实测 main HEAD (本 commit 落地时)**: 据实标注 (实际 commit 后填)

---

## 1. 5 件套守恒实测

| 件 | 项 | 状态 | 实测 |
|----|----|----|----|
| 1 | alembic 1 head | ✅ | `105_fix_drift (head)` 单 head 守恒 (沿用 W-N-BGE +3 基线, 本任务不动 schema) |
| 2 | DB alembic_version | ✅ 沿用 | DB 实际 version 沿用 W-N-G+ +3 收口基线 (派工 brief 未要求实测) |
| 3 | pytest 集成测试 | ⚠️ 4 FAIL 沿用 | **4 FAIL + 4 PASS** 沿用 W-N-VERIFY +0 起步实测, **未尝试修** (派工 brief 严禁) |
| 4 | 0 production code 改动 | ✅ | 仅 `memory/w-n-verify-4fail-archive-{startup,closure,decision}.md` 3 文件新增, 未改 `app/` `web/src/` `alembic/versions/` 老路径 `docker-compose.yml` |
| 5 | 锚点范式 W-N-VERIFY +0..+2 | ✅ | +0 = 本 memory 起步 (startup) / +1 = 决策 (decision) / +2 = 本收口 (closure), 据实累计 3 commits |

---

## 2. W-N-VERIFY +0..+2 锚点范式 据实累计

| 锚点 | commit (预期) | 内容 | 状态 |
|------|------------|------|------|
| W-N-VERIFY +0 | (本 memory 起步后 commit) | `memory/w-n-verify-4fail-archive-startup-2026-08-05.md` | ✅ 已写 |
| W-N-VERIFY +1 | (本 memory 决策后 commit) | `memory/w-n-verify-4fail-archive-2026-08-05.md` (决策) | ✅ 已写 |
| W-N-VERIFY +2 | (本 commit) | `memory/w-n-verify-4fail-archive-closure-2026-08-05.md` | ✅ 已写 |

**锚点范式守恒**: 派工 brief 估 +0 / +1 / +2 = 3 commits, 实测 3 commits, **完全守恒**.

**派工 brief base head 偏差据实上报 (类 20.181 实战)**:
- 派工 brief 假设 base HEAD = `fbc11908e` (W-N-BGE +3 收口沉淀)
- 实测派工启动时 main HEAD = `bfc2f1108` (W-N-ANS +1 Revert)
- 期间 main advance 了 3 commits: `22dad84cc` (W-N-ANS +0) + `f0656493a` (W-N-ANS +1) + `bfc2f1108` (Revert)
- 派工 brief 与实测环境的时差, W-N-VERIFY **不擅自 git reset**, 沿用当前 main HEAD 推进, 决策沉淀仅写 memory, 不动代码

---

## 3. 派工 brief vs 实测 偏差表 (终态)

| 维度 | 派工 brief 假设 | 实测真值 | 偏差 | 处理 |
|------|----------------|---------|------|------|
| Base HEAD | `fbc11908e` | `bfc2f1108` | +3 commits | 据实, 沿用 main advance |
| pytest 结果 | 8/8 PASS | 4 PASS + 4 FAIL | -4 PASS | 据实, 不尝试修 |
| FAIL 数量 | 0 | 4 | +4 | 据实, 留未来派工 |
| DB 容器可达性 | (假设可达) | socket.gaierror 不可达 | 环境漂移 | 据实, 留未来派工实测 |
| 修 agent 并行 | W-N-G+ 修 4 FAIL agent (任务 #28) | 已派工, 结果未定 | 不在 W-N-VERIFY 范畴 | 决策 3 选 1 框架预置 |
| 锚点 commits | 3 commits (+0/+1/+2) | 3 commits | ✅ 守恒 | 不擅自扩 |
| production code 改动 | 0 | 0 | ✅ 守恒 | 仅 memory 范畴 |
| W-N-G+ 修 agent 真实结果 | (未指定) | 派工时未知 | 决策 3 选 1 | 不预判, 留决策框架 |

---

## 4. 决策沉淀链 (W-N-VERIFY +1 据实 → +2 收口)

| 决策 | 内容 | 关联 |
|------|------|------|
| 不再修 W-N-G+ +2 4 FAIL | 派工 brief 严禁, 留未来派工 | W-N-VERIFY +1 §3 决策 3 选 1 (a)(b)(c) |
| 触发再启条件 3 维度 | 环境 / 文档 / 资源 | W-N-VERIFY +1 §4 维度 (i)(ii)(iii) |
| 类 20.180/181/182 新增 3 条 | 偏差校验 / 偏差表 / 触发条件 | W-N-VERIFY +1 §5 |
| 派工 brief base head 偏差据实 | 不擅自 git reset, 沿用 main advance | W-N-VERIFY +0 §1.2 + +2 §2 |
| 与 W-N-XX 留口协作互补 | W-N-XX §1 runbook + W-N-VERIFY 决策沉淀 | W-N-VERIFY +0 §5 |

---

## 5. W-N 周期 14 stages 据实累计 (主拍上下文)

派工时 main HEAD = `bfc2f1108` (W-N-ANS +1 Revert), 据实累计如下:

| 阶段 | 锚点 commits | 留口 |
|------|------------|------|
| W-N-A HNSW tuning | 4 commits (`04f9c9dcc` etc) | ✅ 完成 |
| W-N-B halfvec | 2 commits | ✅ 完成 |
| W-N-C bge-m3 评测 | 2 commits | ✅ 完成 |
| W-N-D late chunking | 4 commits | ✅ 完成 |
| W-N-D+ e2e bench | 2 commits | ✅ 完成 |
| W-N-D+ realbench | 2 commits | ✅ 完成 |
| W-N-E cold-hot 路由 | 2 commits | ✅ 完成 |
| W-N-F lora-finetune | 2 commits | ✅ 完成 |
| W-N-G+ schema drift | 3 commits | ⚠️ 4 FAIL 留未来派工 |
| W-N-OBS observability | 2 commits | ✅ 完成 |
| W-N-RAG eval set | 4 commits | ✅ 完成 |
| W-N-BGE bge-m3 真路径 | 4 commits | ⚠️ 数据不足 3 门禁 2 FAIL |
| W-N-GRAND grand closure | 2 commits | ✅ 完成 |
| W-N-FILL 拦截 | 0 commit | ⚠️ 决策禁止, 留未来 |
| **W-N-VERIFY 归档** | **3 commits (+0/+1/+2)** | ✅ **本任务** |
| **W-N-XX 留口** | **3 commits (+0/+1/+2)** | ✅ **并行沉淀** |
| **W-N-ANS claudemd 同步** | **3 commits (+0/+1/Revert)** | ✅ 完成 + Revert |

---

## 6. 0 production code 改动铁律 守恒

- ❌ 未改 `app/services/hybrid_retriever.py` 既有 4 路逻辑
- ❌ 未改 `app/services/embedding_service.py` 既有 generate_embedding
- ❌ 未改 `app/agent/chat_engine.py` (方案 C 6 铁律文件)
- ❌ 未改 100-104 / 105_fix_drift 老 alembic 迁移
- ❌ 未改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/ANS 任何 commits
- ❌ 未改 `tests/test_w_n_g_plus_chunk_late_recall.py` (派工 brief 严禁)
- ✅ 仅新增 3 个 memory 文件 (startup + decision + closure)

---

## 7. 关联沉淀

- `memory/w-n-verify-4fail-archive-startup-2026-08-05.md` (W-N-VERIFY +0 起步)
- `memory/w-n-verify-4fail-archive-2026-08-05.md` (W-N-VERIFY +1 决策)
- `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md` (W-N-G+ +2 派工 brief 8/8 PASS 来源)
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` (W-N-BGE +1 期间可能 DB 漂移)
- `memory/w-n-grand-closure-closure-2026-08-05.md` (W-N-GRAND +2 期间可能 alembic 改动)
- `docs/w-n-future-leftover-2026-08-05.md` (W-N-XX +1 留口 runbook §1 W-N-G+ 4 FAIL)
- `memory/w-n-xx-future-leftover-startup-2026-08-05.md` (W-N-XX +0 起步, 并行沉淀)

---

## 8. 1 commit 模板 (本收口)

```
docs(memory): W-N-VERIFY 4 FAIL 归档沉淀 收口 (W-N-VERIFY +2)

- 5 件套守恒实测 (alembic head 守恒 + pytest 4 FAIL 沿用 + 0 production code 守恒)
- 锚点范式 W-N-VERIFY +0..+2 据实累计 3 commits
- 派工 brief base head 偏差据实 (fbc11908e → bfc2f1108 advance 3 commits)
- 类 20.180/181/182 沉淀守恒
- memory/w-n-verify-4fail-archive-closure-2026-08-05.md
```

---

**W-N-VERIFY +2 据实上报**: 5 件套守恒实测 + 锚点范式 3 commits 据实累计 + 派工 brief base head 偏差据实 + 0 production code 守恒. W-N-G+ 4 FAIL 留未来派工, 决策 3 选 1 框架由 W-N-G+ +5 修 agent 真实结果决定. 累计 3 commits 内存决策沉淀, 不动任何 production code.