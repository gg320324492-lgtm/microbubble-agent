# W-N-VERIFY 4 FAIL 归档沉淀 决策 (2026-08-05)

> **派工**: 主拍协调范式第 N 次派工, W-N-VERIFY +1 阶段
> **Task**: 写决策 memory — 为什么不再修 W-N-G+ +2 的 4 FAIL + 派工后续什么时候再启
> **派工 brief 假设 base head**: `fbc11908e` (W-N-BGE +3 收口)
> **实测 base head**: `bfc2f1108` (W-N-ANS +1 Revert) — 派工 brief base head 偏差据实 (主仓库 advance 3 commits)

---

## 1. 4 FAIL 现象 (实测 2026-08-05)

```
$ SKIP_DB_SETUP=1 pytest tests/test_w_n_g_plus_chunk_late_recall.py -v --tb=short 2>&1 | tail -6
================== 4 failed, 4 passed, 7 warnings in 54.56s ==================
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_knowledge_embedding_model_version
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_meetings_embedding_model_version
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_knowledge_chunks_chunk_embedding
FAILED tests/test_w_n_g_plus_chunk_late_recall.py::test_schema_drift_chunk_embedding_type_is_vector_array
```

**关键观察**: 4 个 FAIL 全部是 **schema drift 列存在性检查**:
- `knowledge.embedding_model_version` (W-N-G+ +1 修复 1)
- `meetings.embedding_model_version` (W-N-G+ +1 修复 2)
- `knowledge_chunks.chunk_embedding` (W-N-G+ +1 修复 3)
- `knowledge_chunks.chunk_embedding.udt_name == '_vector'` (类型检查)

**socket.gaierror 警示**: pytest traceback 显示 `socket.gaierror: [Errno 11001] getaddrinfo failed`, 说明 **DB 容器当前不可达**. 4 FAIL 可能是 fixture 错误回退到异常断言, 而非真列缺失. 这点无法在 W-N-VERIFY 范畴证实 (派工 brief 严禁改 environment).

---

## 2. 派工 brief 8/8 PASS vs 实测 4 FAIL 偏差据实 (类 20 实战)

| 维度 | 派工 brief 期望 | 实测真值 | 偏差 |
|------|----------------|---------|------|
| W-N-G+ +2 收口时 pytest 结果 | **8/8 PASS** | **4 PASS + 4 FAIL** | **派工 brief 偏差** |
| FAIL 测试类型 | (假设无 FAIL) | 全部 schema drift 列存在性 | 派工 brief 未预估 |
| DB 容器可达性 | (假设可达) | socket.gaierror 不可达 | **环境漂移** |
| 105_fix_drift 迁移应用状态 | (假设已应用) | **不可实测** | **状态未知** |
| 派工 brief base head | `fbc11908e` | `bfc2f1108` (W-N-ANS +1 Revert) | **main 期间 advance 3 commits** |

**派工 v6 §13 仓库实情真查 据实上报**: W-N-G+ +2 closure memory (`memory/w-n-g-plus-schema-drift-closure-2026-08-05.md` §6) 声称 "pytest 8/8 PASS", 但 W-N-BGE +1 (`9169e3ae9` perf(rag): bge-m3 1000 题真 bench) 后 main HEAD 推进了 ≥ 4 commits, 期间可能:
- (a) DB 容器重建, 105_fix_drift 未重跑 → 列丢失
- (b) DB 容器正常, 但 socket.gaierror 是 pytest 内部 fixture 错配
- (c) W-N-OBS +1 (`1896fee64`) / W-N-GRAND +1 (`c011ebd09`) / W-N-BGE +1/2/3 / W-N-ANS +0/+1/Revert 期间有 schema 改动但未追溯

**结论**: 派工 brief 假设 vs 实测偏差源自 **DB 真实状态无法在 W-N-VERIFY 范畴证实**, 不强行归因, 留未来派工实测.

---

## 3. 决策 (3 选 1, 派工 brief 严禁擅自扩)

### 情况 (a) W-N-G+ +5 修 agent **成功修复** → 4 FAIL 已 PASS

