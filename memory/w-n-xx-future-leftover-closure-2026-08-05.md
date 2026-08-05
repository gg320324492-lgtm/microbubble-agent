# W-N-XX 未来派工留口 收口 (2026-08-05)

> **派工**: W-N-XX +2 收口 memory (本任务收口阶段)
> **基线 HEAD**: `fbc11908e` (W-N-BGE +3 收口沉淀)
> **当前 HEAD**: W-N-XX +1 (待 commit, runbook + MEMORY.md #26 段) + W-N-XX +2 (本文件)
> **派工锚点**: W-N-XX +0 起步 / +1 写 runbook + MEMORY.md #26 / +2 收口 (本文件)

---

## 1. 5 件套守恒实测 (W-N-XX +2 收口)

| # | 件 | 状态 | 实测 |
|---|----|------|------|
| 1 | alembic 1 head | ✅ | `105_fix_drift (head)` 守恒 (本任务 0 改 alembic) |
| 2 | pytest 全套件 | ✅ | 沿用 W-N-BGE +3 closure (派工 brief 不要求重跑本任务) |
| 3 | PWA build | ✅ | 沿用 W-N-D++ baseline (件 3 三档之"否", 0 frontend 改动) |
| 4 | 0 production code 改动 | ✅ | 仅 `docs/w-n-future-leftover-2026-08-05.md` (新增) + `memory/MEMORY.md` (新增 #26 段) + `memory/w-n-xx-future-leftover-startup-2026-08-05.md` (新增) + `memory/w-n-xx-future-leftover-closure-2026-08-05.md` (本文件, 新增) |
| 5 | 锚点范式 W-N-XX +0..+2 | ✅ | +0 起步 + +1 runbook + MEMORY.md + +2 收口 (本文件), 3 commits 据实累计 |

---

## 2. 3 项未来派工留口 沉淀清单

### 2.1 W-N-G+ 4 FAIL (漂移测试)

**触发条件**: DB 容器可达 + schema drift 实际列名 + 16GB+ RAM

**4 drift tests 名称** (沿用 W-N-G+ +2 `tests/test_w_n_g_plus_chunk_late_recall.py`):
- `test_schema_drift_knowledge_embedding_model_version`
- `test_schema_drift_meetings_embedding_model_version`
- `test_schema_drift_knowledge_chunks_chunk_embedding`
- `test_chunk_late_recall_path_no_silent_fail`

**修复路径**: W-N-G+ +1 commit `7cb6bf0d1` 4 步 stamp+upgrade (沿用)

**派工 brief 必查**: agent 自报 8/8 PASS vs 实测 4 FAIL 偏差 → 据实上报

### 2.2 W-N-FILL 拦截 (回填不执行)

**触发条件**: 修订 W-N-D++ 决策 OR 新业务理由

**决策**: W-N-D++ §5 决策 "不创建 + 不执行" **拦截中**, **永远不派** (除非主拍明确批准)

**派工 brief 必查**: W-N-D++ §5 决策是否仍标 "整段归档" — 若 YES, 拒绝派工

### 2.3 W-N-BGE 数据不足 (模型替换延后)

**触发条件**: 容器预下载 bge-m3 + GPU 真测 pass rate ≥ Qwen3 baseline (93.5%) + VRAM < 4GB

**3 门禁结果** (W-N-BGE +3 决策):
- 门禁 1 (pass rate) ⏸ 数据不足
- 门禁 2 (VRAM) ⏸ 数据不足
- 门禁 3 (latency 1.6x) ✅ 通过

**修复路径**: W-N-BGE +1 commit `9169e3ae9` 真 bench 框架 + 1000 题 JSON 输出

**派工 brief 必查**: 模型本地可达性 — 沿用 W-N-D+ 沉淀 "GPU 可用 + bge-m3 不可达 → 落 W-N-BGE +N 留口"

---

## 3. 派工 v11 段 9 锚点守恒

**本次新增锚点**: W-N-XX +0..+2 (3 commits, 派工 v11 段 9 规则下都是有效锚点)

**不撞其他锚点**:
- W-N-G+ +0/+1/+2/+3 (已用, 4 commits)
- W-N-BGE +0/+1/+2/+3 (已用, 4 commits)
- W-N-FILL +N (N ≥ 0, 全部空闲)
- W-N-D+ +0..+3 (已用, 5 commits)
- W-N-D++ +0..+3 (已用, 4 commits)

**W-N 周期累计**: ~35 commits 推 main (W100 +75 ~537 → W-N-G+ +N ~572 据实累计) + W-N-XX +0..+2 (3 commits, + 575 据实累计)

---

## 4. 派工 brief 严禁 (W-N 周期延续)

- ❌ 0 改 `app/services/hybrid_retriever.py` / `embedding_service.py` / `knowledge_service.py` 既有 4 API
- ❌ 0 改 `app/agent/chat_engine.py` (方案 C 6 铁律)
- ❌ 0 改 `alembic/versions/100-105` 老迁移 (W-N-A/B/C/D/G+ 范畴)
- ❌ 0 改 `docker-compose.yml` / `app/main.py` / `web/src/` / `alembic/versions/`
- ❌ 0 改生产 `.env` / `EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME`
- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 0 改 plan 文件
- ✅ 仅新增 `docs/` / `memory/` / `scripts/` / `tests/` / `results/`

---

## 5. 0 production code 改动铁律 (W-N 周期续守恒)

```bash
# W-N-XX +0..+2 commits 验证
$ git diff fbc11908e..HEAD -- app/ web/src/ alembic/versions/ docker-compose.yml | grep -E "^[+-]" | grep -v "^[+-]{3}" | wc -l
0
```

✅ **0 production code 改动** (W-N-XX 仅 docs/ + memory/ 范畴):
- 不改 `app/services/embedding_service.py` 既有 4 API
- 不改 `app/agent/chat_engine.py`
- 不改 `alembic/versions/` (派工 brief 严禁)
- 不真切换生产 bge-m3 backend (派工 brief 严禁)
- 不改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits

---

## 6. 沉淀文件清单

| 类型 | 路径 | 锚点 | 状态 |
|------|------|------|------|
| 未来派工留口 runbook | `docs/w-n-future-leftover-2026-08-05.md` | W-N-XX +1 | ⏳ pending commit |
| startup memory | `memory/w-n-xx-future-leftover-startup-2026-08-05.md` | W-N-XX +0 | ⏳ pending commit |
| closure memory | `memory/w-n-xx-future-leftover-closure-2026-08-05.md` (本文件) | W-N-XX +2 | ⏳ pending commit |
| MEMORY.md #26 段 | `memory/MEMORY.md` | W-N-XX +1 | ⏳ pending commit |

---

## 7. 关键 commit 引用

- 本任务基线: `fbc11908e docs(memory): W-N-BGE +3 收口沉淀`
- W-N-GRAND +1 runbook: `c011ebd09 docs(grand-closure): W-N 系列 14 stages 总 grand closure`
- W-N-D++ +2 commit: `1cc5362e2 feat(rag): W-N-D++ 端到端 late chunking 召回 bench + 决策归档`
- W-N-G+ +2 commit: `322455f5d feat(rag): _chunk_late_recall 路径验证 + 集成测试`
- W-N-G+ +1 commit: `7cb6bf0d1 fix(rag): schema drift 修复迁移`
- W-N-BGE +1 bench: `9169e3ae9 perf(rag): bge-m3 1000 题真 bench`
- W-N-BGE +2 decision: `0eaacda64 docs(decision): bge-m3 1000 题真测决策更新`

---

## 8. 未来派工顺序表 (主拍决策, 不擅自扩)

| 序号 | 派工锚点 | 触发条件 | 范畴 | 期望 commit 数 |
|------|---------|---------|------|---------------|
| 1 | W-N-BGE +N | 容器预下载 bge-m3 + GPU 真测 pass rate + VRAM | 模型替换决策 | 2-3 |
| 2 | W-N-G+ +N | DB 容器可达 + schema drift 实际列名 + 16GB+ RAM | production migration 修复 | 2-3 |
| 3 | W-N-FILL +N | 修订 W-N-D++ 决策 OR 新业务理由 | late_embedding 回填 | 3-4 |

**派工顺序**: W-N-BGE +N → W-N-G+ +N → W-N-FILL +N (依紧迫度优先级)
**W-N-FILL 优先级最低**: 因 W-N-D++ §5 决策已拦截, 除非主拍明确批准, 否则**永远不派**.

---

## 9. 类 20 实战沉淀 (W-N-XX 据实上报)

- **W-N 周期新增类 20**: 类 20.155-179 (W-N-A 6 + W-N-B 4 + W-N-C 1 + W-N-D 2 + W-N-D+ 0 + W-N-D++ 2 + W-N-E 0 + W-N-F 0 + W-N-G+ 2 + W-N-OBS 0 + W-N-ARC 5 + W-N-ANC 1 + W-N-MEM 0 + W-N-RAG 0 + W-N-BGE 0 + W-N-GRAND 6)
- **本任务 W-N-XX 新增类 20**: 0 (仅沉淀 W-N 周期类 20 引用, 不新增)
- **类 20 累计**: 179 + 0 = **179 实例** (据实上报, 不擅自扩也不擅自缩)

---

**W-N-XX +0/+1/+2 据实累计, 0 production code 守恒, 3 项未来派工留口完整沉淀. W-N 周期 14 stages + 1 留口 stages (W-N-XX) 全部收口. W19 选项 A 维持.**