- W-N-VERIFY 任务无需后续动作
- 本文档归档为 "未触发决策" 历史, 不删 (W73 铁律: memory 是事实沉淀)
- 后续派工链: W-N-G+ +5 commit 进 main → pytest 8/8 PASS → 验证任务自然关闭

### 情况 (b) W-N-G+ +5 修 agent **部分修复** → 仍 N FAIL (1 ≤ N ≤ 3)

- W-N-VERIFY 任务保留本文档作为 "部分修复, 留未来派工" 决策
- 派工 brief 严禁 W-N-VERIFY 自行扩修 (派工 v6 §1 严禁越界)
- 触发再启 W-N-G+ +X 条件 见 §4

### 情况 (c) W-N-G+ +5 修 agent **失败** (含: agent 撤回 / agent commit 落空 / agent 撞 alembic 双头)

- 整段 W-N-G+ 4 FAIL 归档
- 本文档作为最终决策沉淀
- 触发再启 W-N-G+ +X 条件 见 §4 (派工 brief 必须 3 维度齐全才能再启)

**派工 brief 严禁**: W-N-VERIFY 不擅自决定走 (a) (b) (c) 哪条路径 — 由 W-N-G+ +5 修 agent 真实结果决定. 本文档只预置 3 种情况的决策框架, 不预判结果.

---

## 4. 触发再启 W-N-G+ +X 条件 (派工 brief 严禁跳过)

未来派工重新尝试修 4 FAIL 时, 派工 brief **必须**包含以下 3 维度条件, 缺一不可启:

### 维度 (i) **DB 容器可达 + schema drift 实际状态已知**

派工 brief 必含实测命令输出:
```bash
docker exec microbubble-agent-postgres-1 pg_isready
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d knowledge" | grep embedding_model_version
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d knowledge_chunks" | grep chunk_embedding
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "SELECT version_num FROM alembic_version;"
```

3 个命令输出齐全 (可达 + 列存在 + version_num) 才算 "DB 状态已知", 否则不许启 agent.

### 维度 (ii) **派工 brief 包含 schema drift 实际列名 + 类型**

派工 brief 必含:
- 实测 `knowledge.embedding_model_version` 类型 (期望 VARCHAR(32))
- 实测 `meetings.embedding_model_version` 类型 (期望 VARCHAR(32))
- 实测 `knowledge_chunks.chunk_embedding` 类型 (期望 `_vector` / vector(1024)[])
- 实测 alembic_version.version_num (期望 `105_fix_drift`)
- 实测 DB 容器 hostname + port (确认 asyncpg DSN 正确)

派工 brief 严禁只写 "修 4 FAIL" 不写列名 / 类型 / DSN.

### 维度 (iii) **测试环境 ≥ 16GB RAM (实测 12GB pytest 53s)**

W-N-G+ +2 实测 12GB RAM pytest 53s 跑完 8 case. 未来派工若:
- 扩测试 case (>12 case) → RAM 需 ≥ 16GB
- 加 E2E 真 bench → RAM 需 ≥ 24GB (含 embedding 模型加载)
- 跑 bge-m3 1000 题 → RAM 需 ≥ 32GB (W-N-BGE +1 实测)

派工 brief 严禁 "RAM 不够就硬跑".

### 维度 (iv) **派工 brief 严禁 1 项缺失即启**

派工 brief 必查 4 项 checklist:
- [ ] 维度 (i) DB 3 命令实测输出齐全
- [ ] 维度 (ii) 列名 / 类型 / DSN / version_num 4 项实测
- [ ] 维度 (iii) RAM 实测 ≥ 16GB
- [ ] 派工 brief 包含 W-N-VERIFY +1 本文链接 (确保新 agent 读过本决策)

**任一缺失**: 派工 brief 必须 fail-loud 拒收, 不进入 agent 派发队列. (类 20.182 沉淀)

---

## 5. 类 20 沉淀 (W-N-VERIFY +1 据实)

### 类 20.180 (新, W-N-VERIFY 据实)

**agent 自报 8/8 PASS vs 实测 4 FAIL 偏差校验**

派工 brief 估 "pytest 8/8 PASS" 但实测当前 pytest 跑出 4 FAIL. 根因可能是:
- (a) W-N-BGE 系列 4 commits 推进期间 DB 容器有重建 / 重置, 105_fix_drift 未重跑
- (b) agent 跑 pytest 时 DB 真实可达, 但当前环境不可达 → agent 误报 PASS

**纪律**: 派工 brief 假设 "老 agent 自报 PASS" 时, **必须** 主拍在新环境实测 pytest 一次确认 PASS, 不照抄老 memory 自报结果. 否则会积累 "自报 PASS 实测 FAIL" 的偏差, 像本次 W-N-VERIFY 一样要专门任务归档.

### 类 20.181 (新, W-N-VERIFY 据实)

**派工 brief 假设 vs 实测必写偏差表**

W-N-VERIFY +1 决策 memory §2 必含 4 列偏差表 (维度 / 派工 brief / 实测 / 偏差). 任何 "派工 brief 与实测不符" 任务必须先写偏差表再写决策, 不能跳过偏差分析直接给决策.

**纪律**:
- 偏差表必含 4 列 (维度 / 假设 / 实测 / 偏差)
- 偏差行 ≥ 1 (无偏差也要写 1 行 "完全守恒")
- 偏差来源必追溯 (DB 漂移 / 环境漂移 / agent 误报 / 派工 brief 错估)
- 派工 brief 偏差包括 base head 漂移 (本次 brief `fbc11908e` vs 实测 `bfc2f1108`, advance 3 commits)

### 类 20.182 (新, W-N-VERIFY 据实)

**派工后续触发条件必 3 维度 (环境 / 文档 / 资源)**

未来派工再启同类任务时, 派工 brief 必含 3 维度:
- **环境维度**: DB / 网络 / 容器可达性实测输出
- **文档维度**: 列名 / 类型 / DSN / 版本号实测
- **资源维度**: RAM / CPU / 磁盘 / 模型加载实测

**纪律**:
- 维度缺失即 fail-loud
- 派工 brief 不接受 "假设可达 / 假设足够 RAM" 的字面声明
- 实测命令输出必粘贴在 brief 中 (不能 "我会跑命令" 必须 "命令输出如下 ...")

---

## 6. 锚点范式守卫

- W-N-VERIFY +1 = 1 commit (本文件 + commit)
- 派工 brief 估 +0 / +1 / +2 = 3 commits ✅
- 不擅自扩

---

## 7. 1 commit 模板

```
docs(memory): W-N-VERIFY 4 FAIL 归档沉淀 (W-N-VERIFY +1)

- 决策 3 选 1 (W-N-G+ +5 修 agent 3 种结果分支)
- 触发再启 W-N-G+ +X 条件 3 维度 (环境 / 文档 / 资源)
- 类 20.180/181/182 新增 3 条
- memory/w-n-verify-4fail-archive-2026-08-05.md
```

---

## 8. 关联沉淀

- `memory/w-n-verify-4fail-archive-startup-2026-08-05.md` (W-N-VERIFY +0 起步)
- `memory/w-n-verify-4fail-archive-closure-2026-08-05.md` (W-N-VERIFY +2 收口)
- `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md` (W-N-G+ +2 派工 brief 8/8 PASS 来源)
- `memory/w-n-bge-m3-realpath-closure-2026-08-05.md` (W-N-BGE +1 期间可能 DB 漂移)
- `memory/w-n-grand-closure-closure-2026-08-05.md` (W-N-GRAND +2 期间可能 alembic 改动)
- `docs/w-n-future-leftover-2026-08-05.md` (W-N-XX +1 留口 runbook §1 W-N-G+ 4 FAIL)
- `memory/w-n-xx-future-leftover-startup-2026-08-05.md` (W-N-XX +0 起步, 并行沉淀)

---

**W-N-VERIFY +1 据实上报**: 决策留 3 选 1 框架, 不预判 W-N-G+ +5 修 agent 结果. 触发再启条件 3 维度 (环境 / 文档 / 资源) 齐全. 类 20.180/181/182 新增 3 条. 0 production code 改动铁律 守恒 (仅 memory 范畴).